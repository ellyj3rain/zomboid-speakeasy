# Record 82 educational answer adapter and personal prior

The measured answer adapter adds 16,672 trained FP32 parameters to the frozen
[Record 81 base](../r81-reference/README.md). It learns answer and EOS targets
from complete publisher questions in the training partition. Hidden evaluation
answers remain outside inference inputs. Original family partitions and the
frozen byte tokenizer remain authoritative.

| Measurement | Result |
|---|---|
| Complete training questions | 1,992 of 5,557 supported targets; 3,422 overflow and 143 need missing media |
| Configuration fixed before grading | Seed 82, bottleneck 32, 2,048 updates, batch 64, learning rate 0.001 |
| Actual fitting | 319,436 answer/EOS targets; 49.05 seconds; frozen base unchanged |
| Test multiple choice | Adapter 38/187 correct (20.32%); frozen base 35/187; untrained seed 43/187 |
| Validation multiple choice | Adapter and frozen base 6/18 correct; seed 3/18 |
| Validation numeric | 0/49 correct; 46 incorrect, three unrecognized |
| Export | Four byte-exact tensors; 66,688 little-endian FP32 bytes |

The adapter improves response formatting and three test answers over the frozen
base, while remaining below the untrained seed on test. It establishes no
curriculum competence. The numeric format gain supplies no correct numeric
answers. The fixed candidate was evaluated once after source repair and refit;
the repaired refit has identical adapter tensor values. Retained old attempts
remain historical. Attempted complete inputs, pre-inference exclusions and
unfinished or invalid outputs have separate denominators.

Personal runtime export version 2 preserves original learning states, source
references, policy, independent person/context bindings and the county clock.
Queries age those original states without crediting practice. Runtime registry
packaging reconstructs every explicit person's schooling, ledger and profile
before export. Its world identity uses the game's existing canonical JSON
definition hash; raw file hashes remain provenance. Source birth region and
migrations remain distinct from current residence.

`personal-prior-controls/` contains an Ontario-born outsider who moved to
Kentucky. Its one successful original textbook response is an explicit gold
control dated in 2026, not a model-produced answer or historical 1993 classroom
receipt. Original, newer and empty exports test source custody and decay. They
establish no native actor competence. Modern textbooks require dated concept
mapping before historical exposure.

Speakeasy owns source acquisition, preparation, fitting and automatic grading.
SAO owns native person attachment, persistence, asynchronous inference and
current-state revalidation. Academic concept references do not grant native
skills, recipes, unseen county facts or peer assent. The native consumer and
concept-to-game-action mapping retain their own implementation evidence.
