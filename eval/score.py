#!/usr/bin/env python3
"""Score an audit run against the planted-bug answer key.

Usage: python3 eval/score.py <findings.json>

findings.json shape: {"findings": [{"rule": "STO-1", "file": "db/schema.sql",
"line": 3, "description": "..."}]}

Matching: a finding matches a planted bug when finding.rule == planted.rule and
finding.file ends with one of planted.files. One planted bug can be matched by
several findings (they count once for recall); a finding that matches no planted
bug is reported for manual triage (the fixture is dense, so an unmatched finding
may be a real, unindexed issue rather than a false positive).
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2

    expected = json.loads((HERE / "expected.json").read_text())
    planted = expected["planted"]
    findings = json.loads(Path(sys.argv[1]).read_text())["findings"]

    matched_keys: set[str] = set()
    matched_findings = 0
    unmatched_findings = []

    for finding in findings:
        rule = finding.get("rule", "")
        file = finding.get("file", "")
        hit = None
        for bug in planted:
            if rule == bug["rule"] and any(file.endswith(f) for f in bug["files"]):
                hit = bug
                break
        if hit:
            matched_keys.add(hit["key"])
            matched_findings += 1
        else:
            unmatched_findings.append(finding)

    recall = len(matched_keys) / len(planted)
    precision = matched_findings / len(findings) if findings else 0.0

    print(f"planted bugs:        {len(planted)}")
    print(f"findings reported:   {len(findings)}")
    print(f"planted bugs found:  {len(matched_keys)}  (recall {recall:.0%})")
    print(f"findings on target:  {matched_findings}  (precision vs key {precision:.0%})")

    missed = [b for b in planted if b["key"] not in matched_keys]
    if missed:
        print("\nMISSED planted bugs:")
        for bug in missed:
            print(f"  {bug['key']} {bug['rule']} in {bug['files'][0]}: {bug['note']}")

    if unmatched_findings:
        print("\nFindings not in the answer key (triage by hand, may be real):")
        for finding in unmatched_findings:
            print(f"  {finding.get('rule')} in {finding.get('file')}: {finding.get('description', '')[:100]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
