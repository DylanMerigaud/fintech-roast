# Sample report

**What it finds on real code** (not the planted fixture below): two runs on production
codebases are written up in [`eval/FIELD-REPORT-1.md`](../eval/FIELD-REPORT-1.md) (a private
repo, anonymized: 18 findings confirmed, 1 critical) and
[`eval/FIELD-REPORT-2.md`](../eval/FIELD-REPORT-2.md)
([medusajs/medusa](https://github.com/medusajs/medusa) at a pinned commit: 4 confirmed,
filed upstream with a failing test as
[medusajs/medusa#16012](https://github.com/medusajs/medusa/issues/16012)). Those show the
tool on code nobody wrote to be found, including the findings the verifier refuted. The
report below is the fixture run, kept because it exercises every domain at once.

---

This is the full report of run 1 on the TypeScript planted-bug fixture
([`eval/fixture/`](../eval/fixture/)): the same run the README gif replays and
[`eval/RESULTS.md`](../eval/RESULTS.md) scores (86 percent recall, every finding mapping to a
real planted defect). It is rendered from the archived findings and verifier verdicts in
[`eval/run-1-findings.json`](../eval/run-1-findings.json), with punctuation normalized to
plain ASCII per repo convention. This is the report shape the
plugin prints at the end of `/fintech-roast:roast`.

A fixture built to be full of bugs produces a dense report; on a production repo expect far
fewer findings, and "no findings" is a valid outcome. The `[confirmed|likely]` tag on each
finding is the verdict of the adversarial verification pass; refuted findings are dropped
before the report (this run: none refuted, see RESULTS.md for why that is expected on this
fixture and what it does not prove).

```text
CRITICAL AGG-3 src/reports.ts:11 [confirmed]
  totalAllPages loops LIMIT/OFFSET pages (fetchPage(pageSize, offset); offset += pageSize) and
  accumulates a money total across them (total += sumAmounts(...) on line 19). Each page is a
  separate PageFetcher call with no shared transaction, no ORDER BY / stable unique cursor key,
  and no snapshot isolation. If rows are inserted/deleted before the current page between two
  fetches, OFFSET shifts the window: a duplicated row double-counts and a shifted row is
  skipped, so the summed total is silently over- or under-stated on a live table. reports.ts
  imports nothing and there is zero ordering/snapshot/transaction safeguard anywhere on the
  path.
  fix: Compute the total in a single statement (SELECT SUM(amount) ... WHERE ...) so it
  evaluates against one snapshot instead of stitching offset pages by hand. If it must be
  streamed, read inside one repeatable-read/serializable transaction, or use keyset pagination
  on a stable, unique, immutable (created_at, id) key. None of AGG-3's false positives apply
  here (money is summed, no as-of/append-only snapshot, not a single-query aggregate, not keyset
  on a monotonic key, not wrapped in one serializable txn).
  rule: Paginated or streamed aggregation over data that mutates mid-scan double-counts or misses rows (see rules/aggregation-and-reporting.md for sources)

CRITICAL API-1 src/api.ts:10 [confirmed]
  invoiceResponse does JSON.stringify({ id, total: fromMinorUnits(invoice.totalCents) }).
  fromMinorUnits (money.ts:9-11) returns `minor / 100`, a JS number, so the invoice total goes
  on the wire as a bare JSON number, e.g. {"total":19.99}. A decimal fraction like 19.99 has no
  exact binary64 representation and can round on the round-trip; any consumer parses it back
  into an IEEE 754 double. This is settled money (invoice total), not a rate/count, so it does
  not hit the false-positive carve-outs.
  fix: Do not emit money as a JSON number. Serialize the total as a decimal string
  ("total":"19.99", parsed into a Decimal, never a float) or as integer minor units with an
  explicit currency: {"total_minor":1999,"currency":invoice.currency}. Enforce type:string (or a
  documented integer minor-unit field) at the schema boundary.
  rule: Money serialized as a JSON number (see rules/api-and-serialization.md for sources)

CRITICAL API-1 src/api.ts:14 [confirmed]
  accountBalanceResponse returns JSON.stringify({ balance: balanceCents }) with balanceCents an
  integer minor-unit count. Integer minor units are the recommended fix, but this is an
  aggregate account balance, exactly the case API-1 flags as able to exceed 2^53-1 ("large
  aggregate balances ... serialized as JSON numbers"; the rule's own example is the balance
  90071992547409910). Above 9007199254740991 cents the value silently collides with its
  neighbour (Number.MAX_SAFE_INTEGER+1 === Number.MAX_SAFE_INTEGER+2), so two different balances
  deserialize to the same number. No bound guarantees this balance stays well under 2^53.
  fix: Serialize the balance as a string of minor units plus an explicit currency:
  {"balance_minor":String(balanceCents),"currency":"USD"}, or as a decimal string, so no large
  aggregate can exceed the 2^53 safe-integer range on the wire. Add a round-trip test with a
  value above 2^53.
  rule: Money serialized as a JSON number (see rules/api-and-serialization.md for sources)

CRITICAL FX-4 src/fx.ts:39 [confirmed]
  totalRevenue reduces `sum + invoice.total` over `SettleableInvoice[]`, where every invoice
  carries its own `currency` field. There is no grouping by currency and no currency-equality
  guard, so amounts in different currencies (e.g. one invoice left in EUR, another in USD or
  MXN) are added into a single bare number. Money here is a primitive `number`, so USD + EUR +
  MXN type-checks and runs, producing a meaningless figure. settleInvoice can and does leave
  invoices in different payout currencies, so the collection is not proven same-currency (fails
  the FX-4 false-positive carve-out for a constant-currency roll-up).
  fix: Aggregate per currency: bucket by `invoice.currency` (a Map<currency, total>) or require
  all invoices share one currency and assert it before summing. Never add raw `.total` across
  rows that carry independent currency codes. If a single reporting figure is needed, convert
  each row to one reporting currency with a captured rate/timestamp (FX-2) first, then sum the
  now-same-currency amounts.
  rule: Arithmetic mixing amounts of different currencies (see rules/fx-and-multicurrency.md for sources)

CRITICAL IDE-1 src/webhooks.ts:12 [confirmed]
  handlePaymentSucceeded credits the account balance (account.balance = account.balance +
  event.amount; saveAccount) as a direct money side effect with no dedup on the provider event
  id. PaymentEvent carries an `id` (line 4) that is never consulted, and there is no processed-
  events table (schema.sql has none) or SETNX guard before the credit. Providers deliver
  webhooks at-least-once and retry on any non-2xx/timeout, so a re-delivered 'succeeded' event
  double-credits. The effect is an increment, not an idempotent set-to-absolute-value or upsert
  keyed on the object id, so replay does not converge (excludes the naturally-idempotent false
  positive).
  fix: Before the credit, record and dedupe on event.id: INSERT INTO processed_events(event_id)
  VALUES ($1) guarded by a UNIQUE constraint (or Redis SET NX); if the row already exists, ack
  200 and skip the side effect. Run the dedup insert and the balance mutation in one transaction
  so a crash cannot leave one without the other.
  rule: Payment webhook handlers must dedupe by processed-event-id before running side effects (see rules/idempotency-and-concurrency.md for sources)

CRITICAL IDE-2 src/webhooks.ts:19 [confirmed]
  chargeCustomer POSTs to the provider's /v1/charges (a money movement) inside a hand-rolled
  retry loop (for attempt < 3, retrying on catch, lines 17-27) and sends no idempotency key in
  headers or body. On a timeout/dropped connection the client cannot tell whether the charge
  succeeded, so each retry is a fresh charge and double-charges the customer. This is a raw
  fetch, not an SDK that auto-injects a client-request-token, and it is explicitly auto-retried
  (not a single manual-reconciliation fire), so no false-positive note applies.
  fix: Generate one V4-UUID idempotency key per logical charge before the first send, persist it
  with the operation, and send it as an 'Idempotency-Key' header on every attempt (identical
  params each time). Reuse the same key across all three retries and across a process restart;
  back it with a local UNIQUE constraint per IDE-4.
  rule: Outbound charge/payout API calls must send an idempotency key scoped per logical operation (see rules/idempotency-and-concurrency.md for sources)

CRITICAL IDE-3 src/ledger.ts:16 [likely]
  postEntry does an application-side read-modify-write on the persistent account balance:
  getAccount(entry.accountId) then account.balance += entry.amount then saveAccount(account),
  with no row lock, no version guard, and no atomic single UPDATE. Against the real
  accounts.balance column (schema.sql line 4), two concurrent postEntry calls for the same
  account both read the same balance and the later write loses the earlier increment. Caveat:
  as-written the store.ts Map stub is synchronous single-threaded so no interleaving occurs; the
  flagged defect is the RMW pattern that is a lost update once this runs against the real DB.
  fix: Do the arithmetic in the database in one statement: UPDATE accounts SET balance = balance
  + $amount WHERE id = $id, so concurrent updates serialize on the row. If a prior read is
  genuinely needed, take SELECT ... FOR UPDATE and update within the same transaction, or use a
  version column with retry.
  rule: Balance and quantity updates must be atomic (single UPDATE or row lock), never application-side read-modify-write (see rules/idempotency-and-concurrency.md for sources)

CRITICAL IDE-3 src/ledger.ts:26 [likely]
  correctEntry does an application-side read-modify-write on a persistent account balance:
  getAccount(entry.accountId) then account.balance += newAmount - entry.amount then
  saveAccount(account), with no row lock, no version column, and no single atomic UPDATE. Backed
  by the real accounts.balance column (schema.sql line 4), two concurrent corrections both read
  the same starting balance and the second saveAccount clobbers the first (lost update). Caveat:
  the current store.ts stub is a synchronous in-memory Map, so as-written there is no
  interleaving; the defect is the RMW-on-balance pattern the rule targets, which becomes a
  genuine lost update once the stub is the real DB.
  fix: Apply the delta in one statement against the current row: UPDATE accounts SET balance =
  balance + ($newAmount - $oldAmount) WHERE id = $id (or take SELECT ... FOR UPDATE for the
  whole read-modify-write in one transaction, or add a version column and retry on zero rows
  affected). Never round-trip the balance through application memory to mutate it.
  rule: Balance and quantity updates must be atomic (single UPDATE or row lock), never application-side read-modify-write (see rules/idempotency-and-concurrency.md for sources)

CRITICAL LED-1 src/ledger.ts:27 [confirmed]
  correctEntry() fixes a mistake by mutating the original posted entry in place: `entry.amount =
  newAmount` (line 27), and adjusts the balance by the delta at line 26. The entry is posted
  (postedAt is set at creation, ledger.ts:8; there is no draft/pending lifecycle). This is
  precisely the forbidden correction-in-place path the rule flags: it should leave the wrong
  entry untouched and post an equal-and-opposite reversing entry that links back to the original
  (reverses_entry_id), then a corrected entry, atomically. Overwriting amount destroys history
  and silently rewrites any balance already trusted downstream.
  fix: Make correctEntry append two new entries instead of editing: a reversing entry with
  amount = -entry.amount referencing entry.id via reverses_entry_id, then a new corrected entry,
  both in one transaction. Never write entry.amount on a posted row. Add a DB BEFORE UPDATE OR
  DELETE trigger on ledger_entries that raises when the row is posted, so the mutation is
  impossible at the storage layer, not just avoided in code.
  rule: Posted ledger entries mutated or deleted instead of reversed (see rules/ledger-design.md for sources)

CRITICAL LED-2 db/schema.sql:33 [confirmed]
  The ledger_entries table (lines 33-39) records money movement single-entry: one signed
  `amount` per row against one `account_id`, with no `direction`/`side` (debit|credit) column,
  no counter-account, and no shared `transaction_id`/`journal_id` grouping the two legs of a
  transfer. This is the source of truth for money movement (postEntry at ledger.ts:16 writes
  exactly one leg and moves only that account's balance; webhooks.ts:12 credits one account with
  nothing on the other side), not a read-model projection. With no offsetting side there is no
  sum(debits)==sum(credits) invariant possible, so a dropped or partial write silently creates
  or destroys money.
  fix: Model double-entry: add a `direction` (debit|credit), keep `account_id` per leg, add a
  `transaction_id` grouping the legs, an `amount` in minor units, and a `currency`; require
  every transaction to carry >=2 entries that balance per currency, written atomically. Book
  fees/FX/gateway flows to real clearing/suspense/revenue accounts so the system sums to zero,
  and add a per-transaction assertion that sum(debit)==sum(credit).
  rule: Single-entry recording of multi-party money movement (see rules/ledger-design.md for sources)

CRITICAL ROU-2 src/split.ts:5 [confirmed]
  splitProportionally maps each weight to roundMoney((total * w) / weightSum) independently
  inside .map(), with no residual/remainder-distribution pass and no assertion that the parts
  sum to total. This is the textbook proportional-allocation penny bug (Foemmel's Conundrum):
  rounding each share independently means the rounded parts almost never add back to the
  original total, so cents are lost or created on specific amount/ratio pairs (e.g. splitting
  0.05 by weights [70,30] cannot sum back to 0.05 under fixed per-part rounding). There is no
  allocate()/largest-remainder/Hamilton logic anywhere in the fixture (grep confirms). None of
  the ROU-2 false positives apply: no remainder pass, no carried-forward residual, no last-
  bucket = total - sum(others) adjustment, and this is a settling split, not a forecast.
  fix: Treat allocation as one operation with the invariant sum(parts) == total. Work in integer
  minor units, floor each bucket's exact share, then distribute the leftover minor units one at
  a time to the buckets with the largest fractional remainders (largest-remainder / Hamilton
  method), or use a vetted Money.allocate(ratios) primitive. This guarantees the parts sum
  exactly to the whole and each part stays within one minor unit of its ideal share.
  rule: Pro-rata allocation that loses or creates cents (see rules/rounding-and-allocation.md for sources)

CRITICAL STO-1 db/schema.sql:10 [confirmed]
  invoices.subtotal is DOUBLE PRECISION. A monetary subtotal held as a binary float carries
  rounding error into every downstream discount/tax computation that reads it.
  fix: Store invoices.subtotal as NUMERIC or integer minor units, not DOUBLE PRECISION.
  rule: Money stored as binary float or double (see rules/storage-and-types.md for sources)

CRITICAL STO-1 db/schema.sql:12 [confirmed]
  invoices.tax is DOUBLE PRECISION. Tax is a money amount (not a rate); storing it as a float
  makes the persisted tax figure inexact, which is a compliance-relevant amount.
  fix: Store invoices.tax as NUMERIC(precision,scale) or integer minor units, not DOUBLE
  PRECISION.
  rule: Money stored as binary float or double (see rules/storage-and-types.md for sources)

CRITICAL STO-1 db/schema.sql:13 [confirmed]
  invoices.total is DOUBLE PRECISION. The invoice total is the amount billed/collected; a float
  representation makes the persisted total inexact and order-dependent, so two valid tax paths
  can disagree by a cent (Modern Treasury's 16.77 vs 16.78).
  fix: Store invoices.total (and subtotal, tax) as NUMERIC(precision,scale) or integer minor
  units instead of DOUBLE PRECISION.
  rule: Money stored as binary float or double (see rules/storage-and-types.md for sources)

CRITICAL STO-1 db/schema.sql:22 [confirmed]
  invoice_lines.unit_price is REAL (32-bit binary float). Unit prices are money and are
  multiplied by quantity to form line totals; REAL has even fewer mantissa bits than DOUBLE, so
  per-line amounts are inexact and errors compound across many lines.
  fix: Store unit_price as NUMERIC with guard digits (e.g. NUMERIC(19,4)) or integer minor
  units, not REAL.
  rule: Money stored as binary float or double (see rules/storage-and-types.md for sources)

CRITICAL STO-1 db/schema.sql:28 [confirmed]
  payments.amount is DOUBLE PRECISION. Received-payment amounts move real money; a binary float
  stores 0.1-class cents as approximations, so a payment can be recorded a sub-cent off and
  reconciliation against the invoice total fails.
  fix: Store payments.amount as NUMERIC(precision,scale) sized for the largest payment, or as
  integer minor units; not DOUBLE PRECISION.
  rule: Money stored as binary float or double (see rules/storage-and-types.md for sources)

CRITICAL STO-1 db/schema.sql:37 [confirmed]
  ledger_entries.amount is DOUBLE PRECISION. A ledger's posted amount is the canonical money-
  movement record, and IEEE-754 binary floats cannot represent common decimal cents exactly, so
  entries drift and the ledger stops balancing across accumulated postings.
  fix: Change ledger_entries.amount to NUMERIC with an appropriate precision/scale (e.g.
  NUMERIC(19,4)) or store integer minor units; never DOUBLE PRECISION for a ledger amount.
  rule: Money stored as binary float or double (see rules/storage-and-types.md for sources)

CRITICAL STO-1 src/api.ts:14 [confirmed]
  accountBalanceResponse serializes balance as a raw JSON number (balanceCents emitted
  directly), and invoiceResponse (line 10) emits total: fromMinorUnits(...) as a JSON number
  too. Declaring a money amount as a JSON number sends it through a double on any consumer,
  losing exactness above 2^53 and reintroducing float rounding.
  fix: Serialize monetary values as string decimals or integer-minor-unit strings in the JSON
  payload, never as JSON numbers.
  rule: Money stored as binary float or double (see rules/storage-and-types.md for sources)

CRITICAL STO-1 src/money.ts:1 [confirmed]
  parseAmount returns parseFloat(input): a JS number (IEEE-754 double) holding money that flows
  into invoice/tax/split arithmetic and back to persistence without ever being converted to an
  exact type. This is the FP exclusion inverted: the boundary value is NOT parsed into an exact
  type, it stays a float.
  fix: Parse the amount into an exact representation at the boundary: integer minor units (a
  branded Cents type) or a decimal library instance, not a bare number.
  rule: Money stored as binary float or double (see rules/storage-and-types.md for sources)

CRITICAL TIM-3 src/interest.ts:16 [confirmed]
  transactionsInPeriod filters with `t.at >= periodStart && t.at <= periodEnd`, a closed [start,
  end] interval on both ends. monthlyStatement (lines 19-21) calls it with periodStart =
  monthStarts[monthIndex] and periodEnd = monthStarts[monthIndex+1], so the end of period N is
  literally the start of period N+1. A transaction whose `at` equals monthStarts[monthIndex+1]
  is counted in BOTH month monthIndex (as <= periodEnd) and month monthIndex+1 (as >=
  periodStart) - the boundary transaction is double-counted across adjacent statements. This is
  not the half-open [start, next_start) shape; the false-positive exemptions (date-only column
  with strictly-later next period, intentional anchor spec, non-money analytics view) do not
  apply since these are Date instants, the ends collide exactly, and monthlyStatement is a
  money/statement path.
  fix: Model each statement period as a half-open interval [start, next_start) and make
  transactionsInPeriod use `t.at >= periodStart && t.at < periodEnd` so each transaction belongs
  to exactly one period with no overlap or gap. Derive both period ends from one canonical
  interval.
  rule: Ambiguous billing/statement period boundaries and month-end clamping (see rules/time-and-dates.md for sources)

HIGH AGG-1 src/fx.ts:39 [confirmed]
  totalRevenue sums money with invoices.reduce((sum, invoice) => sum + invoice.total, 0) where
  invoice.total is a native number carrying a decimal-dollar amount (settleInvoice writes
  convert()'s .toFixed(2) result into it, and invoices.total is DOUBLE PRECISION in
  db/schema.sql). Accumulating currency in a JS float drifts as sqrt(n)/n and depends on add
  order/partitioning, yielding reconciliation mismatches. This is a distinct file/function/money
  path from reports.ts sumAmounts.
  fix: Sum invoice totals in integer minor units or a fixed-precision decimal type rather than a
  Number accumulator, and never compare two such sums for exact equality (use a tolerance). Not
  an integer-cents false positive: the totals are dollar floats (DOUBLE PRECISION column +
  .toFixed(2) rounding in convert).
  rule: Summing money as binary floats: error accumulates with n and depends on order and partitioning (see rules/aggregation-and-reporting.md for sources)

HIGH AGG-1 src/reports.ts:2 [confirmed]
  sumAmounts sums money with amounts.reduce((a, b) => a + b, 0) accumulating into a native JS
  number (binary64 float). These are decimal-dollar amounts, not integer minor units: the source
  columns are DOUBLE PRECISION (payments.amount, ledger_entries.amount, invoices.total in
  db/schema.sql) and fx.convert rounds with .toFixed(2), proving dollar-value floats. IEEE-754
  addition is non-associative, so error grows with n and the total depends on
  order/partitioning; line 19 (total += sumAmounts(page...)) compounds the same float-sum across
  pages. No decimal/integer money type exists anywhere on this path.
  fix: Keep money out of binary floats: sum in integer minor units (cents as safe integers) or a
  fixed-precision decimal (decimal.js / Prisma.Decimal), and never let the accumulator be a
  Number. The integer-minor-unit AGG-1 false positive does not apply because these are dollar
  floats (DOUBLE PRECISION source columns + .toFixed(2) rounding), not BIGINT cents.
  rule: Summing money as binary floats: error accumulates with n and depends on order and partitioning (see rules/aggregation-and-reporting.md for sources)

HIGH API-3 src/money.ts:2 [confirmed]
  parseAmount does `return parseFloat(input)` and is called by parsePaymentRequest
  (api.ts:17-20) on `parsed.amount`, an API-supplied amount string from JSON.parse(body), whose
  result flows onward as the payment { amount } with no validity gate. parseFloat is a partial
  parse: parseFloat("12,34") returns 12 (stops at the comma, mis-reads DE/FR/BR locale amounts),
  parseFloat("3.14xyz") returns 3.14 (ignores trailing garbage), and unparseable input returns
  NaN which is not caught by any Number.isNaN guard here. It also lands the amount in an IEEE
  754 double. This is raw request input on a charge path, not a pre-validated canonical string
  and not display-only, so it is not a false positive.
  fix: Do not parse money with parseFloat. Validate the amount string against a strict numeric
  grammar (reject trailing chars, empty input, unexpected separators), then parse into an exact
  decimal type or an integer minor-unit parse; reject a non-matching value as a 400 rather than
  best-effort rounding. Use a locale-aware parser if localized input is accepted.
  rule: parseFloat / Number()-style parsing of money input strings (see rules/api-and-serialization.md for sources)

HIGH FX-1 src/fx.ts:16 [confirmed]
  convert() returns `Number((amount * rate).toFixed(2))`, rounding to the minor unit on every
  conversion leg, and the helper is used symmetrically for there-and-back settlement
  (settleInvoice at line 25 converts to the payout currency; refundInOriginalCurrency at line 35
  converts back). Because each leg rounds independently, A->B->A is not invertible: 74 of the
  first 199 whole-dollar amounts leak a cent on a USD->EUR->USD round trip (e.g. 133.00 USD ->
  122.36 EUR -> 133.01 USD). The rounded result is persisted and settled/refunded, not a
  display-only preview, so the informational-estimate false positive does not apply.
  `.toFixed(2)` also hardcodes 2 minor-unit digits for all currencies regardless of ISO 4217
  exponent.
  fix: Treat conversion as one-way and lossy: keep full precision internally and round exactly
  once at the settlement boundary, storing the pre-rounded high-precision value if
  reconciliation is needed. For refunds/reversals compare against the originally stored source
  amount (FX-3), never against a value recomputed by reversing the conversion, and allow a
  documented minor-unit tolerance. Derive the minor-unit exponent from the currency rather than
  hardcoding 2.
  rule: Currency conversion round-trips assumed lossless (see rules/fx-and-multicurrency.md for sources)

HIGH FX-2 src/fx.ts:25 [confirmed]
  settleInvoice applies an exchange rate and persists only the converted amount
  (`invoice.total`) with no rate value, no rate source, and no as-of timestamp captured on the
  invoice. The rate itself comes from the module-level `RATES` constant (lines 1-6), a single
  mutable in-code map reused for every conversion and every direction, with no point-in-time /
  append-only rate record. Editing RATES silently changes every historical conversion, invoices
  stop reproducing, and IAS 21's rate-at-transaction-date cannot be honored. This is a
  settlement path, not an indicative pre-trade quote, so the re-quoted-at-booking false positive
  does not apply.
  fix: Persist the conversion as an immutable fact at the moment it happens: store the rate
  value used, the source/provider identifier, and the as-of timestamp (or rate date) next to the
  amounts. Model rates as append-only point-in-time records (base, quote, rate, source,
  valid_at) instead of a mutable RATES map, and read the captured rate off the row for re-
  renders; only new events look up a fresh rate.
  rule: Exchange rate applied without capturing rate value, source and timestamp (see rules/fx-and-multicurrency.md for sources)

HIGH FX-3 src/fx.ts:25 [confirmed]
  settleInvoice mutates the invoice in place: `invoice.total = convert(invoice.total,
  invoice.currency, payoutCurrency); invoice.currency = payoutCurrency;`. It converts on write
  and overwrites both the original amount and the original currency, discarding the
  transaction's own-currency source of truth. After settlement you can no longer show what the
  customer was actually invoiced, and any later reconversion (see refundInOriginalCurrency)
  rounds an already-rounded value. Real foreign conversion occurs, so this is not the single-
  currency false positive.
  fix: Keep (original_amount, original_currency) as the source of truth and write the settled
  figure to separate derived fields (converted_amount, converted_currency) plus the rate and
  timestamp (FX-2). Never overwrite the source amount/currency in place; treat the payout figure
  as an additional column, not a replacement, so refunds and audits can read the retained
  original.
  rule: Only the converted amount stored, original amount and currency lost (see rules/fx-and-multicurrency.md for sources)

HIGH FX-3 src/fx.ts:35 [confirmed]
  refundInOriginalCurrency computes the refund as `convert(chargedAmount, chargeCurrency,
  originalCurrency)` - it recomputes the original charge amount via a reverse FX conversion
  instead of reading a stored original amount. This is exactly the pattern FX-3 names
  ("Refund/reversal logic that recomputes the original charge amount via FX"). Because convert()
  rounds each leg to 2 decimals, reconverting an already-converted number stacks a second
  rounding: a $133.00 charge settled to 122.36 EUR refunds back to $133.01 USD, over-refunding a
  cent. The customer is refunded a different amount than they were charged.
  fix: Read the stored original charge amount and currency and refund that exact value; do not
  reconvert the converted/settled figure. If the original must be retained (see FX-3 on
  settleInvoice), the refund becomes a direct lookup with no FX arithmetic and no second
  rounding.
  rule: Only the converted amount stored, original amount and currency lost (see rules/fx-and-multicurrency.md for sources)

HIGH IDE-4 db/schema.sql:29 [confirmed]
  The payments table stores the provider transaction reference `external_ref TEXT` (line 29)
  with no UNIQUE constraint and no NOT NULL. external_ref is precisely the external-reference
  dedup identifier named by the rule; without a unique index the database cannot be the last
  line of defense, so two concurrent inserts of the same provider payment (a check-then-insert
  race, or an app that skips the check) both succeed and create duplicate payment rows for one
  real payment. It is nullable, so even a unique index would not collapse multiple NULLs. It is
  not a legitimately-repeating field, is not covered by the PK (id is an internal id), and
  payments is a money table not an append-only audit log.
  fix: Make it UNIQUE NOT NULL at the provider's dedup grain: external_ref TEXT NOT NULL UNIQUE
  (or a partial UNIQUE INDEX WHERE external_ref IS NOT NULL if genuinely optional), and insert
  with INSERT ... ON CONFLICT (external_ref) DO NOTHING, treating a conflict as 'already
  recorded, skip the side effect'.
  rule: External transaction references need a database UNIQUE constraint as the last line of dedup defense (see rules/idempotency-and-concurrency.md for sources)

HIGH LED-3 db/schema.sql:4 [confirmed]
  accounts.balance is a standalone mutable column used as the source of truth for money: it is
  written directly by adding deltas (ledger.ts:16 `account.balance += entry.amount`,
  ledger.ts:26, webhooks.ts:12) with no reconciliation. It is not provably a function of the
  entries: in the running code the entries live in a separate in-memory array (ledger.ts:11)
  while balances live in a separate Map (store.ts:6), and in the schema ledger_entries and
  accounts.balance are independent with no query comparing stored balance to SUM(entries), no
  drift alert, no recompute path. On any partial failure/retry/race the two diverge and money
  decisions run on a wrong number (balance drift).
  fix: Make entries the source of truth and derive the balance by summing entries (or from per-
  account debit/credit counters updated in the SAME atomic transaction as the entry). If a
  materialized balance is kept, write it transactionally with the entry and add a reconciliation
  job that recomputes SUM(entries) per account, compares to the stored balance, and alerts on
  drift beyond tolerance.
  rule: Stored balances neither derived from entries nor reconciled against them (see rules/ledger-design.md for sources)

HIGH LED-4 db/schema.sql:33 [confirmed]
  ledger_entries (lines 33-39) has no attribution or reason columns: no `created_by`/`actor_id`,
  no `reason`/`memo`, no `idempotency_key`/`source`. It carries created_at only, so a row cannot
  explain WHO moved money or WHY. Combined with correctEntry (ledger.ts:27) overwriting the
  prior amount with no history/versioning table and webhooks.ts:12 mutating a balance with no
  entry recorded at all, there is no immutable, attributable record of money mutations, so a
  balance cannot be explained or audited.
  fix: Stamp every entry with created_by/actor_id, created_at, a reason/source, and an
  idempotency_key, and route ALL balance changes through ledger entries (never a bare balance
  write as in webhooks.ts:12). Keep entries append-only so history is inherently tamper-
  resistant; for corrections append a reversing entry rather than overwriting amount, preserving
  the full chronicle.
  rule: Money mutations without an audit trail (see rules/ledger-design.md for sources)

HIGH ROU-1 src/money.ts:14 [confirmed]
  roundMoney returns Number(value.toFixed(2)) on a binary float, the literal ROU-1 anti-pattern:
  no explicit rounding mode, and toFixed rounds in a direction that depends on the input's
  binary float representation (MDN: (2.35).toFixed(1) => 2.4 but (2.55).toFixed(1) => 2.5). This
  is the single shared money-rounding helper, imported and used by lineTotal,
  unitPriceFromBundle, bundleLineTotal, invoiceTotal, and splitProportionally, so its output is
  stored/fed into downstream balances, not a display-only string. The display-only and non-
  monetary false positives therefore do not apply, and there is no decimal type or documented
  banker's-rounding house policy anywhere in the fixture (grep confirms no
  BigDecimal/Decimal/RoundingMode).
  fix: Pick one money-rounding policy, name the mode explicitly, and centralize it. Round on a
  decimal type or integer minor units rather than a binary float, and choose the mode from the
  requirement (half-up for many tax/payment rules, half-even for accounting close) instead of
  relying on toFixed's float-dependent behavior. Apply it consistently at every call site and
  document why.
  rule: No explicit rounding mode on money operations (see rules/rounding-and-allocation.md for sources)

HIGH ROU-3 src/invoice.ts:26 [confirmed]
  invoiceTotal applies a discount then tax as chained multipliers with a roundMoney after each
  step: discounted = roundMoney(subtotal * (1 - discountPct/100)); taxed = roundMoney(discounted
  * (1 + taxRate)). Rounding between each multiply compounds error and bakes the discount-
  before-tax order plus a per-step rounding point into the total with no documented policy.
  Compounded by per-line rounding upstream (subtotal accumulates roundMoney(unitPrice*quantity)
  from lineTotal), so the invoice mixes per-line and per-total rounding conventions. This is the
  exact ROU-3 chained round(round(a*r1)*r2) pattern. No false positive applies: there is no
  documented single-rounding-point pipeline, no jurisdiction-mandated per-line rule encoded, and
  the result is the authoritative stored total, not a UI breakdown.
  fix: Define one canonical pipeline (e.g. base, then discount, then tax), carry full precision
  through the intermediate steps, and round once at the settlement boundary instead of after
  every multiply. Decide explicitly whether tax is per-line or per-invoice-total and use that
  same choice in checkout, invoicing and the ledger so they reconcile by construction; assert
  the pipeline matches the tax-authority worked example.
  rule: Discounts, fees and percentages applied in inconsistent order with intermediate rounding (see rules/rounding-and-allocation.md for sources)

HIGH ROU-4 src/invoice.ts:18 [confirmed]
  bundleLineTotal computes unitPriceFromBundle(bundleTotal, quantity) which is
  roundMoney(bundleTotal / quantity) (divide-then-round-to-cents), then multiplies that pre-
  rounded per-unit value back by quantity. This is the ROU-4 round-then-scale shape unit =
  round(total / count); result = unit * count: division discards precision first, then the
  multiply amplifies it back. Example: bundleTotal=100, quantity=3 gives unit 33.33, times 3 =
  99.99, so a cent vanishes vs the upstream bundle total. False positives do not apply: the
  division is not exact (3 does not evenly divide 100), the unit price is not a stored
  authoritative catalog value (it is derived from the upstream bundleTotal), and this posts to
  invoice/billing math, not a UI-only ratio.
  fix: Multiply first and divide last, dividing exactly once at the end. Keep bundleTotal in
  integer minor units and only derive a per-unit figure with a single final rounding when a unit
  price must actually be displayed; never round the unit price and then scale it by quantity.
  For an even split of the bundle across quantity, use a largest-remainder allocation (see
  ROU-2) so the line totals sum back to bundleTotal.
  rule: Dividing before multiplying on money (see rules/rounding-and-allocation.md for sources)

HIGH STO-2 db/schema.sql:4 [confirmed]
  accounts.balance is NUMERIC(6,2), so it overflows above 9999.99. A running account balance is
  an accumulator that can far exceed ~10k; PostgreSQL will error/overflow when the summed
  balance grows past the declared precision.
  fix: Size the precision for the largest balance the account will ever hold (e.g. NUMERIC(19,4)
  or at least NUMERIC(15,2)), not a single small transaction.
  rule: DECIMAL/NUMERIC declared with wrong precision or scale (see rules/storage-and-types.md for sources)

HIGH STO-4 db/schema.sql:13 [confirmed]
  invoices stores subtotal/tax/total with no adjacent currency column, yet src/fx.ts converts
  invoice.total between currencies and rewrites invoice.currency, so currency is a real
  dimension the schema fails to persist. Amounts read back cannot be interpreted without a
  currency, and multi-currency rows silently mix.
  fix: Add a currency_code (ISO 4217) column to invoices (and payments/ledger_entries), stored
  per row alongside each amount.
  rule: Amounts stored or passed around without their currency (see rules/storage-and-types.md for sources)

HIGH STO-4 src/api.ts:10 [confirmed]
  invoiceResponse receives InvoiceRecord which carries a currency field (line 6) but drops it,
  emitting only { id, total } as a bare amount. The consumer gets a number with no currency, so
  100 could be USD, JPY, or BHD.
  fix: Include the currency in the response payload next to the amount (e.g. { id, total,
  currency }).
  rule: Amounts stored or passed around without their currency (see rules/storage-and-types.md for sources)

HIGH STO-5 src/money.ts:6 [confirmed]
  toMinorUnits multiplies by a hardcoded 100 (and fromMinorUnits, line 10, divides by 100) with
  no per-currency exponent lookup. Sending 1000 for JPY would mean 1000 yen not 10, and BHD
  needs a 1000-based scale; the STO-3 named-helper false positive does not apply because the
  conversion is not driven by the currency exponent.
  fix: Drive the multiplier/divisor from the currency's minor-unit exponent (10^exponent from an
  ISO 4217 table), not a literal 100.
  rule: Hardcoded two-decimal assumption (see rules/storage-and-types.md for sources)

HIGH STO-5 src/money.ts:14 [confirmed]
  roundMoney does Number(value.toFixed(2)), applying a fixed 2-decimal round to every amount
  regardless of currency. It is called on all invoice, tax, and split outputs (src/invoice.ts,
  tax.ts, split.ts), so JPY (0-decimal) is over-scaled and BHD/KWD (3-decimal) is truncated.
  fix: Round using the currency's ISO 4217 minor-unit exponent (look up per currency via
  Intl.NumberFormat/a currency table), not a hardcoded toFixed(2).
  rule: Hardcoded two-decimal assumption (see rules/storage-and-types.md for sources)

HIGH TAX-1 src/tax.ts:8 [confirmed]
  invoiceTaxByLines sums already-rounded per-line tax (sum(roundMoney(amount*rate))) while
  invoiceTaxOnTotal (line 15) rounds the tax on the summed subtotal (roundMoney(total*rate)).
  Both are exported and both are imported by tests/billing.test.ts, so the same document's tax
  is computed by two different rounding levels with no config flag choosing line-level vs
  document-level. On lineAmounts=[10.10,10.10] invoiceTaxByLines returns 1.66 and
  invoiceTaxOnTotal returns 1.67: the paths disagree by a cent on multi-line invoices, so the
  invoice total will not tie out to the ledger/payment.
  fix: Pick one rounding level (line vs document) as an explicit configured policy and route
  every path (PDF, API, ledger, tax export) through the same helper. Delete or converge the
  second method, or gate both behind a documented `level` parameter and record which method
  produced the stored total. Persist both the per-line figures and the authoritative document-
  level tax so downstream systems reconcile instead of re-deriving.
  rule: Tax rounded at the wrong or inconsistent level (per line vs per document) (see rules/taxes.md for sources)

HIGH TAX-2 src/tax.ts:20 [confirmed]
  extractTaxFromGross back-calculates net = roundMoney(gross/(1+rate)) (correct inclusive
  method) but then computes tax = roundMoney(gross*rate) independently instead of tax = gross -
  net. The two rounded pieces do not re-sum to the gross: on gross=108.25, net=100.00 and
  tax=8.93, so net+tax=108.93 != 108.25. This breaks the inclusive-line invariant that net+tax
  must equal the displayed gross, under-remitting/mis-stating tax on the invoice.
  fix: Derive the second component from the first: net = roundMoney(gross/(1+rate)) then tax =
  gross - net (or round tax first then net = gross - tax). Do the arithmetic on integer minor
  units so net + tax == gross by construction, never round net and tax in isolation.
  rule: Tax-inclusive vs tax-exclusive confusion (see rules/taxes.md for sources)

HIGH TAX-3 src/tax.ts:3 [confirmed]
  SALES_TAX_RATE = 0.0825 is a binary float literal, and tax is computed as `amount *
  SALES_TAX_RATE` in JS doubles then rounded via roundMoney's Number(value.toFixed(2))
  (money.ts). 0.0825 has no exact binary representation, so amount*rate is computed on a value
  that is not the rate written and the error surfaces after rounding on adversarial amounts and
  accumulates across lines. This is the authoritative charged/persisted tax (not a throwaway UI
  estimate), so it is a money-safety defect.
  fix: Represent the rate as integer basis points (825 for 8.25%) and compute on integer minor
  units: tax_minor = round(amount_minor * 825, half-even) / 10000. Keep the rate and all money
  math out of binary floating point; in JS use a decimal/bigint minor-unit approach rather than
  a float rate literal.
  rule: Tax rates held as binary floats or applied with imprecise percentage arithmetic (see rules/taxes.md for sources)

HIGH TIM-1 db/schema.sql:14 [confirmed]
  invoices.issued_at is typed `TIMESTAMP` (timestamp without time zone), storing an instant with
  the zone discarded. This is the invoice-dating instant that statement/period math buckets into
  a month (the TS monthlyStatement buckets equivalent Dated.at instants). With a naive TIMESTAMP
  the month boundary is computed in whatever zone the server/GUC uses, so a near-midnight
  invoice lands in a different statement month depending on the deploy region - exactly the 'an
  invoice is dated a day off' failure the rule names. No explicit business zone is pinned or
  enforced, and issued_at is a real instant (not a floating wall-clock value), so no false-
  positive exemption applies.
  fix: Store the instant as `TIMESTAMPTZ` (UTC) and derive statement/period boundaries in the
  account's explicit business zone, e.g. `date_trunc('month', issued_at AT TIME ZONE
  'America/New_York')`, passing the zone as data on the account rather than inheriting the host
  locale.
  rule: Financial period calculations run in server-local or mixed time zones (see rules/time-and-dates.md for sources)

HIGH TIM-1 db/schema.sql:30 [confirmed]
  payments.received_at is typed `TIMESTAMP` (without time zone), storing the instant a payment
  was received with the zone discarded. Payments are bucketed into statement/accounting periods
  (the same monthlyStatement-style period math), so a near-midnight receipt shifts periods with
  the server zone. No business zone is pinned/enforced and received_at is a real instant, so no
  false-positive exemption applies.
  fix: Store as `TIMESTAMPTZ` (UTC) and bucket receipts into periods using the account's
  explicit business zone (received_at AT TIME ZONE <business_zone>) rather than the host locale.
  rule: Financial period calculations run in server-local or mixed time zones (see rules/time-and-dates.md for sources)

HIGH TIM-1 db/schema.sql:38 [confirmed]
  ledger_entries.created_at is typed `TIMESTAMP` (without time zone). This is precisely the
  column the rule's own fix example buckets (`date_trunc('month', ts AT TIME ZONE ...) FROM
  ledger_entries`): revenue/ledger entries near a period edge get booked into the wrong month
  when the period is truncated in the ambient server zone instead of an explicit business zone.
  The zone is not pinned or enforced and created_at is a genuine instant, so the single-zone /
  floating-wall-clock / display-only exemptions do not apply.
  fix: Type it `TIMESTAMPTZ` and compute any accounting-period bucket in the account's business
  zone (`date_trunc('month', created_at AT TIME ZONE 'America/New_York')`), never in the
  server's inherited zone.
  rule: Financial period calculations run in server-local or mixed time zones (see rules/time-and-dates.md for sources)

HIGH TIM-2 src/interest.ts:2 [confirmed]
  daysBetween computes `Math.round((end.getTime() - start.getTime()) / 86400000)` - an epoch-
  millis difference divided by 86_400_000 to get calendar days. This result feeds
  accruedInterest (line 6), so it is a calendar-day count, not elapsed physical time. Across a
  DST spring-forward boundary a full local day is only 23h = 0.958 days, so Math.round can drop
  or add a day, mispricing the accrual. The instants originate from naive TIMESTAMP columns
  (schema issued_at/received_at/created_at) with no zone pin, so the UTC-only false-positive
  exemption does not hold, and the intended meaning is a calendar 'day' (per-day interest), not
  an SLA/TTL second-count.
  fix: Count days with a calendar-aware API on zoned or local dates (e.g. LocalDate differences
  / a date library's calendar day-diff) in the account's business zone, rather than dividing an
  epoch-millis difference by 86_400_000.
  rule: DST-naive day arithmetic (86400 s per day, epoch-ms division) (see rules/time-and-dates.md for sources)

HIGH TIM-4 src/interest.ts:7 [confirmed]
  accruedInterest computes `principal * (annualRate / 365) * days` (lines 7-8), baking the 365
  denominator and an implicit ACT day-count basis into a literal with no convention parameter on
  the instrument. There is no enum/config (ACT/360, ACT/365F, ACT/ACT, 30/360, 30E/360)
  representing how a given loan accrues; every instrument is forced onto /365. It is not a
  labeled estimate nor a non-money /365 (the function is literally named accruedInterest and
  returns a money figure via toFixed(2)), and no single convention is asserted/tested, so the
  false-positive exemptions do not apply.
  fix: Make the day-count convention an explicit attribute of each instrument and compute the
  year fraction through a convention object (accrual = notional * rate *
  dayCountFraction(convention, start, end)), sourcing the denominator/basis from the contract
  rather than a hardcoded /365. Prefer a vetted day-count library over an inline divide.
  rule: Interest day-count convention ignored or hardcoded (see rules/time-and-dates.md for sources)

MEDIUM TST-1 tests/billing.test.ts:46 [confirmed]
  The only test for splitProportionally is expect(splitProportionally(100, [1, 1,
  2])).toEqual([25, 25, 50]) - an evenly-divisible case (100/4 = 25 exactly). The suite never
  asserts the conservation invariant sum(parts) === total across arbitrary totals and ratios,
  and there is no fast-check / property-based import anywhere in the file (only vitest, line 1).
  splitProportionally (src/split.ts:5) rounds each part independently with roundMoney and has no
  remainder-distribution logic, so it is a leaky allocator: e.g. splitProportionally(100, [1, 1,
  1]) yields [33.33, 33.33, 33.33] summing to 99.99, which this exact-division fixture can never
  surface.
  fix: Add a property-based test (fast-check) that generates arbitrary totals and weight vectors
  and asserts sum(splitProportionally(total, weights)) === total with strict equality, then pin
  any shrunk counterexample (e.g. 100 split into 3) as a regression case.
  rule: Money invariants asserted only on hand-picked examples, never with property-based generators (see rules/testing.md for sources)

MEDIUM TST-1 tests/billing.test.ts:61 [confirmed]
  The ledger test posts a single entry then corrects it (postEntry {amount:50} +
  correctEntry('e1', 60)) and checks balance === 60. It never generates random operation
  sequences and re-checks the running-balance == sum-of-entries invariant, nor a balance-never-
  negative invariant. src/ledger.ts mutates account.balance in place on every post/correct with
  no guard, so correctEntry to a smaller amount can drive the balance negative - an invariant no
  single hand-picked pair of operations exercises.
  fix: Add a property-based test that generates random sequences of post/correct operations and
  re-asserts balance == sum(entry.amount) (and any non-negativity invariant) after each step.
  rule: Money invariants asserted only on hand-picked examples, never with property-based generators (see rules/testing.md for sources)

MEDIUM TST-1 tests/billing.test.ts:67 [confirmed]
  convert is tested one direction only: expect(convert(100, 'USD', 'EUR')).toBe(92). There is no
  round-trip test and no bound on the round-trip residual
  (abs(convert(convert(x,'USD','EUR'),'EUR','USD') - x) <= tolerance). The rate table in
  src/fx.ts is asymmetric (USD:EUR 0.92, EUR:USD 1.087), so a USD->EUR->USD round-trip drifts as
  the amount grows, exactly the property a round-trip test would catch; a single one-way literal
  assertion cannot.
  fix: Add a property-based round-trip test that generates amounts and asserts the residual of
  convert(convert(x, a, b), b, a) stays within a documented tolerance, in addition to the one-
  way example.
  rule: Money invariants asserted only on hand-picked examples, never with property-based generators (see rules/testing.md for sources)

MEDIUM TST-2 tests/billing.test.ts:40 [confirmed]
  invoiceTotal is tested only with round fixtures: expect(invoiceTotal([{quantity:4,
  unitPrice:25}], 10, 0.1)).toBe(99). The computation (subtotal 100 -> 10% discount -> 90 -> 10%
  tax -> 99) lands exactly on cent boundaries at every step, so it returns the identical value
  under floor, round-half-up, and round-half-even. src/invoice.ts:26-28 performs three
  sequential roundMoney (.toFixed(2)) calls whose rounding mode is completely unverified by this
  fixture - swapping the mode would not fail the test.
  fix: Add awkward-amount cases that force a real rounding decision (e.g. a discount/tax
  combination yielding a .xx5 tie or a repeating decimal) and assert the specific rounding mode
  your accounting policy requires, so a truncate-vs-round change fails loudly.
  rule: Round-number fixtures (100.00, 10 percent) that cannot distinguish truncate from round from banker rounding (see rules/testing.md for sources)

MEDIUM TST-2 tests/billing.test.ts:84 [confirmed]
  accruedInterest is tested only with a headline principal and a rate contrived to divide
  evenly: expect(accruedInterest(1000, 0.0365, start, end)).toBe(36.5) over exactly 365 days,
  where 0.0365/365 * 365 collapses back to 0.0365 and yields a clean 36.5 with no fractional
  cent to round. src/interest.ts:8 ends in .toFixed(2), but no realistic principal/rate (e.g.
  12345.67 at 8.375% over 37 days) or tie-boundary input exercises that rounding step.
  fix: Add interest cases with realistic principals and rates over odd day counts that produce
  fractional cents (and a .xx5 tie), asserting the required rounding mode rather than a value
  that is clean regardless of mode.
  rule: Round-number fixtures (100.00, 10 percent) that cannot distinguish truncate from round from banker rounding (see rules/testing.md for sources)

MEDIUM TST-2 tests/billing.test.ts:96 [confirmed]
  The 'line and total methods agree' test uses a single round line:
  expect(invoiceTaxByLines([100])).toBe(8.25) and expect(invoiceTaxOnTotal([100])).toBe(8.25).
  invoiceTaxByLines (src/tax.ts:5-11) rounds tax per line while invoiceTaxOnTotal rounds the
  aggregate; these two methods diverge only on multi-line non-round inputs (e.g. [19.99, 19.99]
  where per-line rounding accumulates differently than rounding the sum), and the round single-
  line fixture is precisely the input where they cannot disagree, so the divergence between per-
  line and aggregate rounding is never tested.
  fix: Test the by-lines vs on-total methods with multiple non-round lines (e.g. [19.99, 19.99,
  12.99]) so the per-line-vs-aggregate rounding difference is exercised, and assert the intended
  reconciliation behavior.
  rule: Round-number fixtures (100.00, 10 percent) that cannot distinguish truncate from round from banker rounding (see rules/testing.md for sources)

MEDIUM TST-3 tests/billing.test.ts:25 [confirmed]
  Every money test uses a two-decimal currency (USD/EUR) and toMinorUnits is exercised only as
  expect(toMinorUnits(100)).toBe(10000). src/money.ts:6 applies Math.round(amount * 100)
  uniformly regardless of currency, but no test asserts a zero-decimal currency (JPY 500 -> 500
  minor units, not 50000) or a three-decimal currency (BHD 5 -> 5000, not 500), so the hardcoded
  *100 that overcharges JPY 100x is never probed. The suite also has no negative-amount / refund
  case despite refund paths existing (refundInOriginalCurrency in src/fx.ts, correctEntry
  reversals in src/ledger.ts), and no boundary-magnitude case (0, smallest minor unit, near
  Number.MAX_SAFE_INTEGER).
  fix: Parameterize the money tests over a currency matrix (at least one zero-decimal JPY, one
  two-decimal USD, one three-decimal BHD) asserting the correct minor-unit scaling per currency;
  add negative-amount cases for the refund/correction paths and boundary-magnitude cases (0 and
  a value near the numeric type's limit).
  rule: Test suite covers one happy currency and no boundary magnitudes, refunds, or negatives (see rules/testing.md for sources)

------------------------------------------------------------------------------------------------
53 findings: 20 critical, 26 high, 7 medium
verification: 51 confirmed, 2 likely
domains audited: STO ROU IDE LED FX TIM AGG TAX API TST (all 10; none skipped, every domain had surface)

Findings are rule-based and adversarially verified, but not human-verified. Read the
cited rule before acting; every rule documents its false positives.
```
