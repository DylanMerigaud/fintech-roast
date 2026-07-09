# Aggregation and reporting

Part of the [fintech-roast](../README.md) rulebook. See [README.md](README.md) for the format contract and severity scale.

## AGG-1: Summing money as binary floats: error accumulates with n and depends on order and partitioning

**Severity**: high

**What to detect**

- SQL columns holding money declared REAL, FLOAT, FLOAT4, FLOAT8, or DOUBLE PRECISION, then fed to SUM() or AVG() (in PostgreSQL, sum(double precision) returns double precision, so the accumulator itself is a float).
- A running total accumulated in a native float: JS/TS `let total = 0; for (const x of rows) total += x.amount` or `rows.reduce((a, r) => a + r.amount, 0)` where amount is a Number; Python `sum(floats)` or `+=` on floats for currency; Java `double total`; Go `var total float64`; Ruby summing Floats.
- Parallel or chunked aggregation that combines per-partition float subtotals (map/reduce, Spark or pandas `.sum()`, sharded workers, DB parallel aggregate), where reordering the adds changes the last bits.
- Money moved through a float on the way to the sum: `parseFloat` or `Number()` on an amount string, `amount * 100` in float, `Math.round` applied after float arithmetic to hide drift.
- Reconciliation code that compares two sums with `==` or exact equality instead of a tolerance, or that occasionally reports a 0.01 imbalance.
- Absence of a decimal or integer-minor-unit money type (no BigDecimal, decimal.Decimal, decimal.js, or NUMERIC) anywhere on the summation path.

**Why it breaks**

IEEE 754 binary floating point cannot represent most decimal fractions exactly, and addition is not associative, so `(a + b) + c` can differ from `a + (b + c)`. Naive sequential summation has a worst-case rounding error that grows proportional to n and a root-mean-square error that grows as sqrt(n), so the more rows you sum the more the total drifts. Because the result depends on the order the additions happen, a parallel or partitioned sum (pairwise or tree reduction) can return a different total than a sequential one for the same data, which shows up as reconciliation mismatches that move when you re-run or re-shard. PostgreSQL's own docs warn that floating-point types are inexact and that floating point should not be used to handle money due to rounding errors.

**Fix**

