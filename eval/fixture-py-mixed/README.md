# fixture-py-mixed: blind mixed fixture

A read-only audit artifact for the blind mixed eval. It mixes correct and buggy money code in one
tree, per a locked per-file split, so a domain auditor handed the whole tree (with no hint which files
are which) has to flag the real bugs AND stay quiet on the correct code, often in the same domain.

This tree is NOT a runnable app. The clean and buggy `money.py` have different signatures and do not
co-import; the auditor reads files statically and never runs them. The two green-by-design apps stay in
`../fixture-py/` (buggy) and `../fixture-py-clean/` (correct); this tree exists only to be read.

## The split

| File | Version (copied verbatim from) | Planted bugs |
| --- | --- | --- |
| `money.py` | buggy (`fixture-py/`) | STO-1 x3, ROU-1, API-3 |
| `db/schema.sql` | buggy (`fixture-py/`) | STO-1/2/4, IDE-4, TIM-1 |
| `fx.py` | buggy (`fixture-py/`) | FX-1/2/3/4 |
| `ledger.py` | buggy (`fixture-py/`) | LED-1/2/3/4 |
| `webhooks.py` | buggy (`fixture-py/`) | IDE-1/2 |
| `store.py` | buggy (`fixture-py/`) | IDE-3 |
| `invoice.py` | clean (`fixture-py-clean/`) | none |
| `split.py` | clean (`fixture-py-clean/`) | none |
| `tax.py` | clean (`fixture-py-clean/`) | none |
| `interest.py` | clean (`fixture-py-clean/`) | none |
| `reports.py` | clean (`fixture-py-clean/`) | none |
| `api.py` | clean (`fixture-py-clean/`) | none |
| `test_*.py` | clean (`fixture-py-clean/`) | none |

21 planted bugs total, all in the 6 buggy files. `expected.json` is the answer key. A confirmed finding
on a clean file is a false positive, not an unindexed bug.

## Split domains (the real test)

API, ROU, and TIM each appear in BOTH a buggy and a clean file, so the auditor must discriminate within
one domain: flag `money.py`'s float parse but not `api.py`'s correct wire shape (API); flag `money.py`'s
bare round but not the correct single-rounding invoice / largest-remainder split (ROU); flag the naive
`TIMESTAMP` in the schema but not the correct calendar-date day math in `interest.py` (TIM).
