# Execution plan

The remaining roadmap, written so any session (or a cheaper model) can execute any task
cold. Each task states its context, exact steps, verification, and done-criterion. Tasks
are ordered by dependency; within a phase they are independent unless stated. House rules
that apply to every task: plain-ASCII punctuation everywhere (CI enforces it via
`python3 scripts/validate_rules.py`, which also scans `scripts/`), one rule change per PR,
rule edits keep two authoritative sources, and nothing that identifies the private
codebase from field report 1 (no company name, no file paths, no ERP vendor names; say
"spend-management space" if it must be referenced).

## Phase 1: close the Medusa campaign

Context: an audit of medusajs/medusa at commit `917ddbe0e56b4e739fa828140cd7973d823d1bbd`
ran in July 2026 (6 domains: ROU, STO, TAX, IDE, AGG, API over the money core: BigNumber
totals, promotion allocation, tax-inclusive pricing, payment webhooks/captures, campaign
budget usage, minor-unit conversion, API serialization). Findings were adversarially
verified per domain.

1. **Write `eval/FIELD-REPORT-2.md`.** Unlike field report 1 this one is reproducible:
   name the repo, pin the commit SHA, list per-domain emitted/confirmed/likely/refuted
   counts, describe each surviving finding with file and line, and each refutation with
   its mechanism. Reuse the structure of `eval/FIELD-REPORT-1.md` (numbers table, findings
   section, verifier-kills section, lessons). State the method honestly: shortlisted
   money-core files, not a cold full-repo scan. Link it from README's Evaluation section
   next to the field report 1 sentence. Done when: report committed, README links it,
   `validate_rules.py` still passes.
2. **Human verification pass.** The repo owner (Dylan) reads each confirmed finding
   against the Medusa source at the pinned commit and marks it real or wrong. This gate
   is manual on purpose; no model files anything upstream. Done when: each finding in the
   report carries a `human: verified|rejected` marker.
3. **File upstream issues.** For each human-verified finding: one GitHub issue on
   medusajs/medusa, polite, with the rule citation, the code reference at the pinned SHA,
   a concrete failing scenario, and the fix direction. No mention of "AI" needed; the
   finding stands on its evidence. Track issue URLs in the field report. Done when: every
   verified finding has an issue URL or an explicit decision not to file (with reason).

## Phase 2: launch assets (start only after phase 1 task 3)

4. **Update the sample-report story.** `docs/sample-report.md` currently shows the
   fixture run. Add a short section at the top linking both field reports as "what it
   finds on real code". Done when: sample report links both field reports.
5. **Launch post.** Draft `docs/launch/show-hn.md`: title options ("Show HN: a sourced
   rulebook of how money code breaks, applied by an agent that verifies its own
   findings"), 300-500 word body leading with field-report numbers (18 confirmed on a
   production codebase, N on Medusa with links to accepted issues), honest limits
   paragraph (self-planted evals, verifier not human, languages covered). No em-dashes,
   no marketing fluff. Done when: draft committed; posting is the owner's manual call.
6. **Directory listings.** Submit the plugin to awesome-claude-code and any active
   Claude Code plugin directories (search current lists at execution time; they change).
   Done when: PRs opened to at least two lists.

## Phase 3: product depth (independent of phase 2)

7. **Semgrep free tier.** Extract the mechanically-detectable subset of the rulebook
   into `lint/` as Semgrep rules: STO-1 (float money columns in migrations), API-3
   (parseFloat/Number on amount-named inputs), API-2 (GraphQL Float on money fields),
   TST has no lintable subset. Each Semgrep rule cites its rulebook id in `metadata`.
   Add a CI job running the pack against `eval/fixture*` and asserting the known lintable
   plants are hit (extend `eval/expected.json` with a `lintable: true` flag on those
   entries rather than a new answer key). README gets a "free tier" section: run the
   Semgrep pack in pre-commit for the pattern-matchable rules; the agent exists for the
   semantic ones. Done when: pack exists, CI job green, README section added.
8. **npm decision.** Either give the package a consumer (ship the Semgrep pack + rules in
   the npm tarball, document "vendor the rulebook into your own agents/CI") or deprecate
   the npm publish. Decide based on whether task 7 shipped; if yes, publish v0.1.0 with
   `lint/` included in `files`. Done when: package.json `files` and README agree on what
   npm is for, or the release workflow is removed.
9. **Second-opinion verification mode.** Add an optional skill argument
   (`/fintech-roast:roast paranoid`) that runs TWO verifiers per finding-domain with
   different lenses (refute-on-reachability vs refute-on-impact) and only reports
   findings both keep. Update SKILL.md step 3 and the README plugin section. Rationale
   from the field runs: single verifiers were right, but the expensive mistakes are
   asymmetric. Done when: SKILL.md documents the mode and the fixture run still finds
   the planted bugs in default mode.

## Phase 4: coverage growth (backlog, any order)

10. **Go rulebook column.** Add per-language detection/fix bullets for Go to each rule
    where Go has a distinct idiom (money as int64 minor units, shopspring/decimal,
    math/big.Rat pitfalls, encoding/json float64 unmarshaling). One rule per PR, two
    sources each. Build `eval/fixture-go/` mirroring the 37-bug structure only after the
    rules land.
11. **Ruby rulebook column**, same contract (BigDecimal, Money gem, ActiveRecord decimal
    columns, JSON float parsing).
12. **Field report 3 target.** Next OSS run candidate: a Python money codebase (ERPNext
    accounting module or Odoo account module), scoped the same way. Prerequisite: none,
    but stagger after phase 1 issues get maintainer reactions, so the method can absorb
    feedback.

## Standing constraints for executors

- The skill and agents are read-only by contract; any state (baselines, reports) is
  written by user-owned hooks, never by the skill.
- Every claim about how money breaks needs a source; every detection pattern needs a
  false-positive note. CONTRIBUTING.md is the contract.
- Cost expectations in docs are mechanics-based (what fans out), never invented numbers.
- Anything learned from a private codebase stays genericized per the field-report-1
  standard.
