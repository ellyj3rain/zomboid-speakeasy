# Bound speaker task: Mara answers Jon

Record 59 carries the Record 58 expression proof into a version 4 speaker task.
The existing version 3 task and the separately approved wording retain their
original records. This task's exact source/situation/answer pairing has its own
review; [current standing](c77-bound-example.json) records the actual return.

**Returned: revision requested.** The operator wants existing personality,
emotion, thought, adaptation and world-relative goals to matter more granularly.
The exact response is preserved in
[the revision receipt](../evidence/49d632b28fd23986a841694901658f49a5cb61791122ab66c5dca1b7509f3453.json).
This task is excluded from training. The
[source audit and revised continuation](PERSONALITY_REVISION.md) explain what
already exists, what this capture lacks and the next contrast cases.

## The scene and answer

On July 11, Jon asks Mara what the July 2 newspaper reported about phone service.
Mara personally read the issue July 10; Jon has no report acquisition. Her
captured state includes anxiety and a relationship not marked trusted. The task
retains the exact traits, relationship/moment channels and unavailable inputs
from that capture rather than creating a personality label for this example.

> The July second paper said the phones were out all over Knox. For hours, Jon. Still down when it went to press, too. Businesses closed. They hadn't announced a cause—there was talk of wires down, lightning, sabotage... but that's all it was. Talk.

This is exactly the wording previously approved as one facet of communicative
style. Its report and dates are unchanged. The source-bound representation now
makes it a mechanically validated task candidate, including Jon's captured name.
The requested review concerned use as one offline task example. The returned
revision leaves that permission unset and preserves the prior wording approval.

## What the task and preparation preserve

| Surface | Contents and purpose |
|---|---|
| Evidence input | Complete catalogue/context, exact import, independently approved understander and retriever chain |
| Speaker model input | Question, semantic intent, situation, captured participant names and bound propositions with voice conditioning and missing inputs |
| Task output | Actual answer and a complete expression witness checked against the reconstructed source |
| Prepared speaker target | Actual answer text; construction choices remain in audit evidence |
| Approval | Exact version 4 task content hash, independently returned through Mousecat |

Version 4 uses the same task schema family, approval snapshot and resolver as
the existing speaker tooling. It validates the complete input against the
source chain, then validates every proposition and the rendered answer. Parts
cover each selected report once, in order. Changed names, voice inputs, sources,
dates, owners, omitted/duplicated reports and appended factual prose refuse even
if an altered record is resealed. Version 3 remains supported unchanged.

## Current limits and learning consequence

The supported source grammar and entity pairs remain those of the bounded
proof. The task is an authored example over that supported meaning; no new
source grammar, personality-to-wording mechanism, register floor or learned
decoder is supplied here. A free-text training target is not itself a runtime
semantic guarantee. The later learned output still needs the ratified enforced
claim boundary and separate factual and voice evaluation.

This example belongs to the same C77 source family as its understanding and
retrieval tasks. It cannot become their independent test scene. Three native
inputs remain unavailable. The [data preparation report](../datasets/c77-preparation/README.md)
shows exact sample inclusion/exclusion and missing evaluation partitions.

## Reproduction

```text
python tools/speaker_tasks.py --propose 02af1fc6d30b308d1d809140bc2972dfc563d825ef713c28fbc0d8071317fb73 --row-id c77-mara-bound-speaker-001 --bound-plans training/speaker/c77-bound-plans.json
python tools/speaker_tasks.py --validate training/evidence/97388368bc3bf12051c4021cb8acd296ad3694bc30bbc1afb62f10c95d50e1a1.json
```

The first command reconstructs the saved task deterministically; publication
into the evidence store is idempotent only for identical content.

Prior proof: [Record 58 comparison](../experiments/expression-proof/README.md).
Prior wording review: `skill-d255b2e7c14ce745`.
Exact task review: `skill-31ada9b3c5ba3c0c`.
