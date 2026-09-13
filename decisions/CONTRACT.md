# Cross-module row contract

| Field | Contract |
| --- | --- |
| Version | 2 |
| Status | RATIFIED 2026-09-12 by the operator (RECORD.md entry 42) - the runtime seam follows this contract |
| Owner | ellyj3rain |

This contract extends the ratified row shape so one row can carry the full
simulation across SAO, ZAO, and Speakeasy.

The six integration rulings are recorded in ZAO as DR-022. This contract
follows them and the event-driven pathogen state now shipped on both sides.

## The four halves

A row still has four halves:

1. person
2. situation
3. options
4. choice

The cross-module extension adds one block to the person half and one block
to the situation half. A ZAO state row is keyed by the same person id and
decision hour as the SAO row it belongs to.

### Person

The person half keeps SAO's living record. It gains a `pathogen` block:

- infection count
- current course
- mutation roll
- current form
- form performance
- attribute mutations
- decay state
- terminal state, where crossed is terminal and afflicted is live state
- the event that produced the state

A body with no assigned form is in the `none` form, and its performance is
zero.
A body carries a form only when the pathogen has already acted on it:
infected, dead, or turned.

### Situation

The situation half keeps SAO's perceived facts. It gains a
`visibleForms` block:

- the forms this person can see
- the provenance of each sighting, when the runtime supplies it
- the pressure each sighting creates inside the branching graph

### Options

The options half stays consumer-owned. It lists the actions actually
available to this person at this moment.

### Choice

The choice half records the chosen action and the form-pressure consequence
written back into the living graph.

## Rules carried from the rulings

- The pathogen owns the mutation roll.
- Form performance is a pathogen roll.
- Crossed is terminal; it does not mutate further.
- Retained form traits are state, not new branches.
- Forms and attribute mutations stack.
- Forms enter Perception and change pressure inside the existing branching
  graph.

## Event rule

Pathogen state and mutation knowledge come from simulated events:
infection, death, turn, carrier exposure, encounter, and testimony. A row
never derives a form, a performance value, or knowledge from a person id,
a clock, or a hash.

## What this does not do

- It does not collect rows yet.
- It does not replace `work-words.jsonl` or `trade-hinges.jsonl`.
- It does not author a form name, a strain name, or a player-facing word.
