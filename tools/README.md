# Tools

`cross_module_rows.py` merges an SAO decision dump with ZAO state rows keyed
by the same person id. It keeps the SAO row unchanged, adds the `pathogen`
block to the person half, adds the `visibleForms` block to the situation
half, and writes one cross-module row per line.

ZAO's own `tools/state_dump.py` emits one state row per SAO decision moment,
keyed by person id and decision hour.
