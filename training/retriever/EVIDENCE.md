# Retriever evidence and continuation

Record 54 makes retriever admission resolve the artifacts named by a target.
The label policy remains Record 53's operator ruling. Retriever anchor, proposal,
review, target and snapshot schemas are now version 2. Version 1 is refused;
there are no real rows to migrate. SAO's catalogue remains version 1.

## What changed

The Record 53 compiler checked that task and approval hashes looked like hashes.
It never opened those artifacts. It also compared only person, listener and tick
between the target context and its task anchor. The motivating control replaced
the question about telephones with "Where is Dana?", recomputed the proposal
hash, and reached `standing: approved` using fixture-only references. Record 54
refuses that input at the context mismatch and refuses missing source evidence.

| Verification | Evidence actually read |
|---|---|
| Source task exists | Exact task evidence document, including its input, output and required claim references |
| Source task belongs to the cited snapshot | Exact snapshot identity, task and matching row/approval entry |
| Anchor describes that source task | Complete catalogue and context equality; required reference equality |
| Operator approved that source task | Saved Mousecat result whose item and response lineage name that exact content hash |
| Operator approved the retriever proposal | Separate saved Mousecat result bound to the proposal hash, interaction and item |
| Dataset excludes a row or cites an evaluation | The named evidence object; evaluation evidence must name the exact dataset row hashes |
| Split independence | A source task or catalogue snapshot cannot appear in multiple splits |

Pending answers, rejection, mismatched items, duplicate answers and qualified
approval do not admit a row. Notes accompanying approval require interpretation
and a revised exact proposal so their conditions cannot disappear. A hash proves
content integrity. The repository review of imported receipts establishes their
authenticity; these files are not digital signatures.

## Evidence storage

`training/evidence/<digest>.json` is the default evidence location. The CLI accepts
`--evidence-root DIRECTORY` for another reviewed collection. The compiler reads
that directory and refuses to publish into it.

Sealed Speakeasy evidence uses the existing canonical JSON body hash, excluding
`contentSha256`. A raw Mousecat result uses the canonical hash of the complete
JSON object. Both use sorted keys, compact separators, UTF-8 and finite numbers.
Every read recomputes the digest. Merely renaming a file cannot change its
identity. Duplicate JSON keys are refused by the existing strict reader.

Two small evidence envelopes bind task artifacts without defining a new model
output grammar:

| Envelope | Required body fields |
|---|---|
| `speakeasy-task-evidence`, version 1 | `rowId`, `task`, `input` containing the exact `catalogue` and `context`, complete `output`, `requiredClaimRefs` |
| `speakeasy-task-evidence-snapshot`, version 1 | `snapshotId`, `task`, `rows` containing `rowId`, `rowContentSha256`, `approvalReceiptSha256` |

Each envelope also carries `schema`, `schemaVersion` and the existing
`contentSha256` seal. A task evidence snapshot indexes the cited task artifacts;
it is not a trainable task dataset. The task-specific builder still owns semantic
frame validation, speaker fencing and source admission.

For a row review, the submitted Mousecat seam's `evidenceRef` is
`speakeasy:content-sha256:<exact-subject-hash>`. The saved returned item and answer
must preserve this reference. The v2 retriever review's `decision` now includes
`resultSha256`, resolving that saved response in addition to its interaction,
item and value. The policy ruling cannot substitute for a row approval because
it binds a different subject and option.

Exclusion/evaluation evidence contains the cited `id` and `reason`. Evaluation
evidence also contains `rowContentSha256s`, the sorted complete set of evaluated
target hashes. This verifies its scope; it does not evaluate a model. The actual
retrieval evaluator, loss masking and model training remain future work.

## Label approval and training eligibility

A v2 target can establish independent label approval. It cannot establish that
SAO supplied every currently available fact, or that an understander/speaker
output passed its task-specific mechanical contract. C75 has no export receipt
for complete conversation-source coverage, and the task-specific builders are
not implemented. Targets and compiled snapshots therefore explicitly retain:

```json
{
  "status": "ineligible",
  "exclusions": [
    "source-catalogue-coverage-not-verified",
    "task-schema-admission-not-implemented"
  ]
}
```

Those are measured missing mechanisms, not operator-imposed prerequisites.
Approval does not erase them. This batch creates no real target, training row,
model or runtime behavior.

## Next concrete example

The protected source establishes a telephone and Internet outage **for hours on
July 2**, and Record 52 establishes Ada's retained memory of it. It does not
establish a continuing outage on July 11. The earlier question "Why can't we call
for help?" is therefore unsuitable as a sole-positive example over this fact.

The proposed first understander example is an explicitly authored exchange:
"Do you remember the telephone outage on July 2?" Its candidate frame would mark
a question, refer to the retained historical claim, and request no executable
action. The eventual panel must show the exact source claim, date, person,
listener, complete input catalogue and proposed frame. Approval would teach that
interpretation of this question; it would establish nothing about current phone
service or the cause of either outage. This is a planned candidate, not an
approved example or a transcript of play.

| Next producer | Owner and implementation | Completion evidence |
|---|---|---|
| Immutable conversation capture | SAO: capture full run/county/person/event/time namespace, calendar, listener, current revisions and every requested knowledge topic; record source failure and coverage explicitly | Export from the production catalogue over frozen owner state; prove that a missing source cannot masquerade as an empty known set |
| Person-specific import | Speakeasy: import exact snapshot bytes and source receipts; retain Record 52's reviewed historical claim and controlled-choice exclusions | Rebuild from the exact SAO revision; reject changed person, time, calendar, coverage or source hashes |
| Typed understander proposal | Speakeasy: validate the ratified frame fields and each listener, claim and action reference; keep authored input distinguishable from play | Concrete candidate and readable Mousecat card; no automatic approval |
| Independent retrieval review | Speakeasy: derive required references from the approved task, preserve unjudged facts and present any hard negatives with reasons | Separate exact-subject ruling, then v2 evidence validation |

The first conversation capture is the next implementation step. The existing
catalogue test's stub people and Record 52's forced food-source event cannot
establish it by relabelling their fixtures.
