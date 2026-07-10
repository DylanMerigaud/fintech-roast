# Taxes

Part of the [fintech-roast](../README.md) rulebook. See [README.md](README.md) for the format contract and severity scale.

## TAX-1: Tax rounded at the wrong or inconsistent level (per line vs per document)

**Severity**: high

**What to detect**

- A tax total computed by summing already-rounded per-line tax amounts in one place, and by rounding the tax on a summed subtotal in another (e.g. the invoice PDF renderer rounds each line but the payment or ledger path rounds the total), so the two disagree by a cent on multi-line documents.
- SQL or ORM aggregates like SUM(ROUND(line_qty*unit_price*rate, 2)) used as the invoice tax, with no single documented rounding policy, or a per-line ROUND(...) column that is later re-summed AND separately re-derived from a total.
- Rounding inside a per-line loop (round(line.net * rate) accumulated) with no configuration flag choosing line-level vs document-level, so the level is accidental rather than a decision.
- A rounding helper called at both line granularity and total granularity on the same tax with different inputs (round(sum(x)) vs sum(round(x))), especially across service boundaries (invoicing service vs tax service vs accounting export).
- Python: `sum(round(line.net * rate, 2) for line in lines)` (per-line rounding then summed) in one path while another does `round(sum(l.net for l in lines) * rate, 2)` (round the document total), or a `.quantize(Decimal("0.01"))` inside the per-line comprehension with no flag choosing the level.
- Storing only a rounded per-line tax and reconstructing the document tax from it (or vice versa) instead of persisting both the chosen level's authoritative figure and the method used.
- Multi-jurisdiction tax where lines with different rates are summed into one pre-rounded pool, ignoring that the permitted level may be per-rate or per-jurisdiction.

**Why it breaks**

round(sum(line_tax)) and sum(round(line_tax)) are not equal on multi-line invoices; the gap is typically one minor unit but recurs on every affected document and surfaces as an invoice total that does not tie out to the ledger, the payment, or the tax return. The permitted level is jurisdiction dependent, so a single hardcoded method can be non-compliant somewhere you operate. UK HMRC's round-down-to-a-whole-penny concession is set in the context of invoice traders, where the rounding is tax neutral because it hits both the supplier's output tax and the customer's input tax (VATREC12010), and HMRC states as a general rule that this concession is not appropriate for retailers, who must round arithmetically or carry extra precision (VATREC12020). Australia's ATO defines two accepted methods on multi-supply invoices, the total invoice rule (round the total GST) and the taxable supply rule (round each supply then sum), which can produce different totals. The bug is not that rounding happens, it is that the level is inconsistent between code paths or wrong for the jurisdiction.

**Fix**

Pick one rounding level per tax rate and per jurisdiction, make it an explicit configured policy (not an accident of loop placement), and apply the exact same function on every path that reports that document's tax (PDF, API, ledger, tax export). Compute tax on integer minor units and persist both the per-line figures and the authoritative document-level figure so downstream systems reconcile to the same number instead of re-deriving it. Where the jurisdiction permits a choice (Stripe exposes an explicit line-item-level vs invoice-level setting for manual rates; the ATO allows the total-invoice vs taxable-supply rules), expose the choice and record which method produced the stored total.

```
tax = roundTax(amount_minor_units, rate, level)   // one helper, every path
assert sum(line_tax_minor) == document_tax_minor  // reconcile under the declared level
```

```python
# Python: one helper, the level is an explicit argument, every path calls it the same way.
from decimal import Decimal, ROUND_HALF_UP

def invoice_tax(lines, rate: Decimal, level: str) -> Decimal:
    cent = Decimal("0.01")
    if level == "line":       # round each line, then sum the rounded parts
        return sum(((l.net * rate).quantize(cent, rounding=ROUND_HALF_UP) for l in lines),
                   start=Decimal("0"))
    if level == "document":   # sum the nets, round the document total once
        subtotal = sum((l.net for l in lines), start=Decimal("0"))
        return (subtotal * rate).quantize(cent, rounding=ROUND_HALF_UP)
    raise ValueError(level)
```

