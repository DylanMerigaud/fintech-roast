# Testing money code

Part of the [fintech-roast](../README.md) rulebook. See [README.md](README.md) for the format contract and severity scale.

## TST-1: Money invariants asserted only on hand-picked examples, never with property-based generators

**Severity**: medium

**What to detect**

- A money/allocation/currency-conversion module (functions named like split, allocate, distribute, prorate, convert, exchange, applyDiscount, computeTax) whose entire test file is a flat list of assertEqual / expect(...).toBe(...) on literal amounts, with no generator in sight.
- No property-based-testing dependency or import anywhere: no `import fc from 'fast-check'` / `fc.assert(fc.property(...))` (JS/TS), no `from hypothesis import given, strategies as st` / `@given(...)` (Python), no `net.jqwik` (Java), no `gopter` / `testing/quick` (Go), no `rantly` / `propcheck` (Ruby).
- A split or allocation function tested only for the exact-division case (splitting 100 by [1,1] into [50,50]) and never asserting the conservation invariant sum(parts) == total across arbitrary totals and ratios.
- Currency conversion tested one direction only (USD to EUR) with a single rate, no round-trip test, and no bound on the round-trip residual (e.g. abs(to_usd(to_eur(x)) - x) <= tolerance).
- A ledger/balance type with an implied invariant (balance never negative, debits == credits, running balance == sum of entries) that has no test generating random operation sequences and re-checking the invariant after each.
- A comment or docstring stating an invariant ("total is always preserved", "balance can never go below zero") with no executable test that generates inputs to try to violate it.

**Why it breaks**

Money code is defined by invariants that must hold for every input, not just the two or three a developer imagined: the parts of a split must sum back to the total, a currency round-trip must stay within a bounded residual, a balance must never silently go negative. Example-based tests only exercise the cases the author already thought of, and the fast-check docs note plainly that even seasoned developers can miss edge cases, which is the whole reason generators exist. The classic trap is allocation: Fowler's Money pattern warns that rounding to the smallest currency unit makes it easy to lose pennies, and splitting an amount by proportions produces fractional minor units, so a naive per-part round leaks or manufactures a cent and sum(parts) != total. A fixed 70/30-of-100 fixture divides evenly and never reveals it. This is a test blind spot rather than a live money bug on its own, but it is the blind spot through which the money bugs ship: property-based tests generate arbitrary totals and ratio vectors, assert the invariant directly, and shrink any counterexample to a minimal failing case.

**Fix**

Add a property-based suite alongside the examples. Generate arbitrary totals and split ratios and assert sum(allocate(total, ratios)) == total (a strict-equality assertion no lucky fixture can satisfy for a leaky allocator); generate amounts and assert conversion round-trips stay within a documented residual bound; generate random operation sequences against a ledger and re-assert balance non-negativity and debits == credits after each step. Feed the generators awkward values (zero ratios, single-element splits, very large totals) and pin any shrunk counterexample as a permanent regression test. Property tests complement the worked examples, they do not replace them.

```javascript
fc.assert(fc.property(fc.integer(), fc.array(fc.nat()), (total, ratios) => {
  const parts = allocate(total, ratios);
  return parts.reduce((a, b) => a + b, 0) === total;
}));
```

**False positives**

- A pure display/formatting helper (render a Money to a localized string) has no arithmetic invariant to violate, so example-based tests are appropriate and a missing generator is not a defect.
- The invariant is already enforced at a lower layer that IS property-tested (allocation lives in a vetted money library such as dinero.js or brick/money with its own suite) and the code under review only wires it up; duplicating generators is redundant.
- A thin adapter that delegates all arithmetic to a decimal or database money type and does no rounding or splitting of its own has nothing to generate against.
- Contract/golden tests pinned to an external system's exact outputs (a payment processor's reference amounts) are legitimately example-based, since the point is byte-for-byte agreement with that authority, not an internal algebraic property.
- A small or early-stage codebase whose example tests genuinely sample the real domain range is a reasonable deliberate choice; property tests are a strong enhancement to recommend, not proof of a defect.

**Sources**

