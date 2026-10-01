# Sourced educational curriculum

Speakeasy owns educational source acquisition, exact course selections,
automatic assessment and training-data preparation. The curriculum runs from kindergarten through
grade twelve to college general education and selected specializations. Actual
books supply the readings, explanations, worked examples and exercises.

| Owner | Artifact and behavior |
|---|---|
| Source identities | `catalogue.json` selects publisher books and pinned editions. |
| Acquisition | `tools/education_corpus.py acquire` preserves publisher metadata, rights evidence, original bytes and hashes in a new immutable archive. |
| Courses | `curriculum.json` binds every sourced unit to its edition, file, extracted text span and activity evidence. Prerequisites define progression. |
| Coverage | `tools/education_curriculum.py coverage` checks source selections and reports missing core subjects, material and teaching requirements. |
| Education histories | `tools/education_curriculum.py compile` resolves dated region, cohort, institution and person histories against exact registered curricula. |
| Background production | `tools/education_backgrounds.py` generates and reconstructs owned region/cohort/institution bodies and probabilistic personal schooling receipts from explicit simulation inputs. |
| Preparation | `tools/education_corpus.py prepare` reconstructs educational passages and their exact source-bound proposal. |
| Admission | `tools/education_corpus.py admit` reconstructs the entire proposal and text, evaluates source/data integrity and saves the evaluation receipt with the dataset. |
| Tokenization | `tools/education_training_data.py` exports and independently reconstructs source-family partitions using a supplied frozen byte tokenizer. |
| Assessments | `tools/education_assessment.py` reconstructs original textbook questions and answers, exposes answer-free learner inputs and grades supported numeric and choice responses. |
| Learning state | `tools/education_learning.py` replays exact person-bound evidence into familiarity, retention, recall calibration and bounded transfer; observation applies declared time and age decay. |
| Foundation training | `tools/foundation_pretraining.py` fits the shared FP32 causal base on source-derived next-token targets and saves weights, optimizer state, loss trace and held-out measurements. |
| Personal knowledge | SAO owns personal acquisition, retention, interests, practice, memory and action admission. |

## Sources and rights

The candidate catalogue contains 47 publisher sources. Project Gutenberg
supplies public-domain editions of graded readers, arithmetic, geometry,
grammar, composition, languages, early number work, science, civics, music,
household work and practical mechanics. Pinned OpenStax books supply algebra,
physics, biology, chemistry, anatomy, history, government, psychology, sociology
and business. Hardy's published TeX supplies analysis material; its preserved
raw export and extracted book body have separate hashes.

Every acquired source retains its actual publisher rights evidence. This route
accepts publisher-established United States public-domain standing or an exact
CC BY 4.0 edition. Several current OpenStax repositories now carry NC-SA terms;
the selected CC BY versions retain their own pinned revision and license.
The repository's MIT license covers code and does not replace book terms or
attribution requirements.

Gutenberg HTML archives preserve the original ZIP, including its supplied
illustrations and other assets. Educational text rows retain figure references
and alternative text; they do not project the images or infer their contents.
OpenStax XML retains mathematical markup, exercise/solution structure and figure
references. Its image assets are outside the acquired XML inventory. Sources
missing diagrams, notation, laboratory work or complete assessed courses retain
those limits in coverage.

The academic route in `../README.md` supplies necessary pre-training material.
Automated checks verify publisher provenance, edition rights, original bytes
and exact extraction. Downstream assessments measure what a learner can do
with that material. Acquisition and preparation produce source passages;
admission saves the automated evaluation that binds their training use.

## Regional and personal progression

Each region owns dated cohorts and institutions. A cohort identifies its exact
curriculum version; an institution declares its offered courses and optional
unit selections. Shared core courses and units propagate within that cohort.
The curriculum's `regionalPolicy` bounds optional variation as a proportion of
core units. Its current candidate setting permits at most one optional unit per
five core units; this is a declared parameter, not a universal school rule.

A person's history records birthplace, migrations, actual source institutions,
attendance, interruptions, completion and selected material. The compiler can
register several exact curricula, so an outsider retains a distinct prior
schooling sequence after migration. Present residence supplies no replacement
education history. Source-state bodies and generated-history receipts belong to
the simulation's background producer.

