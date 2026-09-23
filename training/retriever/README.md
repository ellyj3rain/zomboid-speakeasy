# Retriever targets

The retriever chooses which facts from one person's current claim catalogue are
useful for one utterance and situation. Survivor Awareness owns that catalogue
and the factual fence. Speakeasy owns the examples that teach and measure the
choice inside it.

The operator selected `independent-anchored-targets` through Mousecat interaction
`skill-87fa148534b7e880`, item `seam-e7ecdee5ab14822d`. The machine-readable
receipt is [`policy.json`](policy.json).

## What one target means

The intended training target starts from two complete, immutable inputs. The
current compiler binds these inputs but does not yet prove catalogue coverage
or task-specific output validity (see [evidence and continuation](EVIDENCE.md)):

1. a C75 `sao-claim-catalogue` for one person, listener and tick; and
2. a separately approved understander or speaker example over that exact
   snapshot.

The task example supplies the claim references that were required to understand
or produce it. Those references become required positives. Every other owned
claim remains unjudged unless the retriever target explicitly names it as a hard
negative and records why it is tempting but wrong for this context.

| Label | Meaning during training and evaluation |
|---|---|
| Required | The approved task example needs this exact catalogue reference. Missing it is a retrieval omission. |
| Hard negative | An owned claim is a plausible wrong retrieval for this context. Selecting it is a measured error. |
| Unjudged | The person owns the claim, but this example establishes nothing about its relevance. It contributes neither a positive nor a negative label. |

For example, suppose a person knows about the July 2 Knox telephone outage,
Dana's location and Marcus's death. An approved interpretation of "Do you
remember the telephone outage on July 2?" can require the historical outage
claim. Dana and Marcus remain unjudged merely because the example omitted them.
A second telephone claim about another place or date can become a hard negative
only when review establishes that distinction. The protected record describes
an outage lasting hours; it cannot establish that telephones are still down on
July 11 or answer why a call fails that day.

This preserves several valid answers to the same situation. Brevity, attention,
trust and temperament can cause an answer to omit a useful fact without teaching
the retriever that the fact is irrelevant everywhere.

## Artifact flow

`tools/retriever_targets.py` implements the version 2 evidence-binding path:

| Artifact | Standing | What it proves |
|---|---|---|
| `speakeasy-retriever-anchor` | approved task reference | Exact approved understander or speaker row, current context, catalogue hash and required claim references |
| `speakeasy-retriever-target-proposal` | proposed | Required positives copied from the anchor, explicitly reasoned hard negatives and the exact unjudged catalogue complement |
| `speakeasy-retriever-target-review` | operator ruling | Approval or rejection of this exact proposal through a bound interaction and item |
| `speakeasy-retriever-target` | label approved, conditioning ineligible | Standalone input and labels bound to the matching saved review; source coverage and task validation remain unimplemented |
| `speakeasy-retriever-dataset-snapshot` | label collection, conditioning ineligible | Approved labels, exact train/validation/test assignment, resolved exclusions and evaluation evidence, and derived counts |

Approval of the understander or speaker row does not transfer. The retriever
row has different meaning and needs its own ruling. Catalogue identity, task
anchor, proposal and approval are all content-hash bound. Unknown, duplicate,
foreign, reordered and stale claim references refuse the build.

The compiler records the unjudged complement explicitly. The future loss
function and retrieval evaluator must honor it; neither exists yet. Dataset
snapshots refuse missing splits and shared task or catalogue sources crossing
splits. Split sizes and class balance remain measured dataset parameters.

The compiler opens the exact task row, snapshot membership and saved Mousecat
answers. Source task approval and retriever approval each bind their own content
hash. Exclusion and evaluation objects must exist; evaluation evidence names the
exact compiled row hashes. This verifies evidence integrity and scope, not model
quality or source completeness. The evidence formats and trust boundary are in
[EVIDENCE.md](EVIDENCE.md).

## Commands

Place the source evidence in `training/evidence/` (or pass `--evidence-root` to
any command), then create a proposal from a catalogue and approved task anchor:

```text
python tools/retriever_targets.py propose --catalogue CATALOGUE.json --anchor ANCHOR.json --proposal-id ID --hard-negative CLAIM_REF=REASON --out PROPOSAL.json
```

Admit the exact proposal after its independent operator review:

```text
python tools/retriever_targets.py admit --proposal PROPOSAL.json --review REVIEW.json --row-id ID --out TARGET.json
```

Compile approved rows into a snapshot with explicit split, exclusion and
evaluation-receipt files:

```text
python tools/retriever_targets.py snapshot --snapshot-id ID --target TARGET.json --splits SPLITS.json --exclusions EXCLUSIONS.json --evaluation-receipts RECEIPTS.json --out SNAPSHOT.json
```

Run the controls with:

```text
python tools/test_retriever_targets.py
python tools/test_training_evidence.py
```

## Current state

No real retriever row or dataset snapshot exists yet. Record 52 supplies one
reviewed person-claim reference, and SAO C75 supplies the typed catalogue and
selected-claim fence, but no approved understander or speaker example exists to
anchor a relevance target. Record 53 established the policy; Record 54 repairs
the compiler's unresolved evidence references and incomplete context comparison.
Both create zero training rows, change no model weights and change nothing in
play. The next producer captures an actual immutable conversation snapshot in
SAO, including coverage evidence for the person's available knowledge. A typed
task example and its independent retrieval target then follow that capture.
