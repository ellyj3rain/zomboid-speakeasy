# Training

The runs that produce the two models, and the contract SAO loads
them by.

Rules:

- Model sizes cite measured in-game inference budgets, never a
  guess.
- Every run records its data snapshot, its size, and its result.
- The export contract (format, versioning, how a consumer loads a
  model) is designed here and recorded before the first export.

No training run exists yet. Approved data does: 190 ratified choices and nine
approved world documents. Training is blocked at their conditioning boundary,
not at review. The historical decision rows contain future facts and bare
options, and their version 2 cross-module key collapses distinct county events.
They remain protected intent and audit evidence; they are not admitted to a
training view. `../decisions/ELIGIBILITY.md` records the measured findings and
the version 3 admission contract.

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
