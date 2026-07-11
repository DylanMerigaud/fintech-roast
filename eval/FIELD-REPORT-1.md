# Field report 1: a real production codebase

The evals in this directory are planted-bug fixtures: bugs we wrote, found by the tool we
built. This is the first run on code nobody wrote to be found. The target is a mature,
production B2B platform in the spend-management space (Java/Spring/JPA monorepo with a
TypeScript/Next.js frontend, five-figure file count, strong engineering conventions:
BigDecimal everywhere, canonical NUMERIC scale, checkstyle, architecture tests), audited
with permission. It is deliberately not identified, so unlike the fixture results this
report is not reproducible; read it as a methods-and-numbers account, not as a scoreboard
you can verify.

## Numbers

Two runs, July 2026, roughly 2.2M subagent tokens total.

**Run A, scoped pilot.** Six domains, ~40 hand-shortlisted files from the money core.
3 findings emitted, 3 refuted by the adversarial pass, 0 reported. The refutations were
correct on inspection (an unreachable rounding mode, an exact float round-trip, a
documented derived column).

**Run B, full surface.** All ten domains plus the frontend, the ERP integration layer,
the message consumers, and the test suites. 11 auditors, then one verifier per domain
with findings.

| | count |
| --- | --- |
| findings emitted by auditors | 36 |
| confirmed by the adversarial pass | 18 |
| likely (real pattern, impact indirect or unproven) | 4 |
| refuted before reporting | 14 |

Severity of the 18 confirmed: 1 critical, 11 high, 6 medium. Verdicts are
adversarially verified, not human-verified; the repo owner reviewed the report and
recognized the confirmed findings as real.

## What the confirmed findings looked like (genericized)

- **Critical, concurrency.** Applying a credit note reads the remaining balance from a
  derived snapshot with no lock; the optimistic-version guard sits on a different entity
  that the flow never writes. Two concurrent applications each consume the full balance.
  The junction table also lacks the unique constraint that would have been the backstop.
- **Duplicate money records on redelivery.** An auto-ack queue consumer with no
  processed-message dedup; a crash between commit and ack re-creates a payable invoice.
  The plausible refutation (a unique constraint on the import bookkeeping table) was
  traced and eliminated: that path is an UPDATE by primary key.
- **Tax rate mis-selection.** A user-facing line-merge feature pools every line's net
  amount and applies the first line's tax rate, with no same-rate guard at any layer.
  The persistence hook recomputes tax from the same copied rate, so it re-derives the
  wrong number rather than fixing it.
- **Divide-before-multiply.** A discrepancy percentage for invoice-to-order matching is
  computed as divide-then-scale at the dividend's scale, then truncated: discrepancies
  under ~1% evaluate to 0% and skip the review workflow. Permissive direction.
- **Sync inferring deletions from offset pages.** An ERP sync walks page numbers against
  live data and marks anything unseen as deleted. The safety threshold reads its counter
  before anything writes it (never fires), and a phantom-deleted record is never
  resurrected because the next sync short-circuits on an unchanged content hash.
- **Frontend money parsing.** The app-wide amount parser is `parseFloat` with a
  first-comma-only replace: a US-formatted `1,234.56` silently becomes `1.234` on paths
  whose validation gate accepts it, an unparseable spreadsheet cell silently submits a
  zero price, and line totals are accumulated in raw float arithmetic before being
  submitted (a precise-sum helper existed in the codebase, unused on that path).
- **Wire format.** The external public API serializes fractional money as bare JSON
  numbers (no string serializer configured), and one external DTO carries an amount with
  no currency in a multi-currency product.
- **Tests.** Suite-wide round-number fixtures (the one test of a pro-rata division passes
  identically under any rounding mode), one or two 2-decimal currencies everywhere while
  a zero-decimal currency is reachable into hardcoded scale-2 paths, and no property
  tests: the audited proration provably leaks 0.01 on a 100-over-3-periods split with no
  conservation check anywhere.

## What the verifier killed, and why that matters

14 of 36 plausible-sounding findings died before the report. The kills were not
hand-waving; each one traced a concrete mechanism:

- Every timezone finding died on one fact: the deployment pins UTC at startup, which is
  the rule's own first false-positive note.
- Every ledger-mutation finding died on gating and ground truth: the "mutate the posted
  entry" path was opt-in, carried unchanged amounts, targeted a system that enforces its
  own period locks and audit notes, and the append-only reversal pattern existed for the
  cases that change money.
- Two float-boundary findings died on the shortest-decimal round-trip argument: for
  amounts below 16 significant digits, the double bridge is exact in both directions, so
  no inexact value can reach persisted money. The same standard was then applied
  consistently to kill a third finding in another domain.
- One rounding-mode finding died on scale analysis: every reachable input was already at
  final scale, so the "wrong" mode could never fire.

Two verifier passes found the defect was worse than the auditor claimed (a guard that
never fires; a missing resurrection path). The pass is not a rubber stamp in either
direction.

## Lessons

1. **Sampling decides the verdict.** Run A audited the best-defended files and reported
   nothing; Run B audited the full surface and confirmed 18. A clean scoped roast of a
   mature core says little about the frontier: integrations, frontends, merge/edge
   features, and tests are where the bugs lived.
2. **The bugs were where types cannot reach.** The codebase's BigDecimal/NUMERIC
   discipline was excellent, and it prevented none of the confirmed findings. They were
   concurrency, rate selection, truncation order, sync semantics, parsing, and test
   blindness: exactly the rulebook's semantic rules, and exactly what a type-checker or
   a grep-based linter cannot see.
3. **The verifier earned its cost.** Reporting 36 raw findings would have cost the tool
   its credibility on the 14 wrong ones. A ~39% kill rate on production code, each kill
   with a mechanism, is the number that makes the report usable.
4. **Rulebook feedback.** Two refutation patterns are general enough to become
   false-positive notes: "already at final scale, the mode never fires" (rounding), and
   the shortest-decimal exactness standard for double bridges (storage/API/tax domains).

Findings are rule-based and adversarially verified, but not human-verified. Read the
cited rule before acting; every rule documents its false positives.
