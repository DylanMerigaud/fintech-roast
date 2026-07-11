# Eval results: blind mixed Python fixture, run 1

The eval that removes both caveats hanging over the earlier Python runs at once. `RESULTS-py.md`
measured recall on a SCOPED audit (each auditor pointed at the files where its bugs live = generous).
`RESULTS-py-clean.md` measured false positives on a fixture the auditors were TOLD was a clean twin
(= hinted, and the verifier never fired). This run fixes both: clean and buggy files sit in ONE tree,
the auditors are handed pure code with no hint which is which, and it is the first run where the
adversarial verifier actually had a false positive to refute.

## Headline

- **Blind recall: 18 / 21 = 86 percent** (planted bugs found on the buggy files).
- **False positives on clean code: 1 emitted, 0 survived the verifier** (the one FP was refuted).
- **The verifier earned its cost for the first time:** it refuted a real false positive (TAX-2) that a
  clean-only or buggy-only fixture could never have produced.
- **The blind eval found a genuine gap in our OWN clean fixture** (a mislabeled rounding test), which
  we then fixed. Details below.

Recall matches the TypeScript cold number (86 percent) to the point, including the same
schema-versus-code scoring artifact in the ledger cluster.

## The fixture

`fixture-py-mixed/` is a read-only audit artifact: 6 buggy files (money, schema, fx, ledger, webhooks,
store, copied verbatim from `fixture-py/`, carrying 21 planted bugs) mixed with 7 clean files (invoice,
split, tax, interest, reports, api, tests, from `fixture-py-clean/`). All comments and docstrings are
stripped from every file via `sanitize_mixed.py` (tokenizer-based, so the code is provably AST-identical
to its source), because the source files self-identify (buggy ones with inline bug notes, clean ones
with "correct twin" docstrings). After stripping, the auditor judges pure code and cannot tell a file's
status from prose. The answer key and the split README live OUTSIDE the readable tree
(`fixture-py-mixed.expected.json`, `fixture-py-mixed.README.md`) so an auditor that globs the directory
cannot read them.

Three domains are deliberately SPLIT across a buggy and a clean file, the real discrimination test:

- **API**: buggy `money.py` (API-3 float parse) + clean `api.py`. The auditor flagged money.py and
  explicitly cleared api.py ("money is serialized as a string, no API-1 violation").
- **ROU**: buggy `money.py` (ROU-1 bare round) + clean `invoice.py`/`split.py`. Flagged money.py, cleared
  the correct single-rounding invoice and largest-remainder split.
- **TIM**: buggy `schema.sql` (TIM-1 naive timestamp) + clean `interest.py`. Flagged the schema, cleared
  the correct calendar-date day math and explicit day-count convention.

## Method

Ten domain auditors, waves of <= 3, each given its domain rule file plus the mixed-tree files where its
domain applies, audited BLIND (the prompt never says which files are clean or buggy, never mentions a
twin). Findings accumulate into `run-1-py-mixed/<domain>.json`, combined to
`run-1-py-mixed-findings.json`. Every finding that landed on a CLEAN file (a false-positive candidate)
was then sent to the adversarial `finding-verifier`, which tries to refute it; verdicts in
`run-1-py-mixed-verified.json`. Scored with `score.py --expected fixture-py-mixed.expected.json` (21
buggy-file bugs). Findings on buggy files were not re-verified (they hit planted bugs; the verifier
refutes near zero on real bugs, same rationale as the prior runs).

## Recall detail

34 findings, 32 on buggy files, 2 on clean files. Scored against the 21-bug key:

| Metric | Value |
| --- | --- |
| Planted bugs found | 18 / 21 = **86 percent** |
| Findings on target (precision vs key) | 30 / 34 = 88 percent |

The 3 scored misses, in the same spirit as the TypeScript run:

- **P31 LED-3, P32 LED-4**: found, but at the schema, not the code path the key indexed. The LED auditor
  flagged the cached-balance and missing-audit-trail defects in `schema.sql`; the key indexes them in
  `ledger.py`. This is a scoring artifact (rule id plus file matching), not a missed defect, identical to
  the TypeScript ledger cluster. Counting genuine-defect recall, these are found.
