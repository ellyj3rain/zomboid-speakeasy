"""Bound speaker task integration and data-preparation failure controls."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import conversation_tasks as C
import cross_module_rows as J
import decision_authoring as A
import expression_proof as P
import experimental_admission as X
import retriever_targets as R
import speaker_tasks as S
import task_data as D
import training_evidence as E
import test_retriever_targets as F


def reseal(value):
    value = copy.deepcopy(value)
    value.pop("contentSha256", None)
    return A.seal(value)


class TaskDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for path in E.ROOT.glob("*.json"):
            C.save_evidence(A.read(path), self.root)
        self.store = E.Store(self.root)
        self.index = A.read(C.ROOT / "training/speaker/c77-example.json")
        self.under = A.read(C.ROOT / "training/understander/c77-example.json")
        source = P.from_target(self.index["retrieverTargetSha256"], self.store)
        model = P.compile_source(source)
        self.plan = P.report_plan(model, next(iter(model["reports"])),
                                  {kind: 1 for kind in P.KINDS}, vocative=True)
        self.row = S.propose_bound(self.index["retrieverTargetSha256"],
                                  "test-only-bound-speaker", [self.plan], self.store)
        C.save_evidence(self.row, self.root)
        fixture = F.RetrieverTargetTests()
        fixture.evidence_root = self.root
        self.receipt = fixture.mousecat(self.row["contentSha256"], interaction="test-only-v4")

    def request(self, approved=False):
        speaker = {"rowSha256": self.row["contentSha256"]}
        if approved:
            speaker["approvalReceiptSha256"] = self.receipt
        requests = [speaker, {"rowSha256": self.under["taskSha256"],
            "approvalReceiptSha256": self.under["approvalReceiptSha256"]},
            {"rowSha256": self.index["retrieverTargetSha256"]}]
        return {"schema": "speakeasy-task-data-request", "schemaVersion": 1,
                "scope": X.SCOPE, "requests": requests,
                "splits": {"train": [r["rowSha256"] for r in requests], "validation": [], "test": []}}

    def test_full_wording_captured_names_and_independent_exact_approval(self):
        expected = self.store.read(self.index["wordingProposalSha256"])["output"]["text"]
        self.assertEqual(self.row["output"]["text"], expected)
        self.assertEqual(self.row["input"]["modelInput"]["expressionInput"]["participants"]["sao-2"]["givenName"], "Jon")
        for old in (self.index["wordingReviewReceiptSha256"], self.under["approvalReceiptSha256"]):
            self.assertEqual(X.inspect(self.row, scope=X.SCOPE, approval=old,
                                      evidence=self.store)["status"], "excluded")
        self.assertEqual(X.inspect(self.row, scope=X.SCOPE, approval=self.receipt,
                                  evidence=self.store)["status"], "admitted-to-offline-evaluation")
        self.assertEqual(S.conditioning(self.row, self.store)["status"], "ineligible")

    def test_bound_source_proposition_witness_and_text_tampering_refuse_after_reseal(self):
        for defect in ("name", "source", "voice", "owner", "time", "text", "extra", "duplicate", "empty"):
            bad = copy.deepcopy(self.row)
            model = bad["input"]["modelInput"]
            part = bad["output"]["parts"][0]
            if defect == "name": model["expressionInput"]["participants"]["sao-2"]["givenName"] = "Eve"
            elif defect == "source": model["expressionInput"]["sourceSha256"] = "0" * 64
            elif defect == "voice": model["expressionInput"]["voiceConditioning"]["trust"] = 100
            elif defect == "owner": part["plan"]["propositions"][0]["ownerRef"] = "sao-2"
            elif defect == "time": part["plan"]["propositions"][0]["at"] = "1993-07-11"
            elif defect == "text":
                part["text"] += " Service is restored now."
                bad["output"]["text"] = part["text"]
            elif defect == "extra": part["plan"]["extra"] = "invented"
            elif defect == "duplicate": bad["output"]["parts"].append(copy.deepcopy(part))
            else: bad["output"]["parts"] = []
            with self.subTest(defect=defect), self.assertRaises(J.ContractError):
                S.validate_task(reseal(bad), self.store)

    def test_version4_resolves_through_snapshot_and_retriever_anchor(self):
        snapshot = S.approve(self.row, self.receipt, "test-only-v4-snapshot", self.store)
        C.save_evidence(snapshot, self.root)
        catalogue = self.row["input"]["catalogue"]
        anchor = A.seal({"schema": R.ANCHOR_SCHEMA, "schemaVersion": 2,
            "anchorId": "test-only-v4-anchor", "task": "speaker",
            "catalogue": {"snapshotRef": catalogue["snapshotRef"], "contentSha256": A.digest(catalogue)},
            "context": self.row["input"]["context"],
            "taskExample": {"datasetSnapshotRef": snapshot["snapshotId"],
                "datasetSnapshotSha256": snapshot["contentSha256"], **snapshot["rows"][0], "standing": "approved"},
            "requiredClaimRefs": self.row["requiredClaimRefs"]})
        self.assertEqual(self.store.task_anchor(anchor, catalogue), self.row)
        self.assertEqual(R.task_conditioning(anchor, catalogue, self.store), S.conditioning(self.row, self.store))

    def test_preview_excludes_unapproved_speaker_and_masks_seven_unjudged(self):
        preview = D.prepare(self.request(), self.store)
        self.assertEqual(preview["datasets"]["speaker"]["train"], [])
        retriever = preview["datasets"]["retriever"]["train"][0]
        targets = retriever["target"]["claims"]
        self.assertEqual(sum(t["lossMask"] for t in targets), 1)
        self.assertEqual(sum(t["label"] is None for t in targets), 7)
        self.assertEqual(sum(t["label"] == 0 for t in targets), 0)
        self.assertNotIn("labels", retriever["input"])
        self.assertNotIn("anchor", retriever["input"])
        under = preview["datasets"]["understander"]["train"][0]
        self.assertEqual(under["input"]["utteranceRoles"],
                         self.store.read(self.under["taskSha256"])["input"]["utteranceRoles"])
        self.assertEqual(under["input"]["utteranceRoles"]["speakerRef"], "sao-2")
        self.assertEqual(under["input"]["utteranceRoles"]["listenerRef"], "sao-1")
        self.assertNotIn("output", under["input"])
        with self.assertRaisesRegex(J.ContractError, "release refused"):
            D.release(preview, self.store)

    def test_approved_speaker_target_is_actual_text_and_stays_one_source_family(self):
        preview = D.prepare(self.request(True), self.store)
        speaker = preview["datasets"]["speaker"]["train"][0]
        self.assertEqual(speaker["target"], {"text": self.row["output"]["text"]})
        self.assertNotIn("variants", speaker["target"])
        self.assertEqual(preview["release"]["status"], "excluded")
        request = self.request(True)
        request["splits"]["test"] = [request["splits"]["train"].pop(0)]
        self.assertIn("shared-source-split-leakage", D.prepare(request, self.store)["release"]["exclusions"])

    def test_reordering_requests_and_partitions_does_not_change_prepared_bytes(self):
        original = self.request(True)
        changed = copy.deepcopy(original)
        changed["requests"].reverse()
        changed["splits"]["train"].reverse()
        self.assertEqual(A.encoded(D.prepare(original, self.store)), A.encoded(D.prepare(changed, self.store)))

    def test_resealed_mask_text_input_and_release_tampering_refuse(self):
        preview = D.prepare(self.request(True), self.store)
        for defect in ("mask", "text", "input", "roles", "release"):
            bad = copy.deepcopy(preview)
            if defect == "mask":
                target = next(t for t in bad["datasets"]["retriever"]["train"][0]["target"]["claims"] if t["label"] is None)
                target.update(label=0, lossMask=True)
            elif defect == "text": bad["datasets"]["speaker"]["train"][0]["target"]["text"] = "Service restored."
            elif defect == "input": bad["datasets"]["understander"]["train"][0]["input"]["context"]["utterance"] = "What now?"
            elif defect == "roles": bad["datasets"]["understander"]["train"][0]["input"].pop("utteranceRoles")
            else: bad["release"]["status"] = "ready-for-tokenization"
            with self.subTest(defect=defect), self.assertRaisesRegex(J.ContractError, "differs from source"):
                D.validate(reseal(bad), self.store)

    def test_schema_unknown_fields_and_split_assignments_refuse(self):
        for defect in ("extra", "request", "split", "duplicate", "missing"):
            request = self.request()
            if defect == "extra": request["allowUnapproved"] = True
            elif defect == "request": request["requests"][0]["approved"] = True
            elif defect == "split": request["splits"]["train"] = {}
            elif defect == "duplicate": request["splits"]["train"] *= 2
            else: request["splits"]["train"].pop()
            with self.subTest(defect=defect), self.assertRaises(J.ContractError):
                D.prepare(request, self.store)

    def test_changed_approval_receipt_cannot_validate_existing_preview(self):
        preview = D.prepare(self.request(True), self.store)
        (self.root / (self.receipt + ".json")).unlink()
        with self.assertRaisesRegex(J.ContractError, "differs from source"):
            D.validate(preview, self.store)

    def test_each_task_needs_its_own_partitions_even_if_global_partitions_exist(self):
        # Isolate this materializer rule from the separately tested source-group
        # gate. This fabricated admission response is never production evidence.
        real_compile = X.compile_dataset
        def global_only(*args, **kwargs):
            result = real_compile(*args, **kwargs)
            result["dataset"]["exclusions"] = []
            result["dataset"]["status"] = "admitted-for-offline-experiment"
            return result
        with patch.object(X, "compile_dataset", side_effect=global_only):
            preview = D.prepare(self.request(True), self.store)
        self.assertEqual(preview["release"]["status"], "excluded")
        self.assertEqual(len(preview["release"]["missingPartitions"]), 6)


if __name__ == "__main__":
    unittest.main()
