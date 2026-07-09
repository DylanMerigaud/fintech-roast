# Idempotency and concurrency

Part of the [fintech-roast](../README.md) rulebook. See [README.md](README.md) for the format contract and severity scale.

## IDE-1: Payment webhook handlers must dedupe by processed-event-id before running side effects

**Severity**: critical

**What to detect**

- A webhook/callback HTTP route (Express/Fastify/Flask/Django/Rails/Spring controller) that runs a money side effect (capture, refund, credit balance, fulfill order, send payout) directly in the handler body with no lookup of an already-processed marker first.
- No table or store keyed on the provider event id (Stripe `event.id` / `evt_...`, Adyen `pspReference` plus `eventCode`, PayPal `id`) that is consulted before the side effect. Grep for the handler reading `event.type`/`eventCode`/`resource.type` but never SELECTing or INSERTing an `event_id`/`webhook_id` dedup row.
- Handler logic assumes ordering: `if event.type == 'x' then set status = ...` overwriting later state, or code that treats `payment_intent.succeeded` as final without guarding against a later `.canceled`/`.refunded` arriving first or twice.
- Dedup check and side effect not in one transaction: an `INSERT INTO processed_events` (or Redis `SETNX`) committed separately from, or after, the charge/DB mutation, so a crash between them re-runs the effect.
- Signature verified but no idempotency: presence of `stripe.webhooks.constructEvent` / `hmac` verification with the effect immediately following and no processed-id guard.
- Returning non-2xx (or timing out) after the side effect already committed, which guarantees the provider re-delivers an event whose effect already ran.

**Why it breaks**

Payment providers deliver webhook events at-least-once and out of order, not exactly-once. Stripe's docs state endpoints "can occasionally receive the same event more than once" and recommend recording the event IDs you processed so you skip already-recorded ones; the same page states "Stripe does not guarantee the delivery of events in the order they were generated." Adyen states "in some cases it is possible that you receive the same webhook event twice, so make sure that your system is able to deal with duplicates," and that duplicates share the same `eventCode` and `pspReference` while `eventDate` can differ. A handler that credits a balance, captures a charge, or fulfills an order on every delivery therefore double-applies the effect when the provider retries (which it does on any non-2xx or timeout) or when it emits two Event objects for one state change. Out-of-order delivery separately corrupts state when a later-generated event is processed before an earlier one and blindly overwrites it.

**Fix**

Record the provider's event id and dedupe on it before any side effect, inside the same database transaction as the effect. On receipt, `INSERT INTO processed_events(event_id) VALUES ($1)` guarded by a unique constraint (or Redis `SET key NX`); if the insert reports the id already exists, ack 200 and stop. Only if the insert is new do you run the mutation, and commit the marker and the mutation together so a crash cannot leave one without the other (this is IDE-4 backing IDE-1). For ordering, key state transitions on the object id plus a monotonic field (status precedence, `created`, sequence) and ignore an event that would move state backward rather than trusting arrival order. Always return 2xx once you have durably accepted the event so the provider stops retrying.

**False positives**

- Handlers that only read (log the event, emit a metric, invalidate a cache, forward to an internal queue that is itself idempotent) have no money side effect to double-apply, so a missing event-id dedup is acceptable.
- The effect is naturally idempotent by construction: an upsert keyed on the object id (`INSERT ... ON CONFLICT (payment_intent_id) DO UPDATE`) or a set-to-absolute-value (`status = 'paid'`) rather than an increment, so replaying the same event converges to the same state.
- Dedup is enforced one layer down (the downstream charge/credit call carries its own idempotency key per IDE-2, or the write hits a unique constraint per IDE-4) and the handler correctly treats the resulting duplicate/conflict as a no-op.
- A managed idempotent-consumer framework (a queue with exactly-once processing semantics plus a dedup store, e.g. an SQS FIFO consumer with a message-dedup table) already guarantees single processing upstream of this handler.

**Sources**

