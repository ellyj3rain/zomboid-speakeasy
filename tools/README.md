# Tools

`cross_module_rows.py` joins version 3 SAO decisions to ZAO state on the exact
run, county, person, event and hour namespace. It validates the complete inputs,
executable-option evidence, conditioning time and protected artifact hashes
before writing. A temporary sibling becomes visible through one atomic replace.

The historical version 2 rows are deliberately refused. Their approved intent
remains in place; their `(person, hour)` join and future conditioning do not meet
the version 3 evidence contract.

`coordination_tasks.py` compiles version 3 enacted-process rows into separate
actor-private decision and later-outcome horizons. It binds current work,
competing priorities, feasible responses, executor/body ownership and process
revision to their runtime producers. Same-moment ZAO pathogen state remains
audit-only: only ZAO-supplied activity and capability effects acquired through
the registered execution owner enter the decision input. The output is a
candidate observation, never automatic training admission. See the
[coordination contract](../training/coordination/README.md).

`audit_conditioning.py` reproduces the eligibility counts in
`decisions/ELIGIBILITY.md` from the protected version 2 bytes.

Run the join controls with:

```text
python tools/test_cross_module_rows.py
python tools/test_coordination_tasks.py
```

`decision_authoring.py` builds version 1 knowledge views and separately authored
proposals from immutable version 3 SAO rows or native C65 source-action captures.
It binds explicit actor acquisition evidence to approved-document excerpts and
the full event namespace, excludes future/LOW/unavailable claims, preserves
unreviewed evidence standing, and binds proposals to complete option hashes.
Every proposal remains unratified and conditioning-ineligible. Input formats,
commands and the remaining acquisition/ratification boundary are in
[`decisions/AUTHORING.md`](../decisions/AUTHORING.md).

`import_sao_world_knowledge.py` imports the Record 52 C74 evidence from an exact
SAO commit and validates its manifest, source hashes, event/acquisition binding
and protected source excerpt for historical integrity only. Record 55 supersedes
that acquisition. `r12_acquisition_example.py` refuses current regeneration and
validation; historical artifacts retain their original bytes.

`retriever_targets.py` implements Record 53's independently anchored target
policy. Record 54 upgrades its artifacts to version 2. It binds a supplied
SAO C75 claim catalogue to a separately approved
understander or speaker example, copies that example's required claim references,
accepts only explicit reasoned hard negatives, and records every other owned
claim as unjudged. A matching independent operator review is required before a
target can enter a dataset snapshot. Snapshot compilation requires complete,
non-overlapping splits plus explicit exclusions and evaluation receipts. The
tool creates no real row by itself and records all compiled targets and
snapshots as conditioning-ineligible. Version 1 task evidence retains its original
missing source/task exclusions; Record 56 typed tasks resolve the exact import
and carry the concrete native-input and dataset/evaluation limits.

`training_evidence.py` resolves canonical content hashes into saved task rows,
snapshot membership, exact-subject Mousecat results, exclusions and evaluation
evidence. It compares the entire task input and required references. Evaluation
evidence binds the exact row collection; this is not a model evaluator. The
compiler also groups shared task/catalogue sources within one split and refuses
to publish into its evidence store. See
[`training/retriever/EVIDENCE.md`](../training/retriever/EVIDENCE.md).

`.gitattributes` pins the checkout line endings of protected and imported evidence
to their existing recorded bytes so user Git settings cannot invalidate hashes.

```text
python tools/test_decision_authoring.py
python tools/test_import_sao_world_knowledge.py
python tools/test_retriever_targets.py
python tools/test_training_evidence.py
```


`conversation_tasks.py` imports a registry-reviewed C77 capture from exact SAO
Git blobs and verifies all installed sources against supplied local files. Its
version 2 task evidence retains the source catalogue/context and explicitly binds
incoming utterance roles. The frame validates speech act, owned claim references,
listener, directed stance and finite uncertainty. Action-bearing frames require a
future executable-option source contract. Immutable evidence publication verifies
seals before atomically exposing a new content address. `approve` resolves an
exact completed Mousecat ruling into a task evidence snapshot. It confers no
retriever approval. See [the task contract](../training/understander/README.md).


`speaker_tasks.py` proposes and validates version 3 speaker evidence over an
approved understander/retriever chain. Its bounded reported-source renderer
preserves complete source-summary cells, publication dates and attribution;
model input contains selected claims and exact voice/context channels. The
shared resolver validates this task version before anchor admission, and its
conditioning retains explicit free-composition and register-floor limitations.
See [the speaker example](../training/speaker/README.md). Its exact wording needs
independent Mousecat approval before a speaker evidence snapshot can be made.

`experiments/speech_constraints.py` characterizes the actual external SAO Java
fence and packaged jar alongside the production speaker renderer. It includes
membership controls, synthetic cross-claim associations, explicitly out-of-contract
prose probes and resealed speaker text mutations. The
[Field Test record](../training/experiments/speech-constraints/README.md) states
reproduction, observed results and limits; it is not a semantic admission gate.

`expression_proof.py` implements the bounded source-bound expression experiment.
`from_target` resolves the validated capture and participant names;
`compile_source` recognizes the declared report grammar/entities and typed
location fixtures; `produce` and `validate_output` enforce complete proposition
and rendering bindings. It is a finite construction proof, not arbitrary prose
validation. `experiments/expression_admission.py --check` reproduces the saved
[comparison](../training/experiments/expression-proof/README.md), including
actual validator defect controls and exact approved wording.

`experimental_admission.py` implements the explicit
`offline-authored-conversation-v1` scope. `inspect` reports exact source, input
and label standing; `compile_dataset` requires complete partitions and keeps
shared capture/document/catalogue sources together. Sample admission, dataset
readiness, evaluation and runtime have distinct results. Conversation and speaker
conditioning accept this scope explicitly; omitted scope preserves the legacy
API. Wording approval cannot become task approval, and missing native inputs
remain visible. The current dataset is excluded; no model is trained.

Speaker task version 4 carries the bound expression into the existing validator,
exact-task approval snapshots and shared evidence resolver. Use `--bound-plans`
with `--propose` for an explicit authored expression plan. Version 3 remains
supported. The [bound speaker example](../training/speaker/BOUND_EXAMPLE.md)
shows the actual scene, unchanged approved wording and new task-review consequence.

`task_data.py` prepares deterministic separate task inputs and targets from the
explicit offline admission scope. It preserves incoming utterance roles,
excludes unapproved rows, masks unjudged retrieval labels and keeps speaker
construction witnesses out of the text target. Whole-preview revalidation and
per-task independent partitions precede dataset release. See the
[C77 data preparation](../training/datasets/c77-preparation/README.md).

`behavior_comparisons.py` validates typed SAO behavior channels and prepares
whole-scene comparisons from exact registered imports. It separates the bounded
model input from audit-only owner state, measures channel differences against a
shared baseline and rebuilds the entire sealed result during validation. The
candidate replies are unreviewed authored text, with no training admission path.
See the [C78 family](../training/behavior/c78/README.md).

`byte_tokenizer.py` trains and loads a deterministic frozen byte-BPE vocabulary.
`tokenized_data.py` fits only the training partition of revalidated task data,
preserves byte-exact payloads and retrieval masks, and binds the vocabulary to
the resulting task preview. Release checks retain source admission and partition
requirements. The [reference artifacts](../training/datasets/c77-tokenization/README.md)
include the exact format, commands, known byte vectors and Java-parity limit.
