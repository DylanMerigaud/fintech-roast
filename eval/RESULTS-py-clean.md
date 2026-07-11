# Eval results: clean Python fixture (false-positive benchmark), run 1

Run 1 of the deliberately-CORRECT Python fixture (`fixture-py-clean/`), the twin of the buggy
`fixture-py/`. Same 11 modules, same schema, same 10 domains, but every one of the 37 planted bugs is
inverted to its correct pattern. This is the false-positive benchmark: it measures how often the tool
cries wolf on money code that is right. Auditor findings are in `run-1-py-clean-findings.json` (the
per-domain JSON is under `run-1-py-clean/`).

## Headline

- **False positives: 0**
- **Findings emitted on correct code: 0 / 10 domains**
- **False-positive rate: 0 percent**

Ten domain auditors read correct money handling and, honestly against the rulebook, reported nothing.
No finding fired, so nothing reached the adversarial verifier: the raw output was already clean.

## Why this benchmark matters

The three planted-bug fixtures (TS, Python, Java) prove RECALL: the tool finds real money bugs. None
of them prove PRECISION on correct code, because every file in them is deliberately buggy, so "zero
false positives against the answer key" there only means every finding hit a real bug. `RESULTS-py.md`
flagged this directly (caveat 3): "whether the tool cries wolf on correct code ... is untested ...
that needs a clean-code fixture." This run is that fixture and that number.

## Method

Same recipe as the buggy-fixture run. Ten domain auditors (STO, ROU, IDE, LED, FX, TIM, AGG, TAX,
API, TST), run in waves of three. Each auditor read only its domain rule file (including its
false-positive notes) plus the clean fixture files where that domain applies, and audited
independently. Each was told plainly that the fixture is correct, that its job is the normal audit
(not to find bugs at all costs), and that a finding it cannot defend line-by-line to a skeptical staff
engineer does not get reported. Its findings were written to `run-1-py-clean/<domain>.json`.

Because the raw findings were empty, the adversarial `finding-verifier` pass was not run: it only
attacks findings that fired, and there were none. On this fixture the auditors' own false-positive
discipline (checking every candidate against the rule's false-positive notes) was sufficient.

## Per-domain result

| Domain | Findings on correct code |
| --- | --- |
| STO storage and types | 0 |
| ROU rounding and allocation | 0 |
| IDE idempotency and concurrency | 0 |
| LED ledger | 0 |
| FX multicurrency | 0 |
| TIM time and dates | 0 |
| AGG aggregation | 0 |
| TAX taxes | 0 |
| API serialization | 0 |
| TST testing | 0 |
| Total | 0 |

## The traps the auditors correctly declined

The value of a clean fixture is the near-misses: code that a naive linter would flag, but a
rule-reading auditor should not. Each of these was considered and correctly left alone:

- **STO**: `discount_pct NUMERIC(6,4)` is a rate, not an amount, so it is not an exact-decimal-money
  violation. `to_minor_units` uses an ISO 4217 exponent table, not a hardcoded `* 100`.
- **ROU**: `unit_price_from_bundle` rounds a division, but it is a display-only helper; the
  authoritative `bundle_line_total` never divides. `split_proportionally` already runs a
  largest-remainder residual pass, which ROU-2's own false-positive note blesses.
- **IDE**: `payments.external_ref` is nullable, which the rule warns about, but the actual webhook
  dedup key is `webhook_events.event_id`, which is `NOT NULL UNIQUE`. The `threading.Lock` was read as
  a correctly-scoped stand-in for a row lock, not a read-modify-write race.
- **FX**: the reverse rate is derived as `1 / forward`, applied one-way with a single boundary
  rounding and no round-trip equality expectation, which is what FX-1 permits.
- **TAX**: net and tax are each rounded, but they are complementary values summing to the exact gross,
  so `net + tax == gross` holds. This is the inclusive-pricing pattern TAX-2 explicitly allows.
- **LED**: `reset_ledger`'s `.clear()` is a test helper, not a mutation of posted history.
- **AGG**: keyset pagination (`WHERE id > cursor`) is stable by construction, the AGG-3 false-positive
  carve-out, not a mid-scan offset drift.
- **TIM**: `(end - start).days` on `date` objects is the correct day count TIM-2 endorses, not the
  epoch-seconds-over-86400 pattern it flags.

That the auditors reasoned through these rather than pattern-matching on `round`, `float`, `.clear()`,
or a nullable unique column is the real signal here.

## Honest caveats (read these before quoting the number)

1. **Zero on this fixture is not zero on all correct code.** The fixture is one billing app. A
   different correct codebase with unusual-but-valid idioms could still draw a false positive. This
   number says the tool does not fire on a realistic, idiomatic correct implementation of the exact
   surfaces the rulebook targets, not that its false-positive rate is provably zero everywhere.
2. **The auditors were told the fixture is a clean twin.** That is honest framing (it is), but a
   fully blind run that does not know whether it is auditing clean or buggy code would be a stronger
   test of the default disposition. The buggy-fixture auditors were given the mirror-image framing
   ("deliberately buggy"), so the two runs are symmetric; a blind mixed-fixture run is the stricter
   future test.
3. **The verifier was not exercised here either.** With zero raw findings there was nothing to refute.
   The verifier's suppression power gets tested only when the auditors DO emit a borderline finding on
   correct code; that would need a harder clean fixture (or a blind mixed run) designed to bait a
   false positive. This run shows the auditors did not need the verifier on this fixture.

## Reproduce

```
# The clean fixture is green by design:
cd eval/fixture-py-clean && pip install pytest hypothesis && python3 -m pytest -q

# Audit each domain scoped to its clean fixture files (the money-domain-auditor agent),
# write each domain's JSON under eval/run-1-py-clean/, then combine into
# eval/run-1-py-clean-findings.json. Zero findings = zero false positives; no scorer needed
# (there is no answer key on a clean fixture).
```

## Next

- A harder clean fixture (or a blind mixed-fixture run) designed to bait a borderline finding, so the
  adversarial verifier's false-positive suppression is actually exercised, not just found unnecessary.
- The same clean-twin treatment for the TS and Java fixtures, to publish a false-positive number
  alongside each recall number.
