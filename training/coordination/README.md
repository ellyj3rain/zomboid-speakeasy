# Enacted coordination task evidence

Status: implemented candidate-observation contract plus one approved bounded
offline reference run. Record 66 approves the response kinds of 20 exact C81
synthetic production rows; it does not demonstrate a loaded-world scene,
population frequency, native model, or learned runtime.

Records 64-65 correct Record 63's execution ownership and carry the resulting
state-policy boundary while retaining its version 3 source namespace. A recipient's
decision row names one run, county, person,
event and decision hour. Its executable options bind the same actor, process and
proposal revision to `SAO.Organization.respond`. Same-moment ZAO state remains
join audit evidence; pathogen truth and other people's visible forms do not enter
the actor's decision input.

| Horizon | Included evidence | Excluded evidence |
|---|---|---|
| Decision time | Acquired proposal and reception, current activity, source-owned competing pressure/relationship/interests/constraints, executor/body owner, current capabilities, feasible responses and the response formed at that hour | Return-channel success, commitments, route/work receipts, later process state, hidden pathogen truth |
| Later outcome | Return-channel receipt, process standing and that actor's revision-bound commitments with acquisition, route and handover results | Private inputs, proposal/reception payloads and other participants' responses |

`tools/coordination_tasks.py` emits task schema version 2 and refuses a wrong person, incomplete or extended v3
namespace, stale proposal/response/commitment revision, impossible response,
missing input owner, unavailable executor advertised as capable, foreign work
owner, missing pressure availability, hidden diagnosis/pathogen/form/diet fields,
future timestamp and any commitment or delivery fact in the decision horizon.
An older decision revision remains addressable after the process is revised;
the later horizon records the observed current revision separately.

The compiled view makes current work and competing priorities legible without
creating new priority weights. Competing pressure carries separate value,
availability and source owner; an unavailable value is null instead of a
misleading zero.
Relationship, interests and constraints remain source-owned. Survivors execute
through SAO. Afflicted and Crossed living human shells both execute through the
registered `ZAO.Driver`, while their distinct policy inputs remain behind their
ZAO owners. Crossed ordinary physiology and human-origin preference remain
distinct from Crossed predatory pressure; Afflicted water, food and protein
maintenance remain distinct again. None is named by this generic pressure field.
The task does not infer diagnosis, satisfier, diet, predation or behavior from shared
execution ownership.

Run the focused controls with:

```text
python tools/test_cross_module_rows.py
python tools/test_coordination_tasks.py
```

The tests use controlled rows to discriminate the contract. SAO's installed
Kahlua border separately executes proposal, response, revision, work receipt,
pause/resume and persistence behavior and now emits the production v3 envelope.
A cross-repository check preserved and compiled all 13 emitted rows through ZAO,
covering all seven response kinds and one completed-work result. This remains a
controlled headless mechanism run, not a sampled game session. Independent task
review and admission were required before this path could contribute training
data. Record 66 supplies that review for one exact source family only.

## Record 66 bounded reference learning

`tools/coordination_data.py` imports the committed C81 evidence from exact Git
objects rather than trusting checkout bytes. It binds SAO commit
`6ce4b90c5a4b726063361b98c6214fded7d709ce`, ZAO commit
`7ffbcbadb31ae3dc4ac619bcf18806121e6e938c`, every producer-source hash,
the ZAO state projector and both existing coordination compilers. The sealed
source import is `82940233a0f05ec6f97770a862ce1903fb7b06f8806f2c5cff7184eacde69e77`.

The review subject exposes all 20 rows and their production response while
keeping the explicit actor-kind/pathogen record audit-only. It was approved without notes in
Mousecat interaction `skill-e7d7df5652dcc08e`, item
`seam-ed76c930231378ee`. Admission resolves the platform-generated item through
the exact evidence reference and unique response, not through a caller-invented
item ID. The exact subject is
`f522fbda0dcb0beaf2fde9e780c954ec1e8c8b2d49bc491775189497f392c0e4`;
the native receipt is
`c3ed75dbd5215e9720095b3269f17a0d7aa95caecce04c5f4b4f6eaea2f7867c`.
An earlier approval receipt,
`b62c494f0829e57bddd153ea75cd7147ed72e7acc66be8bf41aec873d1336a26`,
remains retained as superseded audit history: changing the resolver changed the
sealed review subject, so it could not admit the final compiler.

The admitted dataset is
`a910256c51a5ab2355348ef81100fb14fcaf675c594c0cad33278c43a67c560d`.
Its 20 source lineages divide into 10 train, 5 validation and 5 test rows, with
four examples each of accept, qualify, counter-propose, defer and contest. It
contains seven survivor, six Afflicted and seven Crossed audit identities.
Decline and withdraw remain in the response vocabulary but have no observed
target and cannot be predicted by this run.

`tools/coordination_reference.py` trains a deterministic learned 8-dimensional
byte-token mean embedding and typed softmax adapter. It reuses the frozen shared
tokenizer, seed 66081 and 1,200 full-batch epochs. The model sees the acquired
proposal, reception evidence, current work, source-owned current pressure,
relationships, interests, constraints, capabilities and feasible responses. It
does not see route IDs, explicit actor-kind/pathogen records, the authored choice,
source split, delivery standing or later outcomes. Current executor/body ownership,
activity and pressure provenance remain legitimate decision-time effects. At prediction time both the observed-label
set and current feasible-response set constrain output.

The sealed run is
`eea4f4747bc2277a4a51178038272e428f770687308662b1f44ba46ffeaa5b62`.
Train, validation and test accuracy are each 1.0 over 10, 5 and 5 examples;
negative log likelihood is 0.085255833757, 0.317123748973 and 0.250889491458.
The zero-epoch test reaches 0.2 accuracy with 1.60361673193 NLL, while a
permuted-target training control reaches 0.0 with 3.882001268702 NLL. These
controls discriminate the learned run from initialization and wrong labels.
Audit-only breakdowns are reported for survivor, Afflicted and Crossed rows.
Changing only that audit identity does not change model input; changing an actual
current activity, execution owner or source-owned pressure can.

Reproduce the exact boundary and run with:

```text
python tools/coordination_data.py validate --import-dir training/coordination/r66-source
python tools/coordination_data.py admit --import-dir training/coordination/r66-source --review-receipt training/evidence/c3ed75dbd5215e9720095b3269f17a0d7aa95caecce04c5f4b4f6eaea2f7867c.json --out training/coordination/r66-source/dataset.json
python tools/coordination_reference.py train --dataset training/coordination/r66-source/dataset.json --out training/coordination/r66-reference
python tools/coordination_reference.py validate --dataset training/coordination/r66-source/dataset.json --run-dir training/coordination/r66-reference
```

Perfect results on this deliberately balanced production-rule family establish
only deterministic bounded learnability. The rows begin from synthetic starting
conditions and are not a natural gameplay sample. No loaded person chose through
this adapter, no native bundle consumes it, and no measured result describes how
often any response or pressure dominates play. In particular, shared
`ZAO.Driver` execution does not make Afflicted and Crossed physiology, motives,
maintenance or action policy interchangeable.
