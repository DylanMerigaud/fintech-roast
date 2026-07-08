# Contributing

The most useful contribution right now: **roast the rules.**

Every rule in `rules/` is a claim about how money-handling code breaks. If a rule is wrong,
overstated, missing a jurisdiction nuance, or would flag perfectly fine code, open an issue
or a PR that says so. Rules only get better by surviving contact with people who ship
payment systems.

Ground rules for rule changes:

- One rule per PR. Keep the diff reviewable.
- A rule keeps at least two authoritative sources (specs, standards, primary vendor docs,
  canonical engineering literature). If you change a claim, bring the source that backs it.
- Jurisdiction-dependent claims (tax rounding, legal rounding modes) must say which
  jurisdiction they apply to. "The law requires X" without naming the law gets rejected.
- False-positive notes are part of the rule. A detection pattern without them is half a rule.
- Follow the format contract in `rules/README.md`; CI validates it, including a plain-ASCII
  punctuation check (no em/en dashes).

New rules are welcome if they are (1) about correctness of code that touches money, not
general code quality, and (2) sourced as above. Rule ids are stable and never renumbered;
new rules take the next free number in their domain.
