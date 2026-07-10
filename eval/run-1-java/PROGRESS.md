# J3 eval run-1-java: COMPLETE (all 10 domains)

Per-domain auditor agents, dispatched ONE AT A TIME (serial, one sub-agent per domain),
each reading only its domain rule file + the fixture files where that domain's bugs live,
auditing blind (never sees expected.json), writing findings JSON to this dir.

## All 10 domains done

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
| API    | api.json        | 4        | 2/3           |
| TST    | tst.json        | 3        | 3/3           |

Combined: `run-1-java-findings.json` (54 findings, 10 domains).

## Final score vs the 37-bug key

- Recall: 36/37 (97 percent)
- Precision vs key: 52/54 (96 percent)
- Missed: P34 API-4 (auditor flagged API-4 on Money.java, not the cross-endpoint Api.java instance).
- Off-key (both defensible, not false positives): STO-3 on Money.java (alt of STO-5), API-4 on Money.java.

Written up in eval/RESULTS-java.md.

## Next (J4)

- README claims Java with its benchmark number (97 percent), so the rulebook is fully trilingual
  with three benchmarks (TS 86, Python 37/37 scoped, Java 36/37 scoped). Keep the scoped-audit
  caveat explicit so TS-86 and the scoped numbers are not conflated.
- Later: a clean-code FP fixture + the adversarial verifier pass; a cold full-repo Java scan.