```java
// Java: one helper, the level is an explicit argument, every path (PDF, API, ledger) calls it.
BigDecimal invoiceTax(List<Line> lines, BigDecimal rate, Level level) {
    if (level == Level.LINE)          // round each line, then sum the rounded parts
        return lines.stream()
            .map(l -> l.net().multiply(rate).setScale(2, RoundingMode.HALF_UP))
            .reduce(BigDecimal.ZERO, BigDecimal::add);
    BigDecimal subtotal = lines.stream().map(Line::net).reduce(BigDecimal.ZERO, BigDecimal::add);
    return subtotal.multiply(rate).setScale(2, RoundingMode.HALF_UP);   // document: round the total once
}
```

**False positives**

- A deliberately configured, single-source rounding policy where line-level rounding is the intended and jurisdiction-permitted method and every reporting path calls the same rounded values (e.g. a country that requires per-line rounding); consistency, not the level, is what matters.
- Single-line documents, where per-line and per-document rounding are identical by construction, so SUM(ROUND(...)) is harmless.
- Systems that intentionally over-precision intermediate tax (e.g. the ATO or HMRC option of at least 5 or 6 digits before a final round) and round only once at the final display step; extra precision before a single final rounding is correct, not a bug.

**Sources**

1. [VATREC12010: Rounding on invoices and rounding at retailers, the rounding concession](https://www.gov.uk/hmrc-internal-manuals/vat-trader-records/vatrec12010) (HM Revenue and Customs)
2. [VATREC12020: Rounding on invoices and rounding at retailers, rounding at retailers](https://www.gov.uk/hmrc-internal-manuals/vat-trader-records/vatrec12020) (HM Revenue and Customs)
3. [Tax invoices (GST rounding: total invoice rule vs taxable supply rule)](https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst/tax-invoices) (Australian Taxation Office)
4. [Set up your tax rates (line-item level vs invoice level rounding)](https://docs.stripe.com/billing/taxes/tax-rates) (Stripe)
5. [Java SE 21 java.math.BigDecimal (setScale, RoundingMode)](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/math/BigDecimal.html) (Oracle)

## TAX-2: Tax-inclusive vs tax-exclusive confusion

**Severity**: high

**What to detect**

- Adding tax to a price that already includes it (gross * rate) or extracting tax from a net price, i.e. the code path does not check a tax_behavior or inclusive flag before choosing add-on vs back-out math.
- Back-calculating the net from a gross with the wrong divisor: net = gross - gross*rate (subtracting the rate off the gross) instead of net = gross / (1 + rate), or tax = gross*rate instead of tax = gross - gross/(1+rate).
- A price stored without an inclusive or exclusive marker (a bare amount column with no tax_behavior, inclusive boolean, or price_includes_tax field), so the same number is treated as net in one path and gross in another.
- Displaying an inclusive price to the buyer while the charge or settlement path treats the same figure as exclusive and adds tax on top (or the reverse), changing what the customer actually pays.
- Rounding the back-calculated tax and the back-calculated net independently so that net + tax != gross, breaking the invariant that an inclusive line must reconcile to the displayed gross.
- Python: `net = gross - gross * rate` (wrong back-out) instead of `net = gross / (1 + rate)`, or rounding both pieces separately (`net = round(gross / (1 + rate), 2); tax = round(gross * rate / (1 + rate), 2)`) so `net + tax != gross`; a bare amount with no `tax_behavior`/`inclusive` field guiding which branch runs.
- Mixing per-region behavior in one code path (US sales tax is exclusive, EU VAT and many GST regimes are commonly inclusive for B2C) without branching on the jurisdiction's expected behavior.

**Why it breaks**

Exclusive tax is added on top of the listed price, so the final price the buyer pays changes; inclusive tax is already in the listed price, so the amount the buyer pays stays constant and the pre-tax unit price is the lower, tax-excluded figure back-calculated as net = gross / (1 + rate), per Stripe's tax-behavior docs. Confuse the two and you either overcharge the customer (added tax to a gross price) or under-remit to the authority (treated a net price as gross). The back-calculation also has to round consistently: if tax and net are each rounded in isolation the inclusive line no longer sums to the price shown, which fails audit and touches fiscal neutrality, the concern examined in the Advocate General's Opinion in J D Wetherspoon (C-302/07), where systematic rounding that lets a trader retain a fraction of the VAT due is measured against the principles of fiscal neutrality and proportionality. Because a price's behavior is often fixed once set (Stripe forbids changing tax_behavior after creation), a wrong default silently corrupts every downstream amount.

**Fix**

Store tax behavior explicitly next to every price (an inclusive boolean or a tax_behavior enum), and branch on it: exclusive means tax = round(net * rate) and total = net + tax; inclusive means net = round(gross / (1 + rate)) and tax = gross - net so the pieces always re-sum to the displayed gross. Never subtract rate*gross to get net. Do the arithmetic on integer minor units with a decimal or basis-point rate, and derive the second component from the first (net then tax, or gross then net) rather than rounding both independently, so net + tax == gross by construction. Keep display and settlement on the same behavior for a given line, and pick the jurisdiction-appropriate default (US sales tax exclusive, EU VAT and B2C GST usually inclusive) rather than a global constant.

```python
# Python: branch on the stored behavior; derive the second piece so net + tax == gross.
from decimal import Decimal, ROUND_HALF_UP
cent = Decimal("0.01")

def split(amount: Decimal, rate: Decimal, inclusive: bool):
    if inclusive:
        net = (amount / (1 + rate)).quantize(cent, rounding=ROUND_HALF_UP)
        tax = amount - net            # derived, so net + tax == gross exactly
    else:
        tax = (amount * rate).quantize(cent, rounding=ROUND_HALF_UP)
        net = amount                  # exclusive: total = net + tax
    return net, tax
```

```java
// Java: branch on the stored behavior; derive the second piece so net + tax == gross.
BigDecimal[] split(BigDecimal amount, BigDecimal rate, boolean inclusive) {
    if (inclusive) {
        BigDecimal net = amount.divide(BigDecimal.ONE.add(rate), 2, RoundingMode.HALF_UP);
        return new BigDecimal[]{net, amount.subtract(net)};   // tax derived: net + tax == gross exactly
    }
    BigDecimal tax = amount.multiply(rate).setScale(2, RoundingMode.HALF_UP);
    return new BigDecimal[]{amount, tax};                     // exclusive: total = net + tax
}
```

**False positives**

- A price legitimately annotated as tax-inclusive being back-calculated with gross / (1 + rate); this is the correct method for inclusive pricing, not a bug, provided net and tax re-sum to the gross.
- Systems that intentionally support both behaviors and switch on a stored flag; two code branches (add-on vs back-out) are expected and correct when driven by the price's declared behavior.
- B2C storefronts in VAT or GST jurisdictions that display an inclusive price but expose the extracted tax on the receipt for compliance; showing both the gross and its embedded tax is a legal display requirement, not double counting.

**Sources**

1. [Specify tax behavior (inclusive vs exclusive)](https://docs.stripe.com/tax/products-prices-tax-codes-tax-behavior) (Stripe)
2. [Set up your tax rates (the inclusive flag on a tax rate)](https://docs.stripe.com/billing/taxes/tax-rates) (Stripe)
3. [Opinion of the Advocate General, J D Wetherspoon plc v HMRC, Case C-302/07](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A62007CC0302) (Court of Justice of the European Union)
4. [Java SE 21 java.math.BigDecimal (divide, setScale)](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/math/BigDecimal.html) (Oracle)

## TAX-3: Tax rates held as binary floats or applied with imprecise percentage arithmetic

**Severity**: high

**What to detect**

- A tax or VAT rate declared as a float, double, or REAL literal (rate = 0.1, vatRate float = 0.2, a DECIMAL rate read into a double) rather than an exact decimal or an integer number of basis points.
- Tax computed with binary floating-point multiply then rounded, e.g. round(amount * 0.0825, 2) in Python, JS, or Java where amount and rate are floats, so the intermediate is already off (0.1 and 0.0825 are not exactly representable in binary).
- Constructing a decimal from a float: new BigDecimal(0.1) in Java, Decimal(0.1) in Python, decimal.Parse on a double-derived value, i.e. seeding the exact type with an already-inexact binary value instead of a string or basis-point literal.
- SQL money math done in FLOAT or DOUBLE PRECISION columns, or a rate stored as NUMERIC but multiplied after an implicit cast to double.
- Equality or reconciliation tests on floating-point money (if (tax == expected) or asserting a running total hits zero) that intermittently fail because binary rounding error accumulates.
- Percentage handled as rate/100 in float (amount * pct / 100.0) where pct came in as a float, compounding representation error.

**Why it breaks**

Tax rates are exact decimal quantities but common values like 0.1 (10%) and 0.0825 (8.25%) have no exact binary representation: 0.1 has an infinite repeating binary expansion and lies strictly between two floating-point numbers, exactly representable by neither (Goldberg, ACM Computing Surveys 1991). So amount * rate in a double is computed on a value that is not the rate you wrote, and the error shows up after rounding on adversarial amounts and accumulates across many lines, the same lose-pennies-to-rounding-errors failure Fowler flags for the Money pattern. Seeding an exact type from a float propagates the error rather than fixing it: new BigDecimal(0.1) equals 0.1000000000000000055... and Decimal.from_float(0.1) equals 0.1000000000000000055..., which is why the Java and Python docs tell you to build from strings, not doubles. The result is wrong tax by a minor unit in edge cases and equality invariants that fail nondeterministically.

**Fix**

Represent rates as exact decimals or integer basis points (825 for 8.25%) and do the arithmetic in a decimal type or in integer minor units, never in float or double. In Python use decimal.Decimal built from a string or int (Decimal('0.0825'), not Decimal(0.0825)); in Java use BigDecimal via the String constructor (new BigDecimal("0.1"), never new BigDecimal(0.1)); in SQL use NUMERIC or DECIMAL columns and keep money out of FLOAT and DOUBLE. A robust pattern is tax_minor = round(amount_minor * bps, half-even) / 10000 with all inputs integers and a single explicit rounding mode, so the computation is exact up to the one intended rounding step. Never test money for equality on floats; compare exact decimals or integers.

```python
# Python: rate as integer basis points, amount as integer minor units, one explicit rounding.
from decimal import Decimal, ROUND_HALF_UP

BPS = 825                     # 8.25%, exact integer, not the float 0.0825
amount_minor = 19999          # 199.99 as integer cents
tax_minor = int((Decimal(amount_minor) * BPS / Decimal(10000)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP))     # 1650 cents
# if you keep a Decimal rate, build it from a string, never from a float:
rate = Decimal("0.0825")      # not Decimal(0.0825), which is 0.082500000000000004...
```

```java
// Java: rate as integer basis points, amount as long minor units, one explicit rounding.
long BPS = 825;               // 8.25%, exact integer, not the double 0.0825
long amountMinor = 19999;     // 199.99 as integer cents
long taxMinor = BigDecimal.valueOf(amountMinor).multiply(BigDecimal.valueOf(BPS))
    .divide(BigDecimal.valueOf(10000), 0, RoundingMode.HALF_UP).longValueExact();   // 1650 cents
// if you keep a BigDecimal rate, build it from a String, never new BigDecimal(0.0825) (STO-7).
BigDecimal rate = new BigDecimal("0.0825");
```

**False positives**

- A float used only for transient display or a non-authoritative estimate (a UI preview) where the persisted or charged figure is recomputed in decimal or integer minor units; floats in throwaway presentation code are not a money-safety defect.
- A DECIMAL or NUMERIC rate column, or a basis-points integer, that merely passes through a variable typed to hold it losslessly (e.g. a language decimal type), even if the surrounding API names look float-ish; the test is whether an inexact binary value ever enters the money math.
- Statistical or analytics aggregates (effective-tax-rate reporting, dashboards) that are explicitly approximate and never drive a charge, remittance, or ledger entry.

**Sources**

1. [What Every Computer Scientist Should Know About Floating-Point Arithmetic](https://docs.oracle.com/cd/E19957-01/806-3568/ncg_goldberg.html) (David Goldberg, ACM Computing Surveys, reprinted by Oracle)
2. [decimal, Decimal fixed-point and floating-point arithmetic](https://docs.python.org/3/library/decimal.html) (Python Software Foundation)
3. [Class BigDecimal, Java SE 21 API](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/math/BigDecimal.html) (Oracle)
4. [Money, Patterns of Enterprise Application Architecture](https://martinfowler.com/eaaCatalog/money.html) (Martin Fowler)
