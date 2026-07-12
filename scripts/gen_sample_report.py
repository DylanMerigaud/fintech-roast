#!/usr/bin/env python3
"""Generate docs/sample-report.md from eval/run-1-findings.json.

Formats the archived run-1 findings (TypeScript fixture, scored in eval/RESULTS.md)
in the report shape the roast skill prints (skills/roast/SKILL.md step 4).
"""
import json
import re
import textwrap
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOMAIN_FILES = {
    "STO": "storage-and-types.md",
    "ROU": "rounding-and-allocation.md",
    "IDE": "idempotency-and-concurrency.md",
    "LED": "ledger-design.md",
    "FX": "fx-and-multicurrency.md",
    "TIM": "time-and-dates.md",
    "AGG": "aggregation-and-reporting.md",
    "TAX": "taxes.md",
    "API": "api-and-serialization.md",
    "TST": "testing.md",
}

# rule id -> title from rules/*.md headers
titles = {}
for fname in DOMAIN_FILES.values():
    for line in (ROOT / "rules" / fname).read_text().splitlines():
        m = re.match(r"^## ([A-Z]+-\d+): (.+)$", line)
        if m:
            titles[m.group(1)] = m.group(2)

findings = json.loads((ROOT / "eval" / "run-1-findings.json").read_text())["findings"]

SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
findings.sort(key=lambda f: (SEV_ORDER[f["severity"]], f["rule"], f["file"], f["line"]))


def wrap(text, indent):
    # Repo convention (see CONTRIBUTING.md): plain ASCII punctuation everywhere.
    em, en = "\u2014", "\u2013"  # em/en dash; escaped, the ASCII policy covers this file too
    text = text.replace(f" {em} ", " - ").replace(em, " - ").replace(en, "-")
    return textwrap.fill(
        text, width=96, initial_indent=indent, subsequent_indent=indent
    )


blocks = []
for f in findings:
    domain = f["rule"].split("-")[0]
    head = f"{f['severity'].upper()} {f['rule']} {f['file']}:{f['line']} [{f['tier']}]"
    body = "\n".join(
        [
            wrap(f["evidence"], "  "),
            wrap("fix: " + f["fix"], "  "),
            f"  rule: {titles[f['rule']]} (see rules/{DOMAIN_FILES[domain]} for sources)",
        ]
    )
    blocks.append(head + "\n" + body)

sev_counts = Counter(f["severity"] for f in findings)
tier_counts = Counter(f["tier"] for f in findings)

summary = "\n".join(
    [
        f"{len(findings)} findings: "
        + ", ".join(f"{sev_counts[s]} {s}" for s in ("critical", "high", "medium", "low") if sev_counts[s]),
        "verification: " + ", ".join(f"{tier_counts[t]} {t}" for t in ("confirmed", "likely")),
        "domains audited: STO ROU IDE LED FX TIM AGG TAX API TST (all 10; none skipped, every domain had surface)",
        "",
        "Findings are rule-based and adversarially verified, but not human-verified. Read the",
        "cited rule before acting; every rule documents its false positives.",
    ]
)

report = "\n\n".join(blocks) + "\n\n" + "-" * 96 + "\n" + summary

doc = f"""# Sample report

**What it finds on real code** (not the planted fixture below): two runs on production
codebases are written up in [`eval/FIELD-REPORT-1.md`](../eval/FIELD-REPORT-1.md) (a private
repo, anonymized: 18 findings confirmed, 1 critical) and
[`eval/FIELD-REPORT-2.md`](../eval/FIELD-REPORT-2.md)
([medusajs/medusa](https://github.com/medusajs/medusa) at a pinned commit: 4 confirmed,
filed upstream with a failing test as
[medusajs/medusa#16012](https://github.com/medusajs/medusa/issues/16012)). Those show the
tool on code nobody wrote to be found, including the findings the verifier refuted. The
report below is the fixture run, kept because it exercises every domain at once.

---

This is the full report of run 1 on the TypeScript planted-bug fixture
([`eval/fixture/`](../eval/fixture/)): the same run the README gif replays and
[`eval/RESULTS.md`](../eval/RESULTS.md) scores (86 percent recall, every finding mapping to a
real planted defect). It is rendered from the archived findings and verifier verdicts in
[`eval/run-1-findings.json`](../eval/run-1-findings.json), with punctuation normalized to
plain ASCII per repo convention. This is the report shape the
plugin prints at the end of `/fintech-roast:roast`.

A fixture built to be full of bugs produces a dense report; on a production repo expect far
fewer findings, and "no findings" is a valid outcome. The `[confirmed|likely]` tag on each
finding is the verdict of the adversarial verification pass; refuted findings are dropped
before the report (this run: none refuted, see RESULTS.md for why that is expected on this
fixture and what it does not prove).

```text
{report}
```
"""

out = ROOT / "docs" / "sample-report.md"
out.parent.mkdir(exist_ok=True)
out.write_text(doc)
print(f"wrote {out} ({len(doc)} chars, {len(findings)} findings)")
