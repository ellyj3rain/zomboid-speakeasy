# Decision-time knowledge and authored proposals

`tools/decision_authoring.py` compiles a versioned knowledge view and a separate
choice proposal over a frozen event. Version 1 is an evidence preparation
surface. It preserves source approval, records supplied acquisition evidence,
and accepts separately sealed extraction-review and acquisition-adjudication
receipts. Those receipts change only the technical standing they prove. Choice
and knowledge-example ratification remain separate, and every current output
remains conditioning-ineligible.

## Inputs and identity

The capture input is a version 3 SAO decision row, JSONL containing those rows,
a native C65 `sao-source-decision-event` version 1, or the containing
`sao-source-decision-capture` version 1. A source capture must be observed,
complete and free of capture failures. Unavailable county-sweep coverage
supplies no event. Raw C65 events retain their runtime choice and result in the
input; the authoring view exposes the frozen person, situation and offered
options. Later results and the runtime choice do not become authoring context.

The full `(runId, county, personId, eventId, hour)` namespace is preserved.
Native C65 nested identities must agree. Options retain their owner, parameters
and eligibility evidence, including acquisition/storage operations. Their IDs
alone are insufficient: a proposal binds the complete selected descriptor hash.
The original v3 row admission is shared with the cross-module join, including
its citation and already-enriched-context refusals. Both adapters reject added
pathogen state, visible-form lists and prior join provenance before copying
context. Native option actors,
private evidence actors/source revisions and current admission/inspection hours
must agree with their event. Semantic namespace keys treat county hour `24` and
`24.0` as the same moment; raw event hashes still preserve their different bytes.

The compiler hashes the raw event, complete input files, protected manifest,
review receipts, individual claims and resulting content. JSON object keys are
sorted and UTF-8 is encoded without extra whitespace; `contentSha256` hashes the
complete object before that field is added. Duplicate JSON keys and non-finite
numbers refuse. Original bytes are also hashed separately, so formatting
changes remain visible.

## Knowledge input version 1

A `speakeasy-knowledge-input` object has exactly these fields:

| Field | Meaning |
|---|---|
| `schema`, `schemaVersion` | `speakeasy-knowledge-input`, `1` |
| `namespace`, `eventSha256` | Exact frozen event identity and canonical-content hash |
| `calendar` | `anchorHour`, `anchorAt`, `horizonHour`, `evidence` |
| `claims` | Explicitly extracted approved-document claims |
| `acquisitions` | Supplied person-specific acquisition and retention evidence |

`anchorAt` is a complete `YYYY-MM-DDTHH:MM:SS` local game-calendar instant.
`anchorHour` is the corresponding canonical county hour. The compiler applies
that exact mapping to acquired hours and the person's supplied horizon hour.
It never derives availability from a year alone. The horizon cannot exceed the
event hour and researched knowledge stops at December 31, 1993. The mapping's
evidence reference names the supplying owner, record ID and SHA-256.

A claim has `id`, literal `text`, `confidence`, `knowableAt`, literal `carrier`,
`acquisitionRules` and `source`. Rules name one or more of `read`, `heard`,
`lived`, `told`. The source has its repository-relative `path`, full-byte
`sha256`, one-based `line`, and `excerptSha256` of that line's UTF-8 text without
its newline. The source must match a protected `approved-knowledge` document.
The exact text and carrier must occur on the cited line. Confidence must also
occur literally unless an exact sealed extraction review records its absence,
the assessed value and its basis. The compiler checks that the review correctly
states whether the token exists. LOW material is excluded and cannot be promoted
through a changed confidence field or review.

Without a receipt, extraction is still unreviewed. A source line can contain
several facts, dates and carrier qualifications: document approval alone does
not approve a new claim boundary or prove its `knowableAt`. The compiler checks
declared temporal availability and preserves that distinction in every view.
The three examples
under `world/claim-examples/` identify real approved excerpts with acquisition
explicitly unknown. They use the existing `speakeasy-claim-extraction-example`
version 1 shape and are source material for a knowledge input, with person
evidence supplied separately.

| Excerpt | Protected source and line | Declared knowable time | Selected boundary |
|---|---|---|---|
| `minimum-wage.json` | `world/us-1993/timeline.md:28` | `1991-04-01T00:00:00` | The federal minimum wage rose to $4.25 an hour; omits the later-looking remainder of the line. |
| `first-class-postage.json` | `world/us-1993/work-and-money.md:55` | `1991-02-03T00:00:00` | The first-class stamp cost 29 cents from February 3, 1991; omits the same line's earlier and 1995 rates. |
| `family-medical-leave-act.json` | `world/us-1993/timeline.md:61` | `1993-02-05T09:22:00` | The Family and Medical Leave Act was signed at 9:22 a.m. in the Rose Garden. |

The dates describe the selected change or signing, not when a person learned
about it. Midnight represents the source's date-only boundary for the two rate
changes; the signing preserves the source's stated time. The four listed
acquisition paths are the existing read/heard/lived/told vocabulary, not records
that any path occurred. All three retain `extractionStanding: unreviewed`,
`acquisition: unknown` and the `claim-extraction-not-ratified` and
`person-acquisition-unknown` conditioning exclusions. Their literal excerpts and
source hashes validate through the production `source_claim` reader. Source
approval does not adjudicate these extraction boundaries or their declared times.

