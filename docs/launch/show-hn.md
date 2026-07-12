# Show HN draft

Posting is your manual call. Pick a title, post the body as the text, then drop the
first-comment below right after submitting.

## Title options (pick one)

1. Show HN: A sourced rulebook of how money code breaks, applied by an agent
2. Show HN: An agent that audits code touching money and refutes its own findings
3. Show HN: I pointed a money-bug rulebook at open-source billing code and filed a real bug

(1 matches the positioning best. 3 is the most concrete hook if you want the found bug up front.)

## Body

Most "AI code review" for money is one prompt that greps for `float` and calls it done. I
wanted the opposite: put the value in a rulebook you can read and cite, and make the agent
just the thing that applies it.

fintech-roast is a Claude Code plugin. The rulebook is 41 rules across 10 domains (storage,
rounding, idempotency, ledgers, FX, time, taxes, aggregation, serialization, testing), each
with per-language detection and fixes for TypeScript, Python, and Java, each backed by
primary sources (specs, standards, tax-authority manuals), and each carrying its own
false-positive notes. The agent scans a repo for where money lives, fans out one auditor
per domain, then runs a second agent whose only job is to refute each finding. Refuted
findings are dropped. It is read-only and runs on your own Claude session, so there is no
API key to configure.

The refutation pass is the part I care about. On a run against Medusa (the open-source
commerce platform, at a pinned commit), the auditors emitted 16 findings and the verifier
killed 10 of them before I saw a report, several using arguments I had added to the rulebook
as false-positive notes that same day. The 4 that survived are a real concurrency cluster:
check-then-act races in payment capture/refund and promotion-budget counters, where two
concurrent requests both read the pre-write value, both pass the amount guard, and both
write. I filed it upstream with a failing test that drops into Medusa's own concurrency
test block: https://github.com/medusajs/medusa/issues/16012

Honest limits, since this crowd will ask:

- The eval fixtures are bugs I planted myself. 86% recall on a cold scan, but I wrote the
  answer key, so read that as a floor, not proof.
- The verifier is adversarial, not human. It refuted 10 of 16 findings on Medusa, which is
  the number that matters, but a confirmed finding is still "worth checking," not "proven."
- I have two real-world writeups. One is on a private codebase, anonymized, so you cannot
  reproduce it. The Medusa one you can, at the pinned commit.
- It covers TypeScript, Python, and Java. No Go or Ruby yet.
- A whole-repo run costs real tokens on your own account (millions on a large repo). A
  diff-scoped mode is the cheap default.

The rules are claims about how money code breaks. If one is wrong or overstated, that is the
most useful thing you can tell me.

Repo: https://github.com/DylanMerigaud/fintech-roast

## First comment (post right after submitting)

The design decision I went back and forth on: the rulebook is the product, the agent is the
delivery mechanism. A rule is not a regex, it is a claim with sources and false-positive
notes, so the same rule works whether the executor is today's model or a cheaper one later,
and so a human can check the reasoning instead of trusting the tool. The evals live in the
repo with their misses, and the Medusa run includes every finding the verifier refuted and
why, because the refutations are as much the point as the confirmations. Happy to answer
anything about the pipeline or the rules.
