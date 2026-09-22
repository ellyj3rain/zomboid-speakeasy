#!/usr/bin/env python3
"""Build and verify Record 52's reviewed person-knowledge reference."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

import cross_module_rows as Join
import decision_authoring as Author
import import_sao_world_knowledge as Import


VERSION = 1
CLAIM_ID = "knox-telecommunications-outage-1993-07-02"
CLAIM_TEXT = (
    "Knox Telecommunications' telephone and Internet networks failed across "
    "the Knox area for hours"
)
SOURCE_PATH = "world/us-1993/knox-event.md"
SOURCE_LINE = 71
RULE_SOURCE_PATH = "world/us-1993/who-knows-what.md"
SELECTED_OPTION = "C:second:0"
REFERENCE_SCHEMA = "speakeasy-person-knowledge-reference"
OBSOLETE_OPERATOR_ARTIFACTS = (
    "candidate/choice-request.json",
    "candidate/choice-proposal.json",
    "candidate/ratification-candidate.json",
    "decision/operator-decision.json",
    "decision/ratification.json",
    "admitted/knowledge-example.json",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Join.ContractError(message)


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                    sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(Join.ROOT.resolve()).as_posix()
    except ValueError as error:
        raise Join.ContractError(f"Record 52 artifact is outside repository: {path}") from error


def artifact_binding(path: Path, value: dict[str, Any]) -> dict[str, str]:
    return {
        "path": relative(path),
        "sha256": Join.sha256(path),
        "contentSha256": value["contentSha256"],
    }


def record_hashes(evidence: dict[str, Any]) -> dict[str, str]:
    result = {}
    for row in evidence["recordHashes"]:
        result[row["recordId"]] = row["sha256"]
    return result


def evidence_reference(owner: str, record_id: str,
                       hashes: dict[str, str]) -> dict[str, str]:
    require(record_id in hashes, f"missing imported record hash: {record_id}")
    return {"owner": owner, "recordId": record_id, "sha256": hashes[record_id]}


def claim() -> dict[str, Any]:
    path = Join.ROOT / SOURCE_PATH
    lines = path.read_text(encoding="utf-8").splitlines()
    require(len(lines) >= SOURCE_LINE and CLAIM_TEXT in lines[SOURCE_LINE - 1],
            "protected Knox extraction boundary is absent")
    return {
        "id": CLAIM_ID,
        "text": CLAIM_TEXT,
        "confidence": "HIGH",
        "knowableAt": "1993-07-02T00:00:00",
        "carrier": "county",
        "acquisitionRules": ["lived"],
        "source": {
            "path": SOURCE_PATH,
            "sha256": Join.sha256(path),
            "line": SOURCE_LINE,
            "excerptSha256": hashlib.sha256(
                lines[SOURCE_LINE - 1].encode("utf-8")).hexdigest(),
        },
    }


def rule_source(role: str, start_line: int, end_line: int) -> dict[str, Any]:
    path = Join.ROOT / RULE_SOURCE_PATH
    lines = path.read_text(encoding="utf-8").splitlines()
    require(1 <= start_line <= end_line <= len(lines),
            "protected knowledge-rule excerpt is absent")
    excerpt = "\n".join(lines[start_line - 1:end_line])
    return {
        "role": role,
        "path": RULE_SOURCE_PATH,
        "sha256": Join.sha256(path),
        "startLine": start_line,
        "endLine": end_line,
        "excerptSha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
    }


def inputs(example_dir: Path) -> tuple[dict[str, Any], dict[str, Any],
                                       dict[str, Any], dict[str, Any]]:
    import_receipt = Import.validate_import(example_dir)
    upstream = example_dir / "upstream"
    capture = Author.read(upstream / "decision-capture.json")
    evidence = Author.read(upstream / "world-knowledge-evidence.json")
    event = capture["events"][0]
    return import_receipt, capture, evidence, event


def knowledge_input(evidence: dict[str, Any], event: dict[str, Any],
                    selected_claim: dict[str, Any]) -> dict[str, Any]:
    hashes = record_hashes(evidence)
    acquisition = evidence["acquisition"]
    observation = evidence["retentionObservation"]
    presence = evidence["presence"]
    owner = "Survivor Awareness C74"
    acquisition_ref = evidence_reference(owner, acquisition["recordId"], hashes)
    presence_ref = evidence_reference(owner, presence["recordId"], hashes)
    retention_ref = evidence_reference(owner, observation["recordId"], hashes)
    transformed = {
        "claimId": selected_claim["id"],
        "claimSha256": Author.digest(selected_claim),
        "namespace": copy.deepcopy(evidence["namespace"]),
        "acquiredHour": acquisition["acquiredHour"],
        "asOfHour": observation["asOfHour"],
        "path": acquisition["path"],
        "retained": observation["retained"],
        "checks": {
            "age": {"status": "supported", "evidence": [acquisition_ref]},
            "carrier": {"status": "supported", "evidence": [presence_ref]},
            "access": {"status": "supported", "evidence": [presence_ref]},
            "retention": {"status": "supported",
                          "evidence": [acquisition_ref, retention_ref]},
        },
        "evidence": [acquisition_ref, presence_ref, retention_ref],
    }
    calendar = evidence["calendar"]
    result = {
        "schema": "speakeasy-knowledge-input",
        "schemaVersion": VERSION,
        "namespace": copy.deepcopy(evidence["namespace"]),
        "eventSha256": Author.digest(event),
        "calendar": {
            "anchorHour": calendar["anchorHour"],
            "anchorAt": calendar["anchorAt"],
            "horizonHour": calendar["horizonHour"],
            "evidence": evidence_reference(owner, calendar["recordId"], hashes),
        },
        "claims": [selected_claim],
        "acquisitions": [transformed],
    }
    require(result["namespace"] == {
        "runId": event["runId"], "county": event["county"],
        "personId": event["decision"]["person"]["id"],
        "eventId": event["eventId"], "hour": event["decision"]["hours"],
    }, "knowledge input namespace differs from imported event")
    return result


def claim_review(selected_claim: dict[str, Any], procedure_hash: str) -> dict[str, Any]:
    return Author.seal({
        "schema": Author.CLAIM_REVIEW_SCHEMA,
        "schemaVersion": VERSION,
        "claimId": selected_claim["id"],
        "claimSha256": Author.digest(selected_claim),
        "source": copy.deepcopy(selected_claim["source"]),
        "ruleSources": [
            rule_source("adult-detail", 107, 107),
            rule_source("lived-local-claim-path", 122, 123),
        ],
        "review": {
            "status": "reviewed",
            "textBoundary": "literal-substring",
            "knowableAt": selected_claim["knowableAt"],
            "carrier": selected_claim["carrier"],
            "acquisitionRules": selected_claim["acquisitionRules"],
            "confidence": {
                "value": "HIGH",
                "basis": "approved-direct-game-record",
                "sourceLineHasLiteralConfidence": False,
            },
        },
        "reviewer": {
            "kind": "repository-review",
            "id": "record-52-extraction-review",
            "procedureSha256": procedure_hash,
        },
        "findings": [
            "The selected provider and area-wide outage text is literal and excludes the line's consequences and cause speculation.",
            "The row supplies the July 2 date and county carrier; the approved scoping index supplies the lived path.",
            "The source table has no literal confidence field; HIGH is separately assessed from the approved direct game record.",
        ],
    })


def acquisition_adjudication(selected_claim: dict[str, Any], bundle: dict[str, Any],
                             event: dict[str, Any], import_receipt_path: Path,
                             procedure_hash: str) -> dict[str, Any]:
    record = bundle["acquisitions"][0]
    return Author.seal({
        "schema": Author.ACQUISITION_REVIEW_SCHEMA,
        "schemaVersion": VERSION,
        "claimId": selected_claim["id"],
        "claimSha256": Author.digest(selected_claim),
        "acquisitionSha256": Author.digest(record),
        "namespace": copy.deepcopy(bundle["namespace"]),
        "eventSha256": Author.digest(event),
        "importEvidence": {
            "owner": "Zomboid-Speakeasy SAO importer",
            "recordId": "r12-knox-lived-source/import",
            "sha256": Join.sha256(import_receipt_path),
        },
        "checks": copy.deepcopy(record["checks"]),
        "status": "adjudicated",
        "reviewer": {
            "kind": "repository-review",
            "id": "record-52-acquisition-adjudication",
            "procedureSha256": procedure_hash,
        },
        "limitations": [
            "The evidence supports this one frozen person and event; it is not a sampled natural county.",
            "Installed Kahlua and production action modules were used, but no save was loaded.",
            "The outage claim is contextual at the food-source decision and is not evidence that it caused the selection.",
        ],
    })


def reference_example(selected_claim: dict[str, Any], bundle: dict[str, Any],
                      import_receipt: dict[str, Any], review: dict[str, Any],
                      adjudication: dict[str, Any], view: dict[str, Any],
                      event: dict[str, Any]) -> dict[str, Any]:
    acquisition = bundle["acquisitions"][0]
    person = event["decision"]["person"]
    require(event["choice"]["optionId"] == SELECTED_OPTION,
            "controlled selected option differs")
    return Author.seal({
        "schema": REFERENCE_SCHEMA,
        "schemaVersion": VERSION,
        "scope": "claim-and-person-acquisition",
        "systemRole": {
            "stage": "person-claim-catalogue",
            "currentUse": "compiler-and-producer-reference",
            "downstreamUses": [
                "retriever-input-catalogue",
                "speaker-claim-fence",
                "understander-claim-reference-validation",
            ],
        },
        "effects": {
            "trainingRowsCreated": 0,
            "modelWeightsChanged": False,
            "runtimeBehaviorChanged": False,
            "playerVisibleBehaviorChanged": False,
        },
        "claim": {
            "id": selected_claim["id"],
            "sha256": Author.digest(selected_claim),
            "text": selected_claim["text"],
            "knowableAt": selected_claim["knowableAt"],
            "carrier": selected_claim["carrier"],
            "path": acquisition["path"],
        },
        "personEvent": {
            "person": {
                "id": person["id"],
                "name": person["name"],
                "age": person["age"],
            },
            "namespace": copy.deepcopy(bundle["namespace"]),
            "acquisitionSha256": Author.digest(acquisition),
            "acquiredHour": acquisition["acquiredHour"],
            "asOfHour": acquisition["asOfHour"],
        },
        "evidence": {
            "importReceiptSha256": import_receipt["contentSha256"],
            "claimReviewSha256": review["contentSha256"],
            "acquisitionAdjudicationSha256": adjudication["contentSha256"],
            "knowledgeViewSha256": view["contentSha256"],
        },
        "standing": {
            "claimExtraction": "reviewed",
            "acquisition": "adjudicated",
            "knowledgeExample": "reviewed-reference",
            "choice": "excluded-controlled-selection",
            "conditioning": "ineligible",
            "conditioningExclusions": sorted(set(
                view["conditioning"]["exclusions"]
                + ["controlled-choice-selection"])),
        },
        "choice": {
            "observedOptionId": event["choice"]["optionId"],
            "standing": "excluded-controlled-selection",
            "reason": (
                "C74 forced the second source to exercise the same-person join; "
                "the outage claim neither caused nor justified that selection."
            ),
        },
        "operatorDecisionRequired": False,
    })


def claim_example(selected_claim: dict[str, Any], example_dir: Path,
                  review: dict[str, Any], adjudication: dict[str, Any],
                  reference_path: Path, reference: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "speakeasy-claim-extraction-example",
        "schemaVersion": 2,
        "claim": selected_claim,
        "extractionStanding": "reviewed",
        "reviewReceipt": {
            "path": (example_dir / "reviews/claim-extraction.json").relative_to(
                Join.ROOT).as_posix(),
            "sha256": review["contentSha256"],
        },
        "acquisition": {
            "status": "adjudicated",
            "receipt": {
                "path": (example_dir / "reviews/acquisition-adjudication.json")
                .relative_to(Join.ROOT).as_posix(),
                "sha256": adjudication["contentSha256"],
            },
        },
        "knowledgeExample": {
            "standing": "reviewed-reference",
            "reference": artifact_binding(reference_path, reference),
        },
        "choiceStanding": "excluded-controlled-selection",
        "conditioning": {
            "status": "ineligible",
            "exclusions": [
                "controlled-choice-selection",
                "knowledge-coverage-not-established",
                "later-consequences-not-observed",
                "runtime-choice-not-ratified",
            ],
        },
    }


def build_values(example_dir: Path) -> dict[str, Any]:
    import_receipt, capture, evidence, event = inputs(example_dir)
    selected_claim = claim()
    procedure = example_dir / "review-procedure.md"
    procedure_hash = Join.sha256(procedure)
    bundle = knowledge_input(evidence, event, selected_claim)
    review = claim_review(selected_claim, procedure_hash)
    adjudication = acquisition_adjudication(
        selected_claim, bundle, event, example_dir / "import.json", procedure_hash)
    return {
        "importReceipt": import_receipt,
        "capture": capture,
        "event": event,
        "claim": selected_claim,
        "bundle": bundle,
        "review": review,
        "adjudication": adjudication,
        "procedureHash": procedure_hash,
    }


def build(example_dir: Path, claim_out: Path) -> None:
    for relative_path in OBSOLETE_OPERATOR_ARTIFACTS:
        require(not (example_dir / relative_path).exists(),
                f"obsolete operator artifact remains: {relative_path}")
    values = build_values(example_dir)
    review_path = example_dir / "reviews/claim-extraction.json"
    adjudication_path = example_dir / "reviews/acquisition-adjudication.json"
    knowledge_path = example_dir / "knowledge-input.json"
    atomic_json(knowledge_path, values["bundle"])
    atomic_json(review_path, values["review"])
    atomic_json(adjudication_path, values["adjudication"])
    receipt_paths = [review_path, adjudication_path]
    capture_path = example_dir / "upstream/decision-capture.json"
    view = Author.compile_view(capture_path, knowledge_path, receipt_paths)
    view_path = example_dir / "reference/knowledge-view.json"
    atomic_json(view_path, view)
    reference = reference_example(
        values["claim"], values["bundle"], values["importReceipt"],
        values["review"], values["adjudication"], view, values["event"])
    reference_path = example_dir / "reference/knowledge-example.json"
    atomic_json(reference_path, reference)
    atomic_json(claim_out, claim_example(values["claim"], example_dir,
                                         values["review"], values["adjudication"],
                                         reference_path, reference))


def validate_reference(example_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    for relative_path in OBSOLETE_OPERATOR_ARTIFACTS:
        require(not (example_dir / relative_path).exists(),
                f"obsolete operator artifact remains: {relative_path}")
    values = build_values(example_dir)
    expected = {
        "knowledge-input.json": values["bundle"],
        "reviews/claim-extraction.json": values["review"],
        "reviews/acquisition-adjudication.json": values["adjudication"],
    }
    for relative, value in expected.items():
        require(Author.read(example_dir / relative) == value,
                f"generated example differs: {relative}")
    receipt_paths = [example_dir / "reviews/claim-extraction.json",
                     example_dir / "reviews/acquisition-adjudication.json"]
    capture_path = example_dir / "upstream/decision-capture.json"
    view = Author.compile_view(capture_path, example_dir / "knowledge-input.json",
                               receipt_paths)
    require(Author.read(example_dir / "reference/knowledge-view.json") == view,
            "generated knowledge view differs")
    reference = reference_example(
        values["claim"], values["bundle"], values["importReceipt"],
        values["review"], values["adjudication"], view, values["event"])
    reference_path = example_dir / "reference/knowledge-example.json"
    require(Author.read(reference_path) == reference,
            "generated knowledge reference differs")
    return values, reference


def validate(example_dir: Path, claim_out: Path) -> None:
    values, reference = validate_reference(example_dir)
    reference_path = example_dir / "reference/knowledge-example.json"
    expected_claim = claim_example(
        values["claim"], example_dir, values["review"],
        values["adjudication"], reference_path, reference)
    require(Author.read(claim_out) == expected_claim,
            "generated claim example differs")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "validate"))
    parser.add_argument("--example-dir", type=Path, required=True)
    parser.add_argument("--claim-out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        example_dir, claim_out = args.example_dir.resolve(), args.claim_out.resolve()
        if args.command == "build":
            build(example_dir, claim_out)
        validate(example_dir, claim_out)
    except (Join.ContractError, OSError, UnicodeError, ValueError) as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 2
    reference = Author.read(example_dir / "reference/knowledge-example.json")
    print("validated Record 52 reference " + reference["contentSha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
