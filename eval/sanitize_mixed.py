#!/usr/bin/env python3
"""Strip ALL comments and docstrings from the mixed-fixture files.

The mixed tree is copied verbatim from fixture-py (buggy, with inline bug
annotations and defect-describing prose) and fixture-py-clean (correct, with
"correct twin" prose). Any of that prose tells a reading auditor a file's status
and defeats the blind eval. This removes every comment and every docstring from
all mixed files, symmetrically, leaving pure code the auditor must judge on its
own merits. For .py files it uses the tokenizer, so code is provably untouched
(only COMMENT tokens and standalone string-expression statements are dropped).
For .sql it drops -- comment lines. Run from the repo root:
python3 eval/sanitize_mixed.py
"""

import io
import re
import tokenize
from pathlib import Path

MIXED = Path(__file__).parent / "fixture-py-mixed"


def strip_python(source: str) -> str:
    """Remove comments and docstrings from Python source via the tokenizer.

    A docstring is a string expression statement: a STRING token that is the sole
    content of a simple statement (preceded by NEWLINE/INDENT/DEDENT and followed
    by NEWLINE). We drop COMMENT tokens always, and drop such standalone STRING
    statements. Every other token is emitted verbatim, so executable code is
    byte-for-byte preserved (modulo whitespace normalisation by untokenize).
    """
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    result = []
    prev_meaningful = tokenize.NEWLINE  # start-of-file behaves like a new logical line
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == tokenize.COMMENT:
            i += 1
            continue
        if tok.type == tokenize.STRING and prev_meaningful in (
            tokenize.NEWLINE,
            tokenize.NL,
            tokenize.INDENT,
            tokenize.DEDENT,
            tokenize.ENCODING,
        ):
            # Look ahead: a docstring is a lone STRING followed by NEWLINE.
            j = i + 1
            while j < len(tokens) and tokens[j].type in (tokenize.NL, tokenize.COMMENT):
                j += 1
            if j < len(tokens) and tokens[j].type == tokenize.NEWLINE:
                # drop the docstring string and its terminating NEWLINE
                i = j + 1
                continue
        result.append(tok)
        if tok.type not in (tokenize.NL, tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT):
            prev_meaningful = tok.type
        i += 1
    out = tokenize.untokenize(result)
    # tidy: collapse 3+ blank lines to 2, strip trailing whitespace
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n\n", out)
    return out.lstrip("\n")


def strip_sql(source: str) -> str:
    """Drop -- comment lines and trailing -- comments; keep DDL intact."""
    out_lines = []
    for line in source.split("\n"):
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        if "--" in line:
            line = line.split("--", 1)[0].rstrip()
            if not line.strip():
                continue
        out_lines.append(line)
    out = "\n".join(out_lines)
    out = re.sub(r"\n{3,}", "\n\n\n", out)
    return out.lstrip("\n")


def main() -> None:
    for path in sorted(MIXED.rglob("*.py")):
        path.write_text(strip_python(path.read_text()))
        print("stripped", path.relative_to(MIXED))
    for path in sorted(MIXED.rglob("*.sql")):
        path.write_text(strip_sql(path.read_text()))
        print("stripped", path.relative_to(MIXED))


if __name__ == "__main__":
    main()
