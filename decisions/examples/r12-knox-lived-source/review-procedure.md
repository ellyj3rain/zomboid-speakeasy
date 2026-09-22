# Record 52 review procedure

This procedure reviews one protected claim extraction and one person-specific
acquisition. It does not approve the controlled source choice as training data.

## Claim extraction

1. Reproduce the protected document and cited line hashes from
   `decisions/PROTECTED.json` and the current source bytes.
2. Require the claim text and carrier to be literal substrings of the cited
   line. The extraction ends before the line's closed businesses, unknown
   cause, and proposed explanations.
3. Use the row date at local midnight for `knowableAt`; the source gives a date
   rather than a time.
4. Admit only `lived`. Bind that rule to
   `world/us-1993/who-knows-what.md:122-123`, where the protected scoping index
   names the county's own July days as lived claims. Reading the paper is a
   separate acquisition.
5. Bind adult detail to `world/us-1993/who-knows-what.md:107`. The frozen
   person is 31 at the event; this is a detailed claim rather than a child's
   vague household-memory form.
6. Record confidence separately. This Knox Event table predates the later
   per-row confidence column, so the compiler must refuse `HIGH` unless a
   review receipt states that absence. The basis for `HIGH` is the approved
   document's direct reconstruction from the shipped game record, not a
   confidence token invented on the source line.

## Acquisition adjudication

1. Verify the imported SAO manifest and every imported file against merge
   commit `739ff0a026c2fc2c9450f71a5169b1e72b302c46`.
   Preserve the one recorded portability exception: the C74 generator hashed
   `VERSION` from a CRLF checkout before Git stored its LF blob. Both hashes
   and the exact reversible normalization remain in the import receipt.
2. Recompute the event, calendar, presence, acquisition, and retention hashes.
3. Require one full namespace across the event, frozen person, acquisition,
   and retention observation.
4. Require acquisition at the July 2 event hour, county presence beginning
   July 1, adult age at the event, the lived path, and retention through the
   decision hour.
5. Preserve the controlled-ground and loaded-save limits. Adjudication means
   the evidence supports this person-specific claim; it does not make the
   controlled run a natural county sample.

## Choice boundary

C74 forced the second of two food sources so the same-person join could be
observed through a completed native action. The outage claim is context the
person carried. It neither caused nor justified choosing the banana source over
the apple source. The event remains useful evidence for the join; its controlled
selection remains excluded from choice training.
