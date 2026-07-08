# roastable-billing

A small, deliberately buggy billing service. It exists as the evaluation fixture for
fintech-roast: money-handling bugs are planted throughout, and the answer key lives in
`../expected.json`.

Do NOT copy anything from this directory into real code.

Two things about it are intentional and part of the point:

- It compiles clean under `tsc --strict` and the test suite is green. The tests only use
  round numbers, a single currency, and happy paths, which is exactly why they catch
  nothing (see rules TST-1, TST-2, TST-3).
- The bugs are the boring, realistic kind that pass code review, not puzzles.
