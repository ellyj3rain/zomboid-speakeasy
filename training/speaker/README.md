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

The operator answered the original review: **"This information is valuable but
I can't approve it without the actual personified answer."** The returned
receipt is `27abbe3dca8737af8ebf5a5d35b953636724d73a67b5db1d198e388b91f470fc`.
The formal task has **revision requested**; its interaction is answered and
it has no approval snapshot.

### Personified revision

Jon asks: "What did the July 2 newspaper report about phone service?"

Mara's approved authored answer:

> The July second paper said the phones were out all over Knox. For hours, Jon. Still down when it went to press, too. Businesses closed. They hadn't announced a cause—there was talk of wires down, lightning, sabotage... but that's all it was. Talk.

Mara is anxious, fairly talkative and untrusting of Jon, without active hostility.
The fragments and emphasis propose an uneasy delivery; the answer shares the
requested report without personal disclosure or friendly reassurance. This is a
reviewable authored interpretation of the captured channels, not a calibrated
trait-to-style mapping. Native current needs, bite and pressure remain unavailable.

The candidate answers the phone-service question from the selected report.
It omits the combined report's Internet-network clause without denying it or
implying household adoption. Publication-time attribution and uncertain causes
remain explicit. Its evidence object contains clause-by-clause source alignment.

Exact wording proposal:
`5be5bbde154266fab5e75fef546b7ca7a920726c3b7d5143a4ad05ce8b07b77b`.
`c77-personified-review.json` and `c77-personified-invocation.json` hold the
actual new panel. Review is **approved as one facet of personality or communicative style**, interaction
`skill-d255b2e7c14ce745`, item `seam-ba3f2749a58d5c23`.
`c77-example.json` tracks both subjects and their separate standing.

The completed receipt is `4664e4a424891e9f82d95bca1ba31152d3d937a868db838c9f7e3dc310a85d7b`.
The operator selected approval and wrote:

> This is a good example of one facet of personality or communicative style. Approved. Ideally with the ML work we could establish some aspect of psychometric undercurrent rooted in the game. A concept already suggested at

Interpretation `6555142d5f11f7c4afe0971c1cd858a539d02ef30ced1730094890f9863f970a`
preserves the note and records explicit approval of the wording plus prospective
direction for game-rooted psychometric work. The final phrase is incomplete;
no missing citation is inferred. The generic automatic task-admission checker
continues to refuse receipts with freeform notes. This interpreted wording
approval creates no task snapshot and changes no validator.


The revision is a `speakeasy-speaker-wording-proposal`, not an admitted version 3
speaker task. Its seal identifies the exact input, output and review rationale.
The source task retains the machine-checked provenance chain; the new prose has
authored factual alignment for human review. The current exact-summary renderer
refuses it. Wording approval cannot silently bypass that boundary or create a
training-eligible task. Semantic admission of freely composed wording is the next
implementation requirement, before this candidate enters a speaker dataset.

The authored scene supplies Jon's name, but the current speaker model input
supplies only his participant ID. The vocative "Jon" therefore also requires
explicit participant-name conditioning before this wording could become a
model target. The reviewed dialogue alone does not resolve that input gap.

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

## Game-rooted personality continuation

The operator's wording approval accepts one facet of expression and asks for
a psychometric undercurrent rooted in the game. The existing contract already
calls for learned voice from temperament, listener trust and circumstances
(SAO `SPEECH_ML_DESIGN.md`, Decision 5), with the same person speaking
differently under strain. This is the continuation basis.

Source inspection at SAO commit
`9d08d15de222e49e844b9b0e01e0981ce4009cfa` establishes:

| Existing surface | What it supplies | Next evidence required |
|---|---|---|
| `mod/42.20/media/lua/shared/SAO_Disposition.lua`, `trait` and `D.traits` | Eight effective axes from stable identity, history echoes, lesson echoes and condition bends, bounded to 0.15–0.85; downstream decisions consume them | Preserve effective-value meaning and trace each input's provenance; condition labels and already-bent axes must not be mistaken for independent effects |
| `mod/42.20/media/lua/shared/SAO_Knowledge.lua`, `K.conditioning` | Effective traits, conditions, habits, listener trust/debt/hostility, plus available pressure, needs and other moment inputs | Explicit availability, participant identity labels, and live input coverage before training admission |
| `voice/README.md` and `voice/seeds.md` | Authored contrasts between people and between ordinary company, work and threat | Source-bound paired examples with reviewed wording and unchanged factual entitlement |
| `training/ARCHITECTURE.md`, speaker conditioning | Learned composition with external limits on speech under hostility, guardedness, grief, threat, work and exhaustion | Semantic admission and register enforcement, then separate factual and expression evaluation |

The next implementation sequence is to bind participant identity and conditioning
provenance, establish semantic admission for personified wording, and enforce
the ratified register limits. Dataset work then compares the same person across
circumstances and different people given the same facts, while keeping related
captures together across dataset splits. Evaluation must distinguish stable
personality, listener-specific relationships and temporary strain; a change of
voice must not create new knowledge.

These are game-owned behavioral dimensions. Their presence does not establish
a validated psychometric instrument or a calibrated numerical mapping into
speech. No new psychological taxonomy or scoring model is chosen by this
wording approval.

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
