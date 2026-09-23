#!/usr/bin/env python3
"""Mutation controls for Record 52's imported C74 evidence and reference."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import cross_module_rows as Join
import decision_authoring as Author
import import_sao_world_knowledge as Import
import r12_acquisition_example as Example


SOURCE = Join.ROOT / "decisions/examples/r12-knox-lived-source"


def read(path: Path):
    return Author.read(path)


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                               sort_keys=True) + "\n", encoding="utf-8")


def reseal(value: dict) -> dict:
    body = copy.deepcopy(value)
    body.pop("contentSha256", None)
    return Author.seal(body)


class ImportedEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix=".record52-test-", dir=Join.ROOT)
        self.root = Path(self.temporary.name)
        self.example = self.root / "example"
        shutil.copytree(SOURCE, self.example)

    def tearDown(self):
        self.temporary.cleanup()

    def refresh_envelopes(self) -> None:
        upstream = self.example / "upstream"
        manifest_path = upstream / "manifest.json"
        manifest = read(manifest_path)
        manifest["files"] = {
            name: hashlib.sha256((upstream / name).read_bytes()).hexdigest()
            for name in Import.FILES[:2]
        }
        write(manifest_path, reseal(manifest))

        receipt_path = self.example / "import.json"
        receipt = read(receipt_path)
        receipt["files"] = {
            name: hashlib.sha256((upstream / name).read_bytes()).hexdigest()
            for name in Import.FILES
        }
        receipt["source"]["manifestSha256"] = receipt["files"]["manifest.json"]
        receipt["source"]["manifestContentSha256"] = read(
            manifest_path)["contentSha256"]
        write(receipt_path, reseal(receipt))

    @staticmethod
    def refresh_record_hashes(evidence: dict) -> None:
        records = {
            evidence["calendar"]["recordId"]: evidence["calendar"],
            evidence["presence"]["recordId"]: evidence["presence"],
            evidence["acquisition"]["recordId"]: evidence["acquisition"],
            evidence["retentionObservation"]["recordId"]:
                evidence["retentionObservation"],
        }
        evidence["recordHashes"] = [
            {"recordId": row["recordId"], "sha256": Author.digest(row)}
            for row in records.values()
        ]

    def synchronize_acquisition(self, mutation) -> None:
        upstream = self.example / "upstream"
        evidence_path = upstream / "world-knowledge-evidence.json"
        capture_path = upstream / "decision-capture.json"
        evidence, capture = read(evidence_path), read(capture_path)
        mutation(evidence["acquisition"])
        evidence["retentionObservation"]["acquisition"] = copy.deepcopy(
            evidence["acquisition"])
        for name in ("acquiredHour", "claimId", "path", "personId", "retained"):
            if name in evidence["retentionObservation"]:
                evidence["retentionObservation"][name] = evidence["acquisition"][name]
        event = capture["events"][0]
        event["decision"]["person"]["record"]["worldKnowledge"][
            "acquisitions"] = [copy.deepcopy(evidence["acquisition"])]
        evidence["eventSha256"] = Author.digest(event)
        self.refresh_record_hashes(evidence)
        write(evidence_path, evidence)
        write(capture_path, capture)
        self.refresh_envelopes()

    def test_historical_import_integrity_survives_current_correction(self):
        receipt=Import.validate_import(self.example)
        self.assertEqual(receipt["source"]["commit"],"739ff0a026c2fc2c9450f71a5169b1e72b302c46")
        before={p.relative_to(self.example):p.read_bytes() for p in self.example.rglob("*") if p.is_file()}
        output=self.root/"claim.json"
        for operation in (Example.build,Example.validate):
            with self.assertRaisesRegex(Join.ContractError,"superseded"):
                operation(self.example,output)
        self.assertFalse(output.exists())
        self.assertEqual(before,{p.relative_to(self.example):p.read_bytes() for p in self.example.rglob("*") if p.is_file()})

    def current_view(self):
        return Author.compile_view(self.example/"upstream/decision-capture.json",
            self.example/"knowledge-input.json",list((self.example/"reviews").glob("*.json")))

    def test_old_sealed_review_cannot_restore_current_admission(self):
        view=self.current_view()
        self.assertFalse(view["availableClaims"])
        self.assertEqual(view["excludedClaims"][0]["reason"],"record-55:county-presence-does-not-prove-acquisition")

    def test_resealed_person_or_time_changes_cannot_restore_rejected_basis(self):
        bundle=read(self.example/"knowledge-input.json")
        for field,value in (("acquiredHour",0),("asOfHour",49)):
            changed=copy.deepcopy(bundle)
            changed["acquisitions"][0][field]=value
            write(self.example/"knowledge-input.json",changed)
            self.assertFalse(self.current_view()["availableClaims"])
        row=bundle["acquisitions"][0]
        with self.assertRaisesRegex(Join.ContractError,"superseded"):
            Author.acquisition_review(read(self.example/"reviews/acquisition-adjudication.json"),
                row,bundle["claims"][0],bundle["namespace"],bundle["eventSha256"])

    def test_relabelled_and_resealed_legacy_evidence_stays_excluded(self):
        original=read(self.example/"knowledge-input.json")
        old_claim_review=read(self.example/"reviews/claim-extraction.json")
        old_acquisition_review=read(self.example/"reviews/acquisition-adjudication.json")
        for mode in ("read", "new-id"):
            bundle=copy.deepcopy(original)
            claim,row=bundle["claims"][0],bundle["acquisitions"][0]
            cr,ar=copy.deepcopy(old_claim_review),copy.deepcopy(old_acquisition_review)
            if mode=="read":
                row["path"]="read"
                claim["acquisitionRules"]=["read"]
                cr["review"]["acquisitionRules"]=["read"]
            else:
                claim["id"]=row["claimId"]="renamed-outage"
            row["claimSha256"]=Author.digest(claim)
            for review in (cr,ar):
                review["claimId"]=claim["id"]
                review["claimSha256"]=Author.digest(claim)
            ar["acquisitionSha256"]=Author.digest(row)
            write(self.example/"knowledge-input.json",bundle)
            write(self.example/"reviews/claim-extraction.json",reseal(cr))
            write(self.example/"reviews/acquisition-adjudication.json",reseal(ar))
            self.assertFalse(self.current_view()["availableClaims"])

    def test_fresh_read_evidence_is_not_revoked_or_implicitly_approved(self):
        bundle=read(self.example/"knowledge-input.json")
        row=bundle["acquisitions"][0]
        row["path"]="read"
        bundle["claims"][0]["acquisitionRules"]=["read"]
        row["claimSha256"]=Author.digest(bundle["claims"][0])
        for evidence in [row["evidence"]]+[c["evidence"] for c in row["checks"].values()]:
            for ref in evidence:
                ref.update(owner="controlled-new-read",recordId="new-read",sha256="a"*64)
        write(self.example/"knowledge-input.json",bundle)
        cr=read(self.example/"reviews/claim-extraction.json")
        cr["claimSha256"]=Author.digest(bundle["claims"][0])
        cr["review"]["acquisitionRules"]=["read"]
        write(self.example/"reviews/claim-extraction.json",reseal(cr))
        view=Author.compile_view(self.example/"upstream/decision-capture.json",
            self.example/"knowledge-input.json",[self.example/"reviews/claim-extraction.json"])
        self.assertEqual(len(view["availableClaims"]),1)
        self.assertEqual(view["availableClaims"][0]["acquisitionStanding"],"unadjudicated")
        self.assertEqual(view["conditioning"]["status"],"ineligible")

    def test_imported_file_bytes_are_bound(self):
        path = self.example / "upstream/decision-capture.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(Join.ContractError,
                                    "imported SAO file hash differs"):
            Import.validate_import(self.example)

    def test_event_content_hash_is_recomputed(self):
        path = self.example / "upstream/decision-capture.json"
        capture = read(path)
        capture["events"][0]["decision"]["person"]["traits"]["patience"] = 0.6
        write(path, capture)
        self.refresh_envelopes()
        with self.assertRaisesRegex(Join.ContractError,
                                    "evidence event hash differs"):
            Import.validate_import(self.example)

    def test_exact_lived_acquisition_cannot_be_relabelled(self):
        self.synchronize_acquisition(lambda row: row.__setitem__("path", "heard"))
        with self.assertRaisesRegex(Join.ContractError,
                                    "acquisition identity differs"):
            Import.validate_import(self.example)

    def test_presence_and_acquisition_must_remain_bound(self):
        self.synchronize_acquisition(
            lambda row: row.__setitem__("presenceRecordId", "other-presence"))
        with self.assertRaisesRegex(Join.ContractError,
                                    "presence/acquisition binding differs"):
            Import.validate_import(self.example)

    def test_protected_source_excerpt_cannot_be_resealed_away(self):
        def mutate(row):
            row["source"]["excerptSha256"] = "0" * 64

        self.synchronize_acquisition(mutate)
        with self.assertRaisesRegex(Join.ContractError,
                                    "excerpt hash differs from protected bytes"):
            Import.validate_import(self.example)

    def test_version_normalization_exception_is_exact(self):
        path = self.example / "import.json"
        receipt = read(path)
        receipt["sourceNormalizations"] = []
        write(path, reseal(receipt))
        with self.assertRaisesRegex(Join.ContractError,
                                    "source normalization differs"):
            Import.validate_import(self.example)



if __name__ == "__main__":
    unittest.main(verbosity=2)
