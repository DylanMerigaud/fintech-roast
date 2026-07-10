# API and serialization

Part of the [fintech-roast](../README.md) rulebook. See [README.md](README.md) for the format contract and severity scale.

## API-1: Money serialized as a JSON number

**Severity**: critical

**What to detect**

- A money/amount/price/balance/total field emitted into JSON as a bare numeric literal (e.g. `"amount": 19.99` or `"balance": 90071992547409910`), not quoted and not an integer count of minor units.
- Server code that puts a float/double/BigDecimal straight into a JSON body: `json.Marshal(struct{Amount float64}...)` (Go), `JSON.stringify({amount: total})` where `total` is a JS number, Jackson serializing a `double`/`BigDecimal` money field without a to-string serializer.
- Python: a FastAPI/pydantic response model that types the amount `float` (`price: float`), or `json.dumps({"amount": 19.99})` of a float amount, both of which emit a bare JSON number. `json.dumps({"amount": Decimal("19.99")})` raises `TypeError: Object of type Decimal is not JSON serializable`, and the reflexive fix devs reach for (`float(amount)` or a `default=float` encoder) throws the precision away right at the boundary. On the read side `json.loads(body)` decodes every `19.99` into a Python `float` by default, so even a producer that sent an exact value lands it in binary64 unless the caller passes `parse_float=Decimal`.
- Client code parsing the amount back with a default JSON number reader (`JSON.parse` in JS, `encoding/json` into `float64`, `json.loads` into a Python float), so the value lands in an IEEE 754 double regardless of how the producer stored it.
- Integer money in minor units that can exceed 2^53-1 (9007199254740991): large aggregate balances, satoshi/wei-scale crypto amounts, high-precision or high-volume ledgers serialized as JSON numbers.
- OpenAPI/JSON Schema definitions typing a money field as `type: number` or `format: double`/`float` rather than `type: string` (or a documented integer minor-unit contract).

**Why it breaks**

RFC 8259 Section 6 permits any implementation-defined number precision, and states that interoperability is only guaranteed for integers in the range [-(2^53)+1, (2^53)-1], because most JSON parsers decode numbers into an IEEE 754 binary64 double. It even flags that a value like `1E400` signals the producer expects more magnitude and precision than is widely available. A decimal fraction like 19.99 has no exact binary64 representation, so it can round on the round-trip, and any integer minor-unit value above 2^53-1 silently collides with its neighbours. MDN's Number.MAX_SAFE_INTEGER page shows the corruption concretely: `Number.MAX_SAFE_INTEGER + 1 === Number.MAX_SAFE_INTEGER + 2` evaluates to `true`, so two different amounts deserialize to the same number. The producer and consumer can each be individually correct (fixed-point or BigDecimal internally) and still disagree, because the wire format threw the precision away in between. On a payments or ledger path that means a wrong amount posted, charged, or reconciled.

**Fix**

Do not put money on the wire as a JSON number. Serialize it either as a decimal string (`"amount": "19.99"`, parsed into BigDecimal/Decimal, never through a float), or as an integer count of the smallest currency unit (`"amount_minor": 1999`, `"currency": "USD"`), always paired with an explicit currency code since minor-unit scale is currency-dependent. Enforce it at the schema boundary (`type: string` with a numeric pattern, or a documented integer minor-unit field) so no marshaller can quietly emit a bare float, and assert the round-trip in a test with a value above 2^53 and a value like 0.10.

```json
{ "amount_minor": 1999, "currency": "USD" }
```

```python
# Python: serialize Decimal money as a string, and decode with parse_float=Decimal
# so the value never touches a binary float on either side of the wire.
import json
from decimal import Decimal

class MoneyEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return str(o)                      # "19.99", not the float 19.99
        return super().default(o)

body = json.dumps({"amount": Decimal("19.99"), "currency": "USD"}, cls=MoneyEncoder)
data = json.loads(body, parse_float=Decimal)   # data["amount"] is Decimal("19.99")
```

```java
// Java (Jackson): Jackson writes a BigDecimal as a JSON *number* by default (unquoted 19.99),
// which is the bug. Serialize money as a string with ToStringSerializer.
class Invoice {
    @JsonSerialize(using = ToStringSerializer.class)   // -> "amount":"19.99", parsed back into BigDecimal
    BigDecimal amount;
    String currency;                                   // ISO 4217, always alongside the amount
}
// If money must stay numeric, at least mapper.enable(SerializationFeature.WRITE_BIGDECIMAL_AS_PLAIN)
// avoids scientific notation, but a string is the safe wire form.
```

