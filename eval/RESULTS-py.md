# Eval results: Python fixture, run 1

Run 1 of the deliberately-buggy Python fixture (`fixture-py/`, 37 planted money bugs across 10
domains). Auditor findings are in `run-1-py-findings.json`, scored by `score.py` against
`fixture-py/expected.json`.

## Headline

- **Recall: 100 percent (37 / 37 planted bugs found)**
- **Precision vs key: 100 percent (66 / 66 findings on target, zero false positives against the answer key)**

## Method

Ten domain auditors (one per rule domain: STO, ROU, IDE, LED, FX, TIM, AGG, TAX, API, TST), run in
waves of three. Each auditor read only its domain rule file plus the fixture files where that domain
lives, and audited independently: it never saw the answer key. Its findings were appended to
`run-1-py-findings.json` and scored. A finding matches a planted bug when the rule id is equal and
the file path matches, so several findings can map to one planted bug (for example seven `STO-1`
float-column findings in the schema map to the single planted schema-level `STO-1`), which is why
there are 66 findings for 37 bugs.

## Per-domain recall

| Domain | Planted | Found |
| --- | --- | --- |
| STO storage and types | 6 | 6 |
| ROU rounding and allocation | 4 | 4 |
| IDE idempotency and concurrency | 4 | 4 |
| LED ledger | 4 | 4 |
| FX multicurrency | 4 | 4 |
| TIM time and dates | 4 | 4 |
| AGG aggregation | 2 | 2 |
| TAX taxes | 3 | 3 |
| API serialization | 3 | 3 |
| TST testing | 3 | 3 |
| Total | 37 | 37 |

Two clean judgment calls by the auditors, worth noting because they show the tool is reading the
code rather than pattern-matching blindly:

- The AGG auditor did not flag `AGG-2` (precision lost at an ORM or driver boundary) because
  `reports.py` has no such boundary. It flagged only the float-accumulation and paginated-scan bugs
  that are actually present.
- The API auditor did not flag `API-2` (GraphQL Float for money) because the fixture has no GraphQL.
  It flagged the JSON-number, float-parse, and canonical-shape bugs that are present.

## Honest caveats (read these before quoting the number)

1. **This is a scoped-audit number, not a cold full-repo scan.** Each auditor was pointed at the
   files where its domain's bugs live. The TypeScript run 1 (86 percent recall) was a single cold
   scan of the whole fixture, so the two numbers are not directly comparable. A cold Python scan is
   the more comparable figure and is expected to be lower.
2. **Precision here is measured on an all-planted fixture.** Every file is deliberately buggy, so
   "zero false positives" only means every finding hit a real bug. It does not test whether the tool
   cries wolf on correct code. That false-positive dimension is untested, the same limitation the
   TypeScript run documented.
3. **No adversarial verifier pass was run for this number.** On a fixture where every finding is a
   planted bug, the verifier can only refute real bugs, so it would refute close to zero and add
   token cost without signal. The verifier's false-positive suppression is the thing that needs
   testing, and that needs a clean-code fixture (correct money handling) to test properly. That is
   the right next eval, tracked below.

## Reproduce

```
# Audit each domain scoped to its fixture files, capture findings into run-1-py-findings.json,
# then score:
python3 eval/score.py --expected eval/fixture-py/expected.json eval/run-1-py-findings.json
```

## Next

- Add a small clean-code fixture (correct money handling) and roast it to measure false positives.
  That exercises the adversarial verifier, the dimension this all-planted run cannot test.
- A cold full-repo Python scan for a figure directly comparable to the TypeScript 86 percent.
