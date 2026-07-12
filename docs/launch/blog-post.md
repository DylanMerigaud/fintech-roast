# Blog post draft (dev.to and Medium)

Same story as the Show HN post, expanded. Reuse the body on both dev.to and Medium.
Suggested title: "A rulebook of how money code breaks, and an agent that refutes its own
findings". Tags for dev.to: `ai`, `fintech`, `codereview`, `typescript`.

---

## Money bugs pass review

Money bugs are rare per repository and expensive when they happen. Rounding that loses a
cent per invoice, a webhook that captures a payment twice on retry, a cached balance that
quietly drifts from the ledger. These do not look like bugs in review. The code compiles,
the tests pass, and the tests pass precisely because they use round numbers and one
currency, which is itself one of the failure modes.

Most "AI code review" aimed at this problem is a single prompt that pattern-matches on
`float` and calls it a day. That catches the easy cases and misses the part that actually
costs money, which is semantic and spread across files: an allocation that does not sum to
its total, a counter updated without a lock, a tax total rounded at the wrong level.

## Put the value in a rulebook, not a prompt

fintech-roast is built the other way around. The product is a rulebook of 41 rules across
10 domains: storage and types, rounding and allocation, idempotency and concurrency, ledger
design, FX, time and dates, aggregation, taxes, API serialization, and testing. Each rule
has per-language detection and fixes for TypeScript, Python, and Java, at least two sources
you can check (language specs, ISO standards, tax-authority manuals, engineering write-ups
from practitioners), and its own false-positive notes documenting where it cries wolf.

A rule is a claim you can check, not a regex. So a human can read the reasoning and decide
instead of trusting the tool. The same rule keeps working when the executor is a cheaper
model next year. And when a rule is wrong, you can argue with the specific claim.

An example, abbreviated. Rule ROU-2, pro-rata allocation that loses or creates cents:
detect a total split by looping over shares and rounding each independently with no
reconciliation of the residual. Why it breaks: the rounded parts do not sum back to the
total, so a 100.00 split three ways becomes 33.33 + 33.33 + 33.33 = 99.99 and a cent
vanishes. The fix: allocate with an explicit remainder pass (largest-remainder, or push the
residual to the last bucket). False positives: a high-precision internal allocation that
carries the residual forward and only rounds once at the end is fine, do not flag it.

## How the agent applies it

The agent is a Claude Code plugin, read-only, running on your own session. It scans the repo
for where money lives, then fans out one auditor subagent per domain, each pointed at that
domain's rule file and the candidate code. Then a second agent runs whose only job is to
refute each finding: is this display-only, a rate rather than an amount, dead code, already
guarded a layer up, a misreading? Refuted findings are dropped before you ever see them. The
survivors come back with a severity, a confidence tier from the verifier, the offending
code, a fix direction, and the rule citation.

## What happened on real code

The eval fixtures in the repo are bugs I planted, which is useful for measuring recall but
proves nothing about false positives on code that is mostly correct. So I ran it on real
codebases.

On Medusa, the open-source commerce platform, I pointed it at the money-core files across
six domains, at a pinned commit. The auditors emitted 16 findings; the verifier refuted 10,
downgraded 2 to narrower claims, and confirmed 4. The confirmed 4 are one concurrency
cluster. Simplified, the payment capture path does this:

```ts
// read how much has already been captured
const capturedAmount = payment.captures.reduce(/* sum */, 0)
// guard: refuse to capture more than authorized minus already-captured
if (newCaptureAmount > authorizedAmount - capturedAmount) throw new Error()
// insert the capture
await this.captureService_.create({ /* ... */ })
```

The read, the guard, and the write are not serialized. Under the default READ COMMITTED
isolation, two concurrent captures of a 100 authorization both read captured = 0, both see
100 remaining, both pass the guard, and both insert. Result: 200 captured against a 100
authorization. There is no row lock, no version check, and no unique constraint to catch it.
The same shape appears in refunds and in two promotion-budget counters. The gateway does not
save you: the bundled Stripe provider swallows the already-captured error, so both capture
rows persist, and each refund row carries its own idempotency key, so stripe.refunds.create
moves real money twice. I filed the cluster upstream with a failing test that drops straight
into Medusa's own concurrency test block; it is filed, not yet triaged, so judge it by the
test: https://github.com/medusajs/medusa/issues/16012

## The refutations are the interesting part

The verifier killed 10 of the 16 Medusa findings, and that is the number I would judge the
tool on. A tool that dumps raw findings costs you an afternoon per false positive and loses
your trust on the first wrong one.

One example. An auditor flagged that Medusa stores tax rates in a single-precision `REAL`
column, and by the letter of the rule that is a hit. The verifier worked the whole chain
mechanically: a float32 stored rate, read back through PostgreSQL 12+'s
shortest-round-trip text output, parsed by node-postgres, then converted to the exact
decimal. Every rate tested (0.21, 8.25, 9.975, 8.0625, 13.9125) round-trips exactly;
corruption would need a rate with seven or more significant digits. The finding died on the
rule's own test: does an inexact binary value ever actually reach the money math? The
answer was no. That refutation used a false-positive note I had added to the rulebook the
same day, which is the feedback loop working.

All ten kills are published with their mechanisms in the field report, so a wrong kill is
itself checkable.

## Honest limits

- 86% recall on the cold scan is a best case, not proof: I planted the bugs and wrote the
  answer key, the fixture only holds bug classes I already knew to write rules for, and
  the scan still missed 5 of the 35. The misses are in the repo.
- On that fixture the verifier refuted nothing (0 of 53): every file is dense with planted
  bugs, so the fixture says nothing about false-positive suppression. The kill rates on
  real code are the evidence: 10 of 16 on Medusa, 14 of 36 on the private repo.
- The verifier is adversarial, not human. "Confirmed" means the finding survived an attack
  by a second model, not that a person proved it.
- One of my two field writeups is on a private, anonymized codebase you cannot reproduce.
  The Medusa one you can, and its issue is filed upstream, not yet accepted.
- No Go or Ruby yet.
- A whole-repo run costs real tokens on your own account (the two runs in field report 1
  cost roughly 2.2M subagent tokens total). Diff mode is the cheap day-to-day run.

## Try it, or argue with a rule

```
/plugin marketplace add DylanMerigaud/fintech-roast
/plugin install fintech-roast@fintech-roast
/fintech-roast:roast
```

The rules are claims about how money code breaks. If one is wrong, overstated, or missing a
jurisdiction nuance, that is the most valuable contribution you can make. The rulebook, the
evals with their misses, and both field reports are all in the repo:
https://github.com/DylanMerigaud/fintech-roast
