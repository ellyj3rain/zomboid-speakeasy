# Training

The runs that produce the two models, and the contract SAO loads
them by.

Rules:

- Model sizes cite measured in-game inference budgets, never a
  guess.
- Every run records its data snapshot, its size, and its result.
- The export contract (format, versioning, how a consumer loads a
  model) is designed here and recorded before the first export.

Empty. Waits on the first approved data.

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
