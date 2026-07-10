# Rounding and allocation

Part of the [fintech-roast](../README.md) rulebook. See [README.md](README.md) for the format contract and severity scale.

## ROU-1: No explicit rounding mode on money operations

**Severity**: high

**What to detect**

- JavaScript/TypeScript: `.toFixed(` used to produce a currency string or reparsed with `Number(x.toFixed(2))`, or `Math.round(x * 100) / 100` for cents.
- Python: bare `round(x, 2)` on a float used for money, or a `Decimal.quantize(Decimal('0.01'))` call with no explicit `rounding=` argument (it silently inherits the context default, ROUND_HALF_EVEN). Even a dev who knows `round()` is banker's gets bitten by the float repr: `round(2.675, 2)` returns `2.67`, not `2.68`, because `2.675` is stored as the binary value `2.67499999...`, so it rounds down before any tie-breaking rule applies.
- Java: `BigDecimal.setScale(2)` or `divide(...)` with no `RoundingMode` argument (a non-terminating divide then throws `ArithmeticException` at runtime), or `RoundingMode.HALF_UP` in one module and `HALF_EVEN` in another.
- C#: `Math.Round(x, 2)` or `decimal.Round(x, 2)` with no `MidpointRounding` overload (it defaults to banker's ToEven, which surprises devs who expect half-up).
- Ruby: `x.round(2)` on a `Float` for money instead of `BigDecimal`. Go: `math.Round` / `math.Floor` on a float64 amount instead of integer minor units.
- Any codebase where two different rounding helpers coexist (a util that rounds half-up and another path that uses a language default), i.e. no single documented money-rounding policy.

**Why it breaks**

