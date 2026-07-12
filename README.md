# fintech-roast

[![ci](https://github.com/DylanMerigaud/fintech-roast/actions/workflows/ci.yml/badge.svg)](https://github.com/DylanMerigaud/fintech-roast/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

An agent that roasts the code that touches money.

![fintech-roast running over the eval fixture](assets/roast-demo.gif)

<sub>A replay of the run scored in [eval/RESULTS.md](eval/RESULTS.md) (53 findings over the
planted-bug fixture). Real rule ids and file lines; the full report is checked in at
[docs/sample-report.md](docs/sample-report.md).</sub>

It scans a repository for the surfaces where money lives (schemas, webhooks, calculation
code, serialization), audits each against a sourced rulebook of how money-handling code
actually breaks, adversarially verifies every finding, and reports what survives with the
rule and the sources behind it. It is read-only: it never edits your code, opens PRs, or
files issues.

## Quickstart

It is a [Claude Code](https://claude.com/claude-code) plugin, so it runs on your own Claude
session; there is no API key to configure.

```
/plugin marketplace add DylanMerigaud/fintech-roast
/plugin install fintech-roast@fintech-roast
```

Then, in the repo you want audited:

```
/fintech-roast:roast           # full-repo audit
/fintech-roast:roast diff      # only the files changed on this branch
/fintech-roast:roast src/billing   # a specific path
```

What to expect before you run it:

- **Output.** [docs/sample-report.md](docs/sample-report.md) is a complete, real report
  (the run 1 findings on the TypeScript fixture). That shape, with rule
  citations, is exactly what you get. "No findings" is a valid outcome; it does not force
  findings out of a repo that has no money code.
- **Cost and time.** A full-repo roast fans out one auditor per rule domain plus one
  verifier per domain that found something, so up to ~20 subagent runs on your session.
  On a mid-size repo, budget tens of minutes and a meaningful slice of your usage. `diff`
  mode audits only what changed on your branch and is the cheap, day-to-day invocation.
- **A guaranteed first run.** If you want to see it work before pointing it at your own
  code, clone this repo and run `/fintech-roast:roast eval/fixture`. The fixture has 37
  planted bugs, so the first run cannot come back empty.

## Why this exists, and what it is not

Most "AI code review" for money is a single prompt that pattern-matches on "float" and
calls it a day. The value here is not the prompt, it is **the rulebook**: 41 rules across
10 domains, with per-language detection and fixes for JavaScript/TypeScript, Python, and Java,
each one researched against primary sources (specs, standards, tax-authority
manuals, canonical engineering literature), each one carrying its own false-positive notes,
and each one put through an adversarial pass whose only job was to refute it. The agent is
just the mechanism that applies the rulebook to your code.

The authority is meant to come from findings you can check and rules you can cite, not from
a claim of expertise. Findings are rule-based and adversarially verified by a second agent;
they are not a substitute for a human who owns the money path. Read the cited rule before
you act on a finding. Every rule documents where it cries wolf.

Building in public: the rulebook, the plugin, and the benchmarks are all here, misses
included. Languages covered today are JavaScript/TypeScript, Python, and Java (Spring Boot
/ JPA / BigDecimal), each backed by its own eval fixture; Go and Ruby are not covered yet.

## The rulebook

41 rules, in [`rules/`](rules/). Each rule: what to detect, why it breaks (with real
incidents where they exist), the fix, its false positives, and at least two authoritative
sources. Format contract and severity scale in [`rules/README.md`](rules/README.md).

| Domain | Rules | A few of the failures it catches |
| --- | --- | --- |
| [Storage and types](rules/storage-and-types.md) | STO-1..8 | float money, wrong DECIMAL scale, ambiguous minor units, missing currency, hardcoded 2 decimals, type overflow, exact-decimal built from a float, BigDecimal equals vs compareTo |
| [Rounding and allocation](rules/rounding-and-allocation.md) | ROU-1..4 | implicit rounding mode, splits that do not sum to the total, order-dependent discount/tax, divide-before-multiply |
| [Idempotency and concurrency](rules/idempotency-and-concurrency.md) | IDE-1..4 | non-idempotent webhooks, missing idempotency keys, balance read-modify-write races, no unique constraint backstop |
| [Ledger design](rules/ledger-design.md) | LED-1..4 | mutating posted entries, single-entry money movement, drifting cached balances, no audit trail |
| [FX and multi-currency](rules/fx-and-multicurrency.md) | FX-1..4 | round-trips assumed lossless, rates applied without capture, original amount discarded, cross-currency arithmetic |
| [Time and dates](rules/time-and-dates.md) | TIM-1..4 | period math in the server zone, DST-naive day counts, ambiguous statement boundaries, hardcoded day-count basis |
| [Aggregation and reporting](rules/aggregation-and-reporting.md) | AGG-1..3 | float sums, precision lost at ORM/JSON boundaries, paginated aggregation that double-counts |
| [Taxes](rules/taxes.md) | TAX-1..3 | line vs document rounding level, inclusive/exclusive confusion, float tax rates |
| [API and serialization](rules/api-and-serialization.md) | API-1..4 | money as a JSON number, GraphQL Float, parseFloat on input, no canonical cross-service shape |
| [Testing money code](rules/testing.md) | TST-1..3 | no property tests on invariants, round-number fixtures, one happy currency |

## How a roast works

The `/fintech-roast:roast` skill scans the scope for money surfaces, fans out one auditor
subagent per rule domain that has surface, then spawns an adversarial verifier per domain
whose only job is to refute the findings. Refuted findings are dropped; what survives is
reported with severity, a confidence tier from the verifier, evidence, a fix direction,
and the rule citation. The pipeline and the report format live in
[`skills/roast/SKILL.md`](skills/roast/SKILL.md).

### Run it on every PR

[`examples/fintech-roast.yml`](examples/fintech-roast.yml) is a GitHub Actions recipe that
runs the diff-scoped roast on pull requests touching money paths and posts the report as a
PR comment, via [claude-code-action](https://github.com/anthropics/claude-code-action).
Two things to know: in CI it bills per-token against an `ANTHROPIC_API_KEY` repo secret
(not a Claude subscription), and the recipe is young; if it misbehaves,
[open an issue](https://github.com/DylanMerigaud/fintech-roast/issues).

### Roast every commit

[`examples/post-commit-roast.sh`](examples/post-commit-roast.sh) is a git post-commit hook
that roasts each commit's diff in the background on your own Claude session, using a
`fintech-roast.baseline` git config key as an incremental marker so every commit is
roasted exactly once. Opt-in per clone; each run spends your session usage.

## Evaluation

[`eval/`](eval/) holds a deliberately buggy billing service with money bugs planted across
all ten domains, and an answer key. The fixture compiles clean and its tests pass, because
the tests use round numbers and one currency, which is the point (see TST-2, TST-3). The
scorer (`eval/score.py`) measures how many planted bugs the agent finds and how many of its
findings land on a real planted bug. There is a fixture per language, each with 37 planted
bugs across the ten domains: TypeScript ([`eval/fixture/`](eval/fixture/)), Python
([`eval/fixture-py/`](eval/fixture-py/)), and Java + Spring Boot + JPA
([`eval/fixture-java/`](eval/fixture-java/)). Per-language runs are tracked separately, each
with its own method and caveats so the numbers are not read out of context:

| Language | Fixture | Method | Recall | Report |
| --- | --- | --- | --- | --- |
| TypeScript | [`eval/fixture/`](eval/fixture/) | cold full-repo scan | 86 percent | [RESULTS.md](eval/RESULTS.md) |
| Python | [`eval/fixture-py/`](eval/fixture-py/) | audited per domain | 37 / 37 | [RESULTS-py.md](eval/RESULTS-py.md) |
| Python, blind mixed | [`eval/fixture-py-mixed.README.md`](eval/fixture-py-mixed.README.md) | blind, clean and buggy files mixed | 86 percent, 0 surviving false positives | [RESULTS-py-mixed.md](eval/RESULTS-py-mixed.md) |
| Java | [`eval/fixture-java/`](eval/fixture-java/) | audited per domain | 36 / 37 | [RESULTS-java.md](eval/RESULTS-java.md) |

The per-domain runs are a scoped audit (each auditor is pointed at its domain's files) and so
are not directly comparable to the TypeScript cold scan; a cold scan is expected to be lower.
The honest version, including the misses and the limits of each run, stays in the repo.

The fixtures are bugs we planted ourselves. Two runs on real production code are written
up alongside them:

- [`eval/FIELD-REPORT-1.md`](eval/FIELD-REPORT-1.md): a private codebase (with permission,
  anonymized). 36 findings emitted, 18 confirmed (1 critical), 14 refuted by the
  adversarial pass, and the lesson that a scoped roast of a well-built core reports clean
  while the full surface does not.
- [`eval/FIELD-REPORT-2.md`](eval/FIELD-REPORT-2.md): [medusajs/medusa](https://github.com/medusajs/medusa)
  at a pinned commit, so it is fully reproducible. 16 emitted, 4 confirmed (a
  check-then-act concurrency cluster), 2 likely, 10 refuted, several of the refutations
  turning on the same false-positive notes the rulebook documents. The confirmed cluster
  was filed upstream with a failing test:
  [medusajs/medusa#16012](https://github.com/medusajs/medusa/issues/16012).

## Contributing

The rules are claims about how money code breaks. If one is wrong, overstated, or missing a
jurisdiction nuance, [say so](CONTRIBUTING.md). That is the most valuable thing you can do
here.

## License

MIT.
