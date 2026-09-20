# Tools

`cross_module_rows.py` joins version 3 SAO decisions to ZAO state on the exact
run, county, person, event and hour namespace. It validates the complete inputs,
executable-option evidence, conditioning time and protected artifact hashes
before writing. A temporary sibling becomes visible through one atomic replace.

The historical version 2 rows are deliberately refused. Their approved intent
remains in place; their `(person, hour)` join and future conditioning do not meet
the version 3 evidence contract.

`audit_conditioning.py` reproduces the eligibility counts in
`decisions/ELIGIBILITY.md` from the protected version 2 bytes.

Run the join controls with:

```text
python tools/test_cross_module_rows.py
```
