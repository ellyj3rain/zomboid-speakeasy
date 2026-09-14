# Period text

Curated public text supplying language texture for the early 1990s.

Rules:

- Every item records its source and its license before it enters.
- Public-domain or MIT-compatible only.
- Curation notes say what an item is FOR (register, era vocabulary,
  radio speech, regional voice) - nothing enters just to be big.
- Text is somebody's speech. Anything written by an identifiable
  person enters only with the consent question settled first -
  license alone is not consent to be in a training corpus - and
  personal statements about a living person's life never enter at
  all.

Curation opened 2026-09-13, the day the nine world documents were
approved (RECORD.md 43) and the operator ruled what the corpus is for
(RECORD.md 44). The first vein is United States Government work, which
carries no copyright (17 U.S.C. §105); the manifest is `manifest.md`,
and the first two entries are the Monthly Labor Review's June and
July 1993 issues.

## Outputs

`tools/extract_corpus.py` turns the curated items into the plain-text
outputs the work consumes: one file per item under `out/`, plus an
index of derived facts. The outputs are derived artifacts, never
curation - everything an output says is in its PDF, the manifest
remains the record, and an item reaches the outputs by being in the
manifest and never otherwise. The tool is deterministic: two runs
over the same corpus produce byte-identical outputs.
