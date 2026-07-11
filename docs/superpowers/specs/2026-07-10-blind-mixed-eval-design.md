# Design: blind mixed-fixture eval (Python)

## Goal

Run one eval that removes the two biggest caveats hanging over the Python benchmark:

1. `RESULTS-py.md`: recall (100%) was measured on a SCOPED audit (each auditor pointed at the files
   where its bugs live) = generous, not comparable to the TS 86% cold number.
2. `RESULTS-py-clean.md`: false positives (0) were measured on a fixture the auditors were TOLD was a
   clean twin, and the verifier never fired = a skeptic can dismiss it as hinted.

A blind mixed run fixes both at once. Clean and buggy files sit in ONE tree, the auditor is handed the
whole tree with NO hint which files are correct, and the run yields, from a single pass:

- **Recall** on the buggy files (blind, so comparable in spirit to the TS cold scan).
- **False-positive rate** on the clean files (unhinted, the real precision-on-correct-code number).
- The first run where the **adversarial verifier actually has borderline findings to attack.**

## The mixed tree (`eval/fixture-py-mixed/`)

A per-file split: each of the 13 fixture files is assembled from EITHER `fixture-py/` (buggy) OR
`fixture-py-clean/` (clean), copied verbatim. The auditor reads files statically; it never imports or
runs the tree, so the tree does NOT need to be a runnable app (clean and buggy `money.py` have
different signatures and would not co-import). RESULTS will state plainly that the mixed tree is a
read-only audit artifact, not a green-by-design app. The two green-by-design apps continue to live in
`fixture-py/` and `fixture-py-clean/` and prove runnability; the mixed tree exists only to be read.

### The split (locked, deterministic, recorded)

| File | Version | Planted bugs if buggy |
| --- | --- | --- |
| `money.py` | BUGGY | STO-1 x3, ROU-1, API-3 (P01-P05) |
| `db/schema.sql` | BUGGY | STO-1/2/4 x3, IDE-4, TIM-1 (P21-P25) |
| `fx.py` | BUGGY | FX-1/2/3/4 (P12-P15) |
| `ledger.py` | BUGGY | LED-1/2/3/4 (P29-P32) |
| `webhooks.py` | BUGGY | IDE-1/2 (P26-P27) |
| `store.py` | BUGGY | IDE-3 (P28) |
| `invoice.py` | CLEAN | (ROU clean) |
| `split.py` | CLEAN | (ROU clean) |
| `tax.py` | CLEAN | (TAX clean) |
| `interest.py` | CLEAN | (TIM clean) |
| `reports.py` | CLEAN | (AGG clean) |
| `api.py` | CLEAN | (API clean) |
| `test_stateful.py` | CLEAN | (TST clean) |
| `test_money.py`, `test_fiscal.py` | CLEAN | (TST clean, needed so TST auditor has a clean suite to judge) |

**Buggy set = 21 planted bugs** across STO(6), FX(4), IDE(4), LED(4), ROU(1), API(1), TIM(1).

### Why this split is a real test, not a soft one

The value is the domains that are SPLIT across a buggy and a clean file, forcing the auditor to flag
the real bug AND stay quiet on the correct code in the SAME domain:

- **API**: buggy `money.py` carries API-3 (float parse), but `api.py` is clean. The API auditor must
  catch the money.py bug and not cry wolf on the correct canonical wire shape in api.py.
- **ROU**: buggy `money.py` carries ROU-1 (bare round), but `invoice.py` + `split.py` are clean. Must
  flag money.py, leave the correct single-rounding + largest-remainder split alone.
- **TIM**: buggy `schema.sql` carries TIM-1 (naive timestamp), but `interest.py` is clean. Must flag
  the schema, leave the correct calendar-date day math alone.
- **STO/FX/IDE/LED**: buggy files only (recall), **TAX/AGG**: clean files only (precision).

A domain that is buggy-in-one-file and clean-in-another is exactly the discrimination a real codebase
demands, and it is where a pattern-matching linter (fires on `round`, `float`, `TIMESTAMP`) breaks.

## Method

Same 10-domain-auditor recipe as the two prior runs, waves of <= 3 ([[sub-agent-fanout-cap]]):

1. Each auditor gets its domain rule file + the mixed-tree files where its domain applies (the SAME
   file lists as before, now pointing at `fixture-py-mixed/`), and audits **blind**: the prompt does
   NOT say which files are clean or buggy, does NOT say the tree is a twin of anything. It is told only
   "audit this billing app against your domain," the normal roast framing.
2. Findings accumulate into `eval/run-1-py-mixed/<domain>.json`, combined to
   `eval/run-1-py-mixed-findings.json`.
3. **Adversarial verifier pass** (this is the run where it earns its cost): every finding that fires
   goes to the `finding-verifier` (waves of <= 3), which tries to REFUTE it. A finding is CONFIRMED
   only if it survives. This filters the auditors' borderline calls on the clean files.
4. **Score** with `eval/score.py --expected` against a NEW answer key `fixture-py-mixed/expected.json`
   that lists ONLY the 21 buggy-set bugs (paths rewritten to `fixture-py-mixed/...`). Then:
   - Recall = confirmed findings matching a planted bug / 21.
   - False positives = confirmed findings on a CLEAN file (no planted bug there) = the real FP count.
   - Verifier value = how many auditor findings on clean files it refuted before scoring.

## Numbers this produces

- **Blind recall / 21** (comparable in spirit to TS cold 86%; expect some ledger-cluster misses like TS).
- **False positives on clean files** post-verifier (the unhinted precision number).
- **Verifier refutation count** (finally a non-zero verifier signal).

## Deliverables

- `eval/fixture-py-mixed/` (13 files, copied verbatim from the two fixtures per the split) + a short
  `README.md` in it stating the split and "read-only audit artifact."
- `eval/fixture-py-mixed/expected.json` (21 buggy-set bugs, paths rewritten).
- `eval/run-1-py-mixed/*.json` + `eval/run-1-py-mixed-findings.json` + a `*-verified.json`.
- `eval/RESULTS-py-mixed.md` (headline numbers + method + honest caveats).
- Commits petit-a-petit: (1) the mixed fixture + answer key, (2) the eval run + verifier + results.
  `validate_rules.py` green + no em/en dash before each. No CI job (read-only artifact, nothing to run).

## Honest caveats to state in RESULTS

1. The mixed tree is a read-only audit artifact, not a runnable app (the two runnable apps stay).
2. One split, one seed. A different split could move the numbers; the split is recorded for
   reproducibility, not claimed as the only valid one.
3. Blindness is at the PROMPT level (auditor is not told clean-vs-buggy). A model could still infer
   correctness from the code itself, which is the POINT: inferring "this code is correct, no finding"
   is exactly the discrimination we want to measure.
