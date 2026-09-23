# Source-bound understanding

Record 56 connects the corrected C77 capture to a typed understander proposal.
Mara reads the July 2 Knox Knews on July 10. On July 11, Jon asks her:

> What did the July 2 newspaper report about phone service?

The proposed meaning is a neutral question addressed to Mara, referring to her
personally acquired report. It requests no executable action. The report was
ongoing at publication. Nothing here establishes personal Internet use, household
access, recovery after hours or service conditions on July 11.

Approving this example teaches the interpretation of the incoming question.
The eventual answer's wording belongs to a separately authored speaker example.
A separately reviewed retriever target can learn to select the report from her
eight-claim catalogue; the other seven facts remain unjudged.

## Current artifact and review

`c77-example.json` names the exact content-addressed import and task proposal.
`c77-review.json` contains the human-readable scene, system role, causal path,
player consequence, proposed meaning, approval effects and evidence.
`c77-invocation.json` sends that exact panel through Mousecat Crucible with the
task hash as its evidence reference. The task is **approved** through interaction
`skill-41b0c21490237499`, item `seam-3502bc9a6ecbd395`, with no qualifications.
The exact saved response resolves into the task evidence snapshot in the index.
The independent retrieval proposal is **proposed**, awaiting its own ruling in
interaction `skill-49b957a427fb7f46`, item `seam-789dd79fd57f044e`. Its narrative
panel and submitted invocation are `c77-retriever-review.json` and
`c77-retriever-invocation.json`.

No approval is inferred from submission, opening the panel, or a passing test.
The live result is checked through Mousecat's returned continuation. Pending,
held, rejected, stale and qualified answers cannot create an approved snapshot.
Freeform qualifications must be interpreted and incorporated into a new exact
proposal before approval can be consumed.

## What the compiler checks

| Boundary | Evidence |
|---|---|
| Source authenticity | Repository-reviewed registry pins the SAO commit, capture and manifest; hashes alone are not signatures |
| Source integrity | Import reads capture and manifest from the exact Git commit and checks all 58 repository blobs plus three installed source files |
| Personal acquisition | Schema 2 world owner, exact person, reading completion, held issue identifiers, source excerpt, retention and separate publication/acquisition hours |
| Context | Exact namespace, calendar, participants, positions, catalogue and authored question |
| Typed interpretation | Exact six-field frame, known speech act, ordered unique owned claims, intended listener, directed stance, finite uncertainty and null action |
| Review | Saved completed Mousecat item/answer lineage names the exact task hash |
| Independent retrieval | Existing resolver reads version 2 task and its imported source before constructing an anchor |

The capture's catalogue `listenerRef` names Mara's conversation partner, Jon.
Incoming `utteranceRoles` explicitly name Jon as speaker and Mara as listener.
The frame's listener is Mara. Preserving both meanings prevents role reversal
without rewriting the captured source.

Stance has a nonempty `label` and an exact `targetRef`; review judges the label's
meaning. The proposed `neutral` label and `uncertainty: 0` describe this authored
question's interpretation. Zero does not assert source truth or measured model
confidence. Runtime uncertainty requires calibration evaluation.

The native issue probe stores `knoxknews`; the controlled completion stores
`KnoxKnews`. The importer checks normalized media identity and exact issue keys,
while preserving both original values and the controlled item identity. This is
evidence from controlled native completion, not a captured native inventory item
from play or autonomous NPC newspaper reading.

## Scope and remaining work

Knowledge-topic coverage is complete for this bodyless host. Native current
needs, bite and loaded-controller pressure are explicitly unavailable. This
limitation stays attached to the example; it is not a permanent prohibition on
using authored data in a future explicitly scoped dataset.

The current compiler records the unavailable native inputs and missing task
dataset splits/evaluation as conditioning exclusions. Historical version 1 task
evidence retains its older missing-source/task exclusions. No model is trained
and no game behavior changes. C77 has no executable-option inventory; an
action-bearing frame requires that source contract before admission.

The approved task now anchors an independent retriever proposal with claim 0005
required, no presumed hard negatives, and seven unjudged claims. Resolve its own
Mousecat ruling before admitting the retrieval target. Dataset production,
speaker fencing and evaluation remain distinct implementation work.

## Reproduction

```text
python tools/conversation_tasks.py --import-source sao-c77-authored-report --sao-root SAO_CHECKOUT --game-root INSTALLED_GAME
python tools/conversation_tasks.py --validate-task training/evidence/6acc7ddbad5e25d201ce04e6c1cd54f65fc87fe619c8b794fbe860340f0fa5a7.json
python -m unittest discover -s tools -p "test_*.py"
python tools/audit_conditioning.py
```

The Python `propose(imported, row_id, frame)` interface validates and seals new
typed candidates; `save_evidence` checks a seal before immutable atomic
publication. `--approve-task TASK --receipt-hash HASH --snapshot-id ID` resolves
the already-saved operator receipt and creates a task evidence snapshot. It
cannot answer Mousecat or approve a retriever row.
