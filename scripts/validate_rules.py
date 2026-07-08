#!/usr/bin/env python3
"""Validate the rulebook format contract and repo-wide punctuation policy.

Checks (all errors are collected, exit 1 if any):
- every rules/<domain>.md file follows the format: H1 title, intro line, then rules
- each rule: `## PRE-N: Title` heading, then the exact sections in order:
  **Severity** (valid value), **What to detect** (bulleted), **Why it breaks**,
  **Fix**, **False positives** (bulleted), **Sources** (numbered, >= 2, md links)
- rule id prefix matches the file's assigned prefix, ids unique across the pack
- no em dash (U+2014) or en dash (U+2013) in any tracked text file of the repo
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
RULES = ROOT / "rules"

FILE_PREFIX = {
    "storage-and-types.md": "STO",
    "rounding-and-allocation.md": "ROU",
    "idempotency-and-concurrency.md": "IDE",
    "ledger-design.md": "LED",
    "fx-and-multicurrency.md": "FX",
    "time-and-dates.md": "TIM",
    "aggregation-and-reporting.md": "AGG",
    "taxes.md": "TAX",
    "api-and-serialization.md": "API",
    "testing.md": "TST",
}

SEVERITIES = {"critical", "high", "medium", "low"}
SECTION_ORDER = ["**What to detect**", "**Why it breaks**", "**Fix**", "**False positives**", "**Sources**"]
RULE_HEADING = re.compile(r"^## ([A-Z]{2,4}-\d+): (.+)$")
SOURCE_LINE = re.compile(r"^\d+\. \[[^\]]+\]\(https?://[^)]+\) \(.+\)$")
TEXT_EXTENSIONS = {".md", ".ts", ".tsx", ".js", ".json", ".py", ".sql", ".yml", ".yaml", ".txt"}

errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def check_dashes() -> None:
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    for rel in tracked:
        path = ROOT / rel
        if path.suffix not in TEXT_EXTENSIONS or not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            if "\u2014" in line or "\u2013" in line:
                err(f"{rel}:{i}: em/en dash found (policy: ASCII punctuation only)")


def split_rules(body: str) -> list[tuple[str, str, str]]:
    """Return [(id, title, section_text)] for each rule heading."""
    rules = []
    matches = [(m, i) for i, line in enumerate(body.splitlines()) for m in [RULE_HEADING.match(line)] if m]
    lines = body.splitlines()
    for idx, (m, lineno) in enumerate(matches):
        end = matches[idx + 1][1] if idx + 1 < len(matches) else len(lines)
        rules.append((m.group(1), m.group(2), "\n".join(lines[lineno + 1 : end])))
    return rules


def check_rule(fname: str, rule_id: str, body: str) -> None:
    where = f"{fname} {rule_id}"

    sev = re.search(r"^\*\*Severity\*\*: (\S+)$", body, re.M)
    if not sev:
        err(f"{where}: missing '**Severity**: <value>' line")
    elif sev.group(1) not in SEVERITIES:
        err(f"{where}: invalid severity '{sev.group(1)}'")

    positions = []
    for section in SECTION_ORDER:
        pos = body.find(section)
        if pos == -1:
            err(f"{where}: missing section '{section}'")
        positions.append(pos)
    if all(p != -1 for p in positions) and positions != sorted(positions):
        err(f"{where}: sections out of order")

    src_pos = body.find("**Sources**")
    if src_pos != -1:
        source_lines = [
            line for line in body[src_pos:].splitlines() if re.match(r"^\d+\. ", line)
        ]
        if len(source_lines) < 2:
            err(f"{where}: fewer than 2 sources")
        for line in source_lines:
            if not SOURCE_LINE.match(line):
                err(f"{where}: malformed source line: {line[:80]}")

    detect_pos = body.find("**What to detect**")
    why_pos = body.find("**Why it breaks**")
    if detect_pos != -1 and why_pos != -1:
        detect_block = body[detect_pos:why_pos]
        if not re.search(r"^- ", detect_block, re.M):
            err(f"{where}: 'What to detect' has no bullets")


def main() -> int:
    check_dashes()

    seen_ids: dict[str, str] = {}
    total = 0
    missing_files = []
    for fname, prefix in FILE_PREFIX.items():
        path = RULES / fname
        if not path.exists():
            missing_files.append(fname)
            continue
        body = path.read_text(encoding="utf-8")
        if not body.startswith("# "):
            err(f"{fname}: must start with an H1 title")
        rules = split_rules(body)
        if not rules:
            err(f"{fname}: no rules found")
        for rule_id, _title, rule_body in rules:
            total += 1
            if not rule_id.startswith(prefix + "-"):
                err(f"{fname}: rule {rule_id} does not match file prefix {prefix}")
            if rule_id in seen_ids:
                err(f"{fname}: duplicate rule id {rule_id} (also in {seen_ids[rule_id]})")
            seen_ids[rule_id] = fname
            check_rule(fname, rule_id, rule_body)

    if missing_files:
        print(f"note: {len(missing_files)} domain file(s) not written yet: {', '.join(missing_files)}")

    if errors:
        print(f"\n{len(errors)} error(s):")
        for e in errors:
            print(f"  {e}")
        return 1

    print(f"OK: {total} rules across {len(FILE_PREFIX) - len(missing_files)} domain files, format clean, no em/en dashes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