1. [fast-check: Why property-based testing](https://fast-check.dev/docs/introduction/why-property-based/) (fast-check, Nicolas Dubien)
2. [Hypothesis documentation](https://hypothesis.readthedocs.io/en/latest/) (Hypothesis project)
3. [QuickCheck: an automatic testing tool for Haskell](https://www.cse.chalmers.se/~rjmh/QuickCheck/) (Koen Claessen and John Hughes, Chalmers)
4. [Money (Patterns of Enterprise Application Architecture)](https://martinfowler.com/eaaCatalog/money.html) (Martin Fowler)

## TST-2: Round-number fixtures (100.00, 10 percent) that cannot distinguish truncate from round from banker rounding

**Severity**: medium

**What to detect**

- Money fixtures where every amount is a clean round value (100.00, 1000, 50.00) and every rate is a clean fraction (10%, 0.5, 25%), so no computation ever produces a fractional minor unit to round.
- Rounding/tax/interest/discount tests whose expected values are all exact and identical under floor, round-half-up, and round-half-even, i.e. the test would still pass if the rounding mode were swapped.
- A `.toFixed(2)` / `round(x, 2)` / `Math.round` / `BigDecimal.setScale` / `decimal.quantize` call under test, exercised only with inputs that land exactly on a cent boundary (no .xx5 tie cases, no repeating decimals like 1/3).
- Percentage or split math tested only with divisors that divide the amount evenly (split 100 into 4, take 10% of 200) and never with amounts that do not (split 100 into 3, take 8.25% of 12.99).
- No test that pins the intended tie-breaking rule at all: no fixture at a half-cent boundary to lock round-half-even vs round-half-up.
- Interest/APR/VAT tests using headline percentages (5%, 20%) on headline principals, never realistic amounts (a 19.99 line at 8.375% sales tax).

**Why it breaks**

Truncation, round-half-up, and banker rounding (round-half-to-even) diverge only on inputs that fall between minor units, and clean fixtures like 10% of 100.00 never produce such an input, so all three strategies return the identical expected value and the test passes regardless of which one the code runs. That masks two real defects: a truncation-where-you-meant-rounding bug that under- or over-bills by a cent per line, and a mismatch between the code's tie-breaking rule and the one accounting or a downstream ERP expects. The two often disagree, and the platform default is not obvious: Python's built-in round() and its decimal module both default to round-half-to-even, not the round-half-up many developers assume. Round fixtures also hide the floating-point trap underneath: the Python docs show round(2.675, 2) returns 2.67 rather than 2.68, not because of the tie-breaking rule but because 2.675 has no exact binary representation, so an "obvious" expected value silently shifts once a non-round amount flows through a float. As a testing gap this is latent, not a live loss, but it leaves the rounding behavior of production money code entirely unverified while the suite reports green.

**Fix**

Replace round fixtures with awkward amounts and odd divisors that force a real rounding decision: split 100.00 three ways and assert the parts are [33.34, 33.33, 33.33] and sum to 100.00; take 8.375% of 19.99; compute 1/3 of a dollar. Add explicit tie-boundary cases (an input engineered to land on exactly .xx5 before rounding) and assert the specific mode you require, so a change from banker rounding to half-up fails loudly. Do the arithmetic in a decimal type with an explicit rounding mode rather than binary floats, and name the mode your accounting policy or jurisdiction mandates. Pair each rounding test with the conservation check from TST-1 so remainder distribution is verified, not just per-part rounding.

```python
from decimal import Decimal, ROUND_HALF_EVEN
tax = (Decimal("19.99") * Decimal("0.08375")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
assert tax == Decimal("1.67")  # swap the mode and this assertion changes
```

**False positives**

- A fixture is round because the real domain value is genuinely round (a flat 100.00 monthly plan price, a fee defined by contract as exactly 5.00); the value is a business constant, not a test smell, provided some OTHER test still exercises the rounding boundary.
- Integer-cents / minor-unit code that never divides (only adds and subtracts whole minor units) has no rounding step to distinguish, so round inputs are fine and there is nothing for truncation-vs-rounding to catch.
- A test whose explicit purpose is to assert exactness (that adding whole cents introduces no drift) legitimately uses clean values; the absence of a tie case is intentional.
- README or documentation example fixtures chosen for human readability, where a separate rigorous test file carries the awkward-amount cases.

**Sources**

1. [Python built-in functions: round()](https://docs.python.org/3/library/functions.html) (Python Software Foundation)
2. [Python decimal module](https://docs.python.org/3/library/decimal.html) (Python Software Foundation)
3. [Money (Patterns of Enterprise Application Architecture)](https://martinfowler.com/eaaCatalog/money.html) (Martin Fowler)
4. [What Every Computer Scientist Should Know About Floating-Point Arithmetic](https://docs.oracle.com/cd/E19957-01/806-3568/ncg_goldberg.html) (David Goldberg, ACM Computing Surveys 1991, Oracle mirror)

## TST-3: Test suite covers one happy currency and no boundary magnitudes, refunds, or negatives

**Severity**: medium

**What to detect**

- Every money test uses a two-decimal currency (USD/EUR/GBP) and the code hardcodes 2 decimal places (`.toFixed(2)`, `round(x, 2)`, `* 100`, `/ 100`, `setScale(2)`), with no test exercising a zero-decimal currency (JPY, KRW, VND) or a three-decimal currency (BHD, KWD, OMR, TND).
- A minor-unit conversion (`amount * 100`, `cents / 100`) applied uniformly regardless of currency, and no test asserting that JPY 500 is 500 minor units (not 50000) or that BHD 5 is 5000 minor units (not 500).
- No test with a negative amount, refund, chargeback, credit note, or reversal, despite the codebase having refund/credit/void paths.
- No boundary-magnitude test: nothing near zero (0, the smallest minor unit, 0.001 for a 3-decimal currency), nothing large enough to probe the numeric type's limits (values near Int32/Int64/Number.MAX_SAFE_INTEGER, or a NUMERIC/DECIMAL column's declared precision).
- Money stored or computed as a floating-point type (SQL FLOAT/REAL/DOUBLE, JS number) with tests only in the small-magnitude range where float error is invisible.
- A currency column or enum present in the schema but every fixture pins it to one value, so per-currency exponent, minimum-charge, and rounding differences are never exercised.

**Why it breaks**

Money behavior is not uniform across currencies or magnitudes, so a suite that only tests happy-path USD leaves the differences untested. Per ISO 4217, and per both Stripe and Adyen, the minor-unit exponent varies: zero-decimal currencies like JPY take the amount as-is (JPY 10 is 10 minor units), two-decimal currencies multiply by 100, and three-decimal currencies like BHD and KWD multiply by 1000 (BHD 10 is 10000 minor units), so a hardcoded * 100 silently overcharges JPY by 100x and undercharges BHD by 10x. Refund and reversal paths carry negative amounts with their own sign and rounding edge cases a positive-only suite never sees. Boundary magnitudes expose type limits and float drift: near zero a rounding rule can produce a spurious minor unit, and near the type ceiling an amount can overflow or lose precision, which is why boundary value analysis targets exactly the minimum and maximum of each partition, where the ISTQB syllabus notes developers are most likely to place the boundary wrong. One happy currency is a single equivalence-partition sample masquerading as coverage. The defect this misses is a real wrong amount in production, but the rule itself flags a coverage gap, so it is a latent risk until an off-USD or boundary input actually arrives.

**Fix**

Parameterize the money tests over a currency matrix, not a single currency: include at least one zero-decimal (JPY), one two-decimal (USD), and one three-decimal (BHD or KWD), and assert the correct minor-unit scaling for each rather than a hardcoded factor of 100. Drive the exponent from an ISO 4217 lookup so adding a currency does not silently reuse * 100. Add negative-amount cases for every refund/credit/reversal path and assert sign and rounding behavior there. Apply boundary value analysis to magnitude: test 0, the smallest minor unit, a value at the numeric type's or DECIMAL column's declared limit, and just beyond it to confirm the failure mode is rejection, not silent overflow or precision loss. Store money as integer minor units or a fixed-precision DECIMAL/NUMERIC, never binary float, so the large-magnitude tests stay exact.

**False positives**

- A product that is contractually single-currency (a domestic-only service billing exclusively in one currency, enforced at the type or schema level) legitimately tests only that currency; multi-currency fixtures would test unreachable code.
- A codebase that already abstracts the exponent through a vetted currency library (dinero.js, brick/money, java.util.Currency, Ruby Money gem) and only passes currency codes through may cover the matrix at the library boundary, so a per-call currency sweep can be redundant.
- A path with no refund/negative semantics by design (an append-only fee accrual reversed by a separate compensating entry rather than a negative amount) will not have negative-amount tests, and that is correct.
- Deliberately narrow unit tests that isolate one behavior (a formatter for a specific locale) alongside a separate broader integration suite that does exercise the currency and magnitude matrix.

**Sources**

1. [Stripe: Zero-decimal and special-case currencies](https://docs.stripe.com/currencies) (Stripe)
2. [Adyen: Currency codes and minor units](https://docs.adyen.com/development-resources/currency-codes) (Adyen)
3. [ISO 4217](https://en.wikipedia.org/wiki/ISO_4217) (Wikipedia, documenting the ISO 4217 standard)
4. [ISTQB Foundation Level Syllabus: Black-Box Test Techniques](https://astqb.org/4-2-black-box-test-techniques/) (ASTQB / ISTQB)
