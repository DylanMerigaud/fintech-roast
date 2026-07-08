# fintech-roast

An agent that roasts the code that touches money.

Work in progress, building in public. The order of operations:

1. **The rulebook** (`rules/`): ~40 rules covering how money-handling code actually breaks
   (storage types, rounding, allocation, idempotency, ledgers, FX, time, taxes, serialization,
   testing). Every rule is sourced with at least two authoritative references and has been
   through an adversarial review pass. This is the product; the agent is the delivery mechanism.
2. **The Claude Code plugin**: `/fintech-roast` scans a repo for money surfaces, fans out one
   auditor per domain armed with that domain's rules, adversarially verifies every finding,
   and reports with rule citations.
3. **The benchmark**: run on real open-source codebases that move money, findings verified by
   hand before anything is published.

Status: rulebook and plugin skeleton under construction.
