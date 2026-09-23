#!/usr/bin/env python3
"""Controls for independent anchored retriever targets."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cross_module_rows as Join
import decision_authoring as Author
import retriever_targets as Target
import training_evidence as Evidence


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


class RetrieverTargetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.evidence_root = Path(self.temporary.name)
        mock = patch.object(Evidence, "ROOT", self.evidence_root)
        mock.start()
        self.addCleanup(mock.stop)

    def save_evidence(self, value):
        digest = value.get("contentSha256") or Author.digest(value)
        (self.evidence_root / (digest + ".json")).write_text(
            json.dumps(value), encoding="utf-8")
        return digest

    def mousecat(self, subject, status="approved", interaction="skill-row-review",
                 item_id="row-0001"):
        lineage = {"host": "codex", "sessionId": "fixture-only",
                   "evidenceRef": "speakeasy:content-sha256:" + subject}
        return self.save_evidence({
            "schema": "mousecat.skill-invocation/2", "skillRef": "crucible", "action": "await",
            "interactionId": interaction, "status": "answered",
            "items": [{"id": item_id, "shape": "decision", "lineage": lineage}],
            "responses": [{"itemId": item_id, "shape": "decision", "status": "answered", "value": status,
                           "selectedOption": status, "selectedOptions": [status],
                           "lineage": lineage, "notes": None}],
        })

    def catalogue(self) -> dict:
        snapshot = "snapshot/ada/0001"
        return {
            "schema": "sao-claim-catalogue",
            "schemaVersion": 1,
            "snapshotRef": snapshot,
            "personId": "ada",
            "listenerRef": "player",
            "atTick": 432000,
            "conditioning": {"trusted": False},
            "claims": [
                {
                    "ref": f"{snapshot}/claim/0001",
                    "topic": "world",
                    "sourceClaimId": "knox-outage",
                    "fact": {"claimId": "knox-outage", "status": "retained"},
                },
                {
                    "ref": f"{snapshot}/claim/0002",
                    "topic": "person",
                    "fact": {"personId": "dana", "placeId": "house-7"},
                },
                {
                    "ref": f"{snapshot}/claim/0003",
                    "topic": "person",
                    "fact": {"personId": "marcus", "status": "dead"},
                },
            ],
        }

    def anchor(self, catalogue: dict, required: list[str] | None = None) -> dict:
        refs = [row["ref"] for row in catalogue["claims"]]
        anchor = {
            "schema": Target.ANCHOR_SCHEMA,
            "schemaVersion": Target.VERSION,
            "anchorId": "speaker-example-0001/retrieval",
            "task": "speaker",
            "catalogue": {
                "snapshotRef": catalogue["snapshotRef"],
                "contentSha256": Author.digest(catalogue),
            },
            "context": {
                "personId": catalogue["personId"],
                "listenerRef": catalogue.get("listenerRef"),
                "atTick": catalogue["atTick"],
                "utterance": "Why can't we call for help?",
                "situation": {"kind": "conversation", "placeId": "house-7"},
            },
            "taskExample": {
                "datasetSnapshotRef": "speaker-approved/0001",
                "datasetSnapshotSha256": HASH_C,
                "rowId": "speaker-0001",
                "rowContentSha256": HASH_A,
                "approvalReceiptSha256": HASH_B,
                "standing": "approved",
            },
            "requiredClaimRefs": required if required is not None else [refs[0]],
        }
        row = Author.seal({
            "schema": "speakeasy-task-evidence", "schemaVersion": 1,
            "rowId": "speaker-0001", "task": "speaker",
            "input": {"catalogue": catalogue, "context": anchor["context"]},
            "output": {"text": "I remember the outage."},
            "requiredClaimRefs": anchor["requiredClaimRefs"],
        })
        row_hash = self.save_evidence(row)
        decision_hash = self.mousecat(row_hash, interaction="skill-task-review")
        member = {"rowId": row["rowId"], "rowContentSha256": row_hash,
                  "approvalReceiptSha256": decision_hash}
        snapshot = Author.seal({
            "schema": "speakeasy-task-evidence-snapshot", "schemaVersion": 1,
            "snapshotId": "speaker-approved/0001", "task": "speaker", "rows": [member],
        })
        anchor["taskExample"].update(member)
        anchor["taskExample"]["datasetSnapshotSha256"] = self.save_evidence(snapshot)
        return Author.seal(anchor)

    def review(self, proposal: dict, status: str = "approved") -> dict:
        return Author.seal({
            "schema": Target.REVIEW_SCHEMA,
            "schemaVersion": Target.VERSION,
            "proposalId": proposal["proposalId"],
            "proposalContentSha256": proposal["contentSha256"],
            "status": status,
            "reviewedAt": "2026-09-22T06:30:00Z",
            "reviewer": {"kind": "operator", "id": "ellyj3rain"},
            "decision": {
                "interactionId": "skill-row-review",
                "itemId": "row-0001",
                "value": status,
                "resultSha256": self.mousecat(proposal["contentSha256"], status),
            },
        })

    def proposal(self, hard_negatives: list[dict[str, str]] | None = None) -> dict:
        catalogue = self.catalogue()
        return Target.propose(catalogue, self.anchor(catalogue), "proposal-0001",
                              hard_negatives or [])

    def admitted(self) -> dict:
        proposal = self.proposal()
        return Target.admit(proposal, self.review(proposal), "retriever-0001")

    def reseal(self, value: dict) -> dict:
        body = copy.deepcopy(value)
        body.pop("contentSha256", None)
        return Author.seal(body)

    def test_policy_receipt_preserves_the_mousecat_ruling_and_zero_rows(self):
        path = Join.ROOT / "training/retriever/policy.json"
        policy = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(policy["policy"], Target.POLICY)
        self.assertEqual(policy["decision"]["interactionId"],
                         "skill-87fa148534b7e880")
        self.assertEqual(policy["decision"]["itemId"],
                         "seam-e7ecdee5ab14822d")
        self.assertEqual(policy["effects"]["trainingRowsCreated"], 0)
        self.assertFalse(policy["approval"]["taskExampleTransfers"])

    def test_unmentioned_owned_claims_are_the_explicit_unjudged_complement(self):
        proposal = self.proposal()
        refs = [row["ref"] for row in self.catalogue()["claims"]]
        self.assertEqual(proposal["labels"]["requiredClaimRefs"], [refs[0]])
        self.assertEqual(proposal["labels"]["hardNegatives"], [])
        self.assertEqual(proposal["labels"]["unjudgedClaimRefs"], refs[1:])
        Target.validate_proposal(proposal)

    def test_only_explicit_reviewable_claims_become_hard_negatives(self):
        refs = [row["ref"] for row in self.catalogue()["claims"]]
        proposal = self.proposal([{
            "claimRef": refs[2],
            "reason": "The claim concerns another person and cannot answer this question.",
        }])
        self.assertEqual([row["claimRef"] for row in proposal["labels"]["hardNegatives"]],
                         [refs[2]])
        self.assertEqual(proposal["labels"]["unjudgedClaimRefs"], [refs[1]])

    def test_unknown_duplicate_and_required_hard_negatives_refuse(self):
        catalogue = self.catalogue()
        anchor = self.anchor(catalogue)
        required = anchor["requiredClaimRefs"][0]
        cases = [
            ([{"claimRef": "foreign", "reason": "wrong"}], "outside"),
            ([{"claimRef": required, "reason": "wrong"}], "also required"),
            ([{"claimRef": catalogue["claims"][1]["ref"], "reason": "one"},
              {"claimRef": catalogue["claims"][1]["ref"], "reason": "two"}],
             "duplicate"),
        ]
        for negatives, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(Join.ContractError, message):
                    Target.propose(catalogue, anchor, "proposal", negatives)

    def test_required_labels_cannot_drift_from_the_approved_task_anchor(self):
        proposal = self.proposal()
        proposal["labels"]["requiredClaimRefs"] = [
            proposal["input"]["catalogue"]["claims"][1]["ref"]
        ]
        proposal["labels"]["unjudgedClaimRefs"] = [
            proposal["input"]["catalogue"]["claims"][0]["ref"],
            proposal["input"]["catalogue"]["claims"][2]["ref"],
        ]
        proposal = self.reseal(proposal)
        with self.assertRaisesRegex(Join.ContractError, "approved task anchor"):
            Target.validate_proposal(proposal)

    def test_required_and_negative_references_follow_catalogue_order(self):
        catalogue = self.catalogue()
        refs = [row["ref"] for row in catalogue["claims"]]
        reversed_anchor = self.anchor(catalogue, [refs[1], refs[0]])
        with self.assertRaisesRegex(Join.ContractError, "catalogue order"):
            Target.propose(catalogue, reversed_anchor, "proposal", [])
        proposal = Target.propose(
            catalogue, self.anchor(catalogue), "proposal",
            [{"claimRef": refs[2], "reason": "third"},
             {"claimRef": refs[1], "reason": "second"}],
        )
        self.assertEqual([item["claimRef"] for item in proposal["labels"]["hardNegatives"]],
                         refs[1:])

    def test_catalogue_identity_and_c75_order_are_bound(self):
        catalogue = self.catalogue()
        anchor = self.anchor(catalogue)
        catalogue["claims"][0]["ref"] = catalogue["claims"][1]["ref"]
        with self.assertRaisesRegex(Join.ContractError, "C75 order"):
            Target.propose(catalogue, anchor, "proposal", [])

        catalogue = self.catalogue()
        anchor = self.anchor(catalogue)
        catalogue["claims"][0]["fact"]["status"] = "forgotten"
        with self.assertRaisesRegex(Join.ContractError, "catalogue hash"):
            Target.propose(catalogue, anchor, "proposal", [])

    def test_c75_catalogue_without_a_listener_key_remains_valid(self):
        catalogue = self.catalogue()
        catalogue.pop("listenerRef")
        proposal = Target.propose(catalogue, self.anchor(catalogue), "no-listener", [])
        self.assertNotIn("listenerRef", proposal["input"]["catalogue"])
        self.assertIsNone(proposal["input"]["context"]["listenerRef"])

    def test_only_nonempty_string_claim_ids_are_protected_source_ids(self):
        catalogue = self.catalogue()
        catalogue["claims"][1]["fact"]["claimId"] = 7
        proposal = Target.propose(catalogue, self.anchor(catalogue), "numeric-claim-id", [])
        self.assertNotIn("sourceClaimId", proposal["input"]["catalogue"]["claims"][1])

    def test_unknown_c75_topic_refuses(self):
        catalogue = self.catalogue()
        catalogue["claims"][1]["topic"] = "knownPerson"
        with self.assertRaisesRegex(Join.ContractError, "topic is unknown"):
            Target.propose(catalogue, self.anchor(catalogue), "unknown-topic", [])

    def test_boolean_catalogue_version_refuses(self):
        catalogue = self.catalogue()
        anchor = self.anchor(catalogue)
        catalogue["schemaVersion"] = True
        with self.assertRaisesRegex(Join.ContractError, "version 1"):
            Target.propose(catalogue, anchor, "boolean-version", [])

    def test_task_approval_does_not_admit_a_retriever_row(self):
        proposal = self.proposal()
        self.assertTrue((self.evidence_root / (
            proposal["anchor"]["taskExample"]["approvalReceiptSha256"] + ".json")).is_file())
        self.assertEqual(proposal["standing"], "proposed")
        with self.assertRaisesRegex(Join.ContractError, "not approved"):
            Target.admit(proposal, self.review(proposal, "rejected"), "row-0001")

    def test_independent_operator_review_admits_the_exact_proposal(self):
        proposal = self.proposal()
        review = self.review(proposal)
        target = Target.admit(proposal, review, "retriever-0001")
        self.assertEqual(target["standing"], "approved")
        self.assertEqual(target["provenance"]["proposalContentSha256"],
                         proposal["contentSha256"])
        self.assertEqual(target["provenance"]["approvalReceiptSha256"],
                         review["contentSha256"])
        self.assertEqual(target["review"], review)
        Target.validate_target(target)

    def test_review_for_another_proposal_refuses(self):
        proposal = self.proposal()
        review = self.review(proposal)
        review["proposalContentSha256"] = HASH_C
        review = self.reseal(review)
        with self.assertRaisesRegex(Join.ContractError, "proposal hash"):
            Target.admit(proposal, review, "retriever-0001")

    def test_admitted_target_cannot_replace_or_drop_its_review(self):
        target = self.admitted()
        target["review"]["decision"]["interactionId"] = "another-interaction"
        target["review"] = self.reseal(target["review"])
        target = self.reseal(target)
        with self.assertRaisesRegex(Join.ContractError, "Mousecat interaction differs"):
            Target.validate_target(target)

    def test_dataset_snapshot_requires_explicit_complete_splits(self):
        target = self.admitted()
        exclusions = [{
            "id": "candidate-rejected-0001",
            "reason": "Catalogue coverage was incomplete.",
            "evidenceSha256": HASH_A,
        }]
        evaluations = [{
            "id": "retrieval-contract-controls",
            "reason": "The target compiler controls passed.",
            "evidenceSha256": HASH_B,
        }]
        for entry in exclusions + evaluations:
            body = {"id": entry["id"], "reason": entry["reason"]}
            if entry in evaluations:
                body["rowContentSha256s"] = [target["contentSha256"]]
            entry["evidenceSha256"] = self.save_evidence(body)
        snapshot = Target.compile_snapshot(
            "retriever-snapshot-0001", [target],
            {"train": [target["rowId"]], "validation": [], "test": []},
            exclusions, evaluations,
        )
        self.assertEqual(snapshot["counts"], {
            "rows": 1, "requiredPositives": 1, "hardNegatives": 0, "unjudged": 2,
        })
        with self.assertRaisesRegex(Join.ContractError, "cover every row"):
            Target.compile_snapshot(
                "retriever-snapshot-0001", [target],
                {"train": [], "validation": [], "test": []}, exclusions, evaluations)

    def test_snapshot_refuses_unapproved_or_duplicate_rows(self):
        proposal = self.proposal()
        with self.assertRaisesRegex(Join.ContractError, "requires at least one"):
            Target.compile_snapshot(
                "empty", [], {"train": [], "validation": [], "test": []}, [], [])
        target = Target.admit(proposal, self.review(proposal), "same-row")
        with self.assertRaisesRegex(Join.ContractError, "duplicate rowId"):
            Target.compile_snapshot(
                "duplicate", [target, target],
                {"train": ["same-row"], "validation": [], "test": []}, [], [])
        duplicate_proposal = copy.deepcopy(target)
        duplicate_proposal["rowId"] = "another-row"
        duplicate_proposal = self.reseal(duplicate_proposal)
        with self.assertRaisesRegex(Join.ContractError, "same approved proposal"):
            Target.compile_snapshot(
                "duplicate-proposal", [target, duplicate_proposal],
                {"train": ["same-row", "another-row"],
                 "validation": [], "test": []}, [], [])

    def test_cli_writes_atomically_and_refuses_unbound_input(self):
        catalogue = self.catalogue()
        anchor = self.anchor(catalogue)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalogue_path = root / "catalogue.json"
            anchor_path = root / "anchor.json"
            output = root / "proposal.json"
            catalogue_path.write_text(json.dumps(catalogue), encoding="utf-8")
            anchor_path.write_text(json.dumps(anchor), encoding="utf-8")
            self.assertEqual(Target.cli([
                "propose", "--catalogue", str(catalogue_path),
                "--anchor", str(anchor_path), "--proposal-id", "cli-proposal",
                "--out", str(output),
            ]), 0)
            self.assertEqual(Author.read(output)["standing"], "proposed")
            self.assertFalse(output.with_name(output.name + ".tmp").exists())
            original = catalogue_path.read_bytes()
            self.assertEqual(Target.cli([
                "propose", "--catalogue", str(catalogue_path),
                "--anchor", str(anchor_path), "--proposal-id", "overwrite",
                "--out", str(catalogue_path),
            ]), 1)
            self.assertEqual(catalogue_path.read_bytes(), original)

    def test_policy_receipt_cannot_be_an_output(self):
        catalogue = self.catalogue()
        anchor = self.anchor(catalogue)
        before = Target.POLICY_RECEIPT.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalogue_path = root / "catalogue.json"
            anchor_path = root / "anchor.json"
            catalogue_path.write_text(json.dumps(catalogue), encoding="utf-8")
            anchor_path.write_text(json.dumps(anchor), encoding="utf-8")
            self.assertEqual(Target.cli([
                "propose", "--catalogue", str(catalogue_path),
                "--anchor", str(anchor_path), "--proposal-id", "protected",
                "--out", str(Target.POLICY_RECEIPT),
            ]), 1)
        self.assertEqual(Target.POLICY_RECEIPT.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