Exposure remains separate from retention. Historical edition dates must come
from a complete bounded printed notice in the verified source. Ambiguous or
unestablished notices withhold personal exposure; a shortened citation cannot
select the oldest year. Modern editions require dated historical-content
mapping before supporting pre-1993 schooling. A completed course record supplies
neither native skills nor perfect recall.

The current curriculum binds 130 courses and 4,484 units to all 47 academic
sources. Explicit breadth slots retain missing shared language coverage and
secondary health material. Assessment coverage separately records figures,
laboratory activity, unavailable answers and prose requiring semantic grading.
Source coverage and a complete assessed education have separate receipts.

Background production uses a declared world identity, seed, region/cohort and
institution inputs, enrolment and interruption probabilities, and person age,
birthplace and migrations. The compiler reconstructs generated receipts before
using them. Institutions propagate their cohort core; personal attendance and
completion vary within that declared history. Authored source-state bodies keep
their ownership and exact identity.

## Grades and personal learning

The assessment bank preserves every acquired CNXML exercise and its coverage
reason. Supported numeric quantities retain exact fractions and declared units;
supported choices retain the original alternatives. Missing answers, unsupported
multipart work and semantic prose remain unscored. The learner receives problem
and context markup; source solutions stay with the evaluator.

Each grade names the source exercise, model or person version, session, evidence,
time and learning mode. Learning-state replay reconstructs the original grade
and person history. Independent retrieval, hints, practice and passive exposure
have distinct declared contributions. Wrong answers and unavailable grades
remain separate. Use, interests, elapsed time and person age affect stabilization
and decay through a versioned caller-owned policy.

Cross learning uses a successful retained source concept and an exact unit or
prerequisite relation to supply bounded priming. Tutoring joins retained teacher
knowledge at reception time, exact recipient/session/source receipt and the
recipient's actual graded response. Historical passive exposure joins an
attended schooling receipt to an available dated unit and ages from that
schooling time. A read-only memory view and bounded prior export reconstruct the
ledger before returning state; the current export awaits its SAO consumer.

## Training boundary

Evaluation covers the exact archive, extraction version, source inventory and
prepared passages. Admission rederives that content and persists a deterministic
source/data evaluation receipt. Rehashed invented passages and changed metadata
are refused. Source integrity is separate from the grades earned by a learner.

Training and evaluation splits assign whole source families, including alternate
revisions of the same publisher book, shared modules/passages and identical
question/solution content. Non-semantic XML identifiers cannot disguise a copied
assessment; original IDs and markup remain in its provenance. The exporter never
fits a tokenizer on evaluation material. It checks known fitting-corpus hashes
in the supplied frozen artifact; an unknown original fitting corpus remains a
reported provenance limit. Each block retains source/version/row identity,
offsets, exact next-token shifts and padding loss masks. A complete release
requires training, validation and test partitions and reconstruction of the
saved bytes from admitted sources.

Educational text supports the shared cognitive substrate. Ordinary cognition
and opposing associative discovery preserve independent predictions and
outcome owners. Generic education supplies no unseen county object, location,
danger, recipe permission or another person's assent. The
[academic and cultural foundation](../pretraining/README.md) owns reference
pre-training and model assessment. SAO owns the native retention consumer and
task-specific grounded execution.

## Commands

Run from the Speakeasy repository with Python:

```text
python tools/education_corpus.py acquire --archive runs/education-archive
python tools/education_corpus.py verify --archive runs/education-archive
python tools/education_curriculum.py coverage --archive runs/education-archive --out runs/education-coverage.json
python tools/education_corpus.py prepare --archive runs/education-archive --output runs/education-review
```

Archives and derived preparation outputs remain immutable local artifacts under
`runs/`. Admission produces the automated receipt; tokenization additionally
requires the admitted dataset, frozen tokenizer and explicit source-family split
request. The command-line help exposes those inputs. Existing protected period
sources and earlier decisions retain their original bytes and owners.