1. [Receive Stripe events in your webhook endpoint](https://docs.stripe.com/webhooks) (Stripe)
2. [Handle webhook events](https://docs.adyen.com/development-resources/webhooks/handle-webhook-events) (Adyen)
3. [Implementing Stripe-like idempotency keys in Postgres](https://brandur.org/idempotency-keys) (Brandur Leach)

## IDE-2: Outbound charge/payout API calls must send an idempotency key scoped per logical operation

**Severity**: critical

**What to detect**

- A POST to a payment provider that moves money (`stripe.charges/paymentIntents/refunds/transfers/payouts.create`, `adyen /payments`, PayPal capture, a bank/ACH transfer call) with no idempotency key in the request options or headers. Grep for `.create(` / `POST /payments` without an adjacent `idempotencyKey` / `Idempotency-Key` / `idempotency-key`.
- A retry wrapper, `axios-retry`, `tenacity`, resilience4j, or a message-queue redelivery around a money call that resends on timeout/5xx without threading a stable key through, so each attempt is a fresh operation.
- An idempotency key that is regenerated per attempt (`uuid4()` computed inside the retry loop or per HTTP send) instead of once per logical operation, defeating the purpose.
- A key derived from something non-unique or time-based (`now()`, a shared cart id reused across distinct charges) so two different operations collide, or so a legitimately different second charge is silently deduped to the first.
- Key held only in process memory and not persisted with the operation, so a crash-and-retry after restart cannot reuse the same key.
- Retention/scope mismatch: relying on a key beyond the provider's retention window (Stripe prunes keys at least 24h old, Adyen keeps a minimum of 7 days) so a late retry creates a duplicate, or assuming keys are global when they are scoped per account.

**Why it breaks**

On a timeout or dropped connection the client cannot tell whether the charge succeeded: Stripe describes the response-failure case as "the operation executed successfully, but the client couldn't get the result." Retrying a non-idempotent mutation then double-charges: Stripe notes "accidentally calling it twice would lead to the customer being double-charged, which is very bad." An idempotency key sent with the request lets the provider recognize the retry and reply with a cached result of the original operation instead of performing it again. Adyen: "if you do not receive a response (for example, in case of a timeout), you can safely retry the request with the same HTTP header," and the first response is "returned without duplication." Get the key's scope or lifetime wrong and you either duplicate (key expired or regenerated) or wrongly suppress a genuinely distinct payment (key reused across operations).

**Fix**

Generate one idempotency key per logical operation, persist it with that operation before the first send, and reuse the exact same key on every retry, including retries after a process restart. Stripe recommends a V4 UUID or another random string with enough entropy to avoid collisions; pass it via the client's idempotency option (`stripe.paymentIntents.create(params, { idempotencyKey })`) or the `Idempotency-Key` header. Scope the key to the operation, not to a shared entity like a cart, so distinct charges get distinct keys and duplicates of one charge share a key. Send the same request parameters on retry, since Stripe compares parameters against the original request and errors on a mismatch. Respect provider retention (Stripe removes keys at least 24h old, Adyen keeps them a minimum of 7 days and unique to the company account): do not lean on a key older than the window, and pair the outbound key with a local unique constraint (IDE-4) so your own store is a second line of defense.

**False positives**

- The operation is genuinely read-only or naturally idempotent by target (a GET, or a PUT that sets an absolute state), where a retry cannot create a second money movement.
- The provider assigns idempotency implicitly for that call, e.g. an SDK configured with automatic network retries that injects and reuses a client-generated request id for you (Stripe's official libraries, AWS SDK client-request-token operations), so no explicit key is needed at the call site.
- A single, non-retried fire where any failure surfaces to a human for manual reconciliation rather than being auto-retried; the key adds little because there is no automatic second attempt (still recommended, but its absence is not a duplicate-charge bug).
- The call is idempotent at a higher layer: it is dispatched through an idempotent-consumer/outbox that guarantees at-most-once delivery of that command, so the money call executes once regardless of redelivery.

**Sources**

1. [Idempotent requests](https://docs.stripe.com/api/idempotent_requests) (Stripe)
2. [Designing robust and predictable APIs with idempotency](https://stripe.com/blog/idempotency) (Stripe)
3. [API idempotency](https://docs.adyen.com/development-resources/api-idempotency) (Adyen)
4. [Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) (Amazon Web Services)

## IDE-3: Balance and quantity updates must be atomic (single UPDATE or row lock), never application-side read-modify-write

**Severity**: critical

**What to detect**

- A SELECT of a balance/quantity/counter into an application variable, arithmetic in code, then a separate UPDATE writing the computed value back: `SELECT balance ... ; balance = balance - amount; UPDATE ... SET balance = <computedValue>`. The write sets an absolute value derived from a stale read rather than `balance = balance - amount`.
- ORM read-modify-save on a money field: `row = repo.find(id); row.balance -= amt; repo.save(row)` (ActiveRecord, Sequelize, Django `obj.save()`, Hibernate dirty-checking, GORM `Save`) with no row lock and no version column.
- A check-then-act on available funds split across statements: `SELECT balance` then `if (balance >= amount)` in code then `UPDATE`, with no `FOR UPDATE` on the read and no `WHERE balance >= amount` guard on the write, allowing an overdraft under concurrency.
- The read that feeds the decision lacks `SELECT ... FOR UPDATE` / `SELECT ... FOR NO KEY UPDATE`, and the transaction runs at READ COMMITTED (the default), so two concurrent transactions both read the same starting value.
- No optimistic-concurrency guard: an UPDATE with no `WHERE version = :expected` (and no check that exactly one row was affected) on a table whose balance is mutated concurrently.
- Distributed increments implemented as GET then SET in Redis/Memcached instead of `INCRBY`/`DECRBY`, or a compare-and-set done non-atomically.

**Why it breaks**

Under concurrency, two transactions that each SELECT the balance, compute in application code, and write back both start from the same value and the second write clobbers the first: the classic lost update. At READ COMMITTED, PostgreSQL notes that "two successive SELECT commands can see different data, even though they are within a single transaction," and that a plain SELECT "sees only data committed before the query began; it never sees either uncommitted data or changes committed by concurrent transactions during the query's execution," so a read-modify-write cycle has no protection. The money consequences are lost deposits, double-spent debits, and overdrafts when a check-then-act on available funds races. A single self-referential statement avoids this: PostgreSQL documents `UPDATE accounts SET balance = balance + 100.00 WHERE acctnum = 12345` running against the current row and notes that a concurrent update makes "the second statement start with the updated version of the account's row," so concurrent updates serialize correctly.

**Fix**

Do the arithmetic in the database in one statement: `UPDATE accounts SET balance = balance - :amt WHERE id = :id AND balance >= :amt` and treat zero rows affected as insufficient funds, which makes the funds check and the debit a single atomic act. When the decision genuinely needs a prior read (multi-row logic), take an explicit row lock first with `SELECT ... FOR UPDATE`, which per PostgreSQL "prevents them from being locked, modified or deleted by other transactions until the current transaction ends," then update within the same transaction. Alternatively use optimistic concurrency: add a `version` column, write `... WHERE id = :id AND version = :v` bumping the version, and retry on zero rows affected. For counters in a cache use native atomics (`INCRBY`/`DECRBY`) rather than GET-then-SET. Never round-trip a money value into application memory to mutate it.

**False positives**

- The value is not concurrently mutated: a per-request row created and owned by one writer, or a field only ever written by a single serialized worker, where no second transaction can interleave.
- The read-modify-write already runs under a correctly scoped guard: `SELECT ... FOR UPDATE` (or an equivalent advisory/row lock) held for the whole cycle in one transaction, or a `WHERE version = :expected` optimistic check with proper affected-row handling and retry.
- SERIALIZABLE isolation is in force and the code correctly retries on serialization failures (SQLSTATE 40001), so a lost update surfaces as an abort-and-retry rather than silent corruption.
- The absolute value written is authoritative and idempotent by design (setting a status, or a reconciled balance computed from an immutable ledger of entries, not an in-place increment of a mutable counter), so a stale intermediate read cannot cause loss.

**Sources**

1. [Explicit Locking (Row-Level Locks, FOR UPDATE)](https://www.postgresql.org/docs/current/explicit-locking.html) (PostgreSQL Global Development Group)
2. [Transaction Isolation (Read Committed Isolation Level)](https://www.postgresql.org/docs/current/transaction-iso.html) (PostgreSQL Global Development Group)

## IDE-4: External transaction references need a database UNIQUE constraint as the last line of dedup defense

**Severity**: high

**What to detect**

- A table storing a provider identifier (`event_id`, `payment_intent_id`, `charge_id`, `psp_reference`, `idempotency_key`, `external_ref`, `transaction_id`) whose DDL has no `UNIQUE` constraint or unique index on that column. Grep the schema/migrations for the column present but no `UNIQUE`/`CREATE UNIQUE INDEX`/`ADD CONSTRAINT ... UNIQUE`.
- Dedup enforced only in application code: `SELECT ... WHERE event_id = ?` followed by a conditional `INSERT`, with nothing at the DB level, so two concurrent requests both see no row and both insert (a check-then-insert TOCTOU).
- Nullable external-reference column used for dedup: `event_id TEXT` without `NOT NULL`, allowing multiple NULLs that a unique index does not collapse.
- Inserts of provider records with no `ON CONFLICT` / `INSERT IGNORE` / `MERGE` and no handling of a unique-violation error (e.g. Postgres SQLSTATE 23505), implying duplicates are simply not caught if the app-level check races.
- Wrong uniqueness grain: a unique key on only part of the natural identity (e.g. `pspReference` alone when Adyen dedup requires `pspReference` plus `eventCode`, or a single global key that should be scoped per account as in `(user_id, idempotency_key)`).
- A `processed_events`/inbox table used for webhook dedup that is a plain heap with a non-unique index on the event id.

**Why it breaks**

Application-level dedup checks are a check-then-act that races: two concurrent deliveries of the same event both run `SELECT` (find nothing) and both `INSERT`, so the effect fires twice. Only the database can enforce single-insertion atomically. As the AWS Database blog puts it, "a common coding strategy is to have multiple application servers attempt to insert the same data into the same table at the same time and rely on the database unique constraint to prevent duplication." Without that constraint the store is not the backstop it is assumed to be, and a duplicate provider event or a re-sent idempotency key silently creates a second money row. Getting the constraint's columns or scope wrong is equivalent to not having it: too narrow rejects legitimate distinct rows, too broad or unscoped lets true duplicates through.

**Fix**

Put a `UNIQUE NOT NULL` constraint on the external reference at its correct grain and let the database be the final arbiter: `event_id TEXT NOT NULL UNIQUE`, or for scoped keys a composite `UNIQUE (account_id, idempotency_key)` (Brandur uses `(user_id, idempotency_key)` so a key is unique per account), or `UNIQUE (psp_reference, event_code)` for Adyen. Match the grain to the provider's own duplicate definition. Then insert with `INSERT ... ON CONFLICT (event_id) DO NOTHING` (which PostgreSQL documents as simply avoiding the insert as its alternative action) and treat a zero-row / conflict result as "already processed, skip the side effect." This makes the constraint the last line of defense behind the application check (IDE-1) and the outbound idempotency key (IDE-2): even if both of those miss, the database physically cannot store the duplicate.

**False positives**

- A column that legitimately repeats and is not an idempotency identifier (a provider customer id or account id that appears on many rows, a status code, a non-unique metadata field) must not be made unique.
- Uniqueness is already enforced by a primary key or a differently-named unique index over the same logical identity (e.g. the external ref is the PK, or a partial unique index `WHERE event_id IS NOT NULL` covers it), so a second constraint is redundant.
- Append-only audit/event-log tables that intentionally record every delivery (including duplicates) for forensic purposes, where deduplication happens downstream on read and uniqueness at write would defeat the log's purpose.
- The store is a genuinely single-writer, serialized pipeline (one partition, one consumer, ordered) where concurrent duplicate inserts cannot occur, making the constraint a belt-and-suspenders nicety rather than a correctness requirement.

**Sources**

1. [Hidden dangers of duplicate key violations in PostgreSQL and how to avoid them](https://aws.amazon.com/blogs/database/hidden-dangers-of-duplicate-key-violations-in-postgresql-and-how-to-avoid-them/) (Amazon Web Services)
2. [INSERT (ON CONFLICT clause)](https://www.postgresql.org/docs/current/sql-insert.html) (PostgreSQL Global Development Group)
3. [Implementing Stripe-like idempotency keys in Postgres](https://brandur.org/idempotency-keys) (Brandur Leach)
