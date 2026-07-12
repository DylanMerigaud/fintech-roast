# Field report 2: Medusa (medusajs/medusa)

The second run on code nobody wrote to be found, and unlike
[field report 1](FIELD-REPORT-1.md) this one is fully reproducible: a named,
public repository at a pinned commit.

- **Target**: [medusajs/medusa](https://github.com/medusajs/medusa), the open-source
  TypeScript commerce platform.
- **Commit**: `917ddbe0e56b4e739fa828140cd7973d823d1bbd`
- **Date**: July 2026
- **Method**: shortlisted money-core files across six domains (STO, ROU, TAX, IDE, AGG,
  API), one auditor per domain, then one adversarial verifier per finding. This is a
  scoped audit, not a cold full-repo scan, so it is not directly comparable to the
  TypeScript fixture's cold-scan recall number.

## Numbers

| | count |
| --- | --- |
| findings emitted by auditors | 16 |
| confirmed by the adversarial pass | 4 |
| likely (real, narrower than the headline claim) | 2 |
| refuted before reporting | 10 |

The confirmed findings are one coherent cluster: check-then-act on money state with no
serialization. They were filed upstream as a single issue with a failing test:
[medusajs/medusa#16012](https://github.com/medusajs/medusa/issues/16012). Before filing,
each was re-verified against the source at the pinned commit (which is the current
`develop` HEAD), confirmed to have no existing open duplicate, and matched to Medusa's own
`describe("concurrency")` test block, which encodes the racy behavior as passing only
because its amounts sum exactly to the authorization.

## Confirmed findings (pending human verification, then upstream issues)

| Rule | Location (at pinned commit) | Defect | Status |
| --- | --- | --- | --- |
| IDE-3 | `packages/modules/payment/src/services/payment-module.ts` ~787 (`capturePayment_`) | Captures relation read before the transaction opens; the over-capture guard is check-then-act at READ COMMITTED with no row lock, version, or unique constraint, and no caller (admin route or workflow) adds a lock or idempotency key. Two concurrent captures both pass the guard; the Stripe provider swallows the already-captured error, so both rows persist and additive-capture providers double-move money. | filed #16012 |
| IDE-3 | `packages/modules/payment/src/services/payment-module.ts` ~942 (`refundPayment_`) | Same unserialized check-then-act for refunds, with per-refund-row idempotency keys, so two concurrent partial refunds both pass and `stripe.refunds.create` moves real money twice. | filed #16012 |
| IDE-3 | `packages/modules/promotion/src/services/promotion-module.ts` ~369 (campaign budget `used`) | `registerUsage` runs under the cart-completion lock keyed on the cart id only, so two carts redeeming the same promotion concurrently both read `used = X` and both write `X + amount` as an absolute value (no `FOR UPDATE`, no version): a lost update that lets a spend-capped campaign budget be exceeded. | filed #16012 |
| IDE-3 | `packages/modules/promotion/src/services/promotion-module.ts` ~229 (per-attribute usage) | The update branch reads `used`, adds 1, writes the absolute value with no lock; the partial unique index on `(attribute_value, budget_id)` only serializes the insert branch, so one customer completing two carts concurrently exceeds a per-customer usage limit. | filed #16012 |

Common fix shape: replace the read-check-write with a single atomic guarded UPDATE
(`SET used = used + :amt WHERE ... AND used + :amt <= :limit`, 0 rows meaning exceeded),
or take a row lock (`FOR UPDATE`) around the guard and the write. For captures/refunds,
serialize per payment.

## Likely (real, but narrower than first stated)

- **ROU-1**, `payment/src/providers/payment-medusa/utils/get-smallest-unit.ts` ~52: the
  minor-unit conversion mixes `Math.round` on a double, a `Math.ceil`-to-nearest-10 for
  three-decimal currencies, and `parseInt` truncation, with no single documented rounding
  mode. The mode genuinely fires (amounts arrive at full precision; nothing rounds them
  upstream), and the ceil-to-10 vs half-up split can put the gateway a few mills off the
  stored capture for three-decimal currencies. Downgraded because the headline
  negative-amount asymmetry was unreachable (refunds pass positive amounts).
- **IDE-1**, `packages/medusa/src/subscribers/payment-webhook.ts` ~59: no provider
  event-id dedup before running the workflow, and the no-linked-cart path acquires no
  lock. Real, but a sequential full-capture redelivery converges on the `captured_at`
  guard, so double side effects need near-concurrent duplicate delivery or partial-capture
  events, narrower than "every redelivery double-charges".

## What the verifier killed (10), and why

The refutations are the point of this report as much as the confirmations: a tool that
reports its raw findings would have posted 10 wrong or overstated claims against a popular
project.

- **STO x4** (epsilon clamp, NUMERIC mirror, `parseInt`, default epsilon): all died on
  the currency data. Medusa's default currency table ships only 0-, 2-, and 3-decimal
  currencies, and the currency API is read-only, so the smallest legal amount is 0.001,
  ten times the 0.0001 epsilon; the clamp only ever zeroes sub-minor-unit float dust, and
  all arithmetic runs on the exact raw string, not the mirror.
- **API-1** (money as bare JSON number, epsilon clamp on the wire): same currency-data
  argument plus the bounded-magnitude carve-out. Commerce totals stay under 15 significant
  digits and round-trip binary64 exactly; the 20-digit internal precision is allocation
  headroom, not a wire contract anyone loses money on.
- **TAX-2** (`automatic_taxes` misread as tax-inclusive): the semantic mismatch is real
  but the fallback is dead code. `includeTaxes` has zero callers, the cart and order
  modules have no `region` relation (only a `region_id` text column), and ORM-loaded items
  always carry a NOT-NULL `is_tax_inclusive` that wins.
- **TAX-3** (tax rate stored as single-precision `REAL`): the `float -> REAL` mapping is
  real, but the full chain float32 -> PG12+ shortest-round-trip text -> `parseFloat` ->
  BigNumber reproduces the exact decimal for every realistic rate (verified for 0.21,
  8.25, 9.975, 8.0625, 13.9125; corruption needs 7+ significant digits). Killed by the
  shortest-decimal false-positive note.
- **ROU** `math.ts` `decimalPlaces` with no mode: single caller, result used only in
  guard comparisons and never stored, bignumber.js's default is a documented deterministic
  half-up, and the auditor's dp=0 claim was mechanically wrong.
- **AGG x2** (binary64 collapse in order summaries): mechanism real, but the drift is
  bounded to ~1 ulp; moving a minor unit needs totals above ~5e12 currency units, and the
  residual dust falls under the epsilon clamp before any money-moving comparison.

## Lessons

1. **A well-architected money core mostly holds, and the tool agreed.** Medusa's exact
   BigNumber-over-raw-string design defeated every storage, serialization, and rounding
   attack; 10 of 16 findings died, most on the same two facts (bounded currency
   precision, exact-raw-string source of truth). The value was not a pile of findings, it
   was surviving the false ones.
2. **The bugs were concurrency, again.** As in field report 1, the confirmed cluster is
   check-then-act races on money counters, exactly what types and decimal discipline
   cannot prevent and what a linter cannot see. The rulebook's semantic rules earn their
   keep here.
3. **A same-day rule change paid off same-day.** The shortest-decimal false-positive note
   added to STO/API/TAX this session is precisely what refuted the `REAL` tax-rate finding
   with a mechanical proof instead of a hand-wave.

Findings are rule-based and adversarially verified, but not human-verified. Read the cited
rule before acting; every rule documents its false positives. Next step for the confirmed
findings is a manual verification pass against the source at the pinned commit, then polite
upstream issues, one per finding, each carrying the rule citation and a concrete failing
interleaving.
