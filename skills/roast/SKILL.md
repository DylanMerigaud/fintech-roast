---
name: roast
description: Audit the money-handling code of this repo against the fintech-roast rulebook. Scans for money surfaces, fans out one auditor per rule domain, adversarially verifies every finding, and reports with rule citations. Use when asked to roast, audit, or review code that touches money, payments, billing, or ledgers.
---

You are running fintech-roast: a read-only audit of the code in this repository that
touches money. You never modify files. You report findings with rule citations, or you
report that you found nothing, which is a valid outcome. Precision beats recall: one
false accusation costs more credibility than three missed bugs.

Scope: `$ARGUMENTS` if provided (a path or a hint about what to audit), otherwise the
repository root. Skip dependency and build output (`node_modules`, `.venv`, `__pycache__`, `target/`, `build/`, `.gradle`, `vendor/`), vendored code, and lockfiles. If the
scope itself looks like a test fixture of planted bugs, audit it anyway and say nothing
special about it.

**Finding the rulebook.** The rule files ship with this plugin under a `rules/` directory
next to this skill's plugin root, referenced below as `${CLAUDE_PLUGIN_ROOT}/rules/`. If
that variable is already an absolute path on disk, use it directly. If it appears as the
literal text `${CLAUDE_PLUGIN_ROOT}`, resolve the plugin root first: this plugin lives in
the Claude plugin cache (typically under `~/.claude/plugins/`), so glob for a `rules/`
directory that contains `storage-and-types.md` and `README.md` and use that absolute path
everywhere below (including the paths you hand to subagents). Do this resolution once, up
front, before Step 1.

## Step 1: scan for money surfaces

Find where money lives before reading anything deeply. Grep the scope (case-insensitive)
for identifier signals: `amount|price|total|balance|fee|invoice|payment|payout|refund|
charge|billing|ledger|currency|tax|rate|settle|payin|payout|wallet`, and for surface
signals:

- schema and migrations: `CREATE TABLE`, `ALTER TABLE`, ORM models with money-ish columns (JPA `@Entity`/`@Column`, Django/SQLAlchemy models, Prisma schema, Sequelize/GORM)
- webhook handlers: routes or functions handling `stripe|paypal|adyen|webhook|event`
- calculation modules: functions doing arithmetic on the identifiers above
- API serialization: response builders, GraphQL schemas, JSON encoders touching amounts
- FX and conversion: `rate|convert|exchange|fx`
- time-based money: `interest|accru|prorat|period|statement|billing_cycle`
- tests covering any of the above

Build a shortlist of candidate files grouped by rule domain. The domain list and its
rules live in `${CLAUDE_PLUGIN_ROOT}/rules/README.md` (read it now): STO storage-and-types,
ROU rounding-and-allocation, IDE idempotency-and-concurrency, LED ledger-design, FX
fx-and-multicurrency, TIM time-and-dates, AGG aggregation-and-reporting, TAX taxes,
API api-and-serialization, TST testing.

If no money surfaces exist, say so and stop; do not force findings out of a repo that
does not handle money.

## Step 2: fan out domain auditors

For each domain with a non-empty shortlist, spawn one `fintech-roast:money-domain-auditor`
subagent, all in parallel. Each auditor's prompt must contain:

- the absolute path to its rules file: `${CLAUDE_PLUGIN_ROOT}/rules/<domain-file>`
- the candidate file list for its domain (absolute paths)
- the repo root, and the instruction to return findings as JSON only

Do not spawn auditors for domains with no candidate files. TST runs whenever any other
domain has candidates (it audits the tests of the money code that exists).

## Step 3: adversarial verification

Collect all findings. If there are none, skip to the report. Otherwise spawn
`fintech-roast:finding-verifier` subagents (one per domain that produced findings, in
parallel), each receiving its domain's findings JSON plus the same rules file path. The
verifier's job is to REFUTE each finding; it returns a verdict per finding: `confirmed`,
`likely`, or `refuted` with a reason. Drop every `refuted` finding. Keep the verifier
verdicts; they become the confidence tier in the report.

## Step 4: report

Print a report, grouped by severity (critical, high, medium, low), each finding as:

```
<SEVERITY> <RULE-ID> <file>:<line> [confirmed|likely]
  <one-line statement of the defect>
  evidence: <short quote or paraphrase of the offending code>
  fix: <one-line direction>
  rule: <rule title> (see rules/<domain-file> for sources)
```

Close with: counts per severity and per tier, the domains audited, the domains skipped
for lack of surface, and this honesty note verbatim: "Findings are rule-based and
adversarially verified, but not human-verified. Read the cited rule before acting; every
rule documents its false positives."

Never auto-fix. Never open PRs or issues. If the user wants fixes, they ask separately.
