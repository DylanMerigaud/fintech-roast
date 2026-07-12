# Show HN draft

Posting is your manual call: open https://news.ycombinator.com/submit, paste the title,
paste the body into the text field (leave url empty), submit, then post the first comment
right away.

## Title (77 chars)

Show HN: An agent that audits money code and tries to refute its own findings

(Fallback variant if ever needed, 74 chars: "Show HN: A rulebook of how money code
breaks, and an agent that applies it".)

## Body

fintech-roast is a Claude Code plugin: a sourced rulebook of how money code breaks, and an
agent that applies it, then tries to refute what it found. Most "AI code review" for money
is one prompt that greps for "float" and calls it done. I built the opposite: the value
lives in the rulebook, readable and citable; the agent is the delivery mechanism.

The rulebook is 41 rules across 10 domains (storage, rounding, idempotency, ledgers, FX,
time, taxes, aggregation, serialization, testing). Each rule has per-language detection and
fixes for TypeScript, Python, and Java, cited sources (language specs, tax-authority
manuals, engineering write-ups), and its own false-positive notes. The agent scans the repo
for where money lives, fans out one auditor per domain, then runs a second agent whose only
job is to refute each finding. Refuted findings are dropped. It is read-only and runs on
your own Claude session, so there is no API key to configure.

The refutation pass is the part I care about. On a run against Medusa (the open-source
commerce platform, at a pinned commit, pointed at the money-core files across six domains),
the auditors emitted 16 findings. The verifier killed 10 of them before I saw a report, one
with a false-positive note I had added to the rulebook that same day, and downgraded 2 more
to narrower claims. The 4 confirmed are one concurrency cluster: check-then-act races in
payment capture/refund and promotion-budget counters, where two concurrent requests both
read the pre-write value, both pass the amount guard, and both write. I filed the cluster
upstream with a failing test that drops into Medusa's own concurrency test block; it is
filed, not yet triaged, so judge it by the test:
https://github.com/medusajs/medusa/issues/16012

Honest limits, since this crowd will ask:

- The eval fixtures are bugs I planted myself, so 86% recall on a cold scan is a best
  case, not proof: the fixture only holds bug classes I already knew to write rules for,
  and the scan still missed 5 of the 35. The misses are listed in eval/RESULTS.md.
- On that planted fixture the verifier refuted nothing (0 of 53): every file is dense with
  planted bugs, so it says nothing about false-positive suppression. The kill rates on
  real code are the evidence: 10 of 16 on Medusa, 14 of 36 on a private repo, each kill
  published with its mechanism.
- The verifier is adversarial, not human. A confirmed finding survived an attack by a
  second model, not a person's review.
- I have two real-world writeups. One is on a private codebase, anonymized, so you cannot
  reproduce it. The Medusa one you can, at the pinned commit.
- No Go or Ruby yet.
- A whole-repo run costs real tokens on your own account (the two runs in field report 1
  cost roughly 2.2M subagent tokens total). Diff mode is the cheap way to run it day to
  day.

The rules are claims about how money code breaks. If one is wrong or overstated, that is
the most useful thing you can tell me.

Repo: https://github.com/DylanMerigaud/fintech-roast

## First comment (post right after submitting)

The design decision I went back and forth on: how much of the value lives in the rulebook
vs the agent. A rule here is a claim with sources and false-positive notes, not a regex. A
human can check the reasoning instead of trusting the tool, and the same rule keeps working
when the executor is a cheaper model later. If you want to call the whole thing a prompt:
the prompt is 41 sourced rules you can read and argue with, and the plugin adds the
scoping, the fan-out, the refutation pass, and the eval harness. The evals live in the repo
with their misses, and the Medusa writeup includes every finding the verifier refuted and
why. Ask me anything about the pipeline or the rules.
