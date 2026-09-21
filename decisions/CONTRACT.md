# Cross-module row contract

| Field | Contract |
| --- | --- |
| Version | 3 for new joins; version 2 remains protected historical data |
| Status | Corrective integrity revision, 2026-09-20; preserves the operator intent ratified for version 2 in RECORD entry 42 |
| Owner | ellyj3rain |

One row carries the four ratified halves across SAO, ZAO and Speakeasy:

1. `person`
2. `situation`
3. `options`
4. `choice`

The version 3 contract tightens the evidence identity and action boundary. It
does not alter an approved choice.

## Full namespace

Every SAO and ZAO input row carries the same `namespace` object:

| Field | Meaning |
| --- | --- |
| `runId` | The source simulation run, bound to its code, settings and seed |
| `county` | The originating county inside that run |
| `personId` | The person whose decision this is |
| `eventId` | The particular decision event |
| `hour` | The county hour at which the event opened |

All five fields form the join key. `person.id`, `situation.county`,
`situation.hour`, any citation, and ZAO `asOfHour` must agree with it. Duplicate,
missing and unmatched namespaces refuse the whole export.

## Input schemas

An SAO row declares `schema: "speakeasy-decision-row"` and
`schemaVersion: 3`. A ZAO row declares `schema: "zao-decision-state"` and
the same version.

The SAO row owns the four halves. The ZAO row owns `pathogen` and
`visibleForms` as of the namespace hour. The join adds `pathogen` to the person,
adds `visibleForms` to the situation, and records both input hashes and the full
namespace in `crossModule`.

## Executable options

`options` is a nonempty list of action objects. Every option carries:

- a stable `id`;
- the real action `owner`;
- a `parameters` object;
- `eligibility.status: "eligible"`;
- one or more evidence objects proving current eligibility.

`choice.optionId` names one offered option. Execution revalidates that option
because the world can change after inference.

## Conditioning time

Each row has a `conditioning` object with `status`, `decisionHour`,
`latestEvidenceHour` and `exclusions`. An eligible row has no exclusions and no
evidence later than the decision hour. An ineligible row may preserve an
approved choice for audit or reconstruction, but cannot enter a training view.

The choice and its conditioning retain separate standing. The protected
version 2 artifacts demonstrate why: future death, lesson and belief facts are
present in most rows even though the choices themselves were ratified. The
counts and hashes are in [`ELIGIBILITY.md`](ELIGIBILITY.md) and
[`PROTECTED.json`](PROTECTED.json).

## Publication

`tools/cross_module_rows.py` validates both complete inputs before it creates a
temporary sibling. It writes the complete joined bytes, flushes them, then
publishes with one atomic replace. The output may not equal either input or any
path protected by `PROTECTED.json`. A failure leaves the previous output
unchanged.

## Pathogen and perception rules

- The pathogen owns the mutation roll.
- Form performance is a pathogen roll.
- Crossed is terminal and does not mutate further.
- Retained form traits are state, not new branches.
- Forms and attribute mutations stack.
- Forms enter Perception and change pressure inside the existing branching
  graph.
- Pathogen state and mutation knowledge come from simulated infection, death,
  turn, carrier exposure, encounter and testimony events. They are never
  derived from a person id, clock or hash.

Version 2 remains the exact ratified historical artifact. It is not rewritten
in place and the version 3 tool refuses it as input.

## Derived knowledge and authoring

Version 1 [knowledge views and proposals](AUTHORING.md) bind to the full event
namespace and immutable event/option hashes. They preserve the source capture's
conditioning exclusions and retain the standing of extracted claims and
acquisition evidence separately from document approval. Authored choices remain
unratified proposals. Neither compilation nor authoring changes the version 3
row or promotes it into a training view.
