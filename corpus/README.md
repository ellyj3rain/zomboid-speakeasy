# Pre-training sources

Academic, cultural and language text supplies the shared cognitive foundation.
The period-text collection supplies early-1990s language and historical context.

Rules:

- Every item records its source and its license before it enters.
- Public-domain or MIT-compatible only.
- Curation notes say what an item is FOR (register, era vocabulary,
  radio speech, regional voice) - nothing enters just to be big.
- Academic and cultural sources pass automated provenance, rights, byte and
  extraction checks. Preparing this prerequisite material requires no operator
  evaluation of individual books. Downstream grades measure learner performance,
  retained knowledge, transfer and use. Personal statements about a living
  person's life remain outside this collection.

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

## Educational curriculum

`education/catalogue.json` owns candidate educational source identities for
the kindergarten-through-college curriculum. `tools/education_corpus.py`
acquires actual publisher text, mathematics markup, examples and exercises
into immutable local archives. An archive preserves publisher rights evidence,
source versions, exact bytes, hashes and acquisition failures. The period-text
manifest remains the owner of the separate early-1990s language corpus.

Educational archives retain United States public-domain standing or the exact
publisher edition's CC BY 4.0 terms and attribution requirements. The repository
MIT license covers its code; it does not replace an acquired book's terms.
NC-SA editions are refused by this route. Academic books supply prerequisite
pre-training material. Automated evaluation verifies publisher provenance,
edition rights, source bytes, extraction and exact passage reconstruction.
Learning quality is measured by downstream assessments and held-out evaluation.

Preparation produces source-derived passages. Admission reconstructs their text
and metadata from the preserved archive and saves a content-bound automated
evaluation receipt. Academic source preparation requires no operator grading or
individual book approval. The period-text and county-event review owners retain
their existing scope.
Protected earlier sources remain unchanged. Educational passages support the
shared cognitive substrate; competing ordinary and associative cognition keep
their independent decision and outcome owners.

The curriculum's course progression, regional variants and each person's
educational history identify possible exposure. SAO owns personal acquisition,
retention, practice and current execution. Exposure grants no native skill,
recipe, unseen county fact or another person's assent. Modern editions need
explicit historical-content mapping before they can support a simulated
pre-1993 schooling history. Missing subjects and unavailable figures remain
visible in curriculum coverage rather than being replaced with authored rules.

## Cultural and language foundation

`pretraining/catalogue.json` combines the academic catalogue with publisher
sources for cultural and language pre-training. The same immutable acquisition,
automatic source/data evaluation and source-family partition owners process
this material. The period-text manifest and preserved extractions retain their
own source identities. A shared trained base supplies prior associations;
person-specific histories and learning state determine accessible knowledge.
