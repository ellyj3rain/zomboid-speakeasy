# Visual scenario teaching

The operator evaluates each scenario before it is ratified into data. Speakeasy
owns authored situations, decision inputs, proposed targets and admission.
Mousecat owns the shared map, timeline, person inspection and response controls.
An authored hypothetical can start this loop without a captured base dataset.

`scenario.json` describes Rhea repairing a water collector when Jon asks her to
carry food. The two authored frames show the situation before contact and at
reception. Coordinates and elapsed time are schematic illustrations. The preview
ends at the decision; it asserts no later response, commitment or successful work.
The proposed teaching response is **defer**, with its rationale kept outside the
model input. This is a candidate for evaluation, not an approved rule about busy
people.

`review-subject.json` seals the complete scene, input, proposed response and
admission scope. `review-invocation.json` supplies that exact subject to Mousecat
Crucible, including `mousecat.scene-preview/1` in the existing ML review record.
The operator can step through frames and inspect personal knowledge before
approving, requesting corrections or rejecting the example. A qualified answer
requires a revised exact proposal. Any scene, input or target edit invalidates
the old subject binding.

Current standing: **unratified**. No approval receipt, admitted row, dataset or
trained artifact is supplied for this example. The existing R66 experiment keeps
its separate exact approval and historical standing.

## Reproduce

Run from the repository root; output paths must be new:

```powershell
python tools/scenario_teaching.py validate training/coordination/r70-teaching/scenario.json
python tools/scenario_teaching.py preview --scenario training/coordination/r70-teaching/scenario.json --out _scratch/teaching-review.json
python tools/scenario_teaching.py review --review _scratch/teaching-review.json --session-id YOUR-TASK --invocation-id UNIQUE-REVIEW --occurred-at ACTUAL-UTC-TIME --out _scratch/teaching-invocation.json
```

Send the invocation object through `mousecat.skill` and await its returned
continuation. Preserve a genuine completed operator receipt in the content-hash
evidence store. Only then can `admit --review REVIEW --receipt RECEIPT-HASH --out
NEW-ROW` emit a `speakeasy-approved-teaching-row` for the declared offline scope.
The admission function reuses `training_evidence.Store.decision`; a caller
approval flag, missing receipt, rejection, wrong subject or qualified approval
cannot admit a row. Dataset partitioning and learned-model integration remain
separate from approving an individual teaching example.

The typed input reuses the existing coordination projection and production
appraisal constraints. Actor names, scene coordinates, personal-knowledge display
text and teaching rationale are review context, outside learned input. The
model's exact values are independently available under Mousecat's input panel.
Authored reception carries an explicit hypothetical basis and cannot impersonate
a captured hearing observation.

The R69 no-engine run has no native weather-hearing observation. Its lack of
receptions is therefore insufficient to diagnose loaded-game communication.
This teaching route supplies explicit hypothetical conditions for review; it
does not rewrite that observed episode.
