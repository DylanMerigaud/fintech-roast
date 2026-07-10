# J3 eval run-1-java: progress (paused after TAX)

Per-domain auditor agents, dispatched ONE AT A TIME (serial, one sub-agent per domain),
each reading only its domain rule file + the fixture files where that domain's bugs live,
auditing blind (never sees expected.json), writing findings JSON to this dir.

## Done: 8 of 10 domains

| domain | file            | findings | domain recall |
|--------|-----------------|----------|---------------|
| STO    | sto.json        | 13       | 6/6           |
| ROU    | rou.json        | 5        | 4/4           |
| IDE    | ide.json        | 7        | 4/4           |
| LED    | led.json        | 4        | 4/4           |
| FX     | fx.json         | 4        | 4/4           |
| TIM    | tim.json        | 9        | 4/4           |
| AGG    | agg.json        | 2        | 2/2           |
| TAX    | tax.json        | 3        | 3/3           |

Combined so far: `run-1-java-findings.json` (47 findings, 8 domains).
Partial score vs the full 37-bug key: 31/37 found (84% recall), 46/47 on target (98% precision).
The only "missed" 6 are the API (3) + TST (3) bugs, not run yet.
The one off-key finding is a defensible STO-3-vs-STO-5 alternative classification on Money.java, not a false positive.
Every domain audited hit FULL recall for its own bugs.

## Remaining: 2 domains

- API auditor -> api.json. Rule file: rules/api-and-serialization.md.
  Fixture files: Api.java, Money.java. Expected: P33 API-1, P01 API-3, P34 API-4.
- TST auditor -> tst.json. Rule file: rules/testing.md.
  Fixture files: all *Test.java (MoneyTest, InvoiceTest, SplitTest, TaxTest, FxTest, InterestTest, StoreTest, LedgerTest, WebhookServiceTest, ApiTest, ReportsTest).
  Expected: P35 TST-1 (no jqwik property tests), P36 TST-2 (round-only fixtures), P37 TST-3 (single currency, no negatives).

## To finish (next session)

1. Run the API auditor, then the TST auditor (same one-at-a-time pattern, prompts mirror the 8 above).
2. Recombine all 10 into run-1-java-findings.json, re-score with:
   `python3 eval/score.py --expected eval/fixture-java/expected.json eval/run-1-java/run-1-java-findings.json`
3. Hand-verify any off-key findings, write eval/RESULTS-java.md (mirror RESULTS-py.md: recall/precision, honest caveats).
   Note the caveat: this is a scoped-per-domain audit (each auditor is told its domain + files), so recall is generous vs a cold full-repo scan, same caveat as RESULTS-py.md.
4. Then J4: README claims Java with its benchmark number (rulebook fully trilingual, 3 benchmarks).
