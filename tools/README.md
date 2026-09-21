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

`decision_authoring.py` builds version 1 knowledge views and separately authored
proposals from immutable version 3 SAO rows or native C65 source-action captures.
It binds explicit actor acquisition evidence to approved-document excerpts and
the full event namespace, excludes future/LOW/unavailable claims, preserves
unreviewed evidence standing, and binds proposals to complete option hashes.
Every proposal remains unratified and conditioning-ineligible. Input formats,
commands and the remaining acquisition/ratification boundary are in
[`decisions/AUTHORING.md`](../decisions/AUTHORING.md).

```text
python tools/test_decision_authoring.py
```
