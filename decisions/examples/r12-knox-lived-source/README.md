# Record 52: one person's knowledge through the pipeline

On July 2, 1993, telephone and Internet service failed across the Knox area.
Ada North was 31 and present in the county. Survivor Awareness records that she
acquired this local claim through the `lived` path and still held it at the July
11 source-use event. This directory proves that Speakeasy can reconstruct that
exact person, claim and time relationship from the C74 evidence at merge commit
`739ff0a026c2fc2c9450f71a5169b1e72b302c46`.

## Where this sits in the ML system

| Stage | Meaning |
|---|---|
| Approved world record | The outage is a supported fact in the shared world. |
| SAO person record | Ada personally acquired and retained the claim. Another person needs their own evidence. |
| This reference | The Speakeasy compiler places the claim in Ada's decision-time catalogue and preserves its provenance, age and access evidence. |
| Future learned retrieval | Given Ada's complete catalogue and a conversation, a model may select this claim when it is relevant. This reference supplies catalogue input only; no relevance target exists here. |
| Future speaking | The speaker may phrase a selected claim in Ada's voice. SAO's claim fence permits only claims still owned by Ada. |
| Future understanding | If the player refers to the outage, the understander may identify this claim and intent in a typed frame. SAO then decides whether any consequence follows. |

The eventual player-visible difference is personal variation. Ada can potentially
remember or discuss an outage she lived through. A person absent from the county,
too young for the detailed form, or lacking another valid acquisition path cannot
receive the same claim by default. Relevance, wording, attention and any action
remain later learned and simulation-owned decisions.

## What this record changes

This record creates one reviewed reference fixture for the future person-claim
catalogue producer. It creates zero training rows, changes no model weights,
changes no runtime behavior, and changes nothing the player can currently see.
The source and acquisition are mechanical evidence review, so no operator ruling
is required. Operator ratification remains attached to authored behavior rows;
human review of a trained runtime candidate remains the final usefulness and
voice gate defined in `training/ARCHITECTURE.md`.

## Evidence layers

| Path | Authority |
|---|---|
| `upstream/` and `import.json` | Immutable C74 capture, evidence port, manifest and import verification |
| `knowledge-input.json` | Exact claim, calendar and same-person acquisition supplied to the compiler |
| `reviews/` | Hash-bound extraction review and acquisition adjudication |
| `reference/knowledge-view.json` | Reproducible decision-time catalogue view |
| `reference/knowledge-example.json` | Reviewed reference role, downstream uses, current effects and exclusions |

The protected Knox Event row predates claim-level confidence fields. The
extraction review records that absence and assesses `HIGH` from the approved
direct game record. It binds the adult-detail and local-claim `lived` rules to
the protected `who-knows-what.md` excerpts. The source capture's historical
`person-knowledge-not-reconstructed` limitation remains visible; the compiled
view removes it from active exclusions because this example performs that
reconstruction explicitly.

C74 forced the banana source to exercise the completed same-person join. The
outage did not cause or justify that selection, so the choice remains
`excluded-controlled-selection`. Complete knowledge coverage, a natural choice,
later consequences and an approved runtime choice remain absent. Those gaps keep
the reference outside every training view.
