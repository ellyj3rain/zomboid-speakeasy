# Learned runtime and training architecture

| Field | Value |
|---|---|
| Status | RATIFIED 2026-09-21 through Mousecat Mass Assault; retriever target policy extended 2026-09-22 through Mousecat Crucible |
| Timestamp | 2026-09-21 08:50 UTC / 01:50 PST; retriever policy 2026-09-22 07:18 UTC / 00:18 PST |
| Interaction | `skill-e6acce0f301ef127`; retriever policy `skill-87fa148534b7e880` item `seam-e7ecdee5ab14822d` |
| Owner | Speakeasy owns data, training, reference inference and export; SAO owns the in-game consumer, current-state revalidation and durable runtime state |
| Scope | The learned retrieval, understanding and speaking path that follows the version 3 decision and knowledge contracts |

This contract resolves the model shape that the earlier speech design left open.
It does not make any existing row training-eligible. Record 52 now supplies one
reviewed person-claim reference, and SAO C75 supplies the typed snapshot-local
catalogue and selected-claim fence. Neither artifact is an approved understander,
retriever or speaker row.

## One base, typed tasks

The first runtime bundle has one shared base model with task-specific adapters.
The understander and speaker remain different learned functions with different
typed contracts and separate evaluation. They share base weights and a tokenizer;
an adapter route is explicit in every request and result. A failure in one task
cannot be interpreted as a result from another.

The learned retriever is a third learned function in the bundle. Its exact weight
sharing is set by measured model size, latency and retrieval quality before model
dimensions are fixed. It uses the same tokenizer and bundle version and cannot
become a separate service or an unversioned runtime dependency.

## Understander contract

The understander consumes player text, the listener identity, the current
conversation target, and the bounded current context supplied for that decision.
It emits a typed semantic frame:

| Field | Meaning |
|---|---|
| `speechAct` | question, statement, request, offer or threat |
| `claimRefs` | claim identifiers the utterance refers to |
| `requestedAction` | the requested executable action or `null` |
| `stance` | the utterance's directed social stance |
| `uncertainty` | the model's uncertainty for the frame |
| `listenerRef` | the intended listener identity |

Every identifier is checked against the immutable input snapshot. Unknown claim,
action or listener references refuse the frame. A semantic frame changes no
belief, relationship or action by itself; the existing communication and action
owners decide what an admitted frame does.

## Learned knowledge retrieval

Each inference begins with the person's own current claim catalogue. The learned
retriever selects a bounded set of claim identifiers for the current utterance
and situation. The runtime then supplies the selected claims with their
provenance, age, uncertainty and access evidence. Retrieval never creates claim
text or authorizes a claim absent from the person's catalogue.

Retrieval quality is measured separately from model fluency. Omitted relevant
claims are observable retrieval misses. A retrieved claim whose current access,
retention or identity no longer validates is removed before the understander or
speaker can use it.

## Bounded model memory

The runtime keeps a bounded, versioned per-person model cache across decisions.
This is a second memory owner and therefore has an explicit save, load,
invalidation and eviction contract. The cache is bound to person identity, model
bundle version and the person's current knowledge revision. A mismatched,
unreadable or unsupported cache is discarded without changing the person's SAO
claims or relationships.

The cache may influence continuity, attention and wording. It does not authorize
a fact or executable action. Any fact-bearing output still names current claim
identifiers and passes the claim fence; any action still names a current option
and passes revalidation. Cache bounds are chosen from measured save size, memory
and latency evidence rather than guessed here.

## Speaker conditioning and fence

The speaker receives selected claims plus typed temperament, trust, situation
and energy channels. Deterministic register floors remain outside the learned
output: hostility limits disclosure, guardedness limits length, grief does not
become casual chat, threat permits one short sentence and no question back, work
permits only what the work needs, and an exhausted person does not chat.

The speaker decodes through SAO's claim fence. Structural tokens and factual
slots can refer only to admitted claim identifiers. Learned wording is free
inside that boundary; the model cache and retriever cannot widen it.

## Frozen tokenizer

