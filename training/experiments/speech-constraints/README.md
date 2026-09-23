# Speech constraint Field Test

Status: experiment complete; general personified speech remains unimplemented.
Authorization: the ratified consolidated direction and the explicit Field Test invocation.
Evidence: [result.json](result.json), content seal
`691932beec45839a0751724cb2fd90e30d4bfaab4fbef3da296704a2a0efe063`.

## What was exercised

The independently written probe compiles the actual SAO `SAOFence.java`
from commit `9d08d15de222e49e844b9b0e01e0981ce4009cfa` in a temporary
directory. The same cases run against the packaged `SAOAgent.jar`.
It also calls the production Speakeasy speaker validator against the exact C77
source task, its approved personified wording and resealed text mutations.
The result records source, jar, probe, tool and subject hashes.

The original question is Jon asking Mara what the July 2 paper reported about
phone service. Her owned claim comes from completing reading on July 10; the
conversation is July 11. The experiment does not add knowledge to either person.

## Observations

| Case | Actual result | What it establishes |
|---|---|---|
| Exact owned report fields | Java accepts | The field membership mechanism admits its positive control |
| Unknown claim, changed explicit publication hour, reported changed to observed, unknown field or absent claims | Java refuses | Explicit unsupported field/value assignments are caught |
| Synthetic observations: Jon east, Eve west; candidate Jon west | Java accepts | Pooling values by field loses the association between person and location |
| Synthetic observations swapped: Jon west, Eve east; same candidate Jon west | Java accepts | Correct and incorrect associations are indistinguishable to pooled field membership |
| Approved personified speech submitted as raw prose | Java returns true | Non-assignment text is skipped by the wire parser; this is not a semantic evaluation |
| Unsupported negation, current outage, direct experience, confirmed sabotage, recovery or household Internet access submitted as prose | Java returns true | The API is not a prose validator; these calls are outside its declared input format |
| Owned assignments followed by an unsupported sentence | Java returns true | Assignments are checked; the added prose is skipped. An outer decoder/parser must enforce its own output contract |
| Exact source-summary speaker task | Speakeasy accepts | The bounded renderer works for its supported expression |
| Mara's approved personified answer | Speakeasy refuses | Accepted authored wording is not expressible by the current renderer |
| Six false text mutations | Speakeasy refuses | Exact-rendering enforcement catches changes, but does not distinguish faithful paraphrase from false prose |

There are 18 Java cases and 8 speaker cases. Compiled source and packaged jar
agree on all 18. The reporter's always-accept control changes six observations;
its always-refuse control changes twelve. Both are detected as failed
characterizations. These are instrument controls, not mutations of production
source.

## Human-readable contrast

Synthetic source: **Jon is east; Eve is west.**

Both `name=Jon / whereWord=east` and
`name=Jon / whereWord=west` pass pooled field membership.
Every word is available, but the second combination attributes Eve's location
to Jon. The fixture uses two selected observations intentionally; this is not
a failure to narrow the selected claim set.

Mara's approved authored reply includes:

> The July second paper said the phones were out all over Knox. For hours, Jon. Still down when it went to press, too.

The summary renderer rejects that faithful authored expression as well as:

> The phones are still down today.

Its refusals enforce the exact-summary representation. They do not establish a
general test of sentence meaning.

## Consequences for the active unit

Preserve whole claim identity and relationships through decoder consumption,
including source attribution, polarity and temporal scope. A valid claim ID
beside unconstrained prose cannot prove that the prose expresses that claim.

The next implementation must demonstrate supported personified realization
from that representation and discriminate the altered-meaning controls.
Requiring the old exact summary would exclude the wording the operator accepted.
Simply retaining IDs would leave the sentence-to-meaning binding unproved.
The ratified constrained-composition requirement remains unchanged.

Task-specific dataset admission and identity/conditioning inputs can progress
alongside this decoder work. Nothing in this experiment changes the examples'
training eligibility or grants broader source coverage.

## Limits

- The Java fixtures match the declared wire shape. The Lua selected-claim
  projector was inspected and hashed, but was not executed in this experiment.
- The two-person location example is synthetic and belongs only to this test.
- Prose parser probes are outside the Java API's contract. There is no live
  learned speaker path here, so these results are not a demonstrated in-game exploit.
- No trained model, gameplay, save/reload or live installation was exercised.
- Speaker mutations are resealed before validation, avoiding false rejection
  solely because an old content hash was retained.
- Technical findings need no operator approval. A concrete voice or architecture
  choice arising from a demonstrated candidate can be reviewed separately.

## Reproduction

From the Speakeasy worktree:

```text
python tools/experiments/speech_constraints.py --sao-root SAO_CHECKOUT --jdk-dir JDK_BIN --output NEW_RESULT_PATH
```

Use the source revision above and the matching packaged jar. The tool refuses
to overwrite a different result at an existing path. A missing prerequisite,
unexpected source behavior or source/jar mismatch fails the run rather than
being reported as a pass. Java classes live only in a temporary directory.