Rounding-to-nearest is ambiguous at the exact half, and every language picks a different default. Python's built-in `round()` and .NET's `Math.Round` / `decimal.Round` default to round-half-to-even (banker's rounding), Java `BigDecimal.divide` with `RoundingMode.UNNECESSARY` (or a plain non-terminating divide) throws `ArithmeticException` rather than guessing, and JavaScript `toFixed` rounds in a direction that depends on the binary float representation of the input (MDN shows `(2.35).toFixed(1)` gives `2.4` while `(2.55).toFixed(1)` gives `2.5`). When a money value is rounded implicitly, the result depends on the language, the operation, and even the exact binary value, so the same conceptual calculation returns different cents in different parts of a system. Over many transactions the mismatches surface as reconciliation breaks, invoice-vs-ledger disagreements, and, where a regulator mandates a specific mode, direct compliance exposure.

**Fix**

Pick one rounding policy per money context, name it explicitly at every call site, and centralize it. Use a decimal type, never binary float, for the value being rounded (Python `decimal`, Java `BigDecimal`, C# `decimal`, Ruby `BigDecimal`, integer minor units in Go/JS). Pass the mode every time, and choose it from the requirement rather than the default: many tax and payment rules want half-up (round half away from zero), while accounting close processes often standardize on half-even to reduce cumulative bias. Whichever you pick, apply it consistently and document why.

```python
# Python: build the Decimal from a string (never from the float 2.675),
# then quantize with an explicit mode.
from decimal import Decimal, ROUND_HALF_UP
amount = Decimal("2.675")                                   # exact, unlike float 2.675
cents = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)  # Decimal("2.68")
```

```
bd.setScale(2, RoundingMode.HALF_UP)                              // Java
Math.Round(x, 2, MidpointRounding.AwayFromZero)                   // C#
```

**False positives**

- A deliberate house policy that documents banker's rounding (half-even) and uses the language default on purpose, e.g. Python `decimal` code that intentionally relies on the context's ROUND_HALF_EVEN and asserts the context at startup.
- Rounding for display or formatting only, where the rounded string is never fed back into a stored balance or a downstream calculation (the authoritative amount stays full-precision).
- Non-monetary quantities (progress bars, analytics percentages, UI layout) where a fraction of a unit has no financial meaning.
- Java code that intentionally omits the mode (or passes `RoundingMode.UNNECESSARY`) to force an `ArithmeticException` when a division is not exact, using it as a guard that the operation must be representable.

**Sources**

1. [RoundingMode (Java SE 21 API)](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/math/RoundingMode.html) (Oracle)
2. [MidpointRounding Enum (System)](https://learn.microsoft.com/en-us/dotnet/api/system.midpointrounding) (Microsoft)
3. [Number.prototype.toFixed()](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Number/toFixed) (MDN Web Docs)
4. [Built-in Functions: round()](https://docs.python.org/3/library/functions.html) (Python Software Foundation)
5. [decimal, Decimal fixed-point and floating-point arithmetic](https://docs.python.org/3/library/decimal.html) (Python Software Foundation)

## ROU-2: Pro-rata allocation that loses or creates cents

**Severity**: critical

**What to detect**

- A total split by looping over shares and independently rounding each share, e.g. `share = round(total * weight[i] / sum_weights, 2)` inside a loop, with no reconciliation of the residual afterward.
- A percentage or ratio split where each part is computed as `total * pct` and rounded, then the parts are stored without asserting `sum(parts) == total`.
- SQL that distributes an amount with `ROUND(amount * ratio, 2)` per row (e.g. `UPDATE ... SET line_amount = ROUND(header_total * weight, 2)`) with no final adjustment row.
- Splitting a charge N ways as `round(total / N, 2)` for every party (bill splitting, tax proration, refund apportionment, cost allocation, dividend or interest distribution).
- Python: a list/dict comprehension that rounds each share, e.g. `[round(total * w, 2) for w in weights]` or `[(total / n).quantize(Decimal("0.01")) for _ in range(n)]`, whose result is stored without asserting `sum(parts) == total`; a `Decimal` split that floors or quantizes each part and never redistributes the residual.
- Absence of a known allocation primitive: no call to a Money `allocate` / `split` helper, no "largest remainder", "Hamilton", "Hare quota", or "distribute remainder" logic anywhere near the split.
- A comment or ticket mentioning off-by-one-cent, "penny rounding", or a plug or adjustment line that silently absorbs a discrepancy.

**Why it breaks**

When you round each proportional share independently, the rounded parts almost never add back to the original total. The canonical example (Foemmel's Conundrum, from Fowler's Patterns of Enterprise Application Architecture) is splitting 5 cents 70/30: the exact shares are 3.5 and 1.5 cents, and no fixed per-part rounding rule makes them sum back to 5 (round-half-up gives 4 and 2, which is 6, so a cent is conjured). Depending on the direction of rounding you either lose cents (the splits sum to less than the total, so money vanishes) or create cents (they sum to more), and on a production ledger that is a hard integrity violation that fails reconciliation and, at scale, misstates balances. Because it is data-dependent it passes casual testing and only shows up on specific amounts and ratios. Betterment's engineering write-up shows the same failure in production: a naive proportional split of $1,234.56 yields impossible amounts like $382.7136.

**Fix**

Treat allocation as a single operation with the invariant sum-of-splits == total, not as N independent roundings. Use the largest-remainder (Hamilton) method: work in integer minor units, give each bucket the floor of its exact share, compute how many minor units remain (total minus the sum of floors), then hand those leftover units out one at a time to the buckets with the largest fractional remainders (or round-robin for an equal split). This guarantees the parts sum exactly to the whole and keeps each part within one minor unit of its ideal share. Prefer a vetted Money `allocate(ratios...)` / `split(n)` primitive (Fowler's Money pattern, implemented by libraries such as go-money) rather than re-deriving it. For equal splits, `split(3)` of 100p yields 34/33/33, not 33/33/33, and Betterment's largest-remainder split of $1,234.56 lands on $382.71 + $432.10 + $246.91 + $172.84, which sums exactly.

```python
# Python: largest-remainder allocation in integer minor units (cents).
def allocate(total_cents: int, weights: list[int]) -> list[int]:
    ws = sum(weights)
    floors = [total_cents * w // ws for w in weights]           # exact integer floor
    remainder = total_cents - sum(floors)                       # cents still to hand out
    # rank buckets by the size of the dropped fraction, largest first
    order = sorted(range(len(weights)),
                   key=lambda i: (total_cents * weights[i]) % ws,
                   reverse=True)
    for i in order[:remainder]:
        floors[i] += 1
    return floors                                               # sum(floors) == total_cents by construction

parts = allocate(5, [70, 30])                                   # [4, 1] on the 5c 70/30 split, sums to 5
```

```java
// Java: same largest-remainder allocation in integer minor units (cents).
static long[] allocate(long totalCents, int[] weights) {
    long ws = 0; for (int w : weights) ws += w;
    long[] parts = new long[weights.length];
    long allocated = 0;
    for (int i = 0; i < weights.length; i++) { parts[i] = totalCents * weights[i] / ws; allocated += parts[i]; }
    long remainder = totalCents - allocated;                     // cents still to hand out
    Integer[] order = new Integer[weights.length];
    for (int i = 0; i < order.length; i++) order[i] = i;         // rank by dropped fraction, largest first
    java.util.Arrays.sort(order, (a, b) -> Long.compare((totalCents * weights[b]) % ws, (totalCents * weights[a]) % ws));
    for (int k = 0; k < remainder; k++) parts[order[k]]++;
    return parts;                                                // sum(parts) == totalCents by construction
}
// allocate(5, new int[]{70, 30}) -> [4, 1] on the 5c 70/30 split, sums to 5
```

**False positives**

- Allocation that already runs a remainder-distribution pass and asserts the parts equal the total (the pattern is present, just spread across a helper); verify before flagging.
- A deliberately unrounded or high-precision internal allocation where the residual is carried forward and only reconciled at a later authoritative step, so no cent is lost across the boundary.
- Splits where the last bucket is intentionally computed as `total - sum(other_parts)` (a valid, if less fair, single-adjustment technique that preserves the invariant).
- Non-settling estimates or forecasts (projected cost splits, dashboards) that never post to a ledger and carry no money-conservation requirement.

**Sources**

1. [Money (P of EAA Catalog)](https://martinfowler.com/eaaCatalog/money.html) (Martin Fowler)
2. [Largest remainder method](https://en.wikipedia.org/wiki/Largest_remainder_method) (Wikipedia)
3. [A Functional Approach to Penny-Precise Allocation](https://www.betterment.com/engineering/penny-precise-allocation-functions) (Betterment Engineering)
4. [go-money: Go implementation of Fowler's Money pattern](https://github.com/Rhymond/go-money) (Rhymond, open source)

## ROU-3: Discounts, fees and percentages applied in inconsistent order with intermediate rounding

**Severity**: high

**What to detect**

- A discount and a tax both applied to a base amount where each intermediate result is rounded, e.g. `net = round(price * (1 - discount), 2); total = round(net * (1 + vat), 2)`, so order and intermediate rounding are baked in without a stated policy.
- Percentage fees computed and rounded per component, then summed, versus summed then rounded once (mixed conventions across services or across the checkout vs the ledger).
- VAT or sales tax rounded per line item in one code path and rounded on the invoice total in another, with no reconciliation between them.
- Chained multipliers on money with a `round(...)` between every step (`round(round(a * r1, 2) * r2, 2)`), especially in pricing, billing, or payout code.
- Python: nested `round()` or `.quantize()` calls on floats, e.g. `round(round(price * (1 - discount), 2) * (1 + vat), 2)`, or a `Decimal` pipeline that calls `.quantize(Decimal("0.01"))` after every multiply instead of once at the end.
- SQL that applies `ROUND(price * discount_rate, 2)` and later `ROUND(... * tax_rate, 2)` in separate statements or views, so the order of rounding is implicit in query sequence.
- Absence of a documented pipeline defining the fixed order (discount, then fee, then tax) and where the single rounding step happens.

**Why it breaks**

Multiplication and rounding do not commute, so rounding between each step compounds error and the final amount depends on the order operations are applied. Discount-before-tax versus tax-before-discount, and per-line rounding versus per-invoice rounding, produce different totals on the same inputs; when the storefront uses one order and the accounting or tax system uses another, the invoice and the ledger disagree by cents. This is a compliance surface, not just an aesthetic one: tax authorities constrain both the method and the direction. In the UK, HMRC's VAT Notice 700 section 17.5 gives invoice traders a concession to round the total VAT payable down to a whole penny (tax-neutral because it hits both the supplier's output tax and the customer's input tax), while section 17.6 and the internal manual VATREC12020 tell retailers and line-level calculations that they must not simply round down, offering instead rounding each line to the nearest 1p, or calculating to at least 5 decimal places and rounding to 4, or truncating at no fewer than 6 decimals. Getting the order or the rounding point wrong systematically over- or under-charges tax.

**Fix**

Define one canonical calculation pipeline and apply it everywhere: fix the order (for example base, then discounts, then fees, then tax), carry full precision through the intermediate steps, and round once at the defined settlement boundary rather than after every multiply. Decide explicitly whether tax is computed per line item or per invoice total and use the same choice in checkout, invoicing, and the ledger so they reconcile by construction. Where a jurisdiction dictates the rule, encode that rule with its citation: under HMRC VAT Notice 700 the invoice-trader concession (section 17.5) lets you round total VAT down to a whole penny, while the retailer and line-level rules (section 17.6 / VATREC12020) require rounding each line to the nearest penny or keeping 5+ decimals and rounding to 4. Make the order and the single rounding point a tested property (assert the pipeline result matches the tax-authority worked example), not an accident of statement sequence.

```python
# Python: carry full Decimal precision through the pipeline, round ONCE at the boundary.
from decimal import Decimal, ROUND_HALF_UP

price    = Decimal("19.99")
discount = Decimal("0.15")   # 15%
vat      = Decimal("0.20")   # 20%

net   = price * (1 - discount)        # 16.9915, no intermediate rounding
gross = net * (1 + vat)               # 20.3898, still full precision
total = gross.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)  # single rounding: 20.39
```

```java
// Java: same pipeline in BigDecimal, no setScale between the multiplies, round ONCE at the end.
BigDecimal price    = new BigDecimal("19.99");
BigDecimal discount = new BigDecimal("0.15");
BigDecimal vat      = new BigDecimal("0.20");

BigDecimal net   = price.multiply(BigDecimal.ONE.subtract(discount));   // 16.9915, full precision
BigDecimal gross = net.multiply(BigDecimal.ONE.add(vat));               // 20.38980, full precision
BigDecimal total = gross.setScale(2, RoundingMode.HALF_UP);             // single rounding: 20.39
```

**False positives**

- A jurisdiction that explicitly mandates per-line rounding (so rounding each line before summing is correct, not a bug); the fix is to match the mandate, and per-line rounding there is a false positive.
- A documented, deliberately-ordered pipeline where the single rounding point is intentional and each step's precision is preserved (the pattern only looks chained).
- Rounding used only to render intermediate values in a UI breakdown, while the authoritative total is computed from full-precision values.
- Fixed-scale decimal arithmetic where the "intermediate rounding" is actually exact at that scale (no information is lost, e.g. integer-cent inputs multiplied by integer quantities).

**Sources**

1. [VATREC12010: Rounding on invoices and rounding at retailers, the rounding concession](https://www.gov.uk/hmrc-internal-manuals/vat-trader-records/vatrec12010) (HM Revenue and Customs)
2. [VATREC12020: Rounding on invoices and rounding at retailers, rounding at retailers](https://www.gov.uk/hmrc-internal-manuals/vat-trader-records/vatrec12020) (HM Revenue and Customs)
3. [Rounding rules for Stripe fees](https://support.stripe.com/questions/rounding-rules-for-stripe-fees) (Stripe)
4. [Manage products and prices (line-item rounding, unit_amount_decimal)](https://docs.stripe.com/products-prices/manage-prices) (Stripe)
5. [Java SE 21 java.math.BigDecimal (setScale, RoundingMode)](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/math/BigDecimal.html) (Oracle)

## ROU-4: Dividing before multiplying on money

**Severity**: high

**What to detect**

- A per-unit or per-share value divided out and then multiplied back up, e.g. `unit = total / count; result = round(unit, 2) * count` (round-then-scale), instead of computing the total and dividing once.
- Percentage-of-amount computed as `(rate / 100) * amount` on floats or fixed-scale where `rate / 100` loses precision before the multiply, rather than `amount * rate / 100`.
- Integer or fixed-point money arithmetic that divides first, e.g. `(amount / divisor) * quantity` in a language with integer-division truncation (SQL, Go, Java `int`/`long`, Python `//`).
- Iterative accumulation that feeds a truncated or rounded intermediate back into the next step (a running index or running balance recomputed from an already-rounded prior value).
- Python: round-then-scale on money, e.g. `unit = round(total / count, 2); result = unit * count`, `(rate / Decimal(100)) * amount` (pre-dividing the rate), or integer `total // count * count` where floor division drops cents before the multiply.
- Unit price times quantity where the unit price was pre-rounded to cents and then multiplied by a large quantity, amplifying the per-unit rounding error.
- SQL like `SUM(amount / n) * n` or `ROUND(x / y, 2) * z` where the division precedes the multiplication.

**Why it breaks**

Division is where precision is thrown away, so dividing first and multiplying later multiplies the discarded error back up. Goldberg's floating-point paper makes the point exactly: to compute a power with a negative exponent, `1/PositivePower(x, -n)` is more accurate than `PositivePower(1/x, -n)` because the first keeps x exact and commits a single final rounding, while the second multiplies n factors that each already carry the rounding error from `1/x`. The same logic governs money: `(total / count) * count` need not equal `total`, and a per-unit amount rounded to cents then multiplied by a large quantity drifts far from the true total. The Vancouver Stock Exchange index is the textbook production failure of carrying a truncated intermediate forward: [established at 1000.000 in 1982 and updated after every transaction, each update was truncated rather than rounded, and about 22 months later the index read roughly 520 while the correctly rounded value was near 1098.892](https://diamhomes.ewi.tudelft.nl/~kvuik/wi211/disasters.html), an error reported and corrected in November 1983.

**Fix**

Multiply first, divide last, and divide exactly once at the end. For unit-price shapes, compute `amount * quantity` in integer minor units and divide only when you must express a per-unit figure, keeping full precision until a single final rounding. For percentages, prefer `amount * rate / 100` (or `amount * numerator / denominator`) over pre-dividing the rate. Never feed a rounded or truncated intermediate back into an iterative calculation: keep a full-precision running value and round only for display or at settlement. Use a decimal type (or integer minor units) rather than binary float so the residual you carry is exact, and where an allocation must split evenly use the largest-remainder approach (see ROU-2) instead of a pre-divided per-unit amount. Stripe's own line-item math is the correct shape: with `unit_amount_decimal = 0.05` and quantity 30, it rounds after multiplying (0.05 * 30 = 1.5 rounds to 2 cents), not by pre-rounding the unit amount.

```python
# Python: multiply first, round once at the end (never round the per-unit figure first).
from decimal import Decimal, ROUND_HALF_UP

unit_price = Decimal("0.05")
quantity   = 30

line = (unit_price * quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)  # 1.50
# percentage: keep the rate whole, divide by 100 last, not before the multiply
tax  = (Decimal("199.99") * Decimal("825") / Decimal("10000")).quantize(
           Decimal("0.01"), rounding=ROUND_HALF_UP)                               # 8.25% of 199.99
```

```java
// Java: multiply first, divide/round once at the end (never pre-round the per-unit figure).
BigDecimal line = new BigDecimal("0.05").multiply(new BigDecimal(30))
        .setScale(2, RoundingMode.HALF_UP);                                    // 1.50
// percentage: keep the rate whole, divide by 10000 last with an explicit mode
BigDecimal tax = new BigDecimal("199.99").multiply(new BigDecimal("825"))
        .divide(new BigDecimal("10000"), 2, RoundingMode.HALF_UP);             // 8.25% of 199.99
```

**False positives**

- Exact division that cannot lose precision (the divisor evenly divides the amount, e.g. splitting an even number of cents by 2, or fixed-scale decimals where the quotient terminates within scale).
- A deliberately pre-divided unit price that is the stored authoritative value (the catalog price genuinely is the per-unit amount), where multiplying by quantity is the intended, correct calculation and no upstream total exists.
- High-precision decimal or rational arithmetic carried through the division with enough guard digits that the later multiply cannot amplify a meaningful error.
- Non-monetary or presentation-only ratios (per-item averages shown in a UI) that never post to a ledger and carry no money-conservation requirement.

**Sources**

1. [What Every Computer Scientist Should Know About Floating-Point Arithmetic](https://docs.oracle.com/cd/E19957-01/806-3568/ncg_goldberg.html) (David Goldberg, Oracle reprint of ACM Computing Surveys 1991)
2. [Disasters due to rounding error (Vancouver Stock Exchange)](https://diamhomes.ewi.tudelft.nl/~kvuik/wi211/disasters.html) (Kees Vuik, TU Delft)
3. [Manage products and prices (multiply-then-round)](https://docs.stripe.com/products-prices/manage-prices) (Stripe)
4. [Currencies (smallest currency unit, zero-decimal currencies)](https://docs.stripe.com/currencies) (Stripe)
5. [Java SE 21 java.math.BigDecimal (multiply, divide, setScale)](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/math/BigDecimal.html) (Oracle)
