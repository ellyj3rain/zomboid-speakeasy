# The 1993 world documents

The world model's declared ground: what people in Knox County knew
in July 1993, written as researched documents.

Rules:

- Every claim carries its confidence and, where it matters, its
  source. Researched, never confabulated.
- Nothing here teaches a model until the document it lives in has
  been reviewed and approved.
- Knowledge is scoped by who a person was - documents mark which
  lives carry which knowledge (a trade, a region, an age).
- The boundary of an answerable question is what THAT PERSON would
  plausibly have lived, not a refusal of the shared world.

The research plan (`PLAN.md`) is approved. The first cut is drafted:
eight documents in [`us-1993/`](us-1993/) - timeline, daily life, media,
institutions, work and money, military, the who-knows-what index, and
the Knox Event - plus [`people-mods.md`](people-mods.md), the
mod catalogue that feeds DR-032 on the SAO side. All of it is
APPROVED as of 2026-09-13, when the operator ordered the review
completed by the record and each document was reviewed claim-by-claim
against its named primary sources (RECORD.md 43). LOW-confidence rows
never teach, and the who-knows-what index scopes every claim per
person.

Version 1 [decision-time knowledge views](../decisions/AUTHORING.md) can now
compile explicit approved-document excerpts with person-specific acquisition
evidence. They preserve document approval separately from the unreviewed claim
extraction and unadjudicated acquisition records. Missing evidence stays missing;
the tool does not populate a person's history. The three protected-source
excerpts in `claim-examples/` carry unknown person acquisition and remain
conditioning-ineligible. They cover the 1991 minimum-wage change, the 1991
first-class postage change and the February 1993 Family and Medical Leave Act
signing. Each keeps its exact source line and full-document hash. The postage
excerpt ends before the source line's 1995 price change; the wage excerpt omits
the retrospective statement that the rate stayed through 1993. Their extraction
remains unreviewed. [`decisions/AUTHORING.md`](../decisions/AUTHORING.md) records
the selected boundaries and times; RECORD entry 50 records this curation.

Record 52's fourth example, `claim-examples/knox-telecommunications-outage.json`,
remains an immutable historical record. Record 55 supersedes its personal
acquisition standing: adulthood and county presence establish neither report
reception nor personal telephone/Internet use. The source's literal report and
its exact bytes remain protected. The reviewed source is not a measurement of
1993 household Internet prevalence, and an ongoing hours-long outage supplies
no end time.

The current correction is recorded in
[`decisions/acquisition-corrections.json`](../decisions/acquisition-corrections.json).
Current data generation excludes the old acquisition evidence despite intact
review hashes. SAO C77 supplies a new exact-issue reading completion with
`reported` knowledge and a distinct acquisition time. It needs its own import
and task review. Computer content or service observations similarly need an
actual person-bound result; owning a device or installing a mod establishes none.
