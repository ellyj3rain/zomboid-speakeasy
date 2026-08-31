# Zomboid-Speakeasy

World documents, curated period text, authored voice material, and
trained speech models for Project Zomboid NPCs. The first consumer
is Survivor Awareness Overhaul (SAO); the project is built so
others can build on it too.

| | |
|---|---|
| Status | Early - charter and structure, no data yet. |
| License | MIT. SAO is GPL-3.0; no code is shared between the repositories; models produced here ship into SAO. |
| Record | `RECORD.md`, append-only. |

## What this project holds

- `world/` - the 1993 world model as researched documents. Every
  claim carries its confidence, and nothing teaches a model until
  it has been reviewed and approved. Knowledge is scoped by who a
  person was: a nurse from Muldraugh and a soldier out of Fort Knox
  do not carry the same 1993.
- `corpus/` - curated public-domain period text for language
  texture, with source and license recorded per item.
- `voice/` - authored voice material demonstrating will, choice,
  and mood; machine-expanded at build time.
- `training/` - the runs that produce the models, sized against
  measured in-game inference budgets, and the export contract
  consumers load them by.

## What this project never does

- No player-speech harvesting, anywhere.
- No live AI service at runtime; models ship self-contained and run
  in-process on the game's own Java.
- The speaker is structurally unable to assert what a person does
  not know; its correctness is verified mechanically, never by
  review.
