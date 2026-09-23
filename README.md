# Zomboid-Speakeasy

Modeling the cognition of Project Zomboid NPCs: how a person decides
in the game space with limited awareness, from their own attributes
and personality.

The architecture across the three repositories - what this,
[Survivor Awareness Overhaul](../survivor-awareness) and
[Zombie Awareness Overhaul](../zombie-awareness) each own, and the
three seams between them - is held in
`../survivor-awareness/PROJECTS.md`, which is
[`PROJECTS.md`](https://github.com/ellyj3rain/sao/blob/main/PROJECTS.md)
on the forge. The relative path is for a reader with the three
repositories side by side, which is how they are worked on; the link is
for a reader who has only this one.

This and Survivor Awareness Overhaul (`../survivor-awareness`) are one
project. This repository is its dataset and training side: what is
built here is a dataset, and it ports into SAO. The repositories are
separate for licensing and for nothing else - SAO is GPL-3.0, this is
MIT, and no code crosses. The work is built so others can build on it
too.

| | |
|---|---|
| Status | The 190 choices remain ratified intent (records 29 and 41), and the nine world documents are approved knowledge (record 43). Their historical conditioning is not training-eligible: most rows contain later facts, all options are bare labels, and the version 2 `(person, hour)` join collapses events across counties. Version 3 now requires an immutable full namespace, executable-option evidence, same-hour ZAO state, whole-input validation and atomic publication. No model has been trained; [`decisions/ELIGIBILITY.md`](decisions/ELIGIBILITY.md) records the measured boundary. |
| License | MIT. SAO is GPL-3.0; no code is shared between the repositories; the dataset produced here ports into SAO. |
| Record | `RECORD.md`, append-only. |

Three [source excerpts](decisions/AUTHORING.md) now isolate the 1991 minimum-wage
and postage changes and the February 1993 Family and Medical Leave Act signing
from the approved world documents. They preserve exact source hashes and known
dates. Extraction is unreviewed and person acquisition is unknown, so these are
conditioning-ineligible source material for the next curation step (record 50).

Record 55 corrects the first acquisition bridge. The July 2 newspaper report
cannot establish personal Internet use or knowledge merely from county residence.
Historical C74 imports and Record 52 reviews remain intact; current admission
rejects their unsupported acquisition basis even after labels or review hashes
change. SAO C77 instead records exact native reading completion and marks the
claim as reported knowledge, acquired when that person reads it. Computer-source
compatibility must provide actual person, endpoint, service/source and result
evidence. Installing a mod or owning a device grants no awareness.

SAO C75 now gives every fact in one current private knowledge snapshot a stable
local reference and fences only the selected references. Record 53 defines the
data that will teach that selection: required references come from an approved
understander or speaker example, explicit reviewed hard negatives are negative,
and all other owned claims stay unjudged. Retriever rows have independent
approval and their own snapshots, exclusions, splits and evaluation receipts.
Record 54 corrects the compiler's evidence binding: it now opens the task row,
snapshot and saved Mousecat rulings, compares the whole conversation context,
and keeps shared sources in one dataset split. Record 56 imports the exact C77 capture, verifies its personal reading evidence,
and validates the first typed understander example. Its interpretation and
retrieval target now have separate, recorded operator approvals. Incoming speaker and listener
roles are explicit: Jon asks, Mara understands. The [narrative review](training/understander/README.md)
shows the scene, source, proposed meaning and what approval teaches. Label approval
and independent retrieval review remain separate. Native-input limitations and
missing task dataset splits/evaluation keep this controlled example ineligible
for training; no model exists.

Record 57 adds the [first speaker example](training/speaker/README.md) over that
approved chain. It mechanically preserves a complete source summary with its
publication date and report attribution. The operator requested an actual personified answer; its
[dialogue and separate review](training/speaker/README.md#personified-revision)
are now recorded and the personified wording is approved as one facet of
communicative style, with the original formal task unapproved. The continuation
traces game-owned personality and circumstance inputs into speech evaluation. This bounded expression is not the general free-composition decoder or
final NPC voice; those and the register floors remain explicit implementation
work.

The learned runtime and training shape is now ratified in
[`training/ARCHITECTURE.md`](training/ARCHITECTURE.md) (record 51). Record 58's
[offline expression proof](training/experiments/expression-proof/README.md)
now reproduces Mara's complete approved wording from bound source propositions,
refuses the tested changes to person, date and attribution, and computes
task-specific experimental admission. The approved understanding and retrieval
examples qualify for offline evaluation; speaker task admission, independent
dataset partitions and learned composition remain unfinished. The proof's
finite grammar is a reference experiment, not the final NPC speaking system.

That architecture uses one shared
base with typed task adapters, learned claim retrieval, bounded versioned model
cache, separate understander, retriever and speaker datasets, asynchronous snapshot and
revalidation, a pure-Java native bundle, FP32 reference plus measured INT8
candidate, and human review as the final gate after mechanical admission.

## What this project is

A person in the county decides. They decide with what they happen to
know, which is never everything, and they decide as the person they
are - their attributes, their temperament, what they have learned and
lived. This project models that: awareness in, a decision out, the
person in the middle.

Speech is one thing a cognition produces. It was the whole of this
project's charter and is now one part of it. The earlier speech work
stands and is not withdrawn; it stopped being the identity.

## Why it exists, concretely

A simulation cannot author the categories its people think in. When a
consumer has no cognition to ask, it writes tables instead, and the
tables are the giveaway:

- SAO deals a company's work from a five-word list - `watch`,
  `scout`, `medic`, `quartermaster`, `forager` - mapped from an
  occupation class. No one in that house decided anything, and two
  houses that organise identically cannot call it different things.
- SAO renders a house's creed from four fixed names.

A house should be able to create a position because it needed one, and
have its own word for it. Another house should be able to create a
position that functions the same and call it something else. That is a
cognition output, and no table can stand in for it.

The same holds wherever a consumer is currently choosing from a list
it wrote: what a group's relationship to a place is, whether it holds
one place or several, whether it stays or leaves.

## What competency means here

Nothing produced here is a capability every person or every group
gets. A group that never works out that it could run stashes across a
town does not run them, and that is a correct outcome rather than a
poor one. Whether a person or a group can do a thing follows from who
they are; the model makes the range possible and never enforces a
point in it.

## What this project holds

- `decisions/` - the dataset this project exists to make: a person,
  the situation they are in, the options actually available, and what
  they chose. Record 24 ratified where rows come from and what a row
  is; the first 112 rows are in `work-words.jsonl`, ratified by
  the operator (records 28 and 29).
- `world/` - the 1993 world model as researched documents: what a
  person can know, scoped by who they were. Every claim carries its
  confidence, and nothing teaches a model until it has been reviewed
  and approved.
- `corpus/` - curated public-domain period text, with source and
  license recorded per item.
- `voice/` - authored voice material demonstrating will, choice, and
  mood; machine-expanded at build time. Speech is one thing a cognition
  produces (record 21), so this is a part of the project rather than
  the whole of it.
- `training/` - the runs that produce the models, sized against
  measured in-game inference budgets, and the export contract
  consumers load them by.

The list is open. A stratum is added when the work needs one, not
because the structure was drawn in advance.

## What this project never does

- No player-speech harvesting, anywhere.
- No live AI service at runtime; what ships is self-contained and runs
  in-process on the game's own Java.
- Nothing asserts what a person does not know. Correctness there is
  verified mechanically, never by review.
