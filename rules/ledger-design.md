# Ledger design

Part of the [fintech-roast](../README.md) rulebook. See [README.md](README.md) for the format contract and severity scale.

## LED-1: Posted ledger entries mutated or deleted instead of reversed

**Severity**: critical

**What to detect**

- SQL that targets a financial/ledger table with UPDATE or DELETE: patterns like `UPDATE ... ledger_entr|journal|posting|transaction|movement` and `DELETE FROM ... ledger|journal|posting|entr`, especially setting `amount`, `debit`, `credit`, `account_id`, or `currency` on an already-posted row.
- ORM save/update or destroy on a posted-entry model: `ledgerEntry.update(...)` / `.save()` after mutating a persisted entry, `repo.delete(entry)`, Prisma `prisma.ledgerEntry.update|delete`; Django `entry.save()` / `.delete()` / `.update()` on a posted queryset, SQLAlchemy `session.delete(entry)`; ActiveRecord `entry.update!` / `entry.destroy`; GORM `db.Save(&entry)` / `db.Delete(&entry)`.
- No enforcement that posted rows are immutable: no BEFORE UPDATE/DELETE trigger raising an exception, no policy/rule, no append-only table type, no CHECK or generated-column lock keyed on `posted_at` / `status='posted'`.
- A correction path that edits the original row (recomputing `amount` in place, `UPDATE ... SET amount = corrected`) instead of inserting a new opposite (reversing) entry that references the original via `reverses_entry_id` / `original_entry_id`.
- Hard-delete of transactions on a `void` / `cancel` / `refund` code path rather than posting a compensating entry: grep handlers named void/cancel/reverse that call delete or update on the entry table.
- Financial tables with no immutability marker at all: no `posted_at`, no distinction between a mutable draft/pending state and an immutable posted state, so any row is freely editable.

**Why it breaks**

A ledger is the authoritative record of money movement and its correctness rests on being append-only: once an entry is posted it is never changed, and mistakes are fixed by posting a new opposing (reversing) entry. Modern Treasury states the rule directly: a ledger transaction is mutable while pending and immutable once posted, and you correct by creating a new transaction with the opposite amount, then a second with the correct amount. Stripe's Ledger makes the same guarantee (transactions previously published cannot be deleted or modified, which is what lets past state be reconstructed), and TigerBeetle enforces it at the database layer (transfers cannot be modified and cannot be deleted after creation; errors are fixed with correcting transfers). Mutating or deleting a posted row destroys history, breaks any digest or audit chain, and can silently change balances that downstream reports, payouts, and reconciliations already trusted: corrupted money on a production path.

**Fix**

