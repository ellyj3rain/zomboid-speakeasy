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

The original evidence envelopes bind task artifacts. Record 56 adds typed task
evidence version 2 over an exact imported source:

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

For legacy task evidence version 1, a v2 target can establish independent label approval. It cannot establish that
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

Record 56 implements bounded source coverage and understander validation for the
exact C77 import. Typed task evidence version 2 adds `sourceImportSha256` and
`utteranceRoles` to its input while preserving the catalogue/context bytes. The
resolver validates the typed row and source before comparing the anchor. For
these rows the original two exclusions are replaced by the actual remaining
limits: unavailable native inputs in the authored bodyless capture, and absent
task dataset splits/evaluation. Mixed snapshots retain the union of row
exclusions. Approval cannot erase them. See [the current task](../understander/README.md).

## First approved example

Record 55 supersedes Record 52's unsupported lived acquisition. The protected
July 2 source is an hours-long telephone and Internet outage report, ongoing at
publication. It establishes neither an individual's service use nor recovery
after hours. Historical approval hashes do not restore that acquisition.

SAO C77 supplies the corrected authored scene: Mara reads the July 2 newspaper
on July 10; Jon asks on July 11, "What did the July 2 newspaper report about phone
service?" Her fact remains `reported` and `read`, with separate publication and
acquisition hours. Jon has no receipt. The native completion executes over
controlled engine objects; it is not a transcript of play or autonomous reading.

The panel must show the person, listener, circumstances, actual report evidence,
complete catalogue, exact question and proposed interpretation together. A task
ruling teaches that interpretation; it establishes no current service condition
and does not approve the independent retriever target.

| Producer | Owner and implementation | Completion evidence |
|---|---|---|
| Corrected conversation import | Speakeasy imports the exact C77 capture and person-bound native reading receipt | Reject changed person, time, calendar, coverage or source hashes; retain report versus experience |
| Typed understander proposal | Validate frame fields, listener, claim and action references; preserve authored input standing | Human-readable scene and exact proposed meaning; no automatic approval |
| Independent retrieval review | Derive required references from the approved task, preserve unjudged facts and explain negatives | Separate exact-subject ruling with resolved evidence |
| Future computer sources | SAO integration binds actor, endpoint, service/application, content version or attempted operation, result and time | Installed mods or owned devices alone cannot grant knowledge; local failure cannot establish provider-wide outage |

The original C74/C76 artifacts remain historical. Record 56 implements the
corrected import, approved typed example and independently approved retrieval
target. Their exact hashes and saved rulings are in
`../understander/c77-example.json`. Both reviews are resolved. Record 57 adds the
[bounded speaker example](../speaker/README.md), with independent review and
explicit free-composition/register exclusions. Task evidence version 3 resolves
through the same anchor store; a target derived from it retains those exclusions.
Dataset splits and evaluation remain unimplemented. No trained model exists.
