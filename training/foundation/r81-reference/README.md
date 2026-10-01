# Record 81 shared foundation reference

This directory preserves the exact measured FP32 export and its training and
evaluation receipts. The export consists of `manifest.json`, `tokenizer.json`
and `weights.fp32le`. Companion records describe source attribution, partition
isolation, configuration, optimization and actual question grades.

| Measurement | Result |
|---|---|
| Source archive | 47 academic books and 16 cultural books; 36,897 prepared passages |
| Source partition | 47 training books, eight validation books, eight test books; duplicate modules and normalized question/answer content remain in one family |
| Model | Four layers, width 256, four attention heads, 256-token context; 3,309,824 FP32 parameters |
| Optimization | 8,192 updates; 130,585,586 sampled target tokens with replacement |
| Validation text loss | 5.801981 from the untrained seed; 1.592964 from saved weights |
| Test text loss | 5.806144 from the untrained seed; 1.616554 from saved weights |
| Held-out language coverage | 4,096 spread blocks per partition, covering all eight families in each |
| Validation question grade | Saved weights: 6/18 scored responses correct; same untrained seed: 3/18 |
| Test question grade | Saved weights: 35/187 scored responses correct (18.72%); same untrained seed: 43/187 (22.99%) |
| Question coverage | 254 of 683 supported held-out questions fit complete input; 415 exceed context and 14 require missing media; 49 attempted validation answers remain unrecognized and unscored |
| Source-derived assessment bank | 6,240 numeric/choice targets; 5,557 train, 372 validation, 311 test |

The improved text loss establishes source-derived language learning. Test
question performance worsened against the seed. This reference establishes
neither curriculum mastery nor retained knowledge in a simulated person. The
next task-learning work needs separately measured adapters, broader answerable
coverage and the SAO personal-learning consumer. Original publisher answers are
evaluator-owned and remain outside model prompts.

`completion-receipt.json` binds the actual saved run and exported tensors.
`export-byte-proof.json` records exact saved-weight equality for all 52 tensors.
`question-evaluation.json` retains actual saved-weight and seed responses, grades,
withheld reasons and source isolation. `source-family-splits.json` and
`assessment-isolation.json` identify the partition proof. The original fitting
run uses the existing frozen C77 tokenizer; evaluation books do not refit it.

The archive contains 50 Project Gutenberg sources marked public domain in the
United States and 13 pinned OpenStax CC BY 4.0 sources. Exact publisher metadata,
rights evidence and source modifications are in `source-attributions.json` and
`publisher-credits.json`; retained CC BY notices are in `source-licenses/`.
Archive attribution and creator-credit links remain authoritative for each
title. Prepared text excludes publisher frontmatter for training while the
archive retains it. Images are retained only where actually acquired and are
outside the text projection.

The corpus and personal-schooling producer have distinct dates. A modern
textbook cannot become a literal historical reading receipt for a pre-1993
person. Dated curriculum exposure, attended background history and actual
grades determine the later bounded personal prior. That prior has no authority
over unseen current county facts, native skills, recipes or another person's
assent.

This export has no activated runtime task adapter or personal-learning consumer.
Native parity and asynchronous runtime scheduling require their own SAO evidence.