- **P12 FX-1**: a genuine miss. The FX auditor saw the lossless-round-trip refund defect but folded it
  into its FX-3 finding rather than reporting FX-1 separately ("I'll report FX-3 as the primary for the
  refund and not double-count"). Seen, refiled, so lost under a strict rule-id match.

So the genuine-defect recall is higher than 86 percent (only FX-1 is a real omission, and even that was
recognized under a neighbouring rule), the same strict-versus-genuine gap the TypeScript run documented.

## False positives and the verifier (the point of this run)

Two findings landed on clean files. Both went to the adversarial verifier:

- **TAX-2 on `tax.py` -> REFUTED (a true false positive, killed).** The auditor claimed net and tax are
  rounded independently so `net + tax` may not equal gross. The verifier proved (about 1M random amounts,
  0 mismatches) that `tax = round(gross - gross / (1 + rate))` is the exact complement of `net`, and since
  gross is a fixed cent-precision value, `round(q) + round(gross - q) == gross` under both HALF_UP and
  HALF_EVEN. It is the inclusive back-calculation the rule EXPLICITLY blesses. **This is the verifier
  doing exactly what it exists for**, catching a plausible-but-wrong finding on correct code, which
  neither the all-buggy nor the all-clean fixture could ever have surfaced.
- **TST-2 on `test_money.py` -> CONFIRMED (a real defect in our OWN clean fixture).** The auditor noticed
  the test named `test_round_money_explicit_half_up` asserted `round_money(2.675) == 2.68`, but 2.675 has
  an odd preceding digit, so it rounds to 2.68 under BOTH HALF_UP and HALF_EVEN. The test claimed to pin
  the rounding mode and did not, and no other test in the suite pinned a discriminating tie. This was NOT
  a false positive: it was a real weakness the blind eval found in the "correct" fixture. Fixed by
  changing the assertion to `round_money(2.665) == 2.67` (an even-preceding-digit tie that HALF_UP and
  HALF_EVEN disagree on), so the test now genuinely pins the mode. `fixture-py-clean` stays 24 green.

**Net false-positive rate on correct code after verification: 0.** The single false positive was refuted;
the other clean-file finding was a real (now fixed) defect, not a false accusation.

## Honest caveats

1. The mixed tree is a read-only audit artifact, not a runnable app. The two runnable green-by-design apps
   stay in `fixture-py/` and `fixture-py-clean/`.
2. One split, one run. A different split or a re-run could move the numbers by a finding or two; the split
   is recorded (`fixture-py-mixed.README.md`) for reproducibility, not claimed as the only valid one.
3. Blindness is at the prompt-and-code level: prose tells are stripped and the auditor is not told
   clean-versus-buggy. A model can still infer correctness from the code itself, which is the point, that
   inference ("this code is correct, no finding") is the discrimination being measured.
4. The 32 buggy-file findings were not adversarially verified (they hit planted bugs). The verifier was
   spent where it has signal: the clean-file findings.

## Reproduce

```
# Re-assemble the blind tree from the two source fixtures, then strip prose tells:
#   cp the 6 buggy files from fixture-py/ and 7 clean files from fixture-py-clean/ into fixture-py-mixed/
python3 eval/sanitize_mixed.py
# Audit each domain blind into run-1-py-mixed/<domain>.json, combine, verify clean-file findings, score:
python3 eval/score.py --expected eval/fixture-py-mixed.expected.json eval/run-1-py-mixed-findings.json
```

## What this establishes

- Blind recall on Python holds at the TypeScript level (86 percent, genuine-defect higher).
- On correct money code, mixed in with buggy code and unlabelled, the tool's surviving false-positive rate
  is 0: it emitted one plausible false positive and the adversarial verifier refuted it.
- The pipeline (auditor then verifier) is validated end to end on a fixture where BOTH recall and precision
  are live, which no prior run tested at once.
