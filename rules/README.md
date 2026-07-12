# The rulebook

41 rules about how code that touches money actually breaks, organized by domain. This is
the product; the agent that applies them is the delivery mechanism.

Every rule went through two passes: a research pass (each claim backed by at least two
authoritative sources, fetched and read, not just linked) and an adversarial pass (a
reviewer whose only job was to refute the rule, kill dead links, and attack severity
inflation and jurisdiction-dependent claims).

## Domains

| File | Prefix | Scope |
| --- | --- | --- |
| [storage-and-types.md](storage-and-types.md) | STO | Column types, minor units, currency columns, numeric limits |
| [rounding-and-allocation.md](rounding-and-allocation.md) | ROU | Rounding modes, pro-rata splits, operation order |
| [idempotency-and-concurrency.md](idempotency-and-concurrency.md) | IDE | Webhooks, retries, balance races, unique constraints |
| [ledger-design.md](ledger-design.md) | LED | Append-only, double-entry, derived balances, audit trail |
| [fx-and-multicurrency.md](fx-and-multicurrency.md) | FX | Round-trips, rate timestamps, cross-currency arithmetic |
| [time-and-dates.md](time-and-dates.md) | TIM | Timezones, DST, period boundaries, day-count conventions |
| [aggregation-and-reporting.md](aggregation-and-reporting.md) | AGG | Float sums, ORM/JSON precision loss, pagination drift |
| [taxes.md](taxes.md) | TAX | Line vs invoice rounding, inclusive/exclusive, rate precision |
| [api-and-serialization.md](api-and-serialization.md) | API | JSON numbers, GraphQL Float, input parsing, canonical formats |
| [testing.md](testing.md) | TST | Property tests, fixture realism, currency coverage |

## Format contract

Machine-validated by `scripts/validate_rules.py` (runs in CI). Each rule is:

```markdown
## PRE-N: Title

**Severity**: critical | high | medium | low

**What to detect**

- concrete, grep-able patterns and semantic signals

**Why it breaks**

The failure mechanism, with real incidents referenced when they exist.

**Fix**

What to do instead, with a short code sketch when useful.

**False positives**

- cases where the flagged pattern is actually fine

**Sources**

1. [Title](url) (publisher)
2. [Title](url) (publisher)
```

Severity scale: **critical** = money lost, duplicated, or corrupted on production paths;
**high** = wrong amounts in realistic edge cases, or compliance exposure; **medium** =
fragile or latent risk; **low** = style with a money-safety rationale.

Rule ids are stable: a dropped rule leaves a hole, ids are never renumbered.
