# Decision data eligibility

The 190 choices in `work-words.jsonl` and `trade-hinges.jsonl` remain
ratified intent. Their decision-time conditioning is not training-eligible.
Those are separate standings: a later evidence defect does not revoke what the
operator approved, and approval does not make future information safe to teach.

`PROTECTED.json` binds the approved choices, their historical cross-module
derivatives, and the nine approved world documents to their SHA-256 hashes.
`tools/audit_conditioning.py` reproduces this audit against those exact bytes.

| Dataset | Rows | Future death | Future lesson | Future belief | Bare options | Rows collapsed by `(person, hour)` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Work words | 112 | 107 | 104 | 95 | 112 | 6 |
| Trade hinges | 78 | 77 | 78 | 68 | 78 | 15 |
| **Total** | **190** | **184** | **182** | **163** | **190** | **21** |

The first work-word choice illustrates the distinction. Its decision hour is
3408. Its captured record includes death at hour 5616 and lessons stamped at
hour 26304. The approved choice still stands; those later facts cannot
condition it.

The historical version 2 ZAO state files contain 106 rows for 112 work-word
choices and 63 rows for 78 trade-hinge choices. Their `(person, hour)` key
collapsed decisions from different counties, so one state could be attached to
several distinct events. The version 3 join uses run, county, person, event and
hour together and refuses every version 2 input.

The unmerged `neo/c126-trajectory-corpus` branch is not admitted. Its eight
rows are aggregate county diagnostics taken from different seeds and horizons.
They contain no person decisions, continuous cohort, source hashes, settings,
failure receipt or training-eligibility record. They remain diagnostic history.

New eligibility begins with immutable SAO decision events, executable options
whose action owner, parameters and current eligibility evidence are recorded,
and a separately authored choice under the same full namespace. Future facts
are excluded or named in `conditioning.exclusions`. ZAO state is captured as of
that same decision hour. Only a row whose conditioning status is `eligible`
can enter a training view.

Record 55 supersedes the acquisition standing of the Record 52 Knox example.
Its C74 import, source review, acquisition review and reference JSON remain
byte-identical historical evidence. County presence and adulthood did not prove
that Ada read the report, heard it, or personally used either service.
[`acquisition-corrections.json`](acquisition-corrections.json) revokes the old
acquisition/retention evidence for current views, including renamed claims and
relabelled, resealed reviews. Import validation still proves historical integrity.
The retired reference generator refuses both build and current validation.
A new reading receipt has independent standing and receives no inherited approval.

The literal game source remains protected and unchanged. An hours-long outage
ongoing at publication supplies no recovery time. The old acquisition review is
superseded; the forced choice remains excluded. C77's corrected authored reading
capture creates zero training rows and carries no task or retrieval approval.
