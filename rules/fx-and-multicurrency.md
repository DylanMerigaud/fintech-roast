# FX and multi-currency

Part of the [fintech-roast](../README.md) rulebook. See [README.md](README.md) for the format contract and severity scale.

## FX-1: Currency conversion round-trips assumed lossless

**Severity**: high

**What to detect**

- A convert() helper used symmetrically, e.g. `convert(convert(amount, 'USD', 'EUR'), 'EUR', 'USD')`, or a test asserting the two are equal (`assertEqual(x, backToX)`).
- Reverse conversion computed as `amount / rate` or `amount * (1/rate)` instead of fetching an independent inverse or opposite-pair quote: look for `1 / rate`, `1.0/rate`, `reciprocal`, `invert(rate)` used to settle or book a value (not just to display).
- Cross-currency conversion done in one multiply (from -> to) with no intermediate base leg, especially between two non-USD currencies (EUR->GBP as a single stored rate), where a same-time round-trip is then expected to reconcile to the cent.
- Rounding applied on every leg (`round`, `.quantize(`, `toFixed(2)`, `Math.round(x*100)/100`, `ROUND_HALF_UP`) inside a function called twice for a there-and-back conversion, with the two ends compared for equality.
- Equality or invariant checks on money that survive a conversion cycle: `if (recomputedTotal == originalTotal)`, or a reconciliation that expects converted balances to net to exactly zero after a round-trip.
- Storing a single mid rate and reusing it for both directions of the same trade (buy leg and sell leg use the identical number) when the two legs settle real money.

**Why it breaks**

