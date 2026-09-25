#!/usr/bin/env python3
"""Learning, leakage, masking and reproduction controls for Record 66."""
from __future__ import annotations

import copy
import unittest

import coordination_data as Data
import coordination_reference as Reference
import decision_authoring as Author


PATTERNS = {
    "accept": {"relationship": .62, "pressure": .12, "activity": "idle",
               "contest": False},
    "qualify": {"relationship": .50, "pressure": .88, "activity": "idle",
                "contest": False},
    "counter-propose": {"relationship": .06, "pressure": .15,
                        "activity": "idle", "contest": False},
    "defer": {"relationship": .45, "pressure": .20,
              "activity": "acquiring-food", "contest": False},
    "contest": {"relationship": -.58, "pressure": .25,
                "activity": "idle", "contest": True},
}


def input_for(label, ordinal):
    pattern = PATTERNS[label]
    zao = ordinal % 2 == 1
    return {
        "schema": "speakeasy-coordination-response-input", "schemaVersion": 1,
        "route": "coordination-response", "process": {"kind": "food-delivery"},
        "actor": {"executor": "ZAO.Driver" if zao else "SAO.Controller",
                  "bodyOwner": "ZAO" if zao else "SAO"},
        "decisionTime": {
            "proposal": {"purpose": "carry-food-to-requester",
                         "destination": {"minX": 1, "minY": 1,
                                         "maxX": 2, "maxY": 2, "z": 0},
                         "scope": {"category": "food", "quantity": 1},
                         "requiredCapabilities": {"acquire": True, "carry": True,
                                                  "deliver": True}},
            "reception": {"channel": "spoken",
                          "evidence": {"kind": "headless", "distance": 1}},
            "currentWork": {"activity": pattern["activity"],
                            "owner": "ZAO.Driver" if zao else "SAO.Controller"},
            "competingPriorities": {
                "competingPressure": {"value": pattern["pressure"],
                                      "available": True,
                                      "owner": "ZAO.Maintenance" if zao else "SAO.Needs"},
                "relationship": pattern["relationship"],
                "interests": {"ownGroup": "group"},
                "constraints": {"represented": True,
                                "currentActivity": pattern["activity"],
                                "executionOwnerAvailable": True,
                                "ownNeedAvailable": True,
                                "contest": pattern["contest"]},
                "owners": {"ownNeed": "owner", "relationship": "standing",
                           "interests": "identity", "constraints": "controller"},
            },
            "capabilities": {"values": {"acquire": True, "carry": True,
                                         "deliver": True, "execute": True},
                             "owner": "driver", "availability": "available"},
            "feasibleOptions": list(Data.OBSERVED_RESPONSES) + ["decline"],
        },
    }


def dataset_fixture():
    rows = []
    ordinal = 0
    for split, repeats in (("train", 2), ("validation", 1), ("test", 1)):
        for repeat in range(repeats):
            for label in Data.OBSERVED_RESPONSES:
                scene = f"{split}-{label}-{repeat}"
                rows.append(Author.seal({
                    "schema": "speakeasy-coordination-reference-row",
                    "schemaVersion": 1, "rowId": "coordination-response/" + scene,
                    "split": split, "sourceLineage": "fixture:" + scene,
                    "routing": {"namespace": {"eventId": scene},
                                "process": {"id": scene}},
                    "auditOnly": {"actorKind": ("survivor", "afflicted", "crossed")
                                  [ordinal % 3], "pathogen": {}, "visibleForms": []},
                    "input": input_for(label, ordinal),
                    "target": {"response": label},
                    "laterOutcome": {"responseDelivery": {"delivered": True}},
                    "provenance": {"taskSha256": "a" * 64,
                                   "reviewSubjectSha256": "b" * 64,
                                   "reviewReceiptSha256": "c" * 64},
                }))
                ordinal += 1
    return Author.seal({
        "schema": "speakeasy-coordination-reference-dataset", "schemaVersion": 1,
        "datasetId": "test", "sourceImportSha256": "d" * 64,
        "reviewSubjectSha256": "b" * 64, "reviewReceiptSha256": "c" * 64,
        "labels": list(Data.RESPONSES),
        "observedLabels": list(Data.OBSERVED_RESPONSES),
        "partitionCounts": {"train": 10, "validation": 5, "test": 5},
        "rows": rows, "standing": "approved-bounded-offline-reference",
        "exclusions": ["synthetic fixture"],
    })


class CoordinationReferenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = dataset_fixture()
        cls.artifact, cls.tokenizer = Reference.load_tokenizer()
        cls.config = {"epochs": 700}
        cls.model = Reference.fit(cls.dataset, cls.artifact, cls.tokenizer,
                                  config=cls.config)

    def test_learns_held_out_patterns_and_reproduces(self):
        rows = Reference.predictions(self.dataset, self.tokenizer, self.model)
        for split in Data.SPLITS:
            result = Reference.metrics([row for row in rows if row["split"] == split])
            self.assertGreaterEqual(result["accuracy"], .8)
        duplicate = Reference.fit(self.dataset, self.artifact, self.tokenizer,
                                  config=self.config)
        self.assertEqual(Author.encoded(self.model), Author.encoded(duplicate))

    def test_outcome_and_condition_audit_are_prediction_inert(self):
        changed = copy.deepcopy(self.dataset)
        changed["rows"][15]["laterOutcome"] = {"future": "different"}
        changed["rows"][15]["auditOnly"] = {
            "actorKind": "crossed", "pathogen": {"terminalState": "crossed"},
            "visibleForms": [{"form": "private"}]}
        changed["rows"][15] = Author.seal({key: value for key, value in
                                            changed["rows"][15].items()
                                            if key != "contentSha256"})
        changed = Author.seal({key: value for key, value in changed.items()
                               if key != "contentSha256"})
        base = Reference.examples(self.dataset, self.tokenizer)[15]
        altered = Reference.examples(changed, self.tokenizer)[15]
        self.assertEqual(base["tokens"], altered["tokens"])
        self.assertEqual(Reference.predict(base, self.model),
                         Reference.predict(altered, self.model))

    def test_feasible_mask_prevents_impossible_prediction(self):
        example = copy.deepcopy(Reference.examples(self.dataset, self.tokenizer)[0])
        example["allowed"] = ["defer"]
        result = Reference.predict(example, self.model)
        self.assertEqual(result["response"], "defer")
        self.assertEqual(set(result["probabilities"]), {"defer"})

    def test_split_or_choice_leak_is_refused(self):
        changed = copy.deepcopy(self.dataset)
        changed["rows"][0]["input"]["split"] = "train"
        changed["rows"][0] = Author.seal({key: value for key, value in
                                           changed["rows"][0].items()
                                           if key != "contentSha256"})
        changed = Author.seal({key: value for key, value in changed.items()
                               if key != "contentSha256"})
        with self.assertRaisesRegex(ValueError, "audit or outcome evidence"):
            Data.validate_dataset(changed)

    def test_reference_evaluation_discriminates_untrained_and_permuted(self):
        evaluation, _ = Reference.evaluate(self.dataset, self.artifact,
                                            self.tokenizer, self.model)
        trained = evaluation["partitions"]["test"]["accuracy"]
        self.assertGreater(trained,
                           evaluation["controls"]["zeroEpochTest"]["accuracy"])
        self.assertGreater(trained,
                           evaluation["controls"]["permutedTrainTargetsTest"]["accuracy"])
        self.assertEqual(evaluation["controls"]["unsupportedLabelsMasked"],
                         ["decline", "withdraw"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
