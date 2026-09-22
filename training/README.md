# Training

The runs that produce the two models, and the contract SAO loads
them by.

Rules:

- Model sizes cite measured in-game inference budgets, never a
  guess.
- Every run records its data snapshot, its size, and its result.
- The export contract (format, versioning, how a consumer loads a
  model) is designed here and recorded before the first export.

The ratified implementation shape is now recorded in
[`ARCHITECTURE.md`](ARCHITECTURE.md). One shared base uses typed task adapters;
knowledge arrives through learned retrieval; bounded per-person model cache is
versioned and persisted without authorizing facts; understander and speaker use
separate provenance-complete datasets; inference runs asynchronously from an
immutable snapshot and is revalidated before any consequence; the pure-Java
consumer loads a versioned native bundle. FP32 remains the reference and INT8 is
a measured candidate. Mechanical contracts precede the selected final human
review gate.

No training run exists yet. Approved data does: 190 ratified choices and nine
approved world documents. Training is blocked at their conditioning boundary,
not at review. The historical decision rows contain future facts and bare
options, and their version 2 cross-module key collapses distinct county events.
They remain protected intent and audit evidence; they are not admitted to a
training view. `../decisions/ELIGIBILITY.md` records the measured findings and
the version 3 admission contract.

The architecture ruling does not change that standing. It determines how
eligible data will train and ship; it does not manufacture acquisition,
conditioning or ratification for an existing row.

The version 1 [knowledge/authoring tool](../decisions/AUTHORING.md) now prepares
content-hashed views and separately authored proposals over frozen events. It
now imports one C74 same-person acquisition, reviews the claim boundary,
adjudicates the evidence and compiles an exact reviewed reference. This closes
the absence of a concrete acquisition example; it does not create a training
row. The source choice was forced, later consequences were not observed, and one
retained claim does not establish the person's complete decision-time knowledge.
Natural choice evidence, broader producer coverage and dataset-scale admission
remain required before training.

## From a world event to play

Record 52 covers one early stage of a longer causal path. Its value is that the
later model can receive Ada's knowledge without receiving every fact in the
world. It does not yet teach the model what to retrieve, say or understand.

| Stage | What exists | Effect now |
|---|---|---|
| World fact | The July 2 telecommunications outage in the approved Knox record | Establishes what happened |
| Person acquisition | SAO C74 records that Ada North was present, acquired the local claim through `lived`, and retained it through the later event | Establishes that this claim may appear in Ada's catalogue |
| Record 52 reference | Speakeasy reproduces that exact person/claim/time join and refuses the forced food choice | Tests the future catalogue producer; creates zero training rows |
| Dataset production | Complete catalogues, natural decisions, authored targets and task-specific approvals across many people | Not built |
| Learned runtime | The retriever selects relevant owned claims, the speaker expresses fenced claims, and the understander maps player text to typed intent | No trained model exists |
| Player experience | Different people can remember, omit and phrase different things while remaining unable to state facts they do not own | No behavior changes in this record |

The ratified architecture names a learned retriever but does not yet define the
source or review contract for its relevance targets. That remains a real ML
design decision. Record 52 supplies a valid input catalogue fixture for that
work; it does not settle the target.

The goal is named now (RECORD.md 45, the operator, 2026-09-13): the
end state is everything works and is ready to play, in theory, and
then the ML work runs a few training passes over the full dataset
and the runtime, tuned to a result sufficient for a first time play.
That is the pre-alpha to alpha bar. The order into it: the sandbox
options revision the operator named the same day, then readiness,
then the passes.

The budget has a ceiling now (record entry 26). SAO's `[C28]` probe is
pure arithmetic and touches no game state, so it was run standalone
against the compiled bridge over that batch's own five shapes: a 256x8
forward pass averages 387 microseconds on an idle Java 25 desktop,
about two percent of a 60fps frame, and 512x8 averages 1493, about
nine. Those are a CEILING - `[C28]` named the game's own thread under
the game's own load as the honest worst case, and this is neither, so
the in-game figures will be worse. The rule above stands: a size is
chosen against the ladder fired from the debug menu in a real session,
not against these.

What does NOT wait, and is already built on the SAO side: the
fence. Decision 4 ratified constrained decoding as the mechanism
for no-invention, and SAO's `SAOFence` (batch C47) implements it -
a model is handed the vocabulary its person can actually say,
slot by slot, read off that person's own claim set, and can emit
nothing else. Its correctness is proved mechanically over a
corpus, near-misses included, as the ratification required.

This matters here because it changes what a training run has to
achieve. The model does not have to learn not to lie about facts:
it cannot. What it has to learn is the language - how this person
says the things they are permitted to say. A run that scores well
on factual faithfulness has measured the fence, not the model.
