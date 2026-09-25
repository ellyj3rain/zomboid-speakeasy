#!/usr/bin/env python3
"""Controls for C81 import, review and decision-only dataset shaping."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

import coordination_data as Data
import coordination_tasks as Tasks
import decision_authoring as Author
from test_coordination_tasks import coordination_row
from test_cross_module_rows import namespace, write_jsonl, zao_row


class CoordinationDataTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="speakeasy-c81-data-")
        self.root = Path(self.temporary.name)
        ns = namespace()
        sao, zao = self.root / "sao.jsonl", self.root / "zao.jsonl"
        write_jsonl(sao, [coordination_row(ns)])
        write_jsonl(zao, [zao_row(ns)])
        self.task = Tasks.task_rows(sao, zao, self.root / "joined.jsonl")[0]

    def tearDown(self):
        self.temporary.cleanup()

    def test_model_input_keeps_private_decision_and_removes_routing_and_outcome(self):
        value = Data.model_input(self.task)
        encoded = Author.encoded(value).decode("utf-8")
        self.assertEqual(value["route"], "coordination-response")
        self.assertIn("competingPriorities", value["decisionTime"])
        for forbidden in ("person-r1", "run-r1", "laterOutcome", "choice",
                          "sourceLineage", "pathogen", "terminalState"):
            self.assertNotIn(forbidden, encoded)

    def test_later_outcome_and_condition_audit_cannot_change_input(self):
        baseline = Data.model_input(self.task)
        changed = copy.deepcopy(self.task)
        changed["laterOutcome"]["responseDelivery"]["delivered"] = False
        changed["provenance"]["crossModule"]["auditMutation"] = "crossed"
        self.assertEqual(baseline, Data.model_input(changed))

    def test_decision_time_change_does_change_input(self):
        changed = copy.deepcopy(self.task)
        changed["decisionTime"]["competingPriorities"]["relationship"] = -0.8
        self.assertNotEqual(Data.model_input(self.task), Data.model_input(changed))

    def test_review_invocation_binds_exact_subject(self):
        subject = Author.seal({
            "schema": "speakeasy-coordination-label-review",
            "schemaVersion": 1, "reviewId": "r66-c81-production-responses",
            "sourceImportSha256": "a" * 64, "targetScope": "response-kind-only",
            "rows": [{"split": "train", "sceneId": "one",
                      "actorKindAuditOnly": "afflicted", "executor": "ZAO.Driver",
                      "currentWork": {"activity": "idle"},
                      "competingPressure": {"value": .4, "available": True,
                                            "owner": "ZAO.Maintenance"},
                      "relationship": .2, "productionResponse": "accept",
                      "responseDelivered": True}],
            "approvalEffects": ["bounded"], "remainingExclusions": ["headless"],
        })
        invocation = Data.review_invocation(
            subject, "session", "invocation", "2026-09-25T02:21:00Z")
        seam = invocation["intake"]["seams"][0]
        self.assertEqual(seam["evidenceRef"],
                         "speakeasy:content-sha256:" + subject["contentSha256"])
        self.assertEqual(seam["options"][0]["value"], "approved")

    def test_review_invocation_groups_every_row_within_mousecat_limit(self):
        rows = []
        scene_ids = []
        for repetition in range(4):
            for response in Data.OBSERVED_RESPONSES:
                scene_id = f"{response}-{repetition}"
                scene_ids.append(scene_id)
                rows.append({
                    "split": ("train", "validation", "test")[repetition % 3],
                    "sceneId": scene_id, "actorKindAuditOnly": "crossed",
                    "executor": "ZAO.Driver", "currentWork": {"activity": "idle"},
                    "competingPressure": {"value": .4, "available": True,
                                          "owner": "ZAO.Maintenance.predatoryPressure"},
                    "relationship": .2, "productionResponse": response,
                    "responseDelivered": True,
                })
        subject = Author.seal({
            "schema": "speakeasy-coordination-label-review",
            "schemaVersion": 1, "reviewId": "r66-c81-production-responses",
            "sourceImportSha256": "a" * 64, "targetScope": "response-kind-only",
            "rows": rows, "approvalEffects": ["bounded"],
            "remainingExclusions": ["headless"],
        })
        invocation = Data.review_invocation(
            subject, "session", "invocation", "2026-09-25T02:21:00Z")
        actual = invocation["intake"]["seams"][0]["mlReview"]["actualInput"]
        self.assertEqual(len(actual), len(Data.OBSERVED_RESPONSES))
        self.assertLessEqual(len(actual), 12)
        rendered = "\n".join(fact["value"] for fact in actual)
        for scene_id in scene_ids:
            self.assertEqual(rendered.count("/" + scene_id + ":"), 1)

    def test_mousecat_generated_item_id_resolves_by_exact_subject(self):
        subject_hash = "b" * 64
        lineage = {"evidenceRef": "speakeasy:content-sha256:" + subject_hash,
                   "threadId": "r66-c81-production-response-labels"}
        receipt = {
            "schema": "mousecat.skill-invocation/2", "action": "await",
            "skillRef": "crucible", "interactionId": "skill-generated",
            "status": "answered",
            "items": [{"id": "seam-platform-generated", "shape": "decision",
                       "lineage": lineage}],
            "responses": [{"itemId": "seam-platform-generated",
                           "shape": "decision", "status": "answered",
                           "value": "approved", "selectedOption": "approved",
                           "selectedOptions": ["approved"], "notes": None,
                           "lineage": lineage}],
        }
        digest = Author.digest(receipt)
        (self.root / (digest + ".json")).write_bytes(Author.encoded(receipt) + b"\n")
        resolved = Data.Evidence.Store(self.root).decision(digest, subject_hash)
        self.assertEqual(resolved["items"][0]["id"], "seam-platform-generated")

    def test_source_validation_refuses_expected_label(self):
        # Use the real source parser on a mechanically copied source only when
        # the sibling checkout is present; CI for this repository need not own it.
        source = Data.ROOT.parent.parent / "survivor-awareness" / Data.SOURCE_PATH
        if not source.is_dir():
            self.skipTest("sibling SAO C81 source is not installed")
        files = {name: (source / name).read_bytes() for name in Data.SOURCE_FILES}
        catalogue, _, _ = Data.validate_source(files)
        changed = copy.deepcopy(catalogue)
        changed["scenes"][0]["expectedChoice"] = "accept"
        changed = Author.seal({key: value for key, value in changed.items()
                               if key != "contentSha256"})
        files["catalogue.json"] = Author.encoded(changed) + b"\n"
        with self.assertRaisesRegex(ValueError, "expected response|fields differ"):
            Data.validate_source(files)


if __name__ == "__main__":
    unittest.main(verbosity=2)