Keep money out of binary floats end to end. Store amounts as integers in the smallest currency unit (Stripe's model: 1099 = 10.99 USD) or as fixed-precision decimals (SQL NUMERIC/DECIMAL, Java BigDecimal, Python decimal.Decimal, JS decimal.js or Prisma.Decimal), and do the SUM in that type so the accumulator never becomes a float. If a legacy float path is unavoidable for a non-authoritative figure, use compensated (Kahan) summation, whose worst-case error bound is independent of n, and never compare two sums for exact equality, use an explicit tolerance. Treat the decimal or integer total as the source of truth; a float is acceptable only for a display estimate that is never persisted or reconciled.

**False positives**

- Non-monetary statistics where a tiny relative error is irrelevant: analytics dashboards, ML feature sums, sensor or telemetry averages, sampled metrics. Float is the correct, fast tool there.
- Values already stored as exact integer minor units (cents) summed as 64-bit integers: `SUM(amount_cents)` over BIGINT is exact and not a float bug, even though it is "summing money"; the risk only appears if the total can overflow the integer type.
- A float used purely for an intermediate ratio or percentage, or a rounded display value that is recomputed from an authoritative decimal or integer total and never written back or reconciled against.
- Single-value or tiny-n reads (one row, a couple of rows) where accumulation error cannot reach half a minor unit, though converting to decimal is still cheaper than proving the bound.

**Sources**

1. [What Every Computer Scientist Should Know About Floating-Point Arithmetic](https://docs.oracle.com/cd/E19957-01/806-3568/ncg_goldberg.html) (Oracle, reprint of Goldberg, Computing Surveys 1991)
2. [Kahan summation algorithm](https://en.wikipedia.org/wiki/Kahan_summation_algorithm) (Wikipedia)
3. [PostgreSQL: Numeric Types](https://www.postgresql.org/docs/current/datatype-numeric.html) (PostgreSQL Global Development Group)
4. [PostgreSQL: Monetary Types](https://www.postgresql.org/docs/current/datatype-money.html) (PostgreSQL Global Development Group)
5. [PostgreSQL: Aggregate Functions](https://www.postgresql.org/docs/current/functions-aggregate.html) (PostgreSQL Global Development Group)
6. [Stripe: Currencies](https://docs.stripe.com/currencies) (Stripe)

## AGG-2: Precision silently lost at ORM, driver, or JSON boundaries

**Severity**: high

**What to detect**

- A DECIMAL/NUMERIC column that surfaces in code as a native float or double instead of a decimal type: e.g. a driver or ORM config that maps NUMERIC to JS Number, Python float, or Go float64, or Prisma's Float scalar (which maps to database Double, not Decimal, since Prisma 2.17).
- `JSON.parse(...)` (or any JSON decode) on a payload containing a monetary amount or a large integer id, then using the result as a Number; large integer literals beyond 2^53 in JSON bodies or webhook payloads.
- A round-trip that stringifies then re-parses money, or converts a decimal type to Number for arithmetic: `Number(row.amount)`, `.toNumber()` on a Decimal, `float(row['amount'])`, `parseFloat`, then summing or comparing.
- Java/JDBC using getDouble() or getFloat() on a DECIMAL column instead of getBigDecimal(); Go scanning a NUMERIC into *float64; Ruby/ActiveRecord attributes typed as :float over a decimal column.
- JSON serializers that emit numbers (not strings) for money or 64-bit ids, sent to a JavaScript consumer with no BigInt or decimal reviver.
- Aggregation whose input is exact (NUMERIC) but which is cast to float mid-pipeline before SUM or AVG, defeating the exact accumulator.

**Why it breaks**

The database can store an amount exactly in DECIMAL/NUMERIC, but the value passes through a boundary that only understands IEEE 754 binary64: a driver mapping, an ORM scalar default, or JSON. RFC 8259 notes that JSON interoperates only for integers in the range -(2^53)+1 to (2^53)-1 and that good interoperability assumes no more precision than IEEE 754 binary64 provides, so any number outside that (a big id, a high-precision or large amount) is silently approximated on decode. MDN confirms numbers in JSON text are converted to JavaScript numbers and may lose precision in the process, before any reviver runs. The corruption is invisible in code review because the column type looks correct; the loss happens in the layer between the column and the variable, and once rounded it cannot be recovered.

**Fix**

Carry money in an exact type across every boundary. Map DECIMAL/NUMERIC columns to a decimal type, not a float: use getBigDecimal in JDBC, decimal.Decimal in Python, decimal.js or Prisma.Decimal in JS (and avoid Prisma's Float scalar for money, since it maps to Double), and a fixed-precision type in Go or Ruby. Over the wire, serialize money and 64-bit ids as strings and revive them into BigInt or a decimal type (MDN's context.source pattern) rather than letting JSON.parse coerce them to doubles. Add a boundary test with a value that is exact in DECIMAL but not in binary64 (e.g. an amount ending in .10 or an id above 2^53) and assert it survives the round trip unchanged.

**False positives**

- A boundary carrying only integer minor units within the safe range: amounts in cents as integers below 2^53, or ids that are UUIDs or strings, round-trip through JSON and native Number exactly, so a Number mapping there is fine.
- Non-monetary or low-precision fields where approximation is acceptable (scores, ratios, geo coordinates within tolerance, analytics), for which a float mapping is a deliberate, correct choice.
- A decimal value converted to float only at the very end for display or formatting, where the authoritative value stays decimal and the float is never persisted, summed, or compared for equality.
- Languages or drivers that already decode JSON numbers into an arbitrary-precision or decimal type by default (e.g. a parser configured with parse_float=Decimal, or a BigDecimal-based JSON binding), so the boundary does not narrow to binary64.

**Sources**

1. [RFC 8259 Section 6: Numbers](https://datatracker.ietf.org/doc/html/rfc8259#section-6) (IETF)
2. [MDN: JSON.parse()](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/JSON/parse) (MDN Web Docs, Mozilla)
3. [Prisma: Fields and types](https://www.prisma.io/docs/orm/prisma-client/special-fields-and-types) (Prisma)
4. [Prisma 2.17.0 release notes](https://github.com/prisma/prisma/releases/tag/2.17.0) (Prisma, GitHub)
5. [PostgreSQL: Numeric Types](https://www.postgresql.org/docs/current/datatype-numeric.html) (PostgreSQL Global Development Group)
6. [PostgreSQL: Aggregate Functions](https://www.postgresql.org/docs/current/functions-aggregate.html) (PostgreSQL Global Development Group)

## AGG-3: Paginated or streamed aggregation over data that mutates mid-scan double-counts or misses rows

**Severity**: critical

**What to detect**

- LIMIT/OFFSET (or SQL Server OFFSET ... FETCH, MySQL LIMIT off,n) paging driven by a page number, with each page fetched in a separate transaction or request while the table is concurrently written.
- Aggregation or export that loops pages and accumulates a total across them (sum, count, invoice or settlement batch, statement generation, balance rollup) rather than computing the aggregate in one query.
- Cursor variables named `page`, `offset`, `skip` computed as `page * pageSize`; ORM calls like `.offset(n).limit(m)`, `.skip(n).take(m)`, `LIMIT n OFFSET m`, Django `qs[offset:offset+limit]` iterated to sum money.
- ORDER BY on a non-unique or mutable key (e.g. ORDER BY created_at without a unique tiebreaker), so rows with equal keys can reshuffle between page fetches.
- Streaming or keyset pagination whose `WHERE key > :last` boundary can be crossed by updates that change the sort key mid-scan, or that runs outside a single snapshot when exactness is required.
- A multi-page read of a financial dataset with no single-snapshot guarantee: pages served under READ COMMITTED across separate transactions, no repeatable-read or serializable snapshot and no immutable cursor key.

**Why it breaks**

OFFSET counts rows to skip at execution time, so if rows are inserted or deleted before the current page between two page fetches, the window shifts. As the Citus and PostgreSQL analysis shows, a row inserted into an earlier page causes both a duplication (the previously-final row of page n is pushed into page n+1) and an omission (the new row), and a deletion shifts a row back so it is skipped entirely. Markus Winand states that the idea of using the number of rows seen to skip over them later is simply wrong, precisely because concurrent writes make the count meaningless. When you are summing money across those pages, a duplicated row double-counts and a shifted row is missed, so the aggregate is silently wrong (over- or under-stated) on production paths where the data is live, which is a corrupted financial total, not a display glitch.

**Fix**

Compute the aggregate in a single statement (`SELECT SUM(amount) ... WHERE ...`) so it evaluates against one consistent snapshot instead of stitching pages by hand. When the dataset is too large or must be streamed, read it inside one transaction with a snapshot isolation level (repeatable read or serializable), or use keyset/cursor pagination on a stable, unique, immutable ordering key, which Winand and Citus show leaves rows before the current position unaffected by inserts and deletes.

```sql
-- keyset page over an immutable (created_at, id) key
SELECT amount FROM txns
WHERE (created_at, id) > (:last_ts, :last_id)
ORDER BY created_at, id
LIMIT :page;
```

Cursors give snapshot consistency on arbitrary queries because the isolation level fixes the view at transaction start; keyset gives it for ordered records without holding a transaction open. For settlement or reporting, snapshot the working set (a stable as-of view or an append-only ledger with an immutable cursor) before aggregating, so a concurrent write cannot move the window mid-run.

**False positives**

- OFFSET pagination for human UI browsing where an occasional duplicate or skipped row across pages is cosmetically acceptable and nothing is summed or reconciled from it.
- Paging over an immutable or as-of snapshot: a closed accounting period, an append-only ledger scanned with an immutable cursor key, or a read replica pinned to a snapshot, where no writes can shift the window during the scan.
- A single-query aggregate (`SELECT SUM(...)` or `COUNT(...)`) that internally uses OFFSET/LIMIT only for output paging of already-aggregated rows, not to accumulate the total itself.
- Keyset pagination on a strictly append-only, monotonic key where the sort key never changes after insert (e.g. an autoincrement id or event timestamp that is never updated), so the `WHERE key > :last` boundary is stable by construction.
- A whole scan wrapped in one serializable or repeatable-read transaction, where the pagination mechanism is irrelevant because every page sees the same snapshot.

**Sources**

1. [We need tool support for keyset pagination (No-Offset)](https://use-the-index-luke.com/no-offset) (Markus Winand, use-the-index-luke.com)
2. [Five ways to paginate in Postgres, from the basic to the exotic](https://www.citusdata.com/blog/2016/03/30/five-ways-to-paginate/) (Citus Data, Joe Nelson)
3. [PostgreSQL: Aggregate Functions](https://www.postgresql.org/docs/current/functions-aggregate.html) (PostgreSQL Global Development Group)