**False positives**

- Zero-decimal or approximate values where sub-unit precision is irrelevant and the magnitude stays well under 2^53: a JPY integer amount, a display-only rounded figure, or a percentage/FX-rate field that is genuinely a rate rather than a settled money amount.
- Internal service-to-service payloads over a non-JSON codec (Protobuf, Avro, gRPC) whose money type is an integer or a fixed-point/decimal type, even if a JSON transcoding exists, because the canonical wire type is not binary64.
- A field named `amount` that is not money at all (a row count, a quantity of items, an amount of time in seconds) where float or large-integer semantics are fine.

**Sources**

1. [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format, Section 6 (Numbers)](https://datatracker.ietf.org/doc/html/rfc8259#section-6) (IETF)
2. [Number.MAX_SAFE_INTEGER](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Number/MAX_SAFE_INTEGER) (MDN Web Docs)
3. [decimal: Decimal fixed-point and floating-point arithmetic](https://docs.python.org/3/library/decimal.html) (Python Software Foundation)
4. [json, JSON encoder and decoder](https://docs.python.org/3/library/json.html) (Python Software Foundation)
5. [Jackson databind Serialization Features (WRITE_BIGDECIMAL_AS_PLAIN)](https://github.com/FasterXML/jackson-databind/wiki/Serialization-Features) (FasterXML, Jackson)

## API-2: GraphQL Float used for a money field

**Severity**: high

**What to detect**

- A schema field for money typed `Float`: `price: Float`, `amount: Float!`, `total: Float`, `balance: Float` in an SDL `.graphql` file or in code-first builders (`t.float(...)`, `GraphQLFloat`, `@Field(() => Float)` in Nest/TypeGraphQL).
- Python: a Graphene field typed `graphene.Float()` for money, a Strawberry field annotated `amount: float` (Strawberry maps the `float` annotation onto the GraphQL `Float` scalar), or a resolver returning a Python `float` for a price/balance. Money as `graphene.Int()` at a magnitude above 2^31-1 has the same overflow trap as any Int minor-unit field.
- Resolvers returning a JavaScript number / Python float / Go float64 for a money field, or input args declared `Float` that feed a charge, transfer, refund, or price mutation.
- A custom scalar named `Money`/`Decimal`/`Currency` that is actually implemented as a thin alias over `Float` (its `serialize`/`parseValue` just cast to a number).
- Java: a graphql-java money field bound to `Scalars.GraphQLFloat` (or an SDL `Float`), or a DGS/spring-graphql resolver returning a `double`/`Double` for a price/balance instead of a custom `Money` scalar backed by `BigDecimal`.
- Money represented as `Int` minor units but at a magnitude that can exceed the GraphQL Int bound of 2^31-1 (2147483647), e.g. a balance in cents above roughly 21.4 million dollars, which overflows the spec's signed 32-bit Int.
- Client codegen (`graphql-codegen`, Apollo typed hooks) mapping a money field to the TS `number` type because the schema said `Float`/`Int`.

**Why it breaks**

The GraphQL specification defines `Float` as a signed double-precision value as specified by IEEE 754, so a `Float` money field inherits every binary64 rounding and range problem: fractional amounts like 19.99 do not round-trip exactly, and large values lose precision. Reaching for `Int` instead caps you at the spec's signed 32-bit range, -(2^31) to 2^31-1 (confirmed by the reference implementation graphql-js: `GRAPHQL_MAX_INT = 2147483647`, `GRAPHQL_MIN_INT = -2147483648`), which overflows for large minor-unit balances. Either way the type the transport promises cannot faithfully carry money. Because the schema is the contract, every generated client and resolver silently adopts the lossy numeric type.

**Fix**

Do not type money as `Float`. Use one of: `Int` minor units when every value provably fits in signed 32 bits and you carry a currency code alongside; a `String` scalar parsed into BigDecimal/Decimal; or a custom `Money` scalar or object type whose `serialize` and `parseValue` refuse floats and round-trip an exact decimal string or an int64 minor-unit plus currency pair. A common robust shape is an object type `{ amountMinor: String!, currency: String! }` (amount as a string to dodge both the Float and the 32-bit Int traps). Validate the scalar at the boundary so a float or an out-of-range integer is a hard error, not a rounded value.

```python
# Python (Graphene): a custom Money scalar that serializes Decimal to a string
# and parses input back into an exact Decimal, rejecting bare floats.
import graphene
from decimal import Decimal

class Money(graphene.Scalar):
    @staticmethod
    def serialize(value):
        return str(value)                      # Decimal("19.99") to "19.99", never a Float

    @staticmethod
    def parse_value(value):
        if isinstance(value, float):
            raise ValueError("money must be a decimal string, not a float")
        return Decimal(str(value))

class Invoice(graphene.ObjectType):
    amount = Money(required=True)              # not graphene.Float()
    currency = graphene.String(required=True)
```

**False positives**

- Genuine floating-point quantities that are not settled money: an FX or interest rate, a tax percentage, a weighting factor, a statistical average, a geodistance. `Float` is the correct scalar for these.
- A money-in-cents field typed `Int` where the domain guarantees the value stays within signed 32 bits (e.g. a single line-item price capped well below 21 million dollars) and a currency code is present, so the Int representation is both exact and in range.
- A custom scalar named `Float` in a private schema that is documented and implemented as an arbitrary-precision decimal (rare, but the name alone is not proof of the built-in IEEE 754 scalar).

**Sources**

1. [graphql-js reference implementation: built-in scalar descriptions (GraphQLFloat, GraphQLInt, GRAPHQL_MAX_INT)](https://raw.githubusercontent.com/graphql/graphql-js/next/src/type/scalars.ts) (GraphQL Foundation)
2. [Graphene: Scalars (Float and Int definitions per the GraphQL spec)](https://docs.graphene-python.org/en/latest/types/scalars/) (Graphene / GraphQL Python)

## API-3: parseFloat / Number()-style parsing of money input strings

**Severity**: high

**What to detect**

- `parseFloat(...)` or `parseInt(...)` applied to a user- or API-supplied amount string in JS/TS (`parseFloat(req.body.amount)`, `parseFloat(input.price)`).
- `Number(x)`, unary `+x`, or `x * 1` coercion of a money string into a JS number before storing or charging.
- Language equivalents: Go `strconv.ParseFloat(s, 64)`, Java `Double.parseDouble(s)` / `Float.parseFloat(s)`, Ruby `s.to_f`, PHP `floatval`/`(float)` on a money value.
- Python: `float(amount_str)` or `float(request.json["amount"])` / `float(request.form["price"])` on a request-supplied amount, coercing it into a binary `float` before it is stored or charged. Unlike JS `parseFloat`, Python `float("12,34")` raises `ValueError` on a comma-decimal locale string rather than silently truncating, but `float("1.1")` still lands an inexact binary value, and a `try/except` that falls back to `0.0` on the `ValueError` turns a malformed amount into a silent zero charge.
- Locale-formatted amounts fed to a dot-only parser: strings containing a comma decimal separator (`"1.234,56"` DE/BR, `"1 234,56"` FR) or thousands separators, parsed with `parseFloat`/`Number` which only accept `.`.
- The parsed result flowing onward without a validity gate: no check that the whole string was consumed, no `Number.isNaN`/`math.isnan` guard, no rejection of trailing garbage.
- Building an amount from concatenated fields then `to_f`/`parseFloat`, or summing several such parsed values into a total that then hits a ledger or charge call.

**Why it breaks**

`parseFloat` does a partial parse: MDN states it takes the longest leading substring that forms a valid number literal and ignores the rest, so `parseFloat("3.14some non-digit characters")` returns 3.14 and `parseFloat("12,34")` returns 12 (it stops at the comma), turning a malformed or locale-formatted amount into a plausible wrong number instead of an error. Its accepted characters are only digits, sign, `.`, `e`/`E` and `Infinity`, so comma-decimal and grouped locales are silently mis-read. When the input cannot start a number it returns `NaN`, which is not caught by ordinary comparisons and propagates through arithmetic (`NaN + x` stays `NaN`), landing a corrupt total downstream. And `Number()` coercion treats an empty or whitespace-only string as `0` (unlike `parseFloat("")`, which is `NaN`), so a blank field can silently become a zero charge. Every one of these lands the value in an IEEE 754 double, which per the Python decimal docs cannot represent amounts like 1.1 exactly, reintroducing rounding on data that arrived as an exact string.

**Fix**

Do not parse money with float-coercing functions. Validate the amount string against a strict, locale-explicit numeric grammar first (reject trailing characters, empty input, and unexpected separators), normalize the known input locale to a canonical form, then parse into an exact decimal type: BigDecimal (Java), `decimal.Decimal` (Python), a big-decimal library or integer-cents parse (JS/TS), `math/big.Rat` or a cents `int64` (Go), `BigDecimal` (Ruby). Reject rather than round: a value that does not fully match the grammar is a 400, not a best-effort number. If the product accepts localized input, parse with an explicit locale-aware parser (for example `Intl.NumberFormat` formatToParts logic or a server-side locale parser), never `parseFloat`.

```python
# Python: match a strict canonical grammar, then build the Decimal from the
# string (never through float), so no partial parse or binary rounding happens.
import re
from decimal import Decimal, InvalidOperation

MONEY_RE = re.compile(r"^-?\d+(\.\d{1,2})?$")   # canonical dot-decimal, up to 2 places

def parse_money(raw: str) -> Decimal:
    if not MONEY_RE.fullmatch(raw.strip()):     # reject "", "12,34", "3.14abc"
        raise ValueError(f"not a canonical money string: {raw!r}")  # -> 400, do not coerce
    try:
        return Decimal(raw.strip())             # exact; float(raw) would reintroduce binary error
    except InvalidOperation:
        raise ValueError(f"not a canonical money string: {raw!r}")
```

```java
// Java: validate a strict grammar, then build the BigDecimal from the string.
// Never Double.parseDouble (binary rounding) and never new BigDecimal(double) (STO-7).
static final Pattern MONEY = Pattern.compile("-?\\d+(\\.\\d{1,2})?");

static BigDecimal parseMoney(String raw) {
    String s = raw.strip();
    if (!MONEY.matcher(s).matches())            // reject "", "12,34", "3.14abc" -> 400, do not coerce
        throw new IllegalArgumentException("not a canonical money string: " + raw);
    return new BigDecimal(s);                    // exact: the String constructor, not Double.parseDouble
}
```

**False positives**

- Parsing a value you fully control and have already validated to be a canonical dot-decimal or integer string (e.g. re-reading your own serialized `"1999"` minor units), where partial-parse and locale ambiguity cannot occur.
- Non-money numeric input where lenient parsing is acceptable (a page number, a search filter, a slider position, a quantity), so `parseFloat`/`Number` leniency is not a money-safety issue.
- `Number()`/`parseFloat` used purely for display formatting or a UI-side sanity hint, where the authoritative amount is still carried and charged as a string or integer minor units and this parse never reaches the ledger.
- A parser that is immediately followed by a strict full-match validation and a NaN/round-trip guard (parse, then assert the reparse equals the input), which neutralizes the partial-parse and NaN hazards.

**Sources**

1. [parseFloat()](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/parseFloat) (MDN Web Docs)
2. [Number coercion (empty and whitespace strings coerce to 0)](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Number#number_coercion) (MDN Web Docs)
3. [decimal: Decimal fixed-point and floating-point arithmetic](https://docs.python.org/3/library/decimal.html) (Python Software Foundation)
4. [Java SE 21 java.math.BigDecimal (String constructor)](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/math/BigDecimal.html) (Oracle)

## API-4: No canonical money representation across services

**Severity**: critical

**What to detect**

- The same logical amount modeled differently in different services or tables: one field in cents (`amount_cents`, integer), another in decimal units (`amount` NUMERIC), a third as a string, with no shared type or documented contract at the boundary.
- A money field passed between services with no accompanying currency code, so the receiver has to assume the currency and the minor-unit scale.
- Adapter/mapper code that multiplies or divides by 100 to bridge two services (`amount * 100`, `total / 100.0`, `cents = int(dollars * 100)`), a tell that the two sides disagree on units and are being reconciled ad hoc (and often via a float).
- Python: one service's pydantic model typing the amount `float` while another types it `Decimal` and a third `int` cents, with no shared Money model imported across them; a `cents = int(dollars * 100)` bridge (which also floats before it ints, dropping a cent) instead of a single canonical type; a pydantic model carrying an amount but no `currency` field, so the scale is assumed at every hop.
- Mixed scale assumptions for zero-decimal or three-decimal currencies (JPY has no minor unit, BHD and TND have three per ISO 4217): a hardcoded `*100` that is wrong for those currencies.
- Java: one service's Jackson DTO typing the amount `double` (or a `long` cents) while another types it `BigDecimal`, with no shared Money type imported across them, and DTOs carrying an amount but no `currency` field, so every hop assumes the scale.
- Column/type drift across the codebase for the same concept: `NUMERIC`/`DECIMAL` in one schema, `BIGINT` cents in another, `money` (the Postgres locale-dependent type) or `FLOAT`/`DOUBLE` elsewhere.
- An internal API or event that names a field just `amount`/`price`/`total` with no unit suffix and no currency sibling, forcing every consumer to guess.

**Why it breaks**

When each service picks its own money shape, every hop across the boundary is a chance to misread the scale or the currency, and the mistake is a real amount off by orders of magnitude. The Verizon 2006 billing dispute (reported by Wikinews) is the canonical human version: customer George Vaccaro was quoted a data rate of .002 cents per KB but billed .002 dollars, a 100x error, because two parties used different units for the same number, turning an expected 72 cents into roughly 71 dollars. Software makes the same error silently when service A emits cents and service B reads the integer as whole dollars, or when a `*100` bridge is applied to a JPY amount that has no minor unit. Martin Fowler's Money pattern warns that money is not a first-class type in mainstream languages and that mixing amounts without accounting for currency, plus rounding to the smallest unit, is exactly where pennies (or 100x errors) leak. Without one canonical representation the bug is not local to one service; it lives in the gaps between them, which are the least tested.

**Fix**

Adopt a single canonical money shape and use it on every internal boundary: an amount plus an explicit ISO 4217 currency, with a defined scale. Two well-trodden options are google.type.Money (int64 `units` plus int32 `nanos` at 10^-9, with sign-consistency rules, plus `currency_code`) and Stripe-style integer minor units (an integer in the smallest unit for that currency, always with the currency code so the scale is unambiguous, e.g. 1099 = 10.99 USD, 10 = 10 JPY). Encapsulate it in a Money type (Fowler's pattern: amount plus currency, never a bare number) and forbid raw `*100` conversions across services. Enforce the shared shape in the API schema and in contract tests so no service can quietly ship its own units, and make currency a required field everywhere money crosses a boundary.

```python
# Python: one shared pydantic Money model, imported by every service. It carries
# a Decimal internally and serializes the amount as a string, so no float and no
# bare *100 bridge crosses a boundary. Currency is required, never assumed.
from decimal import Decimal
from pydantic import BaseModel, field_serializer

class Money(BaseModel):
    amount: Decimal                            # exact, not float
    currency: str                              # ISO 4217, required at every hop

    @field_serializer("amount")
    def _amount_to_str(self, v: Decimal) -> str:
        return str(v)                          # on the wire as "10.99", parsed back into Decimal
```

**False positives**

- A single service (or a set that shares one library) that consistently uses one representation everywhere and never crosses into a differently-scaled system; the `*100` guidance and cross-service currency requirement do not apply within one uniform boundary.
- A deliberate, documented boundary conversion at a third-party edge (e.g. a specific payment provider that demands decimal strings while you use minor units internally) implemented once in an adapter with tests, rather than scattered ad hoc scaling.
- A genuinely single-currency product where the currency is a fixed, documented invariant of the whole system, so omitting a per-field currency code is a conscious, recorded decision rather than an ambiguity (still record it explicitly).
- Presentation-layer formatting that converts minor units to a localized decimal string for display only, where the canonical amount remains the shared minor-unit plus currency shape.

**Sources**

1. [google.type.Money (proto definition: currency_code, units int64, nanos int32)](https://github.com/googleapis/googleapis/blob/master/google/type/money.proto) (Google googleapis)
2. [Money (Patterns of Enterprise Application Architecture)](https://martinfowler.com/eaaCatalog/money.html) (Martin Fowler)
3. [Stripe API: Currencies (amounts as integers in the smallest currency unit)](https://docs.stripe.com/currencies) (Stripe)
4. [Customer says Verizon confuses dollars and cents](https://en.wikinews.org/wiki/Customer_says_Verizon_confuses_dollars_and_cents) (Wikinews)
