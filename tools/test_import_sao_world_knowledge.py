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

    def test_checked_in_import_and_reference_validate(self):
        receipt = Import.validate_import(self.example)
        self.assertEqual(receipt["source"]["commit"],
                         "739ff0a026c2fc2c9450f71a5169b1e72b302c46")
        claim_out = self.root / "claim.json"
        Example.build(self.example, claim_out)
        first = {
            path.relative_to(self.example).as_posix(): path.read_bytes()
            for path in self.example.rglob("*.json")
        }
        first["claim-out"] = claim_out.read_bytes()
        Example.build(self.example, claim_out)
        Example.validate(self.example, claim_out)
        second = {
            path.relative_to(self.example).as_posix(): path.read_bytes()
            for path in self.example.rglob("*.json")
        }
        second["claim-out"] = claim_out.read_bytes()
        self.assertEqual(first, second)

        view = read(self.example / "reference/knowledge-view.json")
        reference = read(self.example / "reference/knowledge-example.json")
        self.assertIn("person-knowledge-not-reconstructed",
                      view["sourceExclusions"])
        self.assertNotIn("person-knowledge-not-reconstructed",
                         view["conditioning"]["exclusions"])
        self.assertEqual(reference["standing"]["choice"],
                          "excluded-controlled-selection")
        self.assertEqual(reference["standing"]["conditioning"], "ineligible")
        self.assertFalse(reference["operatorDecisionRequired"])

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

    def test_reference_has_no_training_or_runtime_authority(self):
        claim_out = self.root / "claim.json"
        Example.build(self.example, claim_out)
        Example.validate(self.example, claim_out)
        reference_path = self.example / "reference/knowledge-example.json"
        reference = read(reference_path)
        claim = read(claim_out)
        self.assertEqual(reference["standing"]["knowledgeExample"],
                         "reviewed-reference")
        self.assertEqual(reference["choice"]["standing"],
                          "excluded-controlled-selection")
        self.assertEqual(reference["standing"]["conditioning"], "ineligible")
        self.assertEqual(reference["effects"], {
            "trainingRowsCreated": 0,
            "modelWeightsChanged": False,
            "runtimeBehaviorChanged": False,
            "playerVisibleBehaviorChanged": False,
        })
        self.assertNotIn("claim-extraction-not-ratified",
                         reference["standing"]["conditioningExclusions"])
        self.assertEqual(claim["extractionStanding"], "reviewed")
        self.assertEqual(claim["knowledgeExample"]["standing"],
                         "reviewed-reference")

        changed = copy.deepcopy(reference)
        changed["effects"]["runtimeBehaviorChanged"] = True
        write(reference_path, reseal(changed))
        with self.assertRaisesRegex(Join.ContractError,
                                    "generated knowledge reference differs"):
            Example.validate(self.example, claim_out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
