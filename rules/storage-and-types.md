# Storage and types

Part of the [fintech-roast](../README.md) rulebook. See [README.md](README.md) for the format contract and severity scale.

## STO-1: Money stored as binary float or double

**Severity**: critical

**What to detect**

- SQL columns typed FLOAT, DOUBLE, DOUBLE PRECISION, or REAL on money-ish names (amount, price, total, balance, fee, tax, subtotal, cost, rate), or a Postgres value cast to `money` from a float.
- Language float/double holding money: Java/C#/Go/Kotlin `double` or `float` fields, a TypeScript/JS `number` used as an amount (JS numbers are IEEE-754 doubles), `float()` on a currency value in Python.
- ORM mappings that pick a float type for a money field: Hibernate `double`, SQLAlchemy `Float`, Sequelize `FLOAT`/`DOUBLE`, GORM `float64`.
- Money arithmetic that relies on `==` equality, or that computes `price * qty * rate` in floating point before rounding.
- JSON/protobuf schemas declaring an amount as `number`/`double` rather than a string decimal or an integer minor unit.
- Comments or code "fixing" drift with epsilon comparisons (`abs(a-b) < 0.001`) on monetary values.

**Why it breaks**

IEEE-754 binary floating point represents values in base 2, so common decimal fractions have no exact representation and are stored as approximations. Goldberg shows 0.1 in binary is the repeating `1.10011001100110011001101 x 2^-4`, exactly representable by no float. These sub-cent errors accumulate across many operations, and they depend on operation order, so ledgers stop balancing and totals disagree by a cent. Modern Treasury shows a $15.25 base taxed two valid ways yielding 16.77 vs 16.78. On production money paths this is corrupted or lost money, not a rounding nicety.

**Fix**

