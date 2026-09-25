#!/usr/bin/env python3
"""Import, review and admit the C81 production coordination reference source.

The imported condition identity and later outcome remain audit evidence.  Model
input contains only the actor's decision-time view and removes routing IDs whose
authored names could reveal the split or scenario.  A completed exact-subject
Mousecat approval is required before the production responses become bounded
offline reference targets.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

import coordination_tasks as Tasks
import cross_module_rows as Join
import decision_authoring as Author
import training_evidence as Evidence


VERSION = 1
ROOT = Join.ROOT
SOURCE_PATH = "artifacts/audits/c81-coordination-reference-source"
SOURCE_FILES = ("catalogue.json", "decisions.jsonl", "manifest.json", "README.md")
SAO_REPOSITORY = "https://github.com/ellyj3rain/sao"
ZAO_REPOSITORY = "https://github.com/ellyj3rain/zao"
RESPONSES = ("accept", "qualify", "counter-propose", "decline", "defer",
             "contest", "withdraw")
OBSERVED_RESPONSES = ("accept", "qualify", "counter-propose", "defer", "contest")
SPLITS = ("train", "validation", "test")
SCENE_FIELDS = {
    "sceneId", "sourceLineage", "split", "actorKind", "relationship",
    "hostile", "activity", "competingPressure", "pressureKind",
    "destinationKnown", "designation",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Join.ContractError(message)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def parse_jsonl(value: bytes, where: str) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(value.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = Author.loads(line)
        require(isinstance(row, dict), f"{where}:{line_number} is not an object")
        rows.append(row)
    require(rows, f"{where} contains no rows")
    return rows


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(Author.encoded(row) + b"\n" for row in rows)


def unseal(value: Any, schema: str) -> dict[str, Any]:
    require(isinstance(value, dict) and value.get("schema") == schema
            and value.get("schemaVersion") == VERSION,
            f"requires {schema} version {VERSION}")
    declared = value.get("contentSha256")
    Author.hash_value(declared, f"{schema} contentSha256")
    body = copy.deepcopy(value)
    body.pop("contentSha256")
    require(Author.digest(body) == declared, f"{schema} content hash differs")
    return value


def git_bytes(root: Path, commit: str, relative: str) -> bytes:
    require(re.fullmatch(r"[a-f0-9]{40}", commit) is not None,
            "source commit must be a full lowercase SHA")
    done = subprocess.run(["git", "-C", str(root), "show", f"{commit}:{relative}"],
                          capture_output=True)
    require(done.returncode == 0, f"source commit does not contain {relative}")
    return done.stdout


def validate_source(files: dict[str, bytes]) -> tuple[
        dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    require(set(files) == set(SOURCE_FILES), "C81 source file set differs")
    catalogue = unseal(Author.loads(files["catalogue.json"].decode("utf-8")),
                       "sao-coordination-scene-catalogue")
    manifest = unseal(Author.loads(files["manifest.json"].decode("utf-8")),
                      "sao-coordination-scene-dump")
    rows = parse_jsonl(files["decisions.jsonl"], "C81 decisions")
    require(set(catalogue) == {"schema", "schemaVersion", "partitionRule",
                               "syntheticStartingConditions", "scenes",
                               "contentSha256"},
            "C81 catalogue fields differ")
    require(catalogue["partitionRule"] == "declared-before-production-execution"
            and catalogue["syntheticStartingConditions"] is True,
            "C81 catalogue partition or source standing differs")
    scenes = catalogue["scenes"]
    require(isinstance(scenes, list) and len(scenes) == 20,
            "C81 catalogue must contain twenty scenes")
    require("expectedChoice" not in json.dumps(scenes, sort_keys=True),
            "C81 catalogue assigns an expected response")
    indexed_scenes: dict[str, dict[str, Any]] = {}
    split_counts = {split: 0 for split in SPLITS}
    for scene in scenes:
        require(isinstance(scene, dict) and set(scene) == SCENE_FIELDS,
                "C81 scene fields differ")
        scene_id = scene["sceneId"]
        Author.identifier(scene_id, "C81 scene id")
        require(scene_id not in indexed_scenes, "duplicate C81 scene id")
        require(scene["sourceLineage"] == "coordination-scene:" + scene_id,
                "C81 source lineage differs from scene")
        require(scene["split"] in SPLITS, "C81 scene split differs")
        require(scene["actorKind"] in {"survivor", "afflicted", "crossed"},
                "C81 actor audit kind differs")
        require(type(scene["relationship"]) in (int, float)
                and type(scene["competingPressure"]) in (int, float),
                "C81 scene pressures must be numeric")
        indexed_scenes[scene_id] = scene
        split_counts[scene["split"]] += 1
    require(split_counts == {"train": 10, "validation": 5, "test": 5},
            "C81 split sizes differ")

    required_manifest = {"schema", "schemaVersion", "catalogueSha256", "rowCount",
                         "sourceHashes", "index", "standing", "exclusions",
                         "contentSha256"}
    require(set(manifest) == required_manifest,
            "C81 manifest fields differ")
    require(manifest["catalogueSha256"] == catalogue["contentSha256"]
            and manifest["rowCount"] == len(rows) == len(scenes)
            and manifest["standing"] == "candidate-observation",
            "C81 manifest identity or standing differs")
    source_hashes = manifest["sourceHashes"]
    require(isinstance(source_hashes, dict) and source_hashes,
            "C81 source hashes are absent")
    for relative, digest in source_hashes.items():
        require(relative.startswith(("sao/", "zao/")),
                "C81 source hash lacks repository owner")
        Author.hash_value(digest, "C81 source hash")

    entries = manifest["index"]
    require(isinstance(entries, list) and len(entries) == len(rows),
            "C81 manifest index differs")
    observed = {split: set() for split in SPLITS}
    for row, entry in zip(rows, entries, strict=True):
        require(isinstance(entry, dict) and set(entry) == {
            "sceneId", "sourceLineage", "split", "actorKind", "namespace",
            "response"}, "C81 index fields differ")
        scene = indexed_scenes.get(entry["sceneId"])
        require(scene is not None and all(entry[name] == scene[name] for name in
                ("sourceLineage", "split", "actorKind")),
                "C81 index differs from its predeclared scene")
        require(entry["namespace"] == row.get("namespace")
                and row.get("choice", {}).get("optionId")
                == "coordination:" + entry["response"],
                "C81 index differs from production choice")
        require(entry["response"] in OBSERVED_RESPONSES,
                "C81 index contains an unsupported observed response")
        private = (row.get("enactedProcess", {}).get("decisionTime", {})
                   .get("privateInputs", {}))
        expected_owner = ("SAO.Controller", "SAO") if scene["actorKind"] == "survivor" \
            else ("ZAO.Driver", "ZAO")
        require((private.get("executor"), private.get("bodyOwner")) == expected_owner,
                "C81 execution attribution differs")
        hidden = {"terminalState", "pathogen", "diagnosis", "diet", "currentForm"}
        require(not (hidden & Tasks.nested_field_names(private.get("constraints", {}))),
                "C81 private constraints expose hidden condition state")
        observed[scene["split"]].add(entry["response"])
    require(all(values == set(OBSERVED_RESPONSES) for values in observed.values()),
            "C81 partitions do not each cover every observed response")
    return catalogue, rows, manifest


def verify_hashes(sao_root: Path, sao_commit: str, zao_root: Path,
                  zao_commit: str, manifest: dict[str, Any]) -> None:
    for owned, expected in manifest["sourceHashes"].items():
        owner, relative = owned.split("/", 1)
        if owner == "sao":
            actual = git_bytes(sao_root, sao_commit, relative)
        elif owner == "zao":
            actual = git_bytes(zao_root, zao_commit, relative)
        else:  # guarded by validate_source; keep this branch fail-closed
            raise Join.ContractError("unknown C81 source owner: " + owner)
        require(sha256_bytes(actual) == expected,
                "committed source hash differs for " + owned)


def zao_states(script: bytes, decisions: bytes) -> bytes:
    with tempfile.TemporaryDirectory(prefix="speakeasy-c81-zao-") as tmp:
        root = Path(tmp)
        script_path = root / "state_dump.py"
        input_path = root / "decisions.jsonl"
        output_path = root / "state.jsonl"
        script_path.write_bytes(script)
        input_path.write_bytes(decisions)
        done = subprocess.run([sys.executable, str(script_path), "--sao",
                               str(input_path), "--out", str(output_path)],
                              capture_output=True, text=True)
        require(done.returncode == 0 and output_path.is_file(),
                "ZAO state projection refused C81: " +
                ((done.stdout or "") + (done.stderr or ""))[-2000:])
        value = output_path.read_bytes()
    require(len(parse_jsonl(value, "ZAO C81 state")) == 20,
            "ZAO C81 state count differs")
    return value


def compile_tasks(decisions: bytes, states: bytes) -> tuple[
        list[dict[str, Any]], bytes]:
    with tempfile.TemporaryDirectory(prefix="speakeasy-c81-tasks-") as tmp:
        root = Path(tmp)
        sao_path, zao_path = root / "sao.jsonl", root / "zao.jsonl"
        sao_path.write_bytes(decisions)
        zao_path.write_bytes(states)
        rows = Tasks.task_rows(sao_path, zao_path, root / "joined.jsonl")
    require(len(rows) == 20, "C81 task count differs")
    return rows, jsonl_bytes(rows)


def model_input(task: dict[str, Any]) -> dict[str, Any]:
    """Remove routing identity and all post-choice evidence from learned input."""
    decision = task["decisionTime"]
    reception = decision["reception"]
    result = {
        "schema": "speakeasy-coordination-response-input",
        "schemaVersion": VERSION,
        "route": "coordination-response",
        "process": {"kind": task["process"]["kind"]},
        "actor": {"executor": task["actor"]["executor"],
                  "bodyOwner": task["actor"]["bodyOwner"]},
        "decisionTime": {
            "proposal": copy.deepcopy(decision["proposal"]),
            "reception": {"channel": reception["channel"],
                          **({"evidence": copy.deepcopy(reception["evidence"])}
                             if "evidence" in reception else {})},
            "currentWork": copy.deepcopy(decision["currentWork"]),
            "competingPriorities": copy.deepcopy(decision["competingPriorities"]),
            "capabilities": copy.deepcopy(decision["capabilities"]),
            "feasibleOptions": list(decision["feasibleOptions"]),
        },
    }
    names = Tasks.nested_field_names(result)
    require(not ({"choice", "laterOutcome", "actorKind", "pathogen",
                  "terminalState", "sourceLineage", "split"} & names),
            "non-decision evidence entered coordination model input")
    encoded = Author.encoded(result).decode("utf-8")
    require("scene-run:" not in encoded and "coordination-scene:" not in encoded
            and "actor-train-" not in encoded and "actor-validation-" not in encoded
            and "actor-test-" not in encoded,
            "authored routing identity entered coordination model input")
    return result


def import_receipt(files: dict[str, bytes], manifest: dict[str, Any],
                   states: bytes, task_bytes: bytes, sao_commit: str,
                   zao_commit: str, state_dump: bytes) -> dict[str, Any]:
    return Author.seal({
        "schema": "speakeasy-coordination-source-import",
        "schemaVersion": VERSION,
        "source": {
            "sao": {"repository": SAO_REPOSITORY, "commit": sao_commit,
                    "path": SOURCE_PATH,
                    "manifestContentSha256": manifest["contentSha256"]},
            "zao": {"repository": ZAO_REPOSITORY, "commit": zao_commit,
                    "stateProjector": "tools/state_dump.py",
                    "stateProjectorSha256": sha256_bytes(state_dump)},
        },
        "files": {name: sha256_bytes(value) for name, value in files.items()},
        "upstreamSourceHashes": copy.deepcopy(manifest["sourceHashes"]),
        "derived": {"zaoStateSha256": sha256_bytes(states),
                    "tasksSha256": sha256_bytes(task_bytes), "rowCount": 20},
        "compilerHashes": {
            "coordinationData": sha256_bytes(Path(__file__).read_bytes()),
            "coordinationTasks": sha256_bytes(Path(Tasks.__file__).read_bytes()),
            "crossModuleRows": sha256_bytes(Path(Join.__file__).read_bytes()),
        },
        "verification": {"committedSourceFiles": "verified",
                         "producerSourceHashes": "verified",
                         "zaoAuditProjection": "verified",
                         "coordinationTaskCompilation": "verified"},
    })


def review_rows(catalogue: dict[str, Any], manifest: dict[str, Any],
                tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scenes = {scene["sceneId"]: scene for scene in catalogue["scenes"]}
    output = []
    for entry, task in zip(manifest["index"], tasks, strict=True):
        scene = scenes[entry["sceneId"]]
        priorities = task["decisionTime"]["competingPriorities"]
        output.append({
            "sceneId": scene["sceneId"], "sourceLineage": scene["sourceLineage"],
            "split": scene["split"], "actorKindAuditOnly": scene["actorKind"],
            "executor": task["actor"]["executor"],
            "bodyOwner": task["actor"]["bodyOwner"],
            "currentWork": copy.deepcopy(task["decisionTime"]["currentWork"]),
            "competingPressure": copy.deepcopy(
                priorities["competingPressure"]),
            "relationship": priorities["relationship"],
            "constraints": copy.deepcopy(priorities["constraints"]),
            "capabilities": copy.deepcopy(task["decisionTime"]["capabilities"]),
            "feasibleOptions": list(task["decisionTime"]["feasibleOptions"]),
            "productionResponse": task["choice"]["response"],
            "responseDelivered": task["laterOutcome"]["responseDelivery"]["delivered"],
            "modelInputSha256": Author.digest(model_input(task)),
        })
    return output


def review_subject(receipt: dict[str, Any], catalogue: dict[str, Any],
                   manifest: dict[str, Any], tasks: list[dict[str, Any]]) -> dict[str, Any]:
    return Author.seal({
        "schema": "speakeasy-coordination-label-review",
        "schemaVersion": VERSION,
        "reviewId": "r66-c81-production-responses",
        "sourceImportSha256": receipt["contentSha256"],
        "targetScope": "response-kind-only",
        "rows": review_rows(catalogue, manifest, tasks),
        "approvalEffects": [
            "Admit these exact twenty production response kinds as targets for one bounded offline coordination reference experiment.",
            "Keep source lineage, actor condition and later response delivery available for audit and evaluation but outside learned input.",
        ],
        "remainingExclusions": [
            "Synthetic starting conditions are not sampled gameplay or a frequency estimate.",
            "Decline and withdrawal have no observed target in this family.",
            "Approval does not approve response terms, define Afflicted or Crossed motives, or infer condition from the shared ZAO driver.",
            "No trained artifact is approved for game runtime by this review.",
        ],
    })


def review_invocation(subject: dict[str, Any], session_id: str,
                      invocation_id: str, occurred_at: str) -> dict[str, Any]:
    rows = subject["rows"]
    grouped: dict[str, list[str]] = {response: []
                                    for response in OBSERVED_RESPONSES}
    for row in rows:
        pressure = row["competingPressure"]
        grouped[row["productionResponse"]].append(
            f"{row['split']}/{row['sceneId']}: "
            f"audit actor={row['actorKindAuditOnly']}, executor={row['executor']}, "
            f"work={row['currentWork']['activity']}, pressure={pressure['value']} "
            f"available={pressure['available']} owner={pressure['owner']}, "
            f"relationship={row['relationship']}, "
            f"return delivered={row['responseDelivered']}"
        )
    actual = [
        {"label": f"{response} ({len(grouped[response])} exact rows)",
         "value": " | ".join(grouped[response])}
        for response in OBSERVED_RESPONSES if grouped[response]
    ]
    seam_id = "r66-c81-production-response-labels"
    evidence_ref = "speakeasy:content-sha256:" + subject["contentSha256"]
    return {
        "action": "invoke", "skillRef": "crucible",
        "frameworkRef": "recursive-deliberation",
        "source": {"host": "codex", "sessionId": session_id,
                   "invocationId": invocation_id},
        "title": "Review exact production coordination targets",
        "intake": {"seams": [{
            "id": seam_id, "occurredAt": occurred_at, "shape": "decision",
            "title": "Twenty production responses as bounded targets",
            "prompt": "Should these exact production response kinds be admitted as targets for the bounded offline coordination reference experiment?",
            "description": "The source situations were split before execution and contain no expected answer. SAO's production Controller formed each response; this review does not generalize their frequency or define Afflicted/Crossed maintenance.",
            "evidenceRef": evidence_ref, "selectionMode": "single",
            "allowFreeform": True,
            "options": [
                {"label": "Approve exact bounded labels (Recommended)",
                 "value": "approved", "recommended": True,
                 "description": "Admit only these response-kind targets for offline reference training and held-out evaluation."},
                {"label": "Request revision", "value": "revision-requested",
                 "recommended": False,
                 "description": "Keep all rows ineligible and explain which labels or review framing must change."},
                {"label": "Reject labels", "value": "rejected",
                 "recommended": False,
                 "description": "Do not use these production responses as training targets."},
            ],
            "mlReview": {
                "schema": "mousecat.ml-review/1",
                "subject": "C81 production coordination response kinds",
                "scenario": "Twenty independent synthetic starting situations raise the same concrete food-delivery matter. Communication and Perception establish reception; the shipped Controller appraises each recipient; Organization freezes the response before its actual return channel. Splits were declared before execution and no expected response appears in the source catalogue.",
                "systemRole": "A bounded coordination-response adapter learns which currently feasible response kind this person selected from their private decision-time evidence.",
                "causalPath": [
                    {"label": "Private situation", "value": "Acquired proposal, current work, generic source-owned pressure, relationship, interests, capabilities and constraints."},
                    {"label": "Production decision", "value": "SAO.Controller forms an individual response through the durable Organization process. Afflicted and Crossed execution snapshots come through their shared registered ZAO.Driver without exposing condition identity to the model."},
                    {"label": "Separate consequence", "value": "Return delivery and any later commitment/work remain outcome evidence, never decision input."},
                ],
                "playerImpact": "This is the first executable-data reference for people accepting, qualifying, counter-proposing, deferring or contesting shared work from their own circumstances. It changes no game behavior yet.",
                "decisionPrecedent": "Approval is exact and bounded: it accepts the twenty observed response kinds as experimental targets. It does not establish population rates, approve response terms, or say Afflicted and Crossed share motives because they share an executor.",
                "actualInput": actual,
                "proposedLearning": [
                    {"label": response, "value": f"Four observed production targets; one is present in each train, validation and test partition."}
                    for response in OBSERVED_RESPONSES
                ],
                "approvalEffects": list(subject["approvalEffects"]),
                "remainingExclusions": list(subject["remainingExclusions"]),
                "evidence": [
                    {"label": "Exact review subject", "value": subject["contentSha256"]},
                    {"label": "Exact source import", "value": subject["sourceImportSha256"]},
                ],
            },
        }]},
    }


def _atomic_file(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix="." + path.name,
                                        suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise


def import_source(sao_root: Path, sao_commit: str, zao_root: Path,
                  zao_commit: str, destination: Path) -> dict[str, Any]:
    files = {name: git_bytes(sao_root, sao_commit, f"{SOURCE_PATH}/{name}")
             for name in SOURCE_FILES}
    catalogue, _, manifest = validate_source(files)
    verify_hashes(sao_root, sao_commit, zao_root, zao_commit, manifest)
    state_dump = git_bytes(zao_root, zao_commit, "tools/state_dump.py")
    states = zao_states(state_dump, files["decisions.jsonl"])
    tasks, task_bytes = compile_tasks(files["decisions.jsonl"], states)
    receipt = import_receipt(files, manifest, states, task_bytes, sao_commit,
                             zao_commit, state_dump)
    subject = review_subject(receipt, catalogue, manifest, tasks)

    destination = destination.resolve()
    require(not destination.exists(), "coordination import destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="." + destination.name + ".",
                                    dir=destination.parent))
    try:
        upstream = staging / "upstream"
        upstream.mkdir()
        for name, value in files.items():
            (upstream / name).write_bytes(value)
        (staging / "zao-state.jsonl").write_bytes(states)
        (staging / "tasks.jsonl").write_bytes(task_bytes)
        (staging / "import.json").write_bytes(
            json.dumps(receipt, ensure_ascii=False, indent=2,
                       sort_keys=True).encode("utf-8") + b"\n")
        (staging / "review-subject.json").write_bytes(
            json.dumps(subject, ensure_ascii=False, indent=2,
                       sort_keys=True).encode("utf-8") + b"\n")
        os.replace(staging, destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    validate_import(destination)
    return receipt


def validate_import(destination: Path) -> tuple[
        dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    receipt = unseal(Author.read(destination / "import.json"),
                     "speakeasy-coordination-source-import")
    require(receipt["compilerHashes"] == {
        "coordinationData": sha256_bytes(Path(__file__).read_bytes()),
        "coordinationTasks": sha256_bytes(Path(Tasks.__file__).read_bytes()),
        "crossModuleRows": sha256_bytes(Path(Join.__file__).read_bytes()),
    }, "coordination import compiler hashes differ")
    files = {}
    for name in SOURCE_FILES:
        path = destination / "upstream" / name
        require(path.is_file(), "imported C81 file is missing: " + name)
        files[name] = path.read_bytes()
        require(receipt["files"].get(name) == sha256_bytes(files[name]),
                "imported C81 file hash differs: " + name)
    catalogue, _, manifest = validate_source(files)
    require(receipt["source"]["sao"]["manifestContentSha256"]
            == manifest["contentSha256"]
            and receipt["upstreamSourceHashes"] == manifest["sourceHashes"],
            "C81 import source identity differs")
    states = (destination / "zao-state.jsonl").read_bytes()
    require(sha256_bytes(states) == receipt["derived"]["zaoStateSha256"],
            "imported ZAO state hash differs")
    tasks, task_bytes = compile_tasks(files["decisions.jsonl"], states)
    require(task_bytes == (destination / "tasks.jsonl").read_bytes()
            and sha256_bytes(task_bytes) == receipt["derived"]["tasksSha256"],
            "imported coordination tasks do not reproduce")
    subject = unseal(Author.read(destination / "review-subject.json"),
                     "speakeasy-coordination-label-review")
    require(subject == review_subject(receipt, catalogue, manifest, tasks),
            "coordination review subject does not reproduce")
    return receipt, subject, tasks, catalogue


def admit(destination: Path, review_receipt: Path, output: Path) -> dict[str, Any]:
    receipt, subject, tasks, catalogue = validate_import(destination)
    review = Author.read(review_receipt)
    review_hash = Author.digest(review)
    require(review_receipt.stem == review_hash,
            "Mousecat receipt filename must equal its canonical hash")
    store = Evidence.Store(review_receipt.parent)
    # Mousecat assigns the concrete item id.  The stable input seam id is kept
    # as lineage.threadId, not reused as that generated id.  Exact evidenceRef
    # matching plus the store's one-item/one-response requirement identifies
    # the reviewed decision without guessing a platform-owned identifier.
    store.decision(review_hash, subject["contentSha256"])
    scenes = {scene["sceneId"]: scene for scene in catalogue["scenes"]}
    entries = Author.read(destination / "upstream" / "manifest.json")["index"]
    states = parse_jsonl((destination / "zao-state.jsonl").read_bytes(),
                         "admitted ZAO state")
    rows = []
    for entry, task, state in zip(entries, tasks, states, strict=True):
        scene = scenes[entry["sceneId"]]
        row = Author.seal({
            "schema": "speakeasy-coordination-reference-row",
            "schemaVersion": VERSION,
            "rowId": "coordination-response/" + scene["sceneId"],
            "split": scene["split"],
            "sourceLineage": scene["sourceLineage"],
            "routing": {"namespace": copy.deepcopy(task["namespace"]),
                        "process": copy.deepcopy(task["process"])},
            "auditOnly": {"actorKind": scene["actorKind"],
                          "pathogen": copy.deepcopy(state["pathogen"]),
                          "visibleForms": copy.deepcopy(state["visibleForms"])},
            "input": model_input(task),
            "target": {"response": task["choice"]["response"]},
            "laterOutcome": copy.deepcopy(task["laterOutcome"]),
            "provenance": {"taskSha256": task["contentSha256"],
                           "reviewSubjectSha256": subject["contentSha256"],
                           "reviewReceiptSha256": review_hash},
        })
        rows.append(row)
    dataset = Author.seal({
        "schema": "speakeasy-coordination-reference-dataset",
        "schemaVersion": VERSION,
        "datasetId": "r66-c81-coordination-response-reference",
        "sourceImportSha256": receipt["contentSha256"],
        "reviewSubjectSha256": subject["contentSha256"],
        "reviewReceiptSha256": review_hash,
        "labels": list(RESPONSES), "observedLabels": list(OBSERVED_RESPONSES),
        "partitionCounts": {split: sum(row["split"] == split for row in rows)
                            for split in SPLITS},
        "rows": rows,
        "standing": "approved-bounded-offline-reference",
        "exclusions": list(subject["remainingExclusions"]),
    })
    validate_dataset(dataset)
    _atomic_file(output, json.dumps(dataset, ensure_ascii=False, indent=2,
                                    sort_keys=True).encode("utf-8") + b"\n")
    return dataset


def validate_dataset(dataset: Any) -> dict[str, Any]:
    unseal(dataset, "speakeasy-coordination-reference-dataset")
    require(dataset["labels"] == list(RESPONSES)
            and dataset["observedLabels"] == list(OBSERVED_RESPONSES),
            "coordination dataset label vocabulary differs")
    require(dataset["standing"] == "approved-bounded-offline-reference",
            "coordination dataset is not approved for the bounded experiment")
    rows = dataset["rows"]
    require(isinstance(rows, list) and len(rows) == 20,
            "coordination dataset row count differs")
    seen, lineages = set(), {split: set() for split in SPLITS}
    coverage = {split: set() for split in SPLITS}
    for row in rows:
        unseal(row, "speakeasy-coordination-reference-row")
        require(row["rowId"] not in seen and row["split"] in SPLITS,
                "coordination dataset row identity or split differs")
        seen.add(row["rowId"])
        require(row["sourceLineage"] not in set().union(*lineages.values()),
                "coordination source lineage crosses partitions")
        lineages[row["split"]].add(row["sourceLineage"])
        target = row["target"].get("response")
        require(target in OBSERVED_RESPONSES
                and target in row["input"]["decisionTime"]["feasibleOptions"],
                "coordination target is unsupported or infeasible")
        require(row["auditOnly"].get("actorKind") in
                {"survivor", "afflicted", "crossed"},
                "coordination audit actor kind differs")
        names = Tasks.nested_field_names(row["input"])
        require(not ({"actorKind", "pathogen", "terminalState", "laterOutcome",
                      "sourceLineage", "split", "choice"} & names),
                "coordination audit or outcome evidence entered model input")
        coverage[row["split"]].add(target)
    require(dataset["partitionCounts"] == {"train": 10, "validation": 5,
                                            "test": 5}
            and all(values == set(OBSERVED_RESPONSES)
                    for values in coverage.values()),
            "coordination dataset partition coverage differs")
    return dataset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    source = commands.add_parser("import")
    source.add_argument("--sao-root", type=Path, required=True)
    source.add_argument("--sao-commit", required=True)
    source.add_argument("--zao-root", type=Path, required=True)
    source.add_argument("--zao-commit", required=True)
    source.add_argument("--out", type=Path, required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--import-dir", type=Path, required=True)
    review = commands.add_parser("review-invocation")
    review.add_argument("--import-dir", type=Path, required=True)
    review.add_argument("--session-id", required=True)
    review.add_argument("--invocation-id", required=True)
    review.add_argument("--occurred-at", required=True)
    review.add_argument("--out", type=Path, required=True)
    admission = commands.add_parser("admit")
    admission.add_argument("--import-dir", type=Path, required=True)
    admission.add_argument("--review-receipt", type=Path, required=True)
    admission.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "import":
            value = import_source(args.sao_root, args.sao_commit,
                                  args.zao_root, args.zao_commit, args.out)
            print("imported C81 coordination source " + value["contentSha256"])
        elif args.command == "validate":
            value = validate_import(args.import_dir)[0]
            print("validated C81 coordination source " + value["contentSha256"])
        elif args.command == "review-invocation":
            subject = validate_import(args.import_dir)[1]
            value = review_invocation(subject, args.session_id,
                                      args.invocation_id, args.occurred_at)
            _atomic_file(args.out, json.dumps(value, ensure_ascii=False, indent=2,
                                              sort_keys=True).encode("utf-8") + b"\n")
            print("wrote exact-label review for " + subject["contentSha256"])
        else:
            value = admit(args.import_dir, args.review_receipt, args.out)
            print("admitted bounded coordination dataset " + value["contentSha256"])
    except (Join.ContractError, OSError, UnicodeError, ValueError,
            subprocess.SubprocessError) as error:
        print("REFUSED: " + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
