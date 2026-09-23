"""Regression controls for Record 53's missing external evidence bindings."""
import copy
import json
import unittest
from unittest.mock import patch

import cross_module_rows as J
import decision_authoring as A
import retriever_targets as R
import training_evidence as E
import test_retriever_targets as Fixtures


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixtures.RetrieverTargetTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.evidence_root

    def object(self, digest):
        return A.read(self.root / (digest + ".json"))

    def test_resealed_question_situation_or_extra_context_cannot_drift(self):
        proposal = self.fixture.proposal()
        for key, value in (("utterance", "Where is Dana?"),
                           ("situation", {"kind": "combat"}), ("hiddenAnswer", "outage"),
                           ("atTick", float(proposal["input"]["context"]["atTick"]))):
            changed = copy.deepcopy(proposal)
            changed["input"]["context"][key] = value
            changed = self.fixture.reseal(changed)
            with self.subTest(key=key), self.assertRaisesRegex(J.ContractError, "context differs"):
                R.validate_proposal(changed)

    def test_missing_snapshot_row_or_task_approval_cannot_be_a_valid_anchor(self):
        for field in ("datasetSnapshotSha256", "rowContentSha256", "approvalReceiptSha256"):
            catalogue = self.fixture.catalogue()
            anchor = self.fixture.anchor(catalogue)
            path = self.root / (anchor["taskExample"][field] + ".json")
            before = path.read_bytes()
            path.unlink()
            with self.subTest(field=field), self.assertRaisesRegex(J.ContractError, "missing evidence"):
                R.propose(catalogue, anchor, "missing", [])
            path.write_bytes(before)
            R.propose(catalogue, anchor, "restored", [])

    def test_hash_looking_strings_cannot_replace_real_task_evidence(self):
        catalogue = self.fixture.catalogue()
        anchor = self.fixture.anchor(catalogue)
        anchor["taskExample"]["datasetSnapshotSha256"] = "f" * 64
        with self.assertRaisesRegex(J.ContractError, "missing evidence"):
            R.propose(catalogue, self.fixture.reseal(anchor), "fabricated", [])

    def test_source_row_file_tamper_refuses_before_approval(self):
        catalogue = self.fixture.catalogue()
        anchor = self.fixture.anchor(catalogue)
        digest = anchor["taskExample"]["rowContentSha256"]
        row = self.object(digest)
        row["output"] = {"text": "The phones are still down today."}
        (self.root / (digest + ".json")).write_text(json.dumps(row), encoding="utf-8")
        with self.assertRaisesRegex(J.ContractError, "content hash differs"):
            R.propose(catalogue, anchor, "tampered", [])

    def test_resealed_source_edit_invalidates_snapshot_membership(self):
        catalogue = self.fixture.catalogue()
        anchor = self.fixture.anchor(catalogue)
        row = self.object(anchor["taskExample"]["rowContentSha256"])
        row["output"] = {"text": "The phones are still down today."}
        anchor["taskExample"]["rowContentSha256"] = self.fixture.save_evidence(
            self.fixture.reseal(row))
        with self.assertRaisesRegex(J.ContractError, "absent from the referenced snapshot"):
            R.propose(catalogue, self.fixture.reseal(anchor), "resealed", [])

    def test_new_source_and_snapshot_still_need_new_approval(self):
        catalogue = self.fixture.catalogue()
        anchor = self.fixture.anchor(catalogue)
        binding = anchor["taskExample"]
        row = self.object(binding["rowContentSha256"])
        row["output"] = {"text": "Different answer."}
        binding["rowContentSha256"] = self.fixture.save_evidence(self.fixture.reseal(row))
        snapshot = self.object(binding["datasetSnapshotSha256"])
        snapshot["rows"][0]["rowContentSha256"] = binding["rowContentSha256"]
        binding["datasetSnapshotSha256"] = self.fixture.save_evidence(self.fixture.reseal(snapshot))
        with self.assertRaisesRegex(J.ContractError, "exact subject"):
            R.propose(catalogue, self.fixture.reseal(anchor), "old-approval", [])

    def test_resealed_anchor_cannot_relabel_source_required_claims(self):
        catalogue = self.fixture.catalogue()
        anchor = self.fixture.anchor(catalogue)
        anchor["requiredClaimRefs"] = [catalogue["claims"][1]["ref"]]
        with self.assertRaisesRegex(J.ContractError, "source task required claims differ"):
            R.propose(catalogue, self.fixture.reseal(anchor), "relabelled", [])

    def test_row_review_requires_saved_mousecat_response(self):
        proposal = self.fixture.proposal()
        review = self.fixture.review(proposal)
        path = self.root / (review["decision"]["resultSha256"] + ".json")
        path.unlink()
        with self.assertRaisesRegex(J.ContractError, "missing evidence"):
            R.admit(proposal, review, "row")

    def test_mousecat_pending_rejected_qualified_and_duplicate_results_refuse(self):
        proposal = self.fixture.proposal()
        review = self.fixture.review(proposal)
        original = self.object(review["decision"]["resultSha256"])
        for defect in ("pending", "rejected", "notes", "duplicate", "lineage",
                       "malformed-skill", "non-decision"):
            raw = copy.deepcopy(original)
            if defect == "pending":
                raw["status"] = "pending"
            elif defect == "rejected":
                raw["responses"][0]["value"] = "rejected"
            elif defect == "notes":
                raw["responses"][0]["notes"] = "Only after the wording changes."
            elif defect == "duplicate":
                raw["responses"].append(copy.deepcopy(raw["responses"][0]))
            elif defect == "malformed-skill":
                raw["skillRef"] = []
            elif defect == "non-decision":
                raw["items"][0]["shape"] = "freeform"
            else:
                raw["responses"][0]["lineage"]["evidenceRef"] = "different"
            changed = copy.deepcopy(review)
            changed["decision"]["resultSha256"] = self.fixture.save_evidence(raw)
            with self.subTest(defect=defect), self.assertRaises(J.ContractError):
                R.admit(proposal, self.fixture.reseal(changed), "row")

    def test_legacy_version_one_approval_is_not_upgraded_automatically(self):
        proposal = self.fixture.proposal()
        proposal["schemaVersion"] = 1
        with self.assertRaisesRegex(J.ContractError, "version 2"):
            R.validate_proposal(self.fixture.reseal(proposal))

    def evaluation(self, targets):
        value = {"id": "eval", "reason": "Controlled fixture check",
                 "rowContentSha256s": sorted(row["contentSha256"] for row in targets)}
        return [{"id": value["id"], "reason": value["reason"],
                 "evidenceSha256": self.fixture.save_evidence(value)}]

    def test_variant_of_same_source_cannot_cross_splits(self):
        first = self.fixture.proposal()
        second = copy.deepcopy(first)
        second["proposalId"] = "second-proposal"
        second["labels"]["hardNegatives"] = [{
            "claimRef": second["labels"]["unjudgedClaimRefs"].pop(),
            "reason": "Separately reviewed negative."}]
        second = self.fixture.reseal(second)
        rows = [R.admit(p, self.fixture.review(p), "row-" + str(i))
                for i, p in enumerate((first, second))]
        receipts = self.evaluation(rows)
        with self.assertRaisesRegex(J.ContractError, "shared source"):
            R.compile_snapshot("leak", rows,
                               {"train": ["row-0"], "validation": [], "test": ["row-1"]},
                               [], receipts)
        R.compile_snapshot("together", rows,
                           {"train": ["row-0", "row-1"], "validation": [], "test": []},
                           [], receipts)

    def test_evaluation_evidence_must_exist_and_cover_exact_rows(self):
        row = self.fixture.admitted()
        split = {"train": [row["rowId"]], "validation": [], "test": []}
        wrong = self.evaluation([])
        with self.assertRaisesRegex(J.ContractError, "exact dataset rows"):
            R.compile_snapshot("wrong", [row], split, [], wrong)
        receipts = self.evaluation([row])
        path = self.root / (receipts[0]["evidenceSha256"] + ".json")
        path.unlink()
        with self.assertRaisesRegex(J.ContractError, "missing evidence"):
            R.compile_snapshot("missing", [row], split, [], receipts)

    def test_excluded_row_cannot_also_be_admitted(self):
        row = self.fixture.admitted()
        with self.assertRaisesRegex(J.ContractError, "excluded row is present"):
            R.compile_snapshot("contradiction", [row],
                               {"train": [row["rowId"]], "validation": [], "test": []},
                               [{"id": row["rowId"], "reason": "excluded",
                                 "evidenceSha256": "a" * 64}], self.evaluation([row]))

    def test_label_approval_cannot_promote_training_eligibility(self):
        row = self.fixture.admitted()
        self.assertEqual(row["conditioning"]["status"], "ineligible")
        snapshot = R.compile_snapshot("labels-only", [row],
                                      {"train": [row["rowId"]], "validation": [], "test": []},
                                      [], self.evaluation([row]))
        self.assertEqual(snapshot["conditioning"], row["conditioning"])
        row["conditioning"] = {"status": "eligible", "exclusions": []}
        with self.assertRaisesRegex(J.ContractError, "missing source/task admission"):
            R.validate_target(self.fixture.reseal(row))

    def test_output_cannot_replace_saved_evidence(self):
        proposal = self.fixture.proposal()
        digest = proposal["anchor"]["taskExample"]["rowContentSha256"]
        path = self.root / (digest + ".json")
        before = path.read_bytes()
        with self.assertRaisesRegex(J.ContractError, "stored evidence"):
            R.publish(path, proposal, [], E.Store(self.root))
        self.assertEqual(path.read_bytes(), before)

    def test_atomic_output_does_not_clobber_preexisting_temporary_sibling(self):
        path = self.root / "output.json"
        sibling = self.root / "output.json.tmp"
        sibling.write_bytes(b"independent input")
        R.atomic_json(path, {"result": "new"})
        self.assertEqual(A.read(path), {"result": "new"})
        self.assertEqual(sibling.read_bytes(), b"independent input")
        self.assertEqual(list(self.root.glob("*.tmp")), [sibling])

    def test_failed_atomic_replace_preserves_destination_and_cleans_temporary(self):
        path = self.root / "output.json"
        path.write_bytes(b"original output")
        with patch.object(R.os, "replace", side_effect=OSError("write failure")):
            with self.assertRaisesRegex(OSError, "write failure"):
                R.atomic_json(path, {"result": "new"})
        self.assertEqual(path.read_bytes(), b"original output")
        self.assertEqual(list(self.root.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