Treat posted entries as write-once. Model an explicit lifecycle (`pending` then `posted`) and only allow field edits while pending; after posting, forbid UPDATE and DELETE. Enforce it in the database, not just the app: a BEFORE UPDATE OR DELETE trigger on the ledger table that raises for any posted row, or an append-only ledger table type where the engine blocks it (for example SQL Server append-only ledger tables reject updates and deletes at the API level). Implement corrections as reversal (Fowler's Reversal Adjustment): leave the wrong entry in place, post an equal-and-opposite entry that links back to it via `reverses_entry_id`, then post the corrected entry, all inside one transaction so the reversal and its replacement land atomically.

```sql
CREATE TRIGGER ledger_entries_no_mutate
BEFORE UPDATE OR DELETE ON ledger_entries
FOR EACH ROW WHEN (OLD.posted_at IS NOT NULL)
EXECUTE FUNCTION raise_posted_entry_is_immutable();
```

**False positives**

- Rows still in a draft/pending/uncommitted state that the design explicitly allows to be edited or discarded before posting (a mutable staging area is legitimate; the invariant only binds once `posted_at` is set).
- Non-financial columns carrying no monetary meaning being updated (a denormalized `search_text`, a `metadata` or tag JSON blob, an `exported_to_erp_at` flag, a soft `discarded_at` marker used instead of a hard delete) rather than the amount/debit/credit/account fields.
- Bulk DELETE/UPDATE against fixtures, seed, or throwaway test schema, or a one-off reviewed data migration that rebuilds the table wholesale, as opposed to a live production correction path.
- Schema-level DDL or partition maintenance (dropping an archived partition, `TRUNCATE` of a scratch table) rather than row-level mutation of live posted entries.

**Sources**

1. [Enforcing Immutability in your Double-Entry Ledger](https://www.moderntreasury.com/journal/enforcing-immutability-in-your-double-entry-ledger) (Modern Treasury)
2. [Transfers - TigerBeetle Docs](https://docs.tigerbeetle.com/reference/transfer/) (TigerBeetle)
3. [Patterns for Accounting](https://martinfowler.com/eaaDev/AccountingNarrative.html) (Martin Fowler)
4. [Ledger: Stripe system for tracking and validating money movement](https://stripe.dev/blog/ledger-stripe-system-for-tracking-and-validating-money-movement) (Stripe)

## LED-2: Single-entry recording of multi-party money movement

**Severity**: critical

**What to detect**

- A money movement recorded as a single row/mutation that changes one side only: `UPDATE accounts SET balance = balance - :amt WHERE id = :from` with no paired credit row, or an INSERT of one signed `amount` into a transactions table with no counter-account.
- A ledger/entries table missing the columns needed to express both legs: no `direction` / `side` (debit|credit) column, no `account_id` per leg, or entries not grouped under a shared `transaction_id` / `journal_id` that could be balanced.
- Transfer code that debits the sender while the corresponding credit to the receiver is missing, conditional, or in a separate un-atomic step: grep handlers that touch a `from` balance without a matching `to` balance write inside the same transaction.
- No invariant asserting sum(debits) == sum(credits) per transaction and per currency: no CHECK, no post-commit assertion, no `SELECT SUM(CASE WHEN direction='debit' ...) = SUM(...credit...)` reconciliation, no test enforcing balanced journals.
- Balances derived from a single running column with no offsetting account, so a create/refund/fee path can add or remove value with nothing on the other side (money created or destroyed).
- External settlement account absent: fees, FX, rounding, or gateway movements booked to a user account with no corresponding revenue/clearing/suspense account, so totals across the system do not sum to zero.

**Why it breaks**

Double-entry exists so that every movement of value goes from one or more accounts to one or more accounts and money never appears from nowhere or disappears (TigerBeetle). Because each transaction carries equal and opposite debits and credits, the system is self-checking: total debits must equal total credits, a built-in error check that single-entry lacks. Single-entry records each transaction once with no offsetting side, so, as Modern Treasury puts it, there are no credit and debit totals to match and you cannot double-check the books; a dropped, duplicated, or partial write silently creates or destroys money. On a real money path that means a sender debited with no receiver credited (funds vanish) or a credit with no debit (funds materialize), with nothing in the schema able to detect it.

**Fix**

Record money movement with double-entry: every transaction has at least two entries whose debits equal credits, grouped under one transaction id, balanced per currency (do not net across currencies). Give the entries table an explicit `direction`, an `account_id` per leg, an `amount` in minor units, and a `currency`; book fees, FX, and gateway flows to real clearing/suspense/revenue accounts so the whole system sums to zero. Write all legs atomically in one database transaction. Enforce the invariant, do not just document it: a per-transaction assertion or constraint that sum(debit) == sum(credit) per currency, plus a periodic reconciliation that the sum of all account balances (including settlement) is zero. Prefer a purpose-built ledger primitive (TigerBeetle, Modern Treasury Ledgers, Formance) over a hand-rolled single-column balance.

**False positives**

- A purely informational or read-model projection (a denormalized reporting table, a cache, an analytics rollup) that mirrors an underlying balanced double-entry ledger; the single-row view is fine because the source of truth is double-entry.
- Domains that are genuinely not multi-party value transfer, for example an event/audit log, a points or usage counter with no monetary redemption, or a metrics table, where there is no counterparty account to balance against.
- A recognized double-entry shape that stores one row per transaction with paired debit/credit columns on the same row (or per-account balance-delta rows the engine treats as legs) rather than two physical rows, still balanced and still summing to zero.
- Early-stage internal tooling where the money never leaves the system and a reconciliation job with alerting is the deliberate compensating control: latent risk, but not an active production money path.

**Sources**

1. [Single vs. Double Entry Accounting](https://www.moderntreasury.com/learn/single-vs-double-entry-accounting) (Modern Treasury)
2. [Debit/Credit: The Schema for OLTP - TigerBeetle Docs](https://docs.tigerbeetle.com/concepts/debit-credit/) (TigerBeetle)
3. [Ledger: Stripe system for tracking and validating money movement](https://stripe.dev/blog/ledger-stripe-system-for-tracking-and-validating-money-movement) (Stripe)
4. [Double-Entry Ledgers: The Missing Primitive in Modern Software](https://www.pgrs.net/2025/06/17/double-entry-ledgers-missing-primitive-in-modern-software/) (Paul Gross)

## LED-3: Stored balances neither derived from entries nor reconciled against them

**Severity**: high

**What to detect**

- A mutable `balance` column on an account/wallet/user table written directly (`UPDATE accounts SET balance = balance + :amt`) as the source of truth, with no entries table it is provably a function of.
- Balance mutation happening in a different transaction, service, or code path than the entry insert, so the two can diverge on partial failure, retry, or race: grep for a balance write not co-located with the entry write inside one DB transaction.
- No reconciliation job: no query comparing the stored balance to sum(entries) per account, no `SELECT balance - (SUM(credits) - SUM(debits))` check, no drift alert crossing a tolerance, no scheduled sweep.
- Balance read and balance acted-upon diverging (balance conflation): code that reads `available` but decrements `posted`, or authorizes against a cached figure that is not the ledger figure.
- A cached/materialized balance with no invalidation or recompute path tied to entry writes (a Redis balance, a summary row) that can be updated out of band from the ledger.
- Money decisions (authorize, allow-withdrawal, block-overdraft) made off the stored column while entries are inserted asynchronously, so the gate runs on a stale number.

**Why it breaks**

A balance is a derived quantity: as Fowler states, the value, or balance, of the Account is derived as the sum of all its Accounting Entries. A ledger should compute posted/pending/available balances from the entries. Modern Treasury keeps only a small set of per-account movement counters and computes the balances on request, so the number can never disagree with the movements behind it. Formance calls storing a running balance as a standalone field on the account table an anti-pattern, and computes the balance at query time by summing debits and credits from the immutable transaction log, noting that failed transactions, concurrency issues, or data-sync bugs otherwise produce balance drift that is hard to trace. When a balance is stored as an independent mutable column and is neither a pure function of the entries nor reconciled against them, it drifts, and money decisions run on a wrong number. That surfaces as wrong amounts in realistic edge cases (failed writes, retries, races) and is a compliance and customer-trust exposure.

**Fix**

Make entries the source of truth and treat any stored balance as a cache of a derivation. Preferably compute balances by summing entries (or from a small set of per-account debit/credit counters updated in the same atomic transaction as the entry), never as a free-standing column mutated on its own path. If you keep a materialized balance for performance, write it in the same database transaction as the entry so they cannot diverge, and run a reconciliation job that recomputes sum(entries) per account, compares it to the stored balance, and alerts on any drift beyond tolerance. Read and act on the same balance type (do not authorize on `available` while posting to `posted`). Index the movement counters and use incremental checkpoints so deriving stays fast enough that caching is never an excuse to skip reconciliation.

**False positives**

- A materialized/checkpointed balance that is provably a function of the entries: updated in the same atomic transaction as the entry and covered by a reconciliation job that recomputes and alerts on drift. This is the standard performance optimization, not a violation.
- An intentionally approximate, clearly-labeled display or UI figure (a dashboard estimate, an eventually-consistent projection) that no money decision is ever taken against, with authorization still gated on the derived ledger balance.
- Per-account running-total columns (posted_debits/posted_credits/pending_*) that are not a second source of truth but the inputs the balance is computed from on read, updated transactionally with each entry (the Modern Treasury pattern).
- Non-monetary counters or rate-limit/quota tallies stored for speed where a small drift has no financial consequence and there is no ledger to reconcile against.

**Sources**

1. [Patterns for Accounting](https://martinfowler.com/eaaDev/AccountingNarrative.html) (Martin Fowler)
2. [How to Scale a Ledger, Part II: Mapping Financial Events](https://www.moderntreasury.com/journal/how-to-scale-a-ledger-part-ii) (Modern Treasury)
3. [Ledger balance: definition, architecture, and fintech use cases](https://www.formance.com/blog/financial-operations/ledger-balance-for-product-and-engineering) (Formance)
4. [Ledger: Stripe system for tracking and validating money movement](https://stripe.dev/blog/ledger-stripe-system-for-tracking-and-validating-money-movement) (Stripe)

## LED-4: Money mutations without an audit trail

**Severity**: high

**What to detect**

- Ledger/entry writes with no actor/reason columns: table lacks `created_by` / `actor_id`, `created_at`, and a `reason` / `memo` / `idempotency_key` / `source` field, so a row cannot explain who moved money, when, or why.
- In-place UPDATEs to money fields with no history/versioning: an updatable financial table with no system-versioning, no history/shadow table, no append-only log, so a prior value is overwritten and gone.
- Balance-affecting mutations routed around the ledger entirely: direct `UPDATE accounts SET balance` or admin scripts/console edits that leave no entry and no record of the operator or justification.
- No immutable/tamper-evident history: no append-only entries table, event log, or ledger table; corrections that overwrite rather than append make it impossible to reconstruct how a balance was reached.
- Manual adjustment / write-off / comp / chargeback paths that mutate money without recording the authorizing user and a linked reason code: grep admin/backoffice handlers that touch balances or entries.
- Logging that exists but is non-durable or mutable for the audit purpose (plain app logs that rotate or are editable) rather than a persisted, queryable, tamper-resistant record tied to each money mutation.

**Why it breaks**

For anything touching money you must be able to answer who changed what, when, and why, and prove the record was not altered. Microsoft's SQL Server Ledger frames the requirement: it preserves historical data (a prior row value is kept in a history table), provides a chronicle of all changes over time, records the user that performed each change, and gives tamper-evidence so you can attest to auditors that data was not altered. Modern Treasury notes the flip side: with immutability, all history of how the database reached its present state is preserved and the audit log is tamper-resistant, whereas if the data is mutable and has been changed it becomes impossible to figure out what went wrong in an inconsistency. Without an audit trail you cannot explain a balance, cannot pass a financial audit, and lose the ability to reconstruct or dispute a money movement: a real compliance exposure and a debugging dead end when funds are questioned.

**Fix**

Make every money mutation produce an immutable, attributable record. Route all balance changes through ledger entries (never a bare balance UPDATE) and stamp each entry with actor (`created_by`), timestamp (`created_at`), a reason/source, and an idempotency key. Keep the entries append-only so the history is inherently tamper-resistant, and for corrections append a reversing entry rather than overwriting, which preserves the full chronicle. Where the platform offers it, use system-versioned or append-only ledger tables that automatically retain prior values and record the acting user, and, for high-assurance cases, tamper-evident storage (for example SQL Server ledger digests) so alteration is detectable. Make the record durable and queryable for audit, not just ephemeral application logs.

**False positives**

- Money moves already fully explained by an immutable append-only entries log carrying actor/time/reason, even without a separate dedicated audit table; the ledger itself is the audit trail and a parallel table would be redundant.
- Non-monetary, non-sensitive metadata updates (a display name, a UI preference, a cosmetic tag) that carry no balance impact and reasonably need no financial audit record.
- Draft/pending entries mutated before posting, where the durable audit obligation attaches at posting time (the final posted entry and its actor/reason are recorded) rather than to every keystroke on an unposted draft.
- System-generated internal bookings (scheduled interest accrual, automated FX revaluation) attributed to a system/service principal and a rule/job identifier rather than a human user; that is a legitimate actor, not a missing audit trail.

**Sources**

1. [Ledger Overview - SQL Server](https://learn.microsoft.com/en-us/sql/relational-databases/security/ledger/ledger-overview) (Microsoft Learn)
2. [What Is Data Immutability?](https://www.moderntreasury.com/learn/data-immutability) (Modern Treasury)
3. [Double-Entry Ledgers: The Missing Primitive in Modern Software](https://www.pgrs.net/2025/06/17/double-entry-ledgers-missing-primitive-in-modern-software/) (Paul Gross)
