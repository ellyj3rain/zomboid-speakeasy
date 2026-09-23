# Personified expression and experimental admission proof

The approved offline proof is complete. The broader admission and learned-speech
unit remains open for implementation: this demonstrates a bounded construction,
not general sentence semantics, a trained speaker or a game runtime.

The [approved work plan](../../direction/admission-work-plan.json) and
[actual returned ruling](../../direction/admission-work-plan-result.json) bind
this work to Mousecat interaction `skill-1269923d11820cf8`. The operator selected
`approved` without qualifications. Only the private continuation capability was
removed from the saved response.

## What changes for the project

The earlier [diagnostic](../speech-constraints/README.md) found two different
limits: pooled field membership could attach Eve's location to Jon, while the
whole-summary renderer rejected Mara's approved personified answer. The new
prototype keeps a proposition's subject, relation, value, owner, attribution,
time and acquisition together, then renders only supported constructions over
that representation. Reusing a valid claim ID with a changed proposition fails.

Mara's captured identity and Jon's name come from the same validated C77 owner
capture as the report. The report was published July 2, Mara read it July 10,
and Jon asks about it July 11. Reading it later does not make its outage current.
The prototype can now produce the complete previously approved wording:

> The July second paper said the phones were out all over Knox. For hours, Jon. Still down when it went to press, too. Businesses closed. They hadn't announced a cause—there was talk of wires down, lightning, sabotage... but that's all it was. Talk.

It also produces a plain expression and mixed clause choices, saved alongside
this answer in [result.json](result.json). Six independently selectable pairs
of clause realizations give 64 supported combinations. Those are lexical
combinations within one report grammar, not 64 independent scenes or approved
voices. The phone projection omits Internet service from this answer; neither
service's presence in a newspaper report establishes personal computer access.

## Demonstrated coverage

| Concern | Evidence | Remaining limit |
|---|---|---|
| Subject and fact association | Jon east / Eve west; swapped subjects or values refuse | Location scenes are explicitly authored synthetic fixtures |
| Report versus observation | `I saw Jon to the east at 09:00.` and `Leah reported Eve to the west at 09:05.` have different bound sources | No new native location-acquisition producer is supplied |
| Date and uncertainty | Publication-time outage and speculative causes pass; current-time invention and confirmed sabotage refuse | Source recognition supports one exact report grammar |
| Personified expression | Exact approved Mara wording passes; all 64 clause combinations validate | No arbitrary prose admission or learned selection among constructions |
| Claim and text integrity | Nine saved hostile controls refuse; two actual validator-source mutations are detected | Construction integrity does not prove arbitrary sentence meaning |
| Independent expectations | Hand-authored location and different-date/region report fixtures match expected text | Synthetic, unreviewed and excluded from approved task data |
| Personality and circumstance | Changed voice inputs do not grant facts; source binding changes | Personality-to-expression behavior and register floors remain unimplemented |

Independent review found that unrestricted location time and reporter strings
could carry additional prose. The corrected input requires a clock value and
an identified reporting participant. Regression controls reject both attacks.
Participant names also use a bounded name grammar; missing or unsupported names
refuse. The same review found a clause disguised as a region name; provider and
region now resolve against the proof's explicit entity pairs (captured Knox
Telecommunications / Knox, synthetic Valley Telecommunications / Valley).
Unrecognized entities refuse. These constraints describe the proof's supported input, not a decision
to restrict the final learned architecture to this grammar.

## Admission is now an explicit computation

The declared scope is `offline-authored-conversation-v1`. Source validity,
required task inputs and exact independent label approvals determine sample
admission. Dataset partitions and runtime readiness have separate results.

| Existing example | Result in this scope | Consequence |
|---|---|---|
| C77 understander | Admitted to offline evaluation | Exact approved interpretation and validated capture can be exercised |
| C77 retriever | Admitted to offline evaluation | Its independently approved target remains one required report, zero negatives and seven unjudged claims |
| Formal version 3 speaker task | Excluded: no matching task approval | Approval of different personified wording cannot approve this formal task |
| Personified wording proposal | Excluded: wording approval is not task admission | Reproduction by this proof does not silently create an approved new speaker task |
| Combined dataset | Excluded: speaker rows excluded and independent evaluation partitions missing | No training dataset or model-quality result is claimed |
| Runtime | Not ready | No trained bundle or native consumer integration; missing native inputs remain explicit |

The compiler requires each exact row in exactly one partition and groups shared
capture, document and catalogue sources together. Splitting linked examples
across training and evaluation refuses. Historical sealed evidence and the
legacy conditioning APIs retain their original standing; all 190 historical
choices remain ineligible. This new scope does not rewrite prior exclusions.

## Reproduction and evidence

From this Speakeasy worktree:

```text
python tools/test_expression_proof.py
python tools/experiments/expression_admission.py --check
python -m unittest discover -s tools -p 'test_*.py'
python tools/audit_conditioning.py
```

The saved result binds the exact source import, approved plan/ruling, inputs,
actual outputs, controls, admission report and implementation hashes. `--check`
recomputes and compares it. `--write` deliberately regenerates that experiment
result after implementation changes. The earlier Java diagnostic remains a
separate immutable characterization of its recorded SAO revision and jar.

Final verification: 111 repository tests passed; the protected conditioning
audit passed with all 190 historical choices still ineligible; the saved proof
reproduced with seal
`6ccc3ba96092fb8d5b9d4203db5c57a6f13bd5c65c3deef12cbdaad8187e4dc0`.
Read-only expression, admission and validation reviews completed. Both source
slot findings were repaired and rechecked before publication.

## Next dependency

Carry the bound proposition representation into a concrete speaker task and
the learned composition experiment, with wider supported meanings and explicit
unsupported cases. Its task labels and new voice contrasts need their own
review with actual scenes and answers. Multiple independently sourced scenes,
lineage-separated partitions and separate grounding/voice evaluation are needed
before a credible training run. The shared tokenizer and reference pipeline can
be prepared alongside that work under the ratified continuation.

This proof supplies a reference construction and failure controls for that
work. It does not select fixed sentences as the final NPC cognition mechanism.
