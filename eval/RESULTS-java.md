# Eval results: Java fixture, run 1

Run 1 of the deliberately-buggy Java (Spring Boot + JPA + H2) fixture (`fixture-java/`, 37 planted
money bugs across 10 domains). Auditor findings are in `run-1-java/run-1-java-findings.json`, scored
by `score.py` against `fixture-java/expected.json`.

## Headline

- **Recall: 97 percent (36 / 37 planted bugs found)**
- **Precision vs key: 96 percent (52 / 54 findings on target)**

## Method

Ten domain auditors (one per rule domain: STO, ROU, IDE, LED, FX, TIM, AGG, TAX, API, TST),
dispatched **one at a time** (serial, one sub-agent per domain, not in waves) to keep the main
context light. Each auditor read only its domain rule file plus the fixture files where that domain
lives, and audited independently: it never saw the answer key. Its findings were written to
`run-1-java/<domain>.json`, then all ten were combined into `run-1-java/run-1-java-findings.json` and
scored. A finding matches a planted bug when the rule id is equal and the file path ends with one of
the planted files, so several findings can map to one planted bug (for example six `TIM-1` findings,
four schema `TIMESTAMP` columns plus two entity `LocalDateTime` fields, map to the single planted
`TIM-1`), which is why there are 54 findings for 37 bugs.

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
| API serialization | 2 | 3 |
| TST testing | 3 | 3 |
| Total | 36 | 37 |

## The one miss and the two off-key findings (read these, they are the honest part)

- **Missed: P34 (API-4) in `Api.java`.** The planted bug is that two endpoints disagree on the money
  unit (`invoiceResponse` returns decimal dollars, `accountBalanceResponse` returns integer cents).
  The API auditor did flag `API-4`, but on `Money.java` (the `toMinorUnits` / `fromMinorUnits` unit
  handling), not the cross-endpoint inconsistency in `Api.java`. So it saw the domain and a related
  instance but not the strongest one the key indexes. A real partial miss, not hidden.
- **Off-key (defensible, not a false positive): `STO-3` on `Money.java`.** The auditor read the
  hardcoded `*100` / `/100` minor-unit conversion as STO-3 (unit convention not encoded in the type).
  The key labels that same code STO-5 (hardcoded two-decimal), which the auditor also found
  separately. A legitimate alternative classification of a genuinely buggy line.
- **Off-key (same as the miss): `API-4` on `Money.java`.** This is the auditor's API-4 finding
  described above, counted off-key because it landed on a different file than P34's canonical locus.

Both off-key findings hit real buggy code; neither is a hallucination. This is the tool reading the
code and occasionally choosing a different rule id or file than the key's canonical one, which is the
expected imperfection at 97 percent, not cried-wolf noise.

## Honest caveats (read these before quoting the number)

1. **This is a scoped-audit number, not a cold full-repo scan.** Each auditor was pointed at the
   files where its domain's bugs live. The TypeScript run 1 (86 percent recall) was a single cold
   scan of the whole fixture, so the two numbers are not directly comparable. A cold Java scan is the
   more comparable figure and is expected to be lower.
2. **Precision here is measured on an all-planted fixture.** Every file is deliberately buggy, so a
   high precision only means most findings hit a real bug. It does not test whether the tool cries
   wolf on correct code. That false-positive dimension is untested, the same limitation the
   TypeScript and Python runs documented.
3. **No adversarial verifier pass was run for this number.** On an all-planted fixture the verifier
   can only refute real bugs, so it would refute close to zero and add token cost without signal. The
   verifier's false-positive suppression needs a clean-code fixture to test, which is the right next
   eval (tracked below).
4. **One fixture divergence from Python, worth noting.** The Java ledger hit a real
   `ledger_entries -> accounts` foreign-key violation that the Python in-memory dict never enforces,
   so `postEntry` credits (auto-creating the account) before saving the entry. That is a legitimate
   ordering fix, no planted LED bug was removed. It is the kind of issue a real database surfaces that
   an in-memory fixture hides.

## Reproduce

```
# Audit each domain scoped to its fixture files, capture findings into
# run-1-java/<domain>.json, combine into run-1-java/run-1-java-findings.json, then score:
python3 eval/score.py --expected eval/fixture-java/expected.json eval/run-1-java/run-1-java-findings.json
```

## Next

- Add a small clean-code fixture (correct money handling) and roast it to measure false positives.
  That exercises the adversarial verifier, the dimension this all-planted run cannot test.
- A cold full-repo Java scan for a figure directly comparable to the TypeScript 86 percent.