Each acquisition has exactly these fields:

| Field | Required evidence |
|---|---|
| `claimId`, `claimSha256` | The exact extracted claim |
| `namespace` | Full decision namespace for the person receiving this knowledge view |
| `acquiredHour` | Actual acquisition time in the same county clock; may precede hour zero |
| `asOfHour`, `retained` | Explicit retention observation at the decision hour |
| `path` | A path admitted by the claim's acquisition rules |
| `checks` | `age`, `carrier`, `access`, `retention`, each with `status` and `evidence` |
| `evidence` | Nonempty acquisition references |

Each reference has `owner`, `recordId`, `sha256`. A check's status is
`supported`, `unsupported` or `unknown`; supported checks require references.
An access check covers the actual modality and relevant literacy/hearing or
testimony constraints. Carrier and age checks refer to this person's supported
history at the event; retention covers later decay or loss. An acquisition
producer owns those records. This tool does not generate them, infer them from
occupation, or verify external reference bytes that were not supplied.

Only exact-person/exact-event, nonfuture, retained acquisitions with all four
checks supported enter `availableClaims`. The view labels their acquisition
evidence unadjudicated unless a sealed adjudication binds the exact acquisition,
event, checks and import evidence. All others produce a claim ID/hash and
exclusion reason, without including excluded claim text. Empty
claims/acquisitions are valid and preserve the lack of evidence. Missing or
unknown evidence does not become proof that the person lacks the knowledge in
reality.

## Review receipts and the Record 52 example

`--receipt` is repeatable on `view` and `propose`. A claim-extraction review
binds the exact claim and source plus protected rule excerpts, the selected
boundary, time, carrier, paths and confidence assessment. An acquisition
adjudication binds the exact person/event acquisition, its four checks and its
import receipt. Duplicate, stale, changed or unsealed receipts refuse. Review
produces `reviewed`; adjudication produces `adjudicated`. These standings
describe evidence review. They do not ratify an authored behavior row.

`examples/r12-knox-lived-source/` is the first production example. Its importer
reads the C74 evidence from exact SAO commit
`739ff0a026c2fc2c9450f71a5169b1e72b302c46`, validates the manifest, complete
event namespace, frozen acquisition, presence, calendar, retention and protected
source hashes, and records the C74 `VERSION` line-ending normalization rather
than hiding it. The example extracts the July 2 Knox telecommunications outage,
binds the `lived` and adult-detail rules to protected scoping excerpts, and joins
Ada North's exact acquired and retained record.

The imported source capture originally listed
`person-knowledge-not-reconstructed`. The compiled view preserves that phrase in
`sourceExclusions` as capture history and removes it from active conditioning
because this compiler reconstructs the person's claim explicitly. The remaining
active exclusions continue to block training.

## Choice request and proposal

A `speakeasy-choice-request` version 1 has `namespace`, `eventSha256`,
`knowledgeViewSha256`, `optionId`, `optionSha256`, `author` and `rationale`.
`author` has `kind` (`human` or `model`), `id`, `version` and `promptSha256`.
For a human author, the last two fields identify the authoring procedure and
instructions. The rationale is authored text, not verified factual evidence.

Proposal construction recompiles the view from its inputs and compares the
whole result before accepting the request. A namespace change, stale input,
changed option descriptor or altered view refuses publication. The output is a
new `speakeasy-choice-proposal` with `approval.status: unratified`. The request
cannot supply approval fields. A proposal never replaces the captured runtime
choice or any protected approved choice.

The tool prepares reviewable proposals and has no ratification authority. Record
52 does not create a proposal from its controlled selection. Its reviewed
reference binds only the claim/person/acquisition pairing and fixes the observed
food choice at `excluded-controlled-selection`. The reference remains
conditioning-ineligible because one claim is not complete knowledge coverage,
the choice was forced, and no natural choice or later-consequence evidence
exists.

## Operation and verification

```text
python tools/decision_authoring.py inspect --capture capture.json
python tools/decision_authoring.py view --capture capture.json --knowledge knowledge.json --receipt review.json --out view.json
python tools/decision_authoring.py propose --capture capture.json --knowledge knowledge.json --receipt review.json --view view.json --request request.json --out proposal.json
python tools/test_decision_authoring.py
python tools/test_import_sao_world_knowledge.py
python tools/test_cross_module_rows.py
python tools/audit_conditioning.py
```

`inspect` prints the validated namespaces, event hashes and complete option
hashes needed to prepare the two inputs. It creates no files. The view command
prints its resulting content hash for the separate choice request.

All inputs and protected hashes validate before output publication. Outputs
cannot replace an input, protected artifact or protected manifest. Publication
uses the existing atomic sibling-file replacement and preserves previous bytes
when validation or replacement fails. Controls use explicitly synthetic
acquisition records and real protected-document excerpts; they are not a new
county corpus. Historical approved choices retain their existing hashes and
conditioning exclusions.
