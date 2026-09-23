# Reported-source speaker example

Record 57 adds a bounded speaker example to the C77 conversation. The
understander and retrieval target already have independent operator approvals.
Mara has read the July 2 paper; Jon asks on July 11 what it reported about phone
service. This task checks an answer expressed from that selected report.

The exact proposed answer is:

> The July 2, 1993 paper reported that Knox Telecommunications' telephone and Internet networks failed across the Knox area for hours and were still down at press time; businesses closed; the cause unannounced, with talk of downed wires, lightning or sabotage.

The wording is formal because this first supported expression retains the whole
protected source-summary cell. Attribution and date distinguish a reported
outage at publication from present service conditions. The combined phone and
Internet wording comes from the source; it establishes neither household access
nor Mara's personal Internet use. The source is a curated summary, so this is
an attributed account, not a purported verbatim quotation of the native paper.

## Review and standing

`c77-example.json` names the exact speaker task and approved retrieval target.
`c77-review.json` holds the narrative review; `c77-invocation.json` is the exact
submitted Crucible panel. The speaker remains **proposed**, pending interaction
`skill-4ce382d92d3da70d`, item `seam-743ad57c38f3212a`. Neither earlier approval
approves the answer. The speaker needs its own exact-subject completed ruling;
freeform qualifications require interpretation and a revised proposal.

## Mechanical contract

Speaker task evidence uses `speakeasy-task-evidence` version 3. It keeps the same
outer row identity, input, output, required references and content seal as the
existing task evidence envelopes. The shared resolver dispatches version 3 to
the speaker validator before admitting an anchor.

| Surface | Meaning and check |
|---|---|
| Evidence input | Exact catalogue/context, imported capture hash, approved retriever target hash and underlying understander hash |
| `modelInput` | Selected claims and source summaries, question and semantic intent, speaker/listener, captured voice and situation, explicitly unavailable inputs |
| Source resolution | Exact person acquisition and reading receipt; protected file and line hashes; whole dated summary cell; date agrees with report hour and county calendar |
| Output | Answer act, exact speaker/listener, ordered reported-source parts and rendered text |
| Report part | `reported-source-summary`, selected claim reference, exact publication date and complete protected summary |
| Rendering | Explicit dated paper attribution plus the exact summary; output text must equal the rendering |
| Approval | Separate saved Mousecat subject and response lineage bind the complete speaker task hash |

The full catalogue is audit evidence outside `modelInput`. The speaker's
conditioning includes only the selected report, so another available personal
fact does not become an authorized utterance. The original question's listener
is Mara; the answer's speaker is Mara and its listener is Jon.

The validator refuses arbitrary literal parts, selective source clipping,
edited facts, substituted dates, extra prose, unselected references, duplicate
parts, role reversal, altered conditioning and missing upstream approvals.
These checks establish a bounded reported-source expression. Merely attaching
a valid claim ID to arbitrary prose would not establish factual correctness.

## Implementation limits and continuation

The ratified runtime remains learned free composition under constrained
decoding. This example compiler does not implement that decoder, choose a
sentence-selection model, or prescribe recitation as the voice of all people.
The deterministic register floors for hostility, guardedness, grief, threat,
work and exhaustion also remain unimplemented here. Their absence is explicit;
this formal answer is not acceptance evidence for those situations.

Every speaker conditioning report retains the upstream native-input and
dataset/evaluation exclusions and adds:

```text
speaker-free-composition-decoder-not-implemented
speaker-register-floor-admission-not-implemented
```

An approved example is not a trainable dataset or a model. Its next data-side
work is explicit task dataset construction and evaluation: keep this shared
capture together across splits, distinguish reference/grounding correctness
from wording quality, and exercise attribution/date mutations as failures.
The runtime's free-composition semantics and register floors need their own
implementation before natural paraphrases can receive the same mechanical
guarantee. No dataset split, evaluator result or runtime behavior is generated
by approving this example.

## Reproduction

```text
python tools/speaker_tasks.py --propose 02af1fc6d30b308d1d809140bc2972dfc563d825ef713c28fbc0d8071317fb73 --row-id c77-july2-report-speaker-001
python tools/speaker_tasks.py --validate training/evidence/147a1c1be6452110629c5e29c97ee8e7faf2203421fe33bc26727c9792bf27c8.json
python -m unittest discover -s tools -p "test_*.py"
```

`--approve TASK --receipt-hash HASH --snapshot-id ID` validates an already-saved
speaker ruling and publishes a task evidence snapshot. It never answers
Mousecat. Changing wording changes the reviewed subject and requires a new
proposal. A future retriever target using a speaker anchor retains the speaker
exclusions and still needs independent review.
