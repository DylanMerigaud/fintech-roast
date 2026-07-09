# Evaluation results

The plugin's auditors, run against the planted-bug fixture in [`fixture/`](fixture/), scored
against [`expected.json`](expected.json). This is the first measurement, zero tuning. The
honest version, misses included, lives here and moves as the plugin improves.

## Run 1 (2026-07-08, no tuning)

10 domain auditors over the fixture, then one adversarial verifier per domain. 53 findings
reported, scored against 35 planted bugs.

| Metric | Value | What it means |
| --- | --- | --- |
| Recall | 30 / 35 = **86%** | planted bugs the auditors found |
| Precision (strict) | 44 / 53 = **83%** | findings that hit a planted bug at the exact file the answer key indexed |
| Precision (genuine defect) | 53 / 53 = **100%** | findings that point at a real money defect, counting a rule flagged at a different-but-valid location |

The gap between the two precision numbers is a scoring artifact, not false positives. The
scorer (`score.py`) matches on rule id plus file. The nine findings it counts as off-target
are all cases where the auditor flagged a real instance of the rule at a location the answer
key did not enumerate (for example, the missing-audit-trail defect LED-4 exists both in
`ledger.ts` and in the schema; the auditor flagged the schema, the key indexed the code).
Every one of the 53 findings maps to a genuine planted defect.

## What it missed (5 of 35)

- **P13 (IDE-3)** balance updated via read-modify-write in `webhooks.ts` + `store.ts`. The
  auditor caught the read-modify-write in `ledger.ts` instead, and missed the webhook path.
- **P16 (LED-2)** single-entry money movement, no counterparty account, in `ledger.ts`. The
  auditor flagged LED-2 on the schema (no debit/credit columns) but did not call the
  single-entry `postEntry` in the code.
- **P17 (LED-3)** cached balance never reconciled to entries, in `ledger.ts`.
- **P18 (LED-4)** corrections leave no audit trail, in `ledger.ts`.
- **P32 (API-4)** two endpoints return money in different shapes (cents vs decimal) with no
  canonical representation.

The ledger cluster (LED-2/3/4) is the clear weak spot: the auditor found these defects in
the schema but did not connect them to the specific code paths, so the code-anchored planted
bugs read as missed. A tighter auditor prompt that cross-references schema findings into the
code is the obvious next improvement.

## Honest caveats

- **The adversarial pass refuted nothing this run (0 of 53).** On a fixture this dense (every
  file carries several real bugs) there was little for a verifier to refute, so this run does
  not tell us how well the refutation stage suppresses false positives on clean code. That is
  exactly what it exists for, and it is untested here. The real test is a low-signal codebase
  where most flags should die.
- **100% genuine-defect precision does not generalize.** It says the auditors did not
  hallucinate bugs into a file built to be full of them. It says nothing about the false
  positive rate on production code that is mostly correct, which is the number that decides
  whether this tool is usable in public. That number comes from the real-repo benchmark
  (Phase 3), not from this fixture.
- **35 planted bugs is a small n.** Recall of 86% here is a first data point, not a
  guarantee.

## How to reproduce

The plugin's `roast` skill runs the same auditors. To re-score a run, capture its findings
as `{"findings": [{"rule", "file", "line", ...}]}` and run:

```
python3 eval/score.py <findings.json>
```
