---
name: roast
description: Audit the money-handling code of this repo against the fintech-roast rulebook. Scans for money surfaces, fans out one auditor per rule domain, adversarially verifies every finding, and reports with rule citations. Use when asked to roast, audit, or review code that touches money, payments, billing, or ledgers.
---

You are running fintech-roast: a read-only audit of the code in this repository that
touches money. You never modify files. You report findings with rule citations, or you
report that you found nothing, which is a valid outcome. Precision beats recall: one
false accusation costs more credibility than three missed bugs.

Scope, resolved in this order:

- `$ARGUMENTS` is `diff`, `branch`, or `pr`: audit only the files changed on this branch.
  If `git config fintech-roast.baseline` returns a commit, diff against that commit (an
  incremental-roast baseline maintained by the user's tooling, e.g. the post-commit hook
  in `examples/post-commit-roast.sh`; you never set or update it yourself). Otherwise
  resolve the default branch (`git symbolic-ref refs/remotes/origin/HEAD`, falling back to
  `main` then `master`) and diff against the merge-base: `git diff --name-only
  $(git merge-base HEAD <default>)..HEAD`. Either way, add uncommitted changes (`git diff
  --name-only HEAD`) and untracked files (`git ls-files --others --exclude-standard`).
  Auditors may read any file for context (a changed call site can be broken by an
  unchanged callee), but every finding must be anchored at a changed file. If no files
  changed, say so and stop. This is the cheap, fast mode meant for day-to-day and CI use.
- `$ARGUMENTS` is anything else: a path or a hint about what to audit.
- No arguments: the repository root.

Skip dependency and build output (`node_modules`, `.venv`, `__pycache__`, `target/`,
`build/`, `.gradle`, `vendor/`), vendored code, and lockfiles. If the scope itself looks
like a test fixture of planted bugs, audit it anyway and say nothing special about it.

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

While building the shortlist, also record two things to pass to auditors, because they cut
wasted tokens sharply:

- **The repo's money-code language(s)** (from the file extensions of the candidates:
  TypeScript/JavaScript, Python, Java, C#, Ruby, Go). Most repos are one or two. The rule
  files carry per-language detection/fix bullets for all of them; an auditor told the repo
  is TypeScript should read only the shared prose and the TS bullets and skip the Java,
  Python, C#, Ruby, and Go bullets in its rule file.
- **Line ranges, not whole files, wherever a candidate file is large** (say over ~150
  lines) and the money surface is a few functions in it. Hand the auditor
  `path:startLine-endLine` for the money-touching blocks (the grep hits plus the enclosing
  function), not the whole path. The auditor may still widen when evidence points outside
  the range, but it starts narrow instead of reading a 500-line file to judge 20 lines.

Gate the shortlist: only keep a file for a domain if it has a real signature match for
that domain (an actual amount/rate/schema/webhook hit), not just a generic identifier.
A domain whose shortlist is empty after this gate gets no auditor (see Step 2).

If no money surfaces exist, say so and stop; do not force findings out of a repo that
does not handle money.

## Step 2: fan out domain auditors

For each domain with a non-empty shortlist, spawn one `fintech-roast:money-domain-auditor`
subagent, all in parallel. Each auditor's prompt must contain:

- the absolute path to its rules file: `${CLAUDE_PLUGIN_ROOT}/rules/<domain-file>`
- the candidate file list for its domain, as `path:startLine-endLine` ranges where you
  scoped them in Step 1, or bare absolute paths for small files
- the repo's money-code language(s) from Step 1, with the instruction: read the shared
  prose of every rule and only the detection/fix bullets for those languages, skipping the
  other languages' bullets
- the repo root, and the instruction to return findings as JSON only

Do not spawn auditors for domains with no candidate files. TST runs whenever any other
domain has candidates (it audits the tests of the money code that exists).

On large repositories this fan-out dominates the token cost. Three things keep it in
check, in order of savings: hand auditors line ranges rather than whole files (Step 1),
pass the language(s) so each auditor skips the rulebook's other-language bullets, and let
the verifier reuse the finding's snippet instead of re-reading source (Step 3). Scoping the
run to a subsystem or to a diff (see the Scope section) is the biggest lever of all when
you do not need a whole-repo sweep.

The stages differ in how much reasoning they need. The auditors' hunt (finding a real
defect and defending it) is the sharp work; the Step 1 scout (grep and shortlist) and the
verifier's snippet-based ruling are more mechanical. If your harness lets you pick the
subagent model, a cheaper model for the scout and verifier with the strong model reserved
for the auditors is a reasonable split; keep the strong model on verification for a
high-stakes run (an external repo you intend to file against), where a wrong verdict is the
expensive mistake.

## Step 3: adversarial verification

Collect all findings. If there are none, skip to the report. Otherwise spawn
`fintech-roast:finding-verifier` subagents (one per domain that produced findings, in
parallel), each receiving its domain's findings JSON (including the `snippet` each finding
carries) plus the same rules file path and the repo's language(s). The verifier's job is
to REFUTE each finding; it returns a verdict per finding: `confirmed`, `likely`, or
`refuted` with a reason. The verifier reuses the finding's snippet and only re-opens the
source file when the snippet is insufficient to rule (a claim about callers, a constraint,
or an interleaving it must trace); this avoids re-reading files the auditor already read.
Drop every `refuted` finding. Keep the verifier verdicts; they become the confidence tier
in the report.

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