Store and compute money in an exact type: a fixed-scale decimal (SQL NUMERIC/DECIMAL, Java BigDecimal, Python `decimal.Decimal`, C# `decimal`, Ruby BigDecimal) or an integer number of minor units. PostgreSQL explicitly recommends `numeric` "for storing monetary amounts and other quantities where exactness is required" and says `real`/`double precision` are inexact. Never use a language float/double or SQL FLOAT/REAL/DOUBLE for amounts, and avoid the PostgreSQL `money` type (it is locale-bound, see STO-4). In JavaScript, where every number is a double, keep amounts as integer minor units or a decimal library, never a bare `Number`.

**False positives**

- Non-monetary quantities that are inherently approximate and used for analytics or ranking (ML scores, geolocation, physics/statistics, latency percentiles), even if the column name looks numeric.
- FX/interest rates and multipliers deliberately held as high-precision floats or decimals for intermediate calculation, then applied and rounded to an exact money type before persistence (the stored amount is exact, the rate is a scientific quantity).
- A float used only for a transient display estimate or a chart axis that is never persisted or used to move money.
- An external API that returns amounts as JSON numbers, where the value is parsed into an exact type immediately at the boundary.

**Sources**

1. [What Every Computer Scientist Should Know About Floating-Point Arithmetic](https://docs.oracle.com/cd/E19957-01/806-3568/ncg_goldberg.html) (David Goldberg, ACM Computing Surveys, Oracle mirror)
2. [PostgreSQL Documentation: Numeric Types](https://www.postgresql.org/docs/current/datatype-numeric.html) (PostgreSQL Global Development Group)
3. [Floats Don't Work For Storing Cents](https://www.moderntreasury.com/journal/floats-dont-work-for-storing-cents) (Modern Treasury)

## STO-2: DECIMAL/NUMERIC declared with wrong precision or scale

**Severity**: high

**What to detect**

- Scale smaller than the currency exponent: `DECIMAL(_, 0)` for a two-decimal currency, or `DECIMAL(_, 2)` for three-decimal currencies (BHD, KWD, OMR) or for sub-cent unit prices.
- Precision too small for accumulators: `DECIMAL(6,2)` or `DECIMAL(9,2)` on a column that sums many rows (line items, running balance, GMV, batch totals) and can overflow.
- Intermediate computations (unit price * quantity, per-unit tax, interest accrual, per-share) truncated to 2 decimals before final rounding, when they need extra guard digits.
- Java BigDecimal / Python Decimal values persisted or divided without an explicit scale and RoundingMode, so the scale is implementation-dependent.
- Mismatched scales across a join or a math expression (a 2-decimal column multiplied by a 4-decimal rate written back into a 2-decimal column).
- Crypto/high-precision assets stored at `DECIMAL(_,2)` instead of the asset's real precision (8 or 18 decimals).

**Why it breaks**

NUMERIC/DECIMAL is exact only within its declared precision (total significant digits) and scale (fractional digits). PostgreSQL defines a `NUMERIC(3,1)` column as rounding values to 1 decimal place, and MySQL caps precision at 65 with scale in 0 to 30 and no larger than the precision. If scale is smaller than the currency minor-unit exponent or than an intermediate step needs, the database silently rounds or truncates every stored value; if precision is too small, a large sum overflows or errors. The Vancouver Stock Exchange index truncated (not rounded) to three decimals on each recalculation about 3000 times a day and drifted from a true 1098.892 down to 524.811 over 22 months. Under-scaled intermediates and under-sized accumulators produce systematically wrong amounts at realistic volumes.

**Fix**

Choose scale from the currency ISO 4217 minor unit (2 for USD/EUR, 0 for JPY, 3 for BHD/KWD) and add guard digits for intermediate math where unit prices, per-share values, tax, or interest need sub-minor precision. A common pattern is a wider working type (for example NUMERIC(19,4) or (23,8)) for computation, rounded to the currency scale only at the final persisted amount. Size precision for the largest accumulator the column will ever hold, not a single transaction. In BigDecimal/Decimal code set scale and RoundingMode explicitly on every division and before persistence rather than relying on defaults (BigDecimal division of a non-terminating quotient throws ArithmeticException when no rounding mode is given). Document the chosen (precision, scale) and the rounding rule next to the column.

**False positives**

- A deliberately wide working/intermediate type (NUMERIC(19,4), (30,15)) rounded down to the currency scale only at the final stored amount is correct, not a bug.
- A reporting or rollup column intentionally holding a coarser scale, where the fine-grained exact values live elsewhere.
- Storing a rate, index, or unit price at more decimals than the currency exponent (required, not wrong), as long as money outputs are rounded correctly.
- A column scale that exceeds the currency exponent (DECIMAL(_,4) for USD) purely to keep guard digits, when a documented rounding step to 2 decimals runs before money leaves the system.

**Sources**

1. [PostgreSQL Documentation: Numeric Types](https://www.postgresql.org/docs/current/datatype-numeric.html) (PostgreSQL Global Development Group)
2. [MySQL 8.4 Reference Manual: DECIMAL Data Type Characteristics](https://dev.mysql.com/doc/refman/8.4/en/precision-math-decimal-characteristics.html) (Oracle, MySQL)
3. [Java SE 21 java.math.BigDecimal](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/math/BigDecimal.html) (Oracle)
4. [Vancouver Stock Exchange](https://en.wikipedia.org/wiki/Vancouver_Stock_Exchange) (Wikipedia)

## STO-3: Integer minor units without an explicit, enforced unit convention

**Severity**: high

**What to detect**

- Bare `*100` and `/100` (or `*1000`, `/1e2`) scattered across the code to convert an amount, with no shared helper and no unit named in the type.
- Integer amount fields named amount/price/total with no suffix or comment stating the unit (cents vs dollars vs minor units).
- The same value passed between modules where one treats it as whole currency and another as minor units (API returns cents, UI divides by 100 in one place but not another).
- Mixed conventions in one codebase: some tables store cents (1999), others store decimal dollars (19.99), then joined or summed together.
- Hardcoded `/100` that assumes 2 decimals, breaking zero- and three-decimal currencies (see STO-5).
- Money passed as a raw int64/number across a service or JSON boundary with no accompanying scale/exponent field.

**Why it breaks**

Storing money as an integer number of minor units is a sound technique (TigerBeetle uses 128-bit integers; Modern Treasury stores $12.34 as 1234), but the integer alone does not say which unit it is in. The convention has to be remembered by every layer that touches the value. When one module reads 1999 as dollars, or a helper multiplies by 100 a value already in cents, amounts are wrong by 100x on a production path. Mixed units across modules make the error intermittent and hard to trace. TigerBeetle further warns the asset scale is fixed per ledger and cannot be changed later without migrating to a new ledger, so an ambiguous or wrong scale is expensive to fix after data exists.

**Fix**

Encode the unit in the type, not in scattered arithmetic. Use a Money value object or a branded/newtype that carries the amount and its scale (Fowler's Money pattern), so a raw integer can never be mistaken for a different unit, and centralize the two conversion points (parse at input, format at output) in one module.

```ts
// unit lives in the type, not in call sites
type Cents = number & { readonly __brand: 'Cents' };
const toCents = (major: number): Cents => Math.round(major * 100) as Cents;
```

```python
# Python has no branded types; a NewType gives a distinct "cents" type the checker enforces
from typing import NewType
from decimal import Decimal
Cents = NewType("Cents", int)
def to_cents(major: Decimal) -> Cents: return Cents(int((major * 100).to_integral_value()))
```

Pick one convention per system, document it, and pin the asset scale per ledger/currency (TigerBeetle: map the smallest useful unit to 1, and treat that scale as immutable). Across service and JSON boundaries, send amount plus currency plus minor-unit exponent together rather than a naked integer. Prefer a decimal type when the app does not clearly benefit from integer minor units.

**False positives**

- A well-encapsulated Money type or library (dinero.js, Joda-Money, py-moneyed) whose internal integer minor-unit representation is never exposed as a bare number, with conversions confined to the boundary.
- A single documented conversion helper (toMinorUnits/fromMinorUnits) driven by the currency exponent, even though it multiplies by a power of ten internally.
- A payment-gateway boundary where `*100` or `*1000` is the gateway's documented required format (Stripe/Adyen minor units) and is applied once at the edge.
- A ledger where the asset scale is a first-class stored field per account/ledger, so every read knows the unit.

**Sources**

1. [TigerBeetle Docs: Data Modeling](https://docs.tigerbeetle.com/coding/data-modeling/) (TigerBeetle)
2. [Floats Don't Work For Storing Cents](https://www.moderntreasury.com/journal/floats-dont-work-for-storing-cents) (Modern Treasury)
3. [Money (Patterns of Enterprise Application Architecture)](https://martinfowler.com/eaaCatalog/money.html) (Martin Fowler)

## STO-4: Amounts stored or passed around without their currency

**Severity**: high

**What to detect**

- SQL amount/price/total/balance columns with no adjacent currency column (no currency_code / currency_id / iso_currency).
- Money passed as a single scalar (int/decimal) through function signatures, DTOs, events, or JSON with no currency field alongside it.
- Currency inferred from context: a global default, the user's locale, or a "we only do USD" assumption baked into logic instead of stored per row.
- Summing or comparing amounts from different rows/tables without checking they share a currency.
- The PostgreSQL `money` type used as the currency-bearing solution (it is not; its format comes from the `lc_monetary` locale, not per value).
- Multi-currency features (FX, international payouts, marketplaces) built on single-currency amount columns.

**Why it breaks**

An amount is meaningless without its currency: 100 is a different obligation in USD, JPY, and BHD. Fowler's Money pattern exists because money is an amount plus a currency and should be one type; a bare number lets you add dollars to yen without a conversion. When currency is assumed from context, the first multi-currency requirement (a new market, an FX payout, a foreign card) silently mixes currencies. The PostgreSQL `money` type does not solve this: per the PostgreSQL wiki it stores no currency with the value and assumes the `lc_monetary` locale, so a value inserted as `$10.00` can read back as `10,00 Lei` or another format if the locale changes. This is direct compliance and financial exposure once more than one currency exists.

**Fix**

Store currency with every amount: a currency_code column (ISO 4217 alpha code) next to each amount, or a Money value object that carries amount plus currency as one unit (Fowler). Make cross-currency arithmetic explicit and refuse to add or compare amounts in different currencies without a conversion step. Do not rely on the PostgreSQL `money` type for multi-currency; use `numeric` plus a currency column. Even in a single-currency system today, storing the currency costs almost nothing and prevents a painful migration when the second currency arrives.

**False positives**

- A closed single-currency system where the currency is a hard, enforced invariant recorded once at the account/tenant/ledger level (not re-derived from ambient locale) and every amount inherits it.
- A narrow internal calculation or private helper operating within one already-established currency context, where the currency is carried by the enclosing aggregate.
- Denormalized reporting tables where currency lives on the parent row and child amount rows are always read joined to it.
- A column that stores a pure count or non-monetary quantity that happens to look money-like.

**Sources**

1. [Money (Patterns of Enterprise Application Architecture)](https://martinfowler.com/eaaCatalog/money.html) (Martin Fowler)
2. [Don't Do This: the money type](https://wiki.postgresql.org/wiki/Don%27t_Do_This) (PostgreSQL Wiki)

## STO-5: Hardcoded two-decimal assumption

**Severity**: high

**What to detect**

- Hardcoded 100 as the minor-unit divisor/multiplier for every currency (`amount/100`, `cents = dollars*100`) with no per-currency exponent lookup.
- `toFixed(2)`, `round(x, 2)`, `Math.round(x*100)/100`, or a number format with 2 fixed decimals applied to all money regardless of currency.
- Validation or DB scale that assumes exactly 2 fractional digits for all amounts (DECIMAL(_,2) everywhere, see STO-2).
- Sending amounts to a payment API in the wrong scale: 1000 for JPY (would mean 1000 yen, not 10) or 1000 for BHD instead of the required 3-decimal minor units.
- No mapping anywhere from currency code to its ISO 4217 minor-unit exponent.
- For three-decimal currencies, ignoring gateway constraints that the smallest supported charge unit may be coarser than the raw minor unit.

**Why it breaks**

ISO 4217 assigns each currency a minor-unit exponent that is not always 2: 0 for JPY, KRW, and others (no minor unit), 2 for most, and 3 for BHD, IQD, JOD, KWD, LYD, OMR, TND (1000 minor units per major). A hardcoded `*100` or `toFixed(2)` therefore over- or under-scales real currencies. Payment APIs enforce this: Stripe takes zero-decimal amounts directly (charge 500 JPY by sending amount 500, no multiply), Adyen requires BHD 10 to be sent as 10000 minor units because BHD has three decimals, and PayPal returns an error for any decimal amount on HUF, JPY, or TWD. Getting the exponent wrong means charging 100x or one-tenth the intended amount, or a hard API error, on live payment paths.

**Fix**

Drive scaling from a currency-to-minor-unit-exponent table (ISO 4217, maintained by SIX Group on behalf of ISO), not a hardcoded 100. Look up the exponent per currency to convert between major and minor units, to set validation and DB scale, and before formatting for display or for a gateway. Honor each processor's stated rules: Stripe zero-decimal currencies take the amount as-is, Adyen wants three-decimal amounts in 1000-based minor units, PayPal forbids decimals on JPY/HUF/TWD. Standard libraries (Intl.NumberFormat, ICU, `java.util.Currency.getDefaultFractionDigits`, py-moneyed) already carry these exponents; use them instead of a literal.

**False positives**

- A system contractually restricted to a fixed set of two-decimal currencies (USD and EUR only) where the 2 is a documented, guarded invariant rather than an accidental assumption.
- A locale/formatting library (Intl.NumberFormat, ICU, java.util.Currency) that internally applies 2 for those currencies because it looks up the correct exponent per currency.
- A pure display rounding to 2 decimals for a currency that genuinely has exponent 2, where storage and gateway calls use the currency's real exponent.
- Test fixtures or examples that hardcode 2 decimals for a specific two-decimal currency under test.

**Sources**

1. [ISO 4217](https://en.wikipedia.org/wiki/ISO_4217) (Wikipedia, standard maintained by SIX Group on behalf of ISO)
2. [Stripe Documentation: Currencies (zero-decimal)](https://docs.stripe.com/currencies) (Stripe)
3. [Adyen: Currency codes and minor units](https://docs.adyen.com/development-resources/currency-codes) (Adyen)
4. [PayPal REST API: Currency codes](https://developer.paypal.com/api/rest/reference/currency-codes/) (PayPal)

## STO-6: Amounts that outgrow the numeric type

**Severity**: high

**What to detect**

- Money held as a JavaScript/TypeScript `Number` in integer minor units, where large totals (aggregate balances, high-value or high-volume sums) can exceed `Number.MAX_SAFE_INTEGER` (9007199254740991).
- 32-bit integer columns/fields (INT, int32, Go int32, Java int) storing prices or amounts, especially in minor units or with 4 implied decimals (INT max 2147483647).
- Accumulators (SUM over many rows, running totals, GMV, batch settlement) narrower than the sum they can reach, even if each row fits.
- Fixed-width wire/price formats (price * 10000 packed into a 4-byte field) without a documented ceiling.
- Arithmetic that widens then narrows: `a * b` computed in a 32-bit type before assignment, silently overflowing the intermediate.
- JSON amounts round-tripped through a JS number without BigInt or a string, losing precision above 2^53.
- Python `int` is arbitrary precision so the amount never overflows in memory, which hides the risk: it resurfaces at the boundary, a wide value written to a 32/64-bit DB column, or serialized to JSON and read back by a JavaScript consumer above 2^53.

**Why it breaks**

Every numeric type has a ceiling, and money in minor units reaches it faster than the major-unit value suggests. JavaScript numbers are IEEE-754 doubles, so integers above `Number.MAX_SAFE_INTEGER` (2^53 - 1 = 9007199254740991) can no longer be represented or compared exactly; MDN shows `MAX_SAFE_INTEGER + 1 === MAX_SAFE_INTEGER + 2` evaluating to true. A signed 32-bit integer maxes at 2147483647, which in cents is only about 21.4 million dollars, and in a 4-decimal price field far less. Nasdaq's price feed hit this in May 2021 when Berkshire Hathaway Class A neared $429,496.7295, the maximum of a 32-bit field storing price times 10000; Nasdaq halted the feed and moved to 64-bit price messages. Overflow silently wraps or saturates, corrupting the amount on a production path.

**Fix**

Size the type for the largest total the system can ever reach in minor units, including accumulators, not just per-transaction values. Use 64-bit integers or exact decimals (BIGINT, int64, Java long/BigDecimal, Python `int` which is unbounded), and in JavaScript use BigInt or a decimal library and keep large amounts out of Number (and out of JSON numbers, serialize as strings or BigInt). Prefer arbitrary-precision integers (TigerBeetle uses 128-bit) for ledgers that must never overflow. Audit widening/narrowing in arithmetic so an intermediate product does not overflow a 32-bit temporary. Treat the ceiling as a design decision and document the headroom.

**False positives**

- A 32-bit or Number-typed amount with a hard, enforced business ceiling well below the limit (a per-item retail price capped far under 2.1M), where overflow is impossible by validation.
- Values already held as arbitrary-precision types (Python int, Java BigInteger/BigDecimal, DECIMAL of adequate precision) that cannot overflow at realistic scale.
- JavaScript amounts kept as BigInt or a decimal-library instance rather than Number, so the 2^53 boundary does not apply.
- A per-line amount that provably fits, where the aggregate is computed in a wider type (a 32-bit row column is fine if sums use 64-bit/decimal).

**Sources**

1. [MDN: Number.MAX_SAFE_INTEGER](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Number/MAX_SAFE_INTEGER) (MDN Web Docs, Mozilla)
2. [TigerBeetle Docs: Data Modeling](https://docs.tigerbeetle.com/coding/data-modeling/) (TigerBeetle)
3. [Nasdaq halts Berkshire Hathaway price feed over 32-bit limit](https://www.theregister.com/2021/05/07/bug_warren_buffett_rollover_nasdaq/) (The Register)

## STO-7: Exact-decimal money constructed from a binary float

**Severity**: critical

**What to detect**

- Python: `Decimal(0.1)`, `Decimal(amount)` where `amount` is a `float`, or `Decimal.from_float(...)` on a money value, instead of `Decimal("0.1")` or `Decimal(str(amount))`.
- A float literal or a float variable passed into a decimal constructor anywhere on a money path, so the value is already wrong before any arithmetic or rounding runs.
- Parsing an amount with `float(...)` first and only wrapping it in `Decimal` afterward (precision is lost at the `float()` call; the `Decimal` just freezes the error).
- A helper that accepts a `float` amount and returns a `Decimal`, which looks safe at the call site but launders a lossy value into an exact-looking one.

**Why it breaks**

An exact-decimal type only helps if it is fed an exact value. A binary float cannot represent most decimal fractions, so constructing a decimal directly from a float copies the float's error into the decimal verbatim: Python's `Decimal(0.1)` is `0.1000000000000000055511151231257827021181583404541015625`, not `0.1`, because `0.1` stopped being `0.1` the moment it became a `float`. The decimal then carries that noise into every downstream sum, rounding, and comparison, and because it is now a "precise" type the error looks authoritative and survives review. The same trap exists in any language where an exact type has a float constructor. Keeping money out of `float` entirely, and building the decimal from a string, is the only reliable fix.

**Fix**

Construct decimals from strings, never from floats. Parse external input straight into `Decimal("...")`, and forbid `float` anywhere on the money path so a float can never reach the constructor. Use `Decimal(str(x))` only when the source is already a correct decimal string or an integer. If a value genuinely arrives as a float from a legacy boundary, fix that boundary; a later `Decimal(...)` cannot recover the lost digits.

```python
from decimal import Decimal
Decimal("0.1")        # 0.1 exactly
Decimal(0.1)          # 0.1000000000000000055... (the float's error, preserved)
Decimal(1999)         # exact: an integer is fine (minor units)
```

**False positives**

- `Decimal(str(x))` or `Decimal(x)` where `x` is known to be a clean decimal string or an integer, and the conversion is deliberate and documented.
- Non-money quantities (a scientific measurement, a ratio, a weight) where the float origin is acceptable and the value never becomes an amount.
- A test that intentionally builds `Decimal(0.1)` to demonstrate the very trap this rule describes.
- A value coming from a decimal-typed database column via a driver that already returns `Decimal`, where no `float` is involved despite a `Decimal(...)` call nearby.

**Sources**

1. [decimal, Decimal fixed-point and floating-point arithmetic](https://docs.python.org/3/library/decimal.html) (Python Software Foundation)
2. [What Every Computer Scientist Should Know About Floating-Point Arithmetic](https://docs.oracle.com/cd/E19957-01/806-3568/ncg_goldberg.html) (David Goldberg, Oracle mirror of ACM Computing Surveys 1991)