All learned tasks use one frozen byte-level subword vocabulary with reserved
structural tokens for schemas, claim references and fenced slots. Its bytes and
normalization rules are part of the bundle identity. Arbitrary player text is
lossless at the byte boundary; an unknown word or name cannot become an unknown
token that the understander silently drops. Training and pure-Java inference
must produce identical token sequences before a model is compared.

## Separate task datasets

The understander, retriever and speaker train from separate datasets. Each
dataset owns its schema, snapshot, provenance, splits, exclusions and evaluation
receipts. None inherits standing from another.

When rows in the three datasets refer to the same county event, each retains the
full version 3 namespace and immutable event, option and claim references. The
build compares those shared references and refuses contradictory identity,
calendar, source or standing. Task-specific fields may differ; the facts they
cite may not silently drift.

The understander dataset maps utterances and current context to typed semantic
frames. The speaker dataset maps admitted claims, semantic intent and typed voice
conditioning to fenced expression. Approval in one dataset does not approve a
row in another.

The retriever dataset uses independent anchored targets. A separately approved
understander or speaker example supplies exact required claim references over a
complete bound catalogue. Other owned claims remain unjudged. A claim becomes a
hard negative only when the retriever target names it and review establishes why
it is a plausible wrong selection for that context. The target then receives its
own operator ruling; approval of the anchor does not transfer.

Required-claim recall and reviewed-hard-negative selection are measured against
their labels. Unjudged claims do not count as correct or incorrect. This prevents
one valid omission from becoming a universal irrelevance label. The exact policy,
artifact flow and current zero-row standing live in
[`retriever/README.md`](retriever/README.md).

## Runtime scheduling

Inference runs asynchronously from an immutable decision snapshot. The snapshot
binds person, listener, event, claims, executable options, permissions, bundle
version and current revisions. No model result mutates the world from the worker.

When a result returns, SAO revalidates the exact identities, claims, options,
permissions and current owner state. A stale or failed result is withheld. A new
decision may take a new snapshot; the old result is never relabelled as current.

## Versioned native bundle

Speakeasy exports one SAO/Speakeasy bundle for the pure-Java consumer. Its
manifest binds:

- bundle, schema and model versions;
- tokenizer bytes and reserved structural tokens;
- shared base weights and every task adapter;
- retriever artifact and index contract;
- numerical precision and quantization parameters;
- understander, retriever and speaker dataset snapshots;
- source, training and evaluation provenance;
- compatibility requirements for the SAO consumer.

Every component is content-hashed. The consumer refuses missing, extra,
unsupported or mismatched components before inference. ONNX is not the first
authoritative interchange and no external inference runtime is required.

## Precision and candidate admission

FP32 is the reference model. INT8 is a deployment candidate measured against the
reference for typed-output parity, retrieval behavior, fenced speaking, stale
result refusal, memory and latency. Compression has no standing merely because
it loads or runs faster.

A runtime candidate first passes the mechanical contracts: schema and bundle
integrity, reference parity, claim-bound output, executable-reference validity,
cache reconstruction, stale-state rejection and the measured in-game budget.
Human review is the final gate for usefulness, voice and conversational quality.
It cannot waive a failed mechanical contract. The reviewed artifact and its exact
receipts are the artifact admitted for runtime evaluation.

## Work this contract unlocks

The next producer captures an immutable conversation snapshot in SAO: county
and calendar identity, person and listener, current context and revisions, the
C75 catalogue, and evidence of source coverage. Speakeasy then imports that
capture and validates a typed understander or speaker example over it. Its
approved required references can anchor a retriever target for separate review.

Record 54's version 2 compiler resolves task evidence and saved approvals, but
source-catalogue coverage and task-specific schema admission remain unimplemented.
It therefore records every compiled target and snapshot as conditioning-ineligible.
This is an implementation boundary, not a new operator decision. The concrete
sequence is in [retriever/EVIDENCE.md](retriever/EVIDENCE.md). After eligible examples
exist, Speakeasy can build the three task datasets, frozen tokenizer, reference
pipeline and native bundle writer. SAO can build a bundle reader and
snapshot/revalidation harness before a trained candidate exists. Model dimensions,
cache bounds, worker concurrency, INT8 tolerances and the human-review rubric stay
evidence-driven and are fixed only by their respective measurements.
