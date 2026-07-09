# Security

fintech-roast is a read-only static auditor. It reads source files and reports findings; it
does not execute the code it audits, modify files, make network calls on your behalf, or
transmit your code anywhere. It runs inside your own Claude Code session.

Two things worth stating plainly:

- **Findings are advisory.** They are rule-based and adversarially verified by a second
  agent, but not human-verified. A finding is a prompt to go read the cited rule and your
  code, not a verdict. Acting on a finding without checking it is on you.
- **The tool can miss real bugs.** Absence of findings is not a proof of correctness. Do not
  treat a clean run as a security or compliance sign-off.

## Reporting a vulnerability

If you find a security issue in this tool itself (for example, a way the plugin could be
made to exfiltrate code or run something), open a GitHub security advisory on the repository,
or a regular issue if it is not sensitive. There is no bounty; this is a solo open-source
project.
