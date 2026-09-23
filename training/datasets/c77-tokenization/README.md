# Shared tokenizer reference

Record 61 implements the frozen byte-level subword tokenizer in the ratified
shared-base architecture. The understanding, retrieval and speaking tasks use
the same vocabulary. It preserves unfamiliar names, punctuation, whitespace and
all byte values. This reference fits an experimental vocabulary to the current
C77 preparation and saves its exact bytes and token sequences for reproduction.

The source [preparation](../c77-preparation/preview-revision.json) contains one
understanding example and one retrieval example. The speaker task remains
revision-requested and excluded. Missing independent evaluation partitions keep
this tokenized preview excluded from reference-model training. The four C78
behavior comparisons contribute no text, labels or approvals to this vocabulary.

| Artifact | Content |
|---|---|
| [tokenizer.json](tokenizer.json) | Frozen rules, reserved IDs, ordered byte-pair merges and training-segment hashes |
| [preview.json](preview.json) | Exact preparation/tokenizer identities, separate task partitions, token IDs, target masks and unchanged admission limits |
| [vectors.json](vectors.json) | Empty text, every byte value, repeated pairs, literal marker strings, whitespace and Unicode reference sequences |

## Byte and task contracts

Byte IDs are `0..255`. Reserved structural IDs are `256..266`, in this order:
`bos`, `eos`, `pad`, `understander`, `retriever`, `speaker`, `schema`, `input`,
`target`, `claim-ref`, `fenced-slot`. Merge IDs start at `267`; each merge refers
only to earlier byte-bearing IDs. The loader refuses changes to these rules,
future/structural merge references, duplicate byte tokens and invalid identities.

Fitting counts adjacent pairs within each independent segment. It chooses the
highest count (at least two), breaking ties by the lowest integer token-ID pair.
Each replacement consumes non-overlapping matches from left to right. Encoding
applies the frozen merges in their saved rank order. Both operations cap merged
tokens at 1,024 bytes. Corpus order has no effect; duplicate segments retain
their frequency. A merge budget is explicit in the artifact, bounded at 8,192;
this small reference uses 64. That value is an experiment configuration, not a
chosen production model or vocabulary size.

Text uses strict UTF-8 without Unicode normalization, case folding, stripping or
newline conversion. The byte API also round-trips non-UTF-8 data. The text API
refuses invalid Unicode scalars or invalid decoded UTF-8 instead of replacing
them. Literal text resembling a structural marker remains ordinary byte tokens.
Only the task serializer emits structural IDs. Reserved claim/slot markers do
not confer factual entitlement or implement the speech meaning constraint.

Model inputs and sequence targets serialize as the existing canonical JSON:
sorted keys, compact separators, UTF-8 and no nonfinite numbers. Each input is
`bos, task, schema, input, payload, eos`; each sequence target is
`target, payload, eos`. These are separate arrays. The target marker has a false
loss mask; the target payload and end marker have true masks. No truncation or
padding is performed; future batching must declare and check length limits.

Retrieval uses the same tokenized input and retains structured claim labels and
their exact masks. It has no sequence target. Its seven unjudged claims have
`label: null, lossMask: false`; the one required claim remains the only active
target. A future retrieval adapter must consume that mask. It must not train on
serialized nulls or treat unjudged claims as negatives.

Only train-partition input payloads and admitted sequence targets fit the
vocabulary. Validation/test payloads, retrieval labels, provenance metadata,
excluded examples, behavior comparisons and review prose do not. The caller
first revalidates the preparation against its source evidence. Tokenized-data
validation then refits the declared vocabulary from the exact train segments
and reconstructs every token, mask, source binding and release field. Changing
a saved result and resealing its hash cannot bypass those checks.

## Reproduction and standing

```text
python tools/tokenized_data.py training/datasets/c77-preparation/preview-revision.json --output-dir training/datasets/c77-tokenization --check
python tools/tokenized_data.py training/datasets/c77-preparation/preview-revision.json --output-dir training/datasets/c77-tokenization --check --require-ready
python -m unittest discover -s tools -p test_byte_tokenizer.py -v
```

The first command must reproduce all three files. The second must refuse with
the source dataset's excluded-row and missing-partition reasons before writing.
Without `--check`, the command creates missing outputs and refuses differing
existing content. A changed corpus or merge budget needs a new output directory.

The tokenizer seal is
`de647099663341a23d8dd85f940770bc866f96b738545eaa42253229cdef1c6d`;
the preview seal is
`536511facee55636b034f6cef28773d4b5d4178d70cf16fb07e2179dc0254b6c`.
The saved vectors provide the target for later pure-Java token parity. They are
not evidence that a Java implementation already matches. No learned weights,
factual-language guarantees, trained voice or game-runtime behavior are added.

Next work remains source coverage and independent scenes, broader supported
communication acts, approved task examples and evaluation partitions. Those
enable a reference training run. Its tokenizer must freeze against that run's
training data, with separately measured held-out behavior and Java parity before
runtime admission.
