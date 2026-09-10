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
| Status | The dataset's source and row shape are ratified (record 24) and a ceiling for the inference budget is measured (record 26). The first rows are in `decisions/work-words.jsonl`, proposed in record 28 and ratified by the operator in record 29; the trades-hinge rows are proposed in `decisions/trade-hinges.jsonl` (record 30), awaiting the ruling. No models yet. |
| License | MIT. SAO is GPL-3.0; no code is shared between the repositories; the dataset produced here ports into SAO. |
| Record | `RECORD.md`, append-only. |

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