Each conversion leg rounds to the target currency's minor unit, so the operation is not invertible: A -> B -> A generally returns a value one or more minor units away from the start, and the error compounds across many transactions (Python's own docs note that rounding differences accumulate and prevent reliable equality testing, which is why decimal is preferred in accounting). The market inverse is not the arithmetic reciprocal either: real quotes carry a bid/ask spread and are sourced independently per pair, so `1/rate(USD,EUR)` does not equal `rate(EUR,USD)` even before rounding (Xignite's example: USDEUR 1.3050 inverts arithmetically to 0.7763, but the quoted EURUSD comes from market makers separately and is only guaranteed to be close, not equal). The EU learned this in the fixed-rate case: for conversions between euro legacy national currencies specifically, Regulation 1103/97 forbids inverse rates and mandates triangulation through the euro precisely because dividing by a rate accumulates rounding inaccuracy (Art. 4(3)-(4)). That regulation governs only the euro legacy currencies, not live USD/EUR/GBP FX, but the underlying arithmetic hazard is the same. Assuming losslessness makes reconciliations fail to balance and lets tiny residuals leak repeatedly.

**Fix**

Treat conversion as one-way and lossy. Never derive the reverse leg by dividing; fetch an independent inverse or opposite-pair rate for the return trip, and expect A -> B -> A to differ from A. Round exactly once, at the boundary to the currency's minor unit, and keep full precision internally; store the pre-rounded high-precision result if you need to reconcile. For cross-currency pairs that share no direct quote, convert through a base currency (triangulate) rather than compounding a single blended rate. In reconciliation, compare against the originally stored source amounts (see FX-3), not against a value you recomputed by reversing the conversion, and allow a documented minor-unit tolerance for residuals.

**False positives**

- A UI display estimate that converts for preview only and never persists or settles the converted number (informational, not a booked amount) can round per view without harm.
- Fixed-rate legacy conversions where the rate is defined as exact by statute and the algorithm is mandated (the euro legacy currencies under Regulation 1103/97): there the mandated triangulation with defined per-leg rounding is the correct, reproducible procedure, so a `round` per leg is required, not a bug.
- High-precision internal accumulators that only round at the final settlement or display boundary and keep the unrounded intermediate are already doing the right thing even though a `round` call appears in the path.
- A deliberate reciprocal used purely to show an indicative inverse quote to a user, clearly labeled as approximate and never used to settle money.

**Sources**

1. [Council Regulation (EC) No 1103/97 on certain provisions relating to the introduction of the euro](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A31997R1103) (EUR-Lex, Official Journal of the European Union)
2. [Why does the inverse of USDEUR not equal to EURUSD (or any 2 currency pairs)?](https://website.xignite.com/faqs/cryptocurrency-and-fx-rates/why-does-the-inverse-of-usdeur-not-equal-to-eurusd-or-any-2-currency-pairs/) (Xignite)
3. [decimal, Decimal fixed-point and floating-point arithmetic](https://docs.python.org/3/library/decimal.html) (Python Software Foundation)

## FX-2: Exchange rate applied without capturing rate value, source and timestamp

**Severity**: high

**What to detect**

- Conversion at read or report time using a live lookup: `getRate(from,to) * amount` inside a serializer, invoice renderer, or dashboard query, with no rate column persisted on the row.
- A converted amount column with no adjacent rate columns: schema has `amount_usd` but lacks `fx_rate`, `fx_rate_source`, and `fx_rate_timestamp` (or `rate_date`).
- Rate fetched from a provider (ECB, openexchangerates, a bank API, `rates[to]`) and used immediately without storing the returned value and the as-of time.
- Historical figures recomputed with today's rate: reports that call the same convert() over past transactions, or a nightly job that re-values old rows using the current rate table.
- A single mutable `rates` config or table overwritten in place (`UPDATE fx_rates SET rate = ...`) so past conversions can no longer be reproduced.
- Absence of a point-in-time rate record: no `ExchangeRate` / `fx_quote` entity carrying (base, quote, rate, provider, valid_at), as JSR 354 models it.

**Why it breaks**

An FX rate is only meaningful together with when it was observed and where it came from. Reference rates are explicitly point-in-time and provider-specific: the ECB publishes euro reference rates once per working day around 16:00 CET and states they are for information only and discouraged for transactions, so "the rate" silently means a different number tomorrow. If you store only the converted output and re-derive conversions later with a current rate, historical amounts change retroactively, invoices stop reproducing, and audits cannot be reconstructed. Accounting standards pin the rate to the event: IAS 21 records a foreign-currency transaction at the spot rate at the date of the transaction, which is impossible to honor if the date and rate were never captured. Purpose-built APIs make the rate a first-class stored fact for exactly this reason: Stripe's BalanceTransaction persists `exchange_rate` alongside `amount`, `currency` and a `created` timestamp, and JSR 354's CurrencyConversion is bound to a specific provider, target currency and optional timestamp.

**Fix**

Persist the conversion as an immutable fact at the moment it happens: store the rate value used, the provider or source identifier, and the as-of timestamp (or rate date) next to the amounts, and never recompute historical conversions from a live rate. Model rates as append-only, point-in-time records (base, quote, rate, source, valid_at) rather than a mutable current-rate cell, mirroring JSR 354's ExchangeRate (which carries provider and validity) and Stripe's stored `exchange_rate` plus `created`. Reports and re-renders read the captured rate off the row; only new events look up a fresh rate. This makes every conversion reproducible and auditable and satisfies IAS 21's rate-at-transaction-date requirement.

**False positives**

- Live pre-trade or shopping-cart quotes that are indicative only and are re-quoted (and re-captured) at the moment of booking: capturing the rate at display time is unnecessary as long as it is captured at settlement.
- Single-currency systems, or internal analytics that intentionally restate everything at one chosen reporting rate (a constant-currency view) where the restatement rate and date are themselves documented.
- A cache of the latest rate for performance, as long as the rate actually used for each booked conversion is copied onto the record; the cache is not the system of record.
- Ledgers that store the rate in transaction metadata rather than a dedicated column (for example Modern Treasury records the FX rate in metadata) still satisfy the rule; the signal is missing capture, not a specific column name.

**Sources**

1. [CurrencyConversion (JSR 354 Money and Currency API)](https://javamoney.github.io/apidocs/java.money/javax/money/convert/CurrencyConversion.html) (JavaMoney, JSR 354)
2. [ExchangeRate (JSR 354 Money and Currency API)](https://javamoney.github.io/apidocs/java.money/javax/money/convert/ExchangeRate.html) (JavaMoney, JSR 354)
3. [The Balance Transaction object (exchange_rate, created)](https://docs.stripe.com/api/balance_transactions/object?lang=node) (Stripe)
4. [Euro foreign exchange reference rates](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html) (European Central Bank)
5. [IAS 21 The Effects of Changes in Foreign Exchange Rates (explained)](https://www.cpdbox.com/ias21-foreign-exchange-rates/) (CPDbox, IFRS training reference)

## FX-3: Only the converted amount stored, original amount and currency lost

**Severity**: high

**What to detect**

- A row holds only a reporting-currency figure: `amount_usd DECIMAL` (or a bare `amount` in a single house currency) with no `original_amount` / `original_currency` / `source_currency` columns.
- Ingestion that converts on write and discards the input: `row.amount = convert(payload.amount, payload.currency, BASE)` then only `row.amount` is persisted; the payload currency and amount are dropped.
- A `currency` column that is constant (always 'USD') across a table that clearly handles foreign payments, indicating conversion happened before storage.
- Re-conversion performed from the stored converted value back to a foreign currency for display or refund (converted -> foreign), stacking a second rounding on an already-rounded number instead of using the retained original.
- Refund, chargeback, or reversal logic that recomputes the original charge amount via FX instead of reading a stored original amount.
- Reconciliation or tax exports that cannot produce the transaction currency because it was never stored (only the functional-currency amount survives).

**Why it breaks**

Conversion is lossy and one-way, so once you keep only the converted number you cannot re-derive the original: the source amount and currency are gone, and any later reconversion rounds a value that was already rounded, compounding the error each hop. It also destroys auditability: you can no longer show what the customer was actually charged or invoiced, which is the transaction currency. Standards and payment platforms keep both sides for this reason. IAS 21 distinguishes monetary items (re-translated at the closing rate every period) from non-monetary historical-cost items (kept at the transaction-date rate), and you cannot apply either treatment correctly without the original foreign amount on hand. Stripe's model likewise retains the presentment amount and currency in addition to the settled amount and the `exchange_rate`, so the original is always recoverable.

**Fix**

Store money as (amount, currency) in the transaction's own currency as the source of truth, and treat any converted or reporting figure as a derived, additional column, never a replacement. Persist `original_amount` plus `original_currency` alongside `converted_amount`, `converted_currency`, and the rate and timestamp (FX-2), so every conversion is reproducible and reversible without recomputing. For refunds, reversals, and re-display, read the stored original rather than reconverting a converted value. This is the shape used by Stripe (presentment amount and currency plus settled amount and `exchange_rate`) and by ledger systems that require each entry to carry its own currency (Modern Treasury: a ledger account is denominated in one ISO 4217 currency and amounts are recorded in that currency's smallest unit).

**False positives**

- Genuinely single-currency products where every transaction is natively in the house currency and no conversion ever occurs: there is no original to lose.
- Derived reporting or analytics tables that intentionally hold only a constant-currency figure, provided the untouched original (amount and currency) lives in the upstream system of record they are built from.
- Fixed-rate legacy redenominations where the source currency is permanently retired and the fixed statutory rate is documented (the euro legacy currencies), so the original is reconstructible from the converted value and the fixed rate.
- Systems that store one amount but also store the currency code per row (so the value is unambiguous) and never convert away from it, which do not lose information even though there is a single amount column.

**Sources**

1. [The Balance Transaction object (amount, currency, exchange_rate)](https://docs.stripe.com/api/balance_transactions/object?lang=node) (Stripe)
2. [IAS 21 The Effects of Changes in Foreign Exchange Rates (explained)](https://www.cpdbox.com/ias21-foreign-exchange-rates/) (CPDbox, IFRS training reference)
3. [Ledger Currencies](https://docs.moderntreasury.com/ledgers/docs/currencies) (Modern Treasury)

## FX-4: Arithmetic mixing amounts of different currencies

**Severity**: critical

**What to detect**

- Money represented as a bare number so cross-currency addition compiles silently: `totalUsd += order.amount` where `order.amount` may be another currency; `sum(amount)` in SQL over rows with different `currency` values.
- Aggregations grouped by anything but currency: `SELECT SUM(amount) FROM payments` with no `GROUP BY currency`, or a portfolio total that adds all rows regardless of currency.
- Comparisons or branches on raw amounts across currencies: `if (invoice.amount > threshold)` or `Math.max(a.amount, b.amount)` where a and b differ in currency.
- A Money/Amount type whose add, subtract, or compareTo does not assert equal currency, or code that reaches into `.amount` / `.value` and does math outside the type's guard.
- Concatenation of amounts from mixed-currency collections into one accumulator, wallet balance, or cart total without a per-currency bucket.
- Absence of a currency-mismatch guard analogous to JSR 354 (MonetaryException on unequal currency) or of per-currency balancing (debits must equal credits within each currency).

**Why it breaks**

With primitive numeric types, adding USD to EUR type-checks and runs, producing a meaningless figure that looks valid and flows into totals, thresholds, and payouts: corrupted money on a production path. There is no automatic conversion: 10 USD plus 10 EUR is not 20 of anything, and minor-unit scale differs too (a zero-decimal currency like JPY is not cents, so even the integer magnitudes are incomparable, per Stripe's smallest-unit rules and ISO 4217 minor units). The canonical defense is the Money value object: Fowler notes the whole point is to avoid adding dollars to yen without accounting for currency, and JSR 354 makes it a hard error, throwing MonetaryException on a currency mismatch for comparison and arithmetic operations. Ledger designs enforce the same invariant structurally by requiring debits to equal credits within each currency, so cross-currency amounts can never net against each other.

**Fix**

Represent money as a Money type that carries amount plus ISO 4217 currency and forbids cross-currency arithmetic: add, subtract, and compare must throw on unequal currency (JSR 354 raises MonetaryException; enforce the same in TypeScript, Go, or Ruby via a guarded value object). Mixing currencies must be an explicit conversion step (with a captured rate and timestamp, FX-2), never an implicit `+`. Aggregate per currency: keep separate totals or `GROUP BY currency`, and in ledgers require debits to equal credits within each currency (the Modern Treasury guarantee) rather than summing across. Include the minor-unit exponent in the type so zero-decimal currencies are not silently treated as cents.

**False positives**

- Adding two amounts already proven to share a currency (line items on a single-currency invoice), where a currency check would pass anyway and no conversion is implied.
- Multiplying or dividing a Money by a dimensionless scalar (quantity, tax rate, percentage, allocation weight) is legitimate; only Money plus Money across currencies is the defect.
- A deliberate constant-currency roll-up where every row was first converted to one reporting currency (FX-2 and FX-3 satisfied), so the summed amounts are genuinely same-currency by construction.
- Comparing counts or ratios derived from amounts (number of transactions, a same-currency ratio) rather than the currency-bearing magnitudes themselves.

**Sources**

1. [Money (Patterns of Enterprise Application Architecture)](https://martinfowler.com/eaaCatalog/money.html) (Martin Fowler)
2. [MonetaryAmount (JSR 354 Money and Currency API)](https://javamoney.github.io/apidocs/java.money/javax/money/MonetaryAmount.html) (JavaMoney, JSR 354)
3. [Use Multiple Currencies (ledger per-currency balancing)](https://docs.moderntreasury.com/docs/working-with-multiple-currencies) (Modern Treasury)
4. [Supported currencies (zero-decimal and smallest-unit rules)](https://docs.stripe.com/currencies) (Stripe)
5. [ISO 4217 currency codes (official maintenance agency)](https://www.six-group.com/en/products-services/financial-information/data-standards.html) (SIX, ISO 4217 Maintenance Agency)
