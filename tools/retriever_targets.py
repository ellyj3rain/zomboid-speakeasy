#!/usr/bin/env python3
"""Compile independently reviewed claim-retrieval targets.

Task-example approval supplies an anchor. It does not approve the retriever row.
Unmentioned catalogue claims remain unjudged unless the row explicitly names and
reviews them as hard negatives.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any

import cross_module_rows as Join
import decision_authoring as Author
import training_evidence as Evidence


VERSION = 2
CATALOGUE_VERSION = 1
POLICY = "independent-anchored-targets"
CATALOGUE_SCHEMA = "sao-claim-catalogue"
ANCHOR_SCHEMA = "speakeasy-retriever-anchor"
PROPOSAL_SCHEMA = "speakeasy-retriever-target-proposal"
REVIEW_SCHEMA = "speakeasy-retriever-target-review"
TARGET_SCHEMA = "speakeasy-retriever-target"
SNAPSHOT_SCHEMA = "speakeasy-retriever-dataset-snapshot"
TASKS = {"understander", "speaker"}
TOPICS = {"self", "person", "zombies", "dead", "food", "water", "house",
          "ground", "lessons", "mutations", "world", "before", "started"}
SPLITS = ("train", "validation", "test")
HASH = re.compile(r"[a-f0-9]{64}")
POLICY_RECEIPT = Join.ROOT / "training/retriever/policy.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Join.ContractError(message)


def nonempty(value: Any, where: str) -> None:
    require(Join.nonempty_string(value), f"{where} must be a nonempty string")


def hash_value(value: Any, where: str) -> None:
    require(isinstance(value, str) and HASH.fullmatch(value) is not None,
            f"{where} must be a lowercase SHA-256")


def fields(value: Any, expected: set[str], where: str) -> None:
    require(isinstance(value, dict) and set(value) == expected,
            f"{where} requires exactly {', '.join(sorted(expected))}")


def sealed(value: Any, schema_name: str) -> dict[str, Any]:
    require(isinstance(value, dict) and value.get("schema") == schema_name
            and type(value.get("schemaVersion")) is int
            and value["schemaVersion"] == VERSION,
            f"requires {schema_name} version {VERSION}")
    body = copy.deepcopy(value)
    actual = body.pop("contentSha256", None)
    hash_value(actual, "contentSha256")
    require(Author.digest(body) == actual, f"{schema_name} content hash differs")
    return value


def ordered_refs(value: Any, where: str) -> list[str]:
    require(isinstance(value, list), f"{where} must be a list")
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        nonempty(item, f"{where} reference")
        require(item not in seen, f"{where} contains a duplicate reference")
        seen.add(item)
        result.append(item)
    return result


def validate_catalogue(value: Any) -> tuple[dict[str, Any], list[str]]:
    expected_fields = {"schema", "schemaVersion", "snapshotRef", "personId",
                       "atTick", "conditioning", "claims"}
    if isinstance(value, dict) and "listenerRef" in value:
        expected_fields.add("listenerRef")
    fields(value, expected_fields,
           "claim catalogue")
    require(value["schema"] == CATALOGUE_SCHEMA
            and type(value["schemaVersion"]) is int
            and value["schemaVersion"] == CATALOGUE_VERSION,
            "requires sao-claim-catalogue version 1")
    nonempty(value["snapshotRef"], "catalogue snapshotRef")
    nonempty(value["personId"], "catalogue personId")
    require(value.get("listenerRef") is None
            or Join.nonempty_string(value["listenerRef"]),
            "catalogue listenerRef must be null or a nonempty string")
    require(Join.finite_number(value["atTick"]), "catalogue atTick must be finite")
    require(isinstance(value["conditioning"], dict),
            "catalogue conditioning must be an object")
    require(isinstance(value["claims"], list), "catalogue claims must be a list")
    require(len(value["claims"]) <= 512, "catalogue exceeds the C75 claim ceiling")

    refs: list[str] = []
    for index, claim in enumerate(value["claims"], start=1):
        expected_fields = {"ref", "topic", "fact"}
        if isinstance(claim, dict) and "sourceClaimId" in claim:
            expected_fields.add("sourceClaimId")
        fields(claim, expected_fields, f"catalogue claim {index}")
        expected_ref = f'{value["snapshotRef"]}/claim/{index:04d}'
        require(claim["ref"] == expected_ref,
                f"catalogue claim {index} reference differs from C75 order")
        require(isinstance(claim["topic"], str) and claim["topic"] in TOPICS,
                f"catalogue claim {index} topic is unknown")
        require(isinstance(claim["fact"], dict),
                f"catalogue claim {index} fact must be an object")
        fact_claim_id = claim["fact"].get("claimId")
        if not Join.nonempty_string(fact_claim_id):
            require("sourceClaimId" not in claim,
                    f"catalogue claim {index} has an unsupported sourceClaimId")
        else:
            require(claim.get("sourceClaimId") == fact_claim_id,
                    f"catalogue claim {index} sourceClaimId differs from its fact")
        refs.append(claim["ref"])

    # Canonical encoding rejects non-finite values and unsupported JSON types.
    Author.encoded(value)
    return value, refs


def validate_anchor(value: Any, catalogue: dict[str, Any],
                    catalogue_refs: list[str], evidence=None) -> dict[str, Any]:
    sealed(value, ANCHOR_SCHEMA)
    fields(value, {"schema", "schemaVersion", "anchorId", "task", "catalogue",
                   "context", "taskExample", "requiredClaimRefs", "contentSha256"},
           "retriever anchor")
    nonempty(value["anchorId"], "anchorId")
    require(isinstance(value["task"], str) and value["task"] in TASKS,
            "anchor task must be understander or speaker")

    binding = value["catalogue"]
    fields(binding, {"snapshotRef", "contentSha256"}, "anchor catalogue binding")
    require(binding["snapshotRef"] == catalogue["snapshotRef"],
            "anchor snapshot differs from catalogue")
    require(binding["contentSha256"] == Author.digest(catalogue),
            "anchor catalogue hash differs")

    context = value["context"]
    fields(context, {"personId", "listenerRef", "atTick", "utterance", "situation"},
           "anchor context")
    require(context["personId"] == catalogue["personId"],
            "anchor person differs from catalogue")
    require(context["listenerRef"] == catalogue.get("listenerRef"),
            "anchor listener differs from catalogue")
    require(context["atTick"] == catalogue["atTick"],
            "anchor tick differs from catalogue")
    nonempty(context["utterance"], "anchor utterance")
    require(isinstance(context["situation"], dict) and context["situation"],
            "anchor situation must be a nonempty object")

    task_example = value["taskExample"]
    fields(task_example, {"datasetSnapshotRef", "datasetSnapshotSha256", "rowId",
                          "rowContentSha256", "approvalReceiptSha256", "standing"},
           "anchored task example")
    nonempty(task_example["datasetSnapshotRef"], "task dataset snapshot")
    hash_value(task_example["datasetSnapshotSha256"], "task datasetSnapshotSha256")
    nonempty(task_example["rowId"], "task rowId")
    hash_value(task_example["rowContentSha256"], "task rowContentSha256")
    hash_value(task_example["approvalReceiptSha256"], "task approvalReceiptSha256")
    require(task_example["standing"] == "approved",
            "anchored task example must be independently approved")

    required = ordered_refs(value["requiredClaimRefs"], "requiredClaimRefs")
    available = set(catalogue_refs)
    require(all(ref in available for ref in required),
            "anchor requires a claim outside the bound catalogue")
    require(required == [ref for ref in catalogue_refs if ref in set(required)],
            "anchor required claims must follow catalogue order")
    (evidence or Evidence.Store()).task_anchor(value, catalogue)
    return value


def hard_negatives(value: Any, available: set[str], required: set[str]) -> list[dict[str, str]]:
    require(isinstance(value, list), "hard negatives must be a list")
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(value, start=1):
        fields(item, {"claimRef", "reason"}, f"hard negative {index}")
        ref = item["claimRef"]
        nonempty(ref, f"hard negative {index} claimRef")
        nonempty(item["reason"], f"hard negative {index} reason")
        require(ref in available, f"hard negative {index} is outside the catalogue")
        require(ref not in required, f"hard negative {index} is also required")
        require(ref not in seen, "hard negatives contain a duplicate reference")
        seen.add(ref)
        result.append(copy.deepcopy(item))
    return result


def label_partition(labels: Any, catalogue_refs: list[str]) -> None:
    fields(labels, {"requiredClaimRefs", "hardNegatives", "unjudgedClaimRefs"},
           "retriever labels")
    required = ordered_refs(labels["requiredClaimRefs"], "requiredClaimRefs")
    negatives = hard_negatives(labels["hardNegatives"], set(catalogue_refs), set(required))
    unjudged = ordered_refs(labels["unjudgedClaimRefs"], "unjudgedClaimRefs")
    negative_refs = [item["claimRef"] for item in negatives]
    require(negative_refs == [ref for ref in catalogue_refs if ref in set(negative_refs)],
            "hard negatives must follow catalogue order")
    require(not (set(required) & set(unjudged)), "required and unjudged claims overlap")
    require(not (set(negative_refs) & set(unjudged)),
            "hard-negative and unjudged claims overlap")
    require(set(required) | set(negative_refs) | set(unjudged) == set(catalogue_refs),
            "labels do not partition the complete catalogue")
    require(required or negative_refs, "target has no reviewed learning signal")
    expected_unjudged = [ref for ref in catalogue_refs
                         if ref not in set(required) | set(negative_refs)]
    require(unjudged == expected_unjudged,
            "unjudged references must be the ordered catalogue complement")


def propose(catalogue: dict[str, Any], anchor: dict[str, Any], proposal_id: str,
            negative_labels: list[dict[str, str]], evidence=None) -> dict[str, Any]:
    catalogue, refs = validate_catalogue(catalogue)
    anchor = validate_anchor(anchor, catalogue, refs, evidence)
    nonempty(proposal_id, "proposalId")
    required = list(anchor["requiredClaimRefs"])
    negatives = hard_negatives(negative_labels, set(refs), set(required))
    order = {ref: index for index, ref in enumerate(refs)}
    negatives.sort(key=lambda item: order[item["claimRef"]])
    negative_refs = {item["claimRef"] for item in negatives}
    unjudged = [ref for ref in refs if ref not in set(required) | negative_refs]
    require(required or negatives, "target has no reviewed learning signal")
    return Author.seal({
        "schema": PROPOSAL_SCHEMA,
        "schemaVersion": VERSION,
        "proposalId": proposal_id,
        "policy": POLICY,
        "input": {
            "catalogue": copy.deepcopy(catalogue),
            "context": copy.deepcopy(anchor["context"]),
        },
        "anchor": copy.deepcopy(anchor),
        "labels": {
            "requiredClaimRefs": required,
            "hardNegatives": negatives,
            "unjudgedClaimRefs": unjudged,
        },
        "standing": "proposed",
    })


def validate_proposal(value: Any, evidence=None) -> dict[str, Any]:
    sealed(value, PROPOSAL_SCHEMA)
    fields(value, {"schema", "schemaVersion", "proposalId", "policy", "input",
                   "anchor", "labels", "standing", "contentSha256"},
           "retriever proposal")
    nonempty(value["proposalId"], "proposalId")
    require(value["policy"] == POLICY, "retriever proposal uses another policy")
    require(value["standing"] == "proposed", "retriever proposal standing differs")
    fields(value["input"], {"catalogue", "context"}, "retriever proposal input")
    catalogue, refs = validate_catalogue(value["input"]["catalogue"])
    anchor = validate_anchor(value["anchor"], catalogue, refs, evidence)
    context = value["input"]["context"]
    require(isinstance(context, dict)
            and context.get("personId") == catalogue["personId"]
            and context.get("listenerRef") == catalogue.get("listenerRef")
            and context.get("atTick") == catalogue["atTick"],
            "proposal context differs from catalogue")
    require(Author.digest(context) == Author.digest(anchor["context"]),
            "proposal context differs from task anchor")
    label_partition(value["labels"], refs)
    require(value["labels"]["requiredClaimRefs"] == anchor["requiredClaimRefs"],
            "proposal required claims differ from the approved task anchor")
    return value


def validate_review(value: Any, proposal: dict[str, Any], evidence=None) -> dict[str, Any]:
    sealed(value, REVIEW_SCHEMA)
    fields(value, {"schema", "schemaVersion", "proposalId", "proposalContentSha256",
                   "status", "reviewedAt", "reviewer", "decision", "contentSha256"},
           "retriever target review")
    require(value["proposalId"] == proposal["proposalId"],
            "review proposalId differs")
    require(value["proposalContentSha256"] == proposal["contentSha256"],
            "review proposal hash differs")
    require(isinstance(value["status"], str) and value["status"] in {"approved", "rejected"},
            "review status must be approved or rejected")
    nonempty(value["reviewedAt"], "reviewedAt")
    fields(value["reviewer"], {"kind", "id"}, "reviewer")
    require(value["reviewer"]["kind"] == "operator",
            "retriever target review must be an operator ruling")
    nonempty(value["reviewer"]["id"], "reviewer id")
    fields(value["decision"], {"interactionId", "itemId", "value", "resultSha256"},
           "review decision")
    nonempty(value["decision"]["interactionId"], "review interactionId")
    nonempty(value["decision"]["itemId"], "review itemId")
    require(value["decision"]["value"] == value["status"],
            "review decision value differs from status")
    (evidence or Evidence.Store()).decision(
        value["decision"]["resultSha256"], proposal["contentSha256"],
        interaction=value["decision"]["interactionId"],
        item_id=value["decision"]["itemId"], status=value["status"])
    return value


def task_conditioning(anchor, catalogue, evidence=None):
    row = (evidence or Evidence.Store()).task_anchor(anchor, catalogue)
    if row.get("schemaVersion") == 2:
        import conversation_tasks as C
        return C.task_conditioning(row, evidence)
    return {"status": "ineligible", "exclusions": [
        "source-catalogue-coverage-not-verified", "task-schema-admission-not-implemented"]}


def admit(proposal: dict[str, Any], review: dict[str, Any], row_id: str,
          evidence=None) -> dict[str, Any]:
    proposal = validate_proposal(proposal, evidence)
    review = validate_review(review, proposal, evidence)
    require(review["status"] == "approved", "retriever target was not approved")
    nonempty(row_id, "rowId")
    return Author.seal({
        "schema": TARGET_SCHEMA,
        "schemaVersion": VERSION,
        "rowId": row_id,
        "policy": POLICY,
        "input": copy.deepcopy(proposal["input"]),
        "anchor": copy.deepcopy(proposal["anchor"]),
        "labels": copy.deepcopy(proposal["labels"]),
        "provenance": {
            "proposalId": proposal["proposalId"],
            "proposalContentSha256": proposal["contentSha256"],
            "approvalReceiptSha256": review["contentSha256"],
            "interactionId": review["decision"]["interactionId"],
            "itemId": review["decision"]["itemId"],
        },
        "review": copy.deepcopy(review),
        "standing": "approved",
        "conditioning": task_conditioning(proposal["anchor"], proposal["input"]["catalogue"], evidence),
    })


def validate_target(value: Any, evidence=None) -> dict[str, Any]:
    sealed(value, TARGET_SCHEMA)
    fields(value, {"schema", "schemaVersion", "rowId", "policy", "input", "anchor",
                   "labels", "provenance", "review", "standing", "conditioning",
                   "contentSha256"},
           "retriever target")
    nonempty(value["rowId"], "rowId")
    require(value["policy"] == POLICY and value["standing"] == "approved",
            "retriever target is not independently approved")
    require(value["conditioning"] == task_conditioning(
        value["anchor"], value["input"]["catalogue"], evidence),
        "target cannot claim missing source/task admission")
    fields(value["input"], {"catalogue", "context"}, "retriever target input")
    catalogue, refs = validate_catalogue(value["input"]["catalogue"])
    context = value["input"]["context"]
    require(isinstance(context, dict)
            and context.get("personId") == catalogue["personId"]
            and context.get("listenerRef") == catalogue.get("listenerRef")
            and context.get("atTick") == catalogue["atTick"],
            "target context differs from catalogue")
    anchor = validate_anchor(value["anchor"], catalogue, refs, evidence)
    require(Author.digest(context) == Author.digest(anchor["context"]),
            "target context differs from task anchor")
    label_partition(value["labels"], refs)
    require(value["labels"]["requiredClaimRefs"] == anchor["requiredClaimRefs"],
            "target required claims differ from the approved task anchor")
    fields(value["provenance"], {"proposalId", "proposalContentSha256",
                                 "approvalReceiptSha256", "interactionId", "itemId"},
           "target provenance")
    nonempty(value["provenance"]["proposalId"], "target proposalId")
    hash_value(value["provenance"]["proposalContentSha256"],
               "target proposalContentSha256")
    hash_value(value["provenance"]["approvalReceiptSha256"],
               "target approvalReceiptSha256")
    nonempty(value["provenance"]["interactionId"], "target interactionId")
    nonempty(value["provenance"]["itemId"], "target itemId")
    proposal = Author.seal({
        "schema": PROPOSAL_SCHEMA,
        "schemaVersion": VERSION,
        "proposalId": value["provenance"]["proposalId"],
        "policy": value["policy"],
        "input": copy.deepcopy(value["input"]),
        "anchor": copy.deepcopy(value["anchor"]),
        "labels": copy.deepcopy(value["labels"]),
        "standing": "proposed",
    })
    require(proposal["contentSha256"] == value["provenance"]["proposalContentSha256"],
            "target contents differ from the approved proposal")
    validate_proposal(proposal, evidence)
    review = validate_review(value["review"], proposal, evidence)
    require(review["status"] == "approved", "target review is not approved")
    require(review["contentSha256"] == value["provenance"]["approvalReceiptSha256"]
            and review["decision"]["interactionId"] == value["provenance"]["interactionId"]
            and review["decision"]["itemId"] == value["provenance"]["itemId"],
            "target approval provenance differs from its review")
    return value


def evidence_rows(value: Any, name: str) -> list[dict[str, str]]:
    require(isinstance(value, list), f"{name} must be a list")
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(value, start=1):
        fields(item, {"id", "reason", "evidenceSha256"}, f"{name} {index}")
        nonempty(item["id"], f"{name} {index} id")
        nonempty(item["reason"], f"{name} {index} reason")
        hash_value(item["evidenceSha256"], f"{name} {index} evidenceSha256")
        key = (item["id"], item["evidenceSha256"])
        require(key not in seen, f"{name} contains a duplicate")
        seen.add(key)
        result.append(copy.deepcopy(item))
    return result


def compile_snapshot(snapshot_id: str, targets: list[dict[str, Any]],
                     split_map: dict[str, Any], exclusions: list[dict[str, str]],
                     evaluation_receipts: list[dict[str, str]], evidence=None) -> dict[str, Any]:
    nonempty(snapshot_id, "snapshotId")
    require(targets, "retriever dataset snapshot requires at least one approved row")
    evidence = evidence or Evidence.Store()
    checked = [validate_target(row, evidence) for row in targets]
    by_id: dict[str, dict[str, Any]] = {}
    proposal_hashes: set[str] = set()
    for row in checked:
        require(row["rowId"] not in by_id, "dataset contains a duplicate rowId")
        proposal_hash = row["provenance"]["proposalContentSha256"]
        require(proposal_hash not in proposal_hashes,
                "dataset contains the same approved proposal more than once")
        proposal_hashes.add(proposal_hash)
        by_id[row["rowId"]] = row

    fields(split_map, set(SPLITS), "dataset splits")
    assigned: list[str] = []
    splits: dict[str, list[str]] = {}
    for split in SPLITS:
        rows = ordered_refs(split_map[split], f"{split} split")
        require(all(row_id in by_id for row_id in rows),
                f"{split} split names an unknown row")
        splits[split] = rows
        assigned.extend(rows)
    require(len(assigned) == len(set(assigned)), "a row appears in more than one split")
    require(set(assigned) == set(by_id), "dataset splits do not cover every row")
    source_splits = {}
    for split, row_ids in splits.items():
        for row_id in row_ids:
            row = by_id[row_id]
            sources = ("catalogue:" + row["input"]["catalogue"]["snapshotRef"],
                       "task:" + row["anchor"]["taskExample"]["rowContentSha256"])
            for source in sources:
                require(source not in source_splits or source_splits[source] == split,
                        "shared source appears in more than one split")
                source_splits[source] = split

    exclusion_rows = evidence_rows(exclusions, "dataset exclusions")
    require(not ({entry["id"] for entry in exclusion_rows} & set(by_id)),
            "excluded row is present in the dataset")
    evaluation_rows = evidence_rows(evaluation_receipts, "evaluation receipts")
    require(evaluation_rows, "dataset snapshot requires an evaluation receipt")
    evidence.references(exclusion_rows, "exclusion")
    evidence.references(evaluation_rows, "evaluation", [row["contentSha256"] for row in checked])
    ordered = [by_id[row_id] for row_id in sorted(by_id)]
    return Author.seal({
        "schema": SNAPSHOT_SCHEMA,
        "schemaVersion": VERSION,
        "snapshotId": snapshot_id,
        "policy": POLICY,
        "rows": copy.deepcopy(ordered),
        "splits": splits,
        "exclusions": exclusion_rows,
        "evaluationReceipts": evaluation_rows,
        "conditioning": {
            "status": "ineligible",
            "exclusions": sorted({reason for row in ordered
                                  for reason in row["conditioning"]["exclusions"]}),
        },
        "counts": {
            "rows": len(ordered),
            "requiredPositives": sum(len(row["labels"]["requiredClaimRefs"])
                                     for row in ordered),
            "hardNegatives": sum(len(row["labels"]["hardNegatives"])
                                 for row in ordered),
            "unjudged": sum(len(row["labels"]["unjudgedClaimRefs"])
                            for row in ordered),
        },
    })


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=path.parent, prefix=path.name + ".",
                                         suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(value, ensure_ascii=False, indent=2,
                                    sort_keys=True, allow_nan=False) + "\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def publish(path: Path, value: Any, inputs: list[Path], evidence=None) -> None:
    protected = Join.protected_artifacts()
    key = Join.canonical(path)
    forbidden = {Join.canonical(item) for item in
                 inputs + [Join.PROTECTED_MANIFEST, POLICY_RECEIPT,
                           Author.ACQUISITION_CORRECTIONS,
                           Join.ROOT / "training/understander/sources.json"]}
    require(path.suffix.lower() == ".json", "retriever output must be a JSON file")
    require(key not in forbidden and key not in protected,
            "output cannot replace an input, policy receipt, protected artifact, or protected manifest")
    evidence = evidence or Evidence.Store()
    require(not path.resolve().is_relative_to(evidence.root.resolve()),
            "output cannot replace stored evidence")
    atomic_json(path, value)


def parse_negative(value: str) -> dict[str, str]:
    ref, separator, reason = value.partition("=")
    require(bool(separator) and bool(ref) and bool(reason),
            "--hard-negative requires CLAIM_REF=REASON")
    return {"claimRef": ref, "reason": reason}


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    proposal = commands.add_parser("propose")
    proposal.add_argument("--catalogue", type=Path, required=True)
    proposal.add_argument("--anchor", type=Path, required=True)
    proposal.add_argument("--proposal-id", required=True)
    proposal.add_argument("--hard-negative", action="append", default=[])
    proposal.add_argument("--out", type=Path, required=True)

    admission = commands.add_parser("admit")
    admission.add_argument("--proposal", type=Path, required=True)
    admission.add_argument("--review", type=Path, required=True)
    admission.add_argument("--row-id", required=True)
    admission.add_argument("--out", type=Path, required=True)

    snapshot = commands.add_parser("snapshot")
    snapshot.add_argument("--snapshot-id", required=True)
    snapshot.add_argument("--target", type=Path, action="append", required=True)
    snapshot.add_argument("--splits", type=Path, required=True)
    snapshot.add_argument("--exclusions", type=Path, required=True)
    snapshot.add_argument("--evaluation-receipts", type=Path, required=True)
    snapshot.add_argument("--out", type=Path, required=True)

    for command in (proposal, admission, snapshot):
        command.add_argument("--evidence-root", type=Path, default=None)

    args = parser.parse_args(argv)
    try:
        evidence = Evidence.Store(args.evidence_root)
        if args.command == "propose":
            result = propose(Author.read(args.catalogue), Author.read(args.anchor),
                             args.proposal_id,
                             [parse_negative(item) for item in args.hard_negative], evidence)
            inputs = [args.catalogue, args.anchor]
        elif args.command == "admit":
            result = admit(Author.read(args.proposal), Author.read(args.review), args.row_id,
                           evidence)
            inputs = [args.proposal, args.review]
        else:
            result = compile_snapshot(
                args.snapshot_id,
                [Author.read(path) for path in args.target],
                Author.read(args.splits),
                Author.read(args.exclusions),
                Author.read(args.evaluation_receipts),
                evidence,
            )
            inputs = (args.target + [args.splits, args.exclusions,
                                     args.evaluation_receipts])
        publish(args.out, result, inputs, evidence)
        return 0
    except (Join.ContractError, OSError) as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli())
