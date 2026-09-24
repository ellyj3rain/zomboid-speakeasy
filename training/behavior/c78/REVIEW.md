# Returned behavioral review

Mousecat interaction `skill-62e946a5714cb8f8` returned all four answers.
`review-result.json` preserves the exact choices, freeform values, notes and
lineage, with continuation capabilities omitted. `review-standing.json` binds
that receipt to the original comparison and records the current standing.
The original comparison, captures and candidate wording remain unchanged.

## What the operator returned

| Scene | Selection | Qualification and consequence |
|---|---|---|
| Trust | Neither; revise | The note calls both examples fine but hyperliteral, asks for variety, and identifies "sabotage--nothing settled" as a model mannerism. Preserve the selected revision request and this nuance together; there is no A/B preference and no instruction to make anxiety a fixed speaking style. |
| Nearby threat | Neither; revise | Nearby danger can change object orientation and priorities. The operator asks for a gradient of prioritization and instinct, tested externally. Continuing the report in both options fails to examine that question. |
| Told lesson | Both | Both are liked, with a stiffness caveat and a question about how well the people know each other. This is qualified acceptance of the alternatives, with no preference between them. |
| Strain | B | The fragmented delivery with one local repair is preferred, with a contextual stiffness caveat. This does not establish a general rule requiring repair under strain. |

These are human judgments over authored comparisons. They guide authoring and
evaluation; they do not approve a speaker task or admit a training dataset.
The operator's prose is retained alongside the selected option, including where
it is more nuanced than the option's label. The receipt does not imply acceptance
of Mousecat's overall composition.

## What the current input actually measures

The relationship channel in `comparison.json` contains trust, debt and hostility
toward Jon. Trust is 0.6 in the trusted case and 0 in the other three cases;
debt is 0 and hostility is false throughout. These fields do not measure duration
of acquaintance, shared experience or conversational familiarity. The current
comparison therefore cannot answer whether familiarity explains the stiffness.
Existing source-owned relationships and remembered experience must be traced
before supplying additional context; no invented familiarity score is warranted.

SAO's `SAO_Pressure.lua`, function `Pressure.threat`, computes
`min(1, 20 / max(1, distance) * (0.6 + formPressure * 0.4))` from a private
perceived zombie. For formPressure 0 it saturates at distances up to 12 tiles:
4, 8 and 12 all give 1, whereas 20 gives 0.6. The capture retains the nearest
belief and distance as well as pressure, so the original information is not
entirely lost. The four-tile case alone cannot establish a behavioral gradient.
This arithmetic describes the existing producer; it is not a calibrated policy.

SAO's `SAO_Knowledge.lua`, function `K.behaviorEvidence`, reads the existing
relationship, threat and cognitive owners. Loaded needs, controller activity
and movement goals have readers, but are unavailable in this bodyless family;
the complete executable-option inventory is also unavailable. In
`SAO_Controller.lua`, `decideThreat` already considers perceived distance,
disposition, overwhelm, armament and Standing permissions when choosing action.
`SAO_Voice.lua` renders transitions and direct answers through separate paths.
The authored comparison demonstrates neither their temporal coordination nor
physical orientation. These source observations identify work to do; they are
not evidence of observed gameplay or a learned speech policy.

## Next experiment and its completion conditions

The next source-and-data unit should capture changing priorities during a real
competing task, then evaluate communication in that changing situation. The
shared-base and typed-task architecture remains the ratified destination.

| Work | Evidence required | Discriminating check |
|---|---|---|
| Trace current producers | Person-private perception, current activity/goal, needs, relationship, executable alternatives and any available orientation evidence, with owner and time | Missing and stale channels remain explicit; an unperceived threat does not enter the person's input. Distinguish physical facing, selected attention and intended target. |
| Capture a graded family | Several evidenced threat distances/ages and competing activity states, using the actual source producers; retain raw distance and saturated pressure separately | The evaluator can distinguish source saturation from unchanged behavior. Compare changing one cause and held-out combinations. Do not manufacture a monotonic successful response as the label. |
| Review whole behavior | Actual attention/action/communication alternatives, including interrupted or postponed answers where supported; varied natural wording | A danger case can change what the person does or communicates. It need not finish the old report. Mechanical correctness and contextual plausibility are evaluated separately. |
| Validate externally to the candidate | Independent scenario controls and subsequent human review, separate from model training and candidate self-scoring | Report threat response, task relevance, knowledge integrity, person continuity and expression separately. Related interventions stay in one data split. |

The review does not select numerical priority weights, a new instinct variable,
an automatic anxiety-to-voice mapping or arbitrary animation behavior. The source
audit determines which existing producers can supply the experiment and which
specific missing mechanism needs implementation. The original Mara report stays
as a factual regression case; further paraphrases of it do not supply independent
situations or a representative evaluation dataset.
