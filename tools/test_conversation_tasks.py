"""Controls for exact C77 import, typed meaning and independent review binding."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import conversation_tasks as C
import cross_module_rows as J
import decision_authoring as A
import retriever_targets as R
import training_evidence as E
import test_retriever_targets as F


def reseal(value):
    value = copy.deepcopy(value)
    value.pop("contentSha256", None)
    return A.seal(value)


class ConversationTests(unittest.TestCase):
    def setUp(self):
        index = A.read(C.ROOT / "training/understander/c77-example.json")
        self.imported = E.Store().read(index["sourceImportSha256"])
        self.row = E.Store().read(index["taskSha256"])
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = E.Store(self.root)
        C.save_evidence(self.imported, self.root)
        C.save_evidence(self.row, self.root)

    def test_exact_capture_and_typed_roles(self):
        self.assertEqual(len(C.validate_capture(self.imported["capture"], self.imported["manifest"])), 8)
        self.assertEqual(C.validate_task(self.row, self.store)["output"]["listenerRef"], "sao-1")
        self.assertEqual(self.row["input"]["context"]["listenerRef"], "sao-2")
        self.assertEqual(C.task_conditioning(self.row, self.store)["status"], "ineligible")

    def test_resealed_import_cannot_rewrite_reviewed_capture(self):
        for part, key, change in (("context", "utterance", "Are phones working today?"),
                                  ("namespace", "personId", "sao-2"),
                                  ("calendar", "atHour", 72),
                                  ("coverage", "status", "failed"),
                                  ("coverage", "unavailableInputs", [])):
            value = copy.deepcopy(self.imported)
            value["capture"][part][key] = change
            value["manifest"]["captureSha256"] = A.digest(value["capture"])
            value["manifest"] = reseal(value["manifest"])
            with self.subTest(part=part, key=key), self.assertRaisesRegex(J.ContractError, "reviewed capture"):
                C.validate_import(reseal(value))

    def test_resealed_producer_hash_and_unknown_source_refuse(self):
        value = copy.deepcopy(self.imported)
        key = next(iter(value["manifest"]["sources"]))
        value["manifest"]["sources"][key] = "a" * 64
        value["manifest"] = reseal(value["manifest"])
        with self.assertRaisesRegex(J.ContractError, "reviewed capture"):
            C.validate_import(reseal(value))
        value = copy.deepcopy(self.imported)
        value["sourceId"] = "unreviewed-source"
        with self.assertRaisesRegex(J.ContractError, "not reviewed"):
            C.validate_import(reseal(value))

    def test_import_reads_every_source_and_refuses_changed_bytes(self):
        profile = self.imported["source"]
        manifest = self.imported["manifest"]
        sources = manifest["sources"]
        def committed(root, commit, path):
            self.assertEqual(commit, profile["commit"])
            if path.endswith("/capture.json"):
                return A.encoded(self.imported["capture"])
            if path.endswith("/manifest.json"):
                return A.encoded(manifest)
            return path.encode()
        # Each real digest is checked; substitute only the external byte readers.
        class Digest:
            def __init__(self, data): self.data = data
            def hexdigest(self): return sources[self.data.decode()]
        original = C.hashlib.sha256
        def digest(data=b""):
            return Digest(data) if data.decode(errors="ignore") in sources else original(data)
        installed = {k:k for k in sources if k.startswith("installed/")}
        original_file = C.file_hash
        def file_hash(path):
            return sources[str(path)] if str(path) in installed else original_file(path)
        with patch.object(C, "git_bytes", side_effect=committed) as git, \
             patch.object(C, "file_hash", side_effect=file_hash), \
             patch.object(C.hashlib, "sha256", side_effect=digest):
            C.import_capture("unused", profile["id"], installed)
            self.assertEqual(git.call_count, 2 + len(sources) - len(installed))
        with patch.object(C, "git_bytes", side_effect=committed), \
             patch.object(C, "file_hash", return_value="0"*64):
            with self.assertRaisesRegex(J.ContractError, "producer source hash differs"):
                C.import_capture("unused", profile["id"], installed)

    def test_missing_receipt_legacy_owner_and_wrong_publication_refuse(self):
        for defect in ("receipt", "legacy", "publication", "retention", "source", "event-kind", "media", "item", "position"):
            capture = copy.deepcopy(self.imported["capture"])
            world = capture["sourceState"]["person"]["worldKnowledge"]
            if defect == "receipt": world["readReceipts"] = {}
            elif defect == "legacy": world["schemaVersion"] = 1
            elif defect == "publication": world["acquisitions"][0]["sourceEvent"]["atHours"] = 24
            elif defect == "retention": capture["sourceState"]["worldRetention"][0]["retained"] = False
            elif defect == "source": world["acquisitions"][0]["source"]["sha256"] = "0"*64
            elif defect == "event-kind": world["acquisitions"][0]["sourceEvent"]["kind"] = "county-lived-day"
            elif defect == "position": capture["context"]["situation"]["personPosition"]["x"] = -1
            else:
                receipt = next(iter(world["readReceipts"].values()))
                receipt["mediaId" if defect == "media" else "itemType"] = "unrelated"
            owners = A.loads(capture["sourceState"]["ownerStateBytes"])
            owners["durable"]["SurvivorAwareness_Records"]["records"]["sao-1"] = capture["sourceState"]["person"]
            capture["sourceState"]["ownerStateBytes"] = A.encoded(owners).decode()
            manifest = copy.deepcopy(self.imported["manifest"])
            manifest["captureSha256"] = A.digest(capture)
            with self.subTest(defect=defect), self.assertRaises(J.ContractError):
                C.validate_capture(capture, reseal(manifest))

    def test_typed_frame_rejects_foreign_duplicate_actions_and_extra_output(self):
        changes = {"claimRefs": ["unknown"], "requestedAction": "repair-phone",
                   "listenerRef": "sao-2", "uncertainty": True,
                   "speechAct": "magic", "extra": "phones work now",
                   "stance": {"label":"neutral","targetRef":"sao-2"}}
        for key, value in changes.items():
            row = copy.deepcopy(self.row)
            row["output"][key] = value
            with self.subTest(key=key), self.assertRaises(J.ContractError):
                C.validate_task(reseal(row), self.store)
        row = copy.deepcopy(self.row)
        row["output"]["claimRefs"] *= 2
        with self.assertRaisesRegex(J.ContractError, "duplicate"):
            C.validate_task(reseal(row), self.store)

    def test_task_cannot_change_context_roles_or_required_refs_after_resealing(self):
        for defect in ("context", "roles", "refs", "import"):
            row = copy.deepcopy(self.row)
            if defect == "context": row["input"]["context"]["utterance"] = "Where is Jon?"
            elif defect == "roles": row["input"]["utteranceRoles"]["listenerRef"] = "sao-2"
            elif defect == "refs": row["requiredClaimRefs"] = []
            else: row["input"]["sourceImportSha256"] = "f" * 64
            with self.subTest(defect=defect), self.assertRaises(J.ContractError):
                C.validate_task(reseal(row), self.store)

    def fixture_review(self, subject):
        fixture = F.RetrieverTargetTests()
        fixture.evidence_root = self.root
        return fixture.mousecat(subject, interaction="test-only-review")

    def anchor(self):
        approval = self.fixture_review(self.row["contentSha256"])
        snapshot = C.approve(self.row, approval, "test-only-snapshot", self.store)
        C.save_evidence(snapshot, self.root)
        catalogue = self.row["input"]["catalogue"]
        return A.seal({"schema":R.ANCHOR_SCHEMA,"schemaVersion":2,"anchorId":"test-anchor",
            "task":"understander", "catalogue":{"snapshotRef":catalogue["snapshotRef"],
            "contentSha256":A.digest(catalogue)}, "context":self.row["input"]["context"],
            "taskExample":{"datasetSnapshotRef":snapshot["snapshotId"],
            "datasetSnapshotSha256":snapshot["contentSha256"], **snapshot["rows"][0],"standing":"approved"},
            "requiredClaimRefs":self.row["requiredClaimRefs"]})

    def test_typed_task_resolves_through_existing_retriever(self):
        anchor = self.anchor()
        catalogue = self.row["input"]["catalogue"]
        proposal = R.propose(catalogue, anchor, "test-retriever", [], self.store)
        self.assertEqual(len(proposal["labels"]["unjudgedClaimRefs"]), 7)
        self.assertEqual(proposal["labels"]["hardNegatives"], [])
        self.assertEqual(R.task_conditioning(anchor, catalogue, self.store), C.task_conditioning(self.row,self.store))
        with self.assertRaisesRegex(J.ContractError,"exact subject"):
            self.store.decision(anchor["taskExample"]["approvalReceiptSha256"],proposal["contentSha256"])

    def test_pending_qualified_and_stale_task_approval_refuse(self):
        receipt = self.store.read(self.fixture_review(self.row["contentSha256"]))
        for defect in ("pending", "qualified", "subject"):
            value = copy.deepcopy(receipt)
            if defect == "pending": value["status"] = "pending"
            elif defect == "qualified": value["responses"][0]["notes"] = "change listener"
            else: value["items"][0]["lineage"]["evidenceRef"] += "stale"
            digest = C.save_evidence(value, self.root)
            with self.subTest(defect=defect), self.assertRaises(J.ContractError):
                C.approve(self.row, digest, "test-only", self.store)

    def test_atomic_immutable_evidence_and_protected_registry(self):
        value = {"new":"evidence"}
        with patch.object(C.os,"link",side_effect=OSError("controlled failure")):
            with self.assertRaises(OSError): C.save_evidence(value,self.root)
        self.assertFalse((self.root/(A.digest(value)+".json")).exists())
        self.assertEqual(list(self.root.glob("*.tmp")),[])
        with self.assertRaisesRegex(J.ContractError,"protected"):
            R.publish(C.REGISTRY, value, [], self.store)

    def test_bad_seal_cannot_occupy_valid_evidence_address(self):
        root = self.root / "new-store"
        value = copy.deepcopy(self.imported)
        value["verification"]["repositorySources"] = "forged"
        with self.assertRaisesRegex(J.ContractError, "content hash differs"):
            C.save_evidence(value, root)
        self.assertFalse(root.exists())
        digest = C.save_evidence(self.imported, root)
        self.assertEqual(E.Store(root).read(digest), self.imported)


if __name__ == "__main__":
    unittest.main()
