# C77 task-data preparation

This prepares separate, inspectable understander, retriever and speaker views
from immutable task evidence. The original [request](request.json) and
[preview](preview.json) preserve the pre-return checkpoint.
The current [request](request-revision.json) supplies the actual revision
receipt to the approval check, and its [preview](preview-revision.json) records
the resulting refusal, partition checks and each admitted model input/target.
The approval field is a candidate receipt to validate, not an assertion that
approval occurred. It is not a training run.

## What each learned task receives

| Task | Input | Target | Current evidence |
|---|---|---|---|
| Understander | Full owned catalogue and captured context, plus explicit incoming utterance roles: Jon speaks to Mara | Approved typed semantic frame | One exact approved example |
| Retriever | Full owned catalogue and context, without target labels or the answer-bearing anchor | Per-claim label and loss mask | One required report; seven unjudged claims; no reviewed negatives |
| Speaker | Selected bound facts, captured identities, question, semantic intent, situation and voice inputs | Actual answer text | Revision requested: excluded. Original wording approval remains separate |

For retrieval, a required claim receives label `1` with `lossMask: true`, a
reviewed hard negative receives `0` with `true`, and an unjudged claim receives
`null` with `false`. Consumers must preserve the mask. Omitting a fact from this
answer does not teach the model that the fact is irrelevant in every context.

The knowledge-capture roles differ from the incoming question's roles. Review
caught preparation dropping `utteranceRoles`; the corrected materializer
preserves the exact approved role map and rejects a resealed preview that omits it.

## Release and provenance

Only independently admitted samples appear in the preview's prepared rows.
Excluded requests remain visible in the admission report. Every requested task
needs its own nonempty training, validation and test partitions before dataset
release. Shared capture, source document and catalogue groups cannot cross
partitions, including across tasks. Caller ordering does not change output bytes.

Validation rebuilds the complete preview from the request and evidence store.
Changing labels, loss masks, text, inputs, standing or source receipts cannot be
made acceptable merely by recalculating the preview's hash. `release` revalidates
before returning data, and refuses this incomplete C77 collection. The affirmative
release state is `ready-for-tokenization`; tokenization, model training, model
evaluation and runtime admission remain distinct work.

The current real examples share one source family. All are assigned to the same
candidate training partition; validation and test remain empty. Approving the
speaker example does not repair that lack of independent scenes. Synthetic
Record 58 contrasts remain tests and have not been promoted into approved data.

## Reproduction

```text
python tools/task_data.py training/datasets/c77-preparation/request-revision.json --output training/datasets/c77-preparation/preview-revision.json --check
python tools/task_data.py training/datasets/c77-preparation/request-revision.json --output training/datasets/c77-preparation/preview-revision.json --require-ready
python tools/test_task_data.py
```

The first command reproduces the preview exactly. The second must refuse while
the dataset is incomplete. Without `--check`, the tool writes a new preview and
refuses to overwrite different existing content. A later review produces a new
request/result record; the previous preview remains historical evidence.

The [returned personality direction](../../speaker/PERSONALITY_REVISION.md)
requires richer existing-state capture and contextual contrasts before another
speaker task review. Next prerequisites are independently sourced and reviewed scenes for each task,
the shared frozen byte-level subword tokenizer, and the reference training and
evaluation pipeline. The single C77 scene remains useful as a regression example.

Verification: 121 tests pass, including ten new bound-task/data-preparation
controls. The protected conditioning audit passes, the Record 58 proof still
reproduces exactly, and this preview reproduces with seal
`6b42681c53cca7044b8c3eea715c28eacf419b7f6e3ae5d68e1ef2c0c1d16d75`.
The release command refuses with explicit missing-partition and excluded-row
reasons and leaves the saved files unchanged. Read-only speaker, data and
validation reviews completed; the utterance-role finding was fixed and rechecked.

After the actual return, the revision preview reproduces with seal
`25df630eadd4a356c405ee0a98e9b7566907da128dcb35e809d90ba759d11cb3`.
It still contains one understander and one retriever example and no speaker
example. The supplied response fails exact task approval; this is a refusal of
the revision receipt as permission, not an invalidation of its historical record.
The original preview remains unchanged.
