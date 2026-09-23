"""Import reviewed SAO captures and validate source-bound understander examples.

Data contracts only: no SAO runtime implementation is imported or executed.
The reviewed source registry is the trust root; content seals prove integrity.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timedelta
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

import cross_module_rows as J
import decision_authoring as A
import retriever_targets as R
import training_evidence as E

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "training/understander/sources.json"
IMPORT_SCHEMA = "speakeasy-conversation-import"
TASK_SCHEMA = "speakeasy-task-evidence"
TASK_VERSION = 2
TOPICS = ["self", "person", "zombies", "dead", "food", "water", "house",
          "ground", "lessons", "mutations", "world", "before", "started"]


def source_profile(source_id):
    registry = A.read(REGISTRY)
    A.schema(registry, "speakeasy-conversation-sources")
    matches = [p for p in registry["sources"] if p["id"] == source_id]
    A.require(len(matches) == 1, "conversation source is not reviewed")
    return matches[0]


def git_bytes(root, commit, path):
    A.require(len(commit) == 40 and all(c in "0123456789abcdef" for c in commit),
              "source requires full commit SHA")
    result = subprocess.run(["git", "-c", "core.longpaths=true", "-C", str(root), "show", f"{commit}:{path}"],
                            capture_output=True)
    A.require(result.returncode == 0, "cannot read committed source: " + path
              + ": " + result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_capture(capture, manifest):
    A.schema(capture, "sao-conversation-capture")
    A.unseal(manifest, "sao-conversation-evidence")
    A.require(A.digest(capture) == manifest["captureSha256"], "capture hash differs")
    catalogue, refs = R.validate_catalogue(capture["catalogue"])
    context, namespace, state = capture["context"], capture["namespace"], capture["sourceState"]
    A.fields(context, {"personId", "listenerRef", "atTick", "utterance", "situation"}, "context")
    A.require(context["personId"] == namespace["personId"] == catalogue["personId"]
              == state["person"]["id"], "person binding differs")
    A.require(context["listenerRef"] == catalogue["listenerRef"] == state["listener"]["id"]
              and context["listenerRef"] != context["personId"], "partner binding differs")
    A.require(context["situation"]["kind"] == "authored-conversation"
              and all(context["situation"][role + "Position"]
                      == {axis: state[role][axis] for axis in ("x", "y", "z")}
                      for role in ("person", "listener")), "participant positions differ")
    A.require(catalogue["snapshotRef"] == capture["snapshotRef"], "snapshot binding differs")
    A.require(capture["inputOrigin"] == "authored"
              and capture["standing"] == "captured-authored-input"
              and capture["trainingEligible"] is False, "authored standing differs")
    coverage = capture["coverage"]
    A.require(coverage["scope"] == "knowledge-topics-v1" and coverage["status"] == "complete"
              and coverage["failures"] in ({}, []) and coverage["topics"] == TOPICS
              and isinstance(coverage["readers"], list) and coverage["readers"],
              "source coverage incomplete")
    calendar, control = capture["calendar"], manifest["calendarControl"]
    hour = namespace["hour"]
    A.require(J.finite_number(hour) and context["atTick"] == catalogue["atTick"]
              == hour * calendar["ticksPerHour"] and calendar["ticksPerHour"] == 9000
              and hour == calendar["atHour"] == control["horizonHour"]
              == context["situation"]["atHour"], "clock binding differs")
    A.require(calendar["anchorInstant"] == control["anchorAt"]
              and calendar["anchorHour"] == control["anchorHour"]
              and calendar["atInstant"] == control["horizonAt"]
              and datetime.fromisoformat(calendar["atInstant"])
              == datetime.fromisoformat(calendar["anchorInstant"])
              + timedelta(hours=hour-calendar["anchorHour"]), "calendar differs")
    owners = A.loads(state["ownerStateBytes"])
    records = owners["durable"]["SurvivorAwareness_Records"]["records"]
    for role in ("person", "listener"):
        person = state[role]
        A.require(records[person["id"]] == person, "frozen owner person differs")
        A.require(person["worldKnowledge"]["schemaVersion"] == 2, "legacy world knowledge")
    A.require(owners["beliefs"][context["personId"]] == state["beliefs"], "frozen beliefs differ")
    world = state["person"]["worldKnowledge"]
    acquisitions = world["acquisitions"] or []
    retained = state["worldRetention"]
    claims = [c for c in catalogue["claims"] if c["topic"] == "world"]
    A.require(len(claims) == len(acquisitions) == len(retained), "world coverage differs")
    for claim, acquisition, retention in zip(claims, acquisitions, retained):
        fact = claim["fact"]
        A.require(acquisition["schemaVersion"] == 2
                  and acquisition["personId"] == context["personId"]
                  and acquisition["path"] == fact["source"] == "read"
                  and acquisition["knowledgeKind"] == fact["knowledgeKind"] == "reported"
                  and acquisition["access"] == "completed-native-print-read"
                  and acquisition["producer"] == "SAO.WorldKnowledge.completedPrintRead"
                  and acquisition["carrier"] == fact["carrier"] == "print"
                  and acquisition["claimId"] == fact["claimId"] == claim["sourceClaimId"]
                  and acquisition["retained"] is True, "unsupported world acquisition")
        receipt = world["readReceipts"].get(acquisition["receiptId"])
        A.require(isinstance(receipt, dict) and receipt["schemaVersion"] == 1
                  and receipt["recordId"] == acquisition["receiptId"] == fact["receiptId"]
                  and receipt["personId"] == acquisition["personId"]
                  and receipt["claimId"] == acquisition["claimId"]
                  and receipt["producer"] == "ISReadABook.complete"
                  and receipt["result"] == "completed"
                  and receipt["completedHour"] == acquisition["acquiredHour"] == fact["acquiredHour"]
                  and receipt["completedHour"] <= hour
                  and type(receipt["itemId"]) is int and receipt["itemId"] > 0
                  and receipt["itemType"] == "Base.Newspaper_Knews"
                  and isinstance(receipt["mediaId"], str)
                  and receipt["mediaId"].lower() == manifest["nativePrintIssue"]["mediaId"]
                  and receipt["infoKey"] == manifest["nativePrintIssue"]["info"]
                  and receipt["textKey"] == manifest["nativePrintIssue"]["text"],
                  "native reading receipt differs")
        A.require(acquisition["sourceEvent"]["kind"] == "dated-report"
                  and acquisition["sourceEvent"]["resolution"] == "publication-date"
                  and acquisition["sourceEvent"]["recordDay"] == control["claimEventRecordDay"]
                  and acquisition["sourceEvent"]["atHours"] == fact["reportHour"]
                  == control["claimEventHour"] and fact["reportHour"] <= fact["acquiredHour"],
                  "publication/acquisition time differs")
        A.require(retention["acquisition"] == acquisition and retention["retained"] is True
                  and retention["personId"] == context["personId"] and retention["asOfHour"] == hour,
                  "retention binding differs")
        source = acquisition["source"]
        source_path = (ROOT / source["path"]).resolve()
        A.require(source_path.is_relative_to(ROOT / "world"), "source path outside world")
        A.require(file_hash(source_path) == source["sha256"], "protected world source hash differs")
        lines = source_path.read_text(encoding="utf-8").splitlines()
        A.require(type(source["line"]) is int and 1 <= source["line"] <= len(lines), "source line differs")
        A.require(hashlib.sha256(lines[source["line"]-1].encode("utf-8")).hexdigest()
                  == source["excerptSha256"], "protected source excerpt differs")
        A.require(A.acquisition_correction(acquisition, {"source": source}) is None,
                  "superseded acquisition")
    return refs


def import_capture(sao_root, source_id, installed):
    profile = source_profile(source_id)
    capture, manifest = [A.loads(git_bytes(sao_root, profile["commit"],
                         profile["path"] + "/" + name).decode("utf-8"))
                         for name in ("capture.json", "manifest.json")]
    A.require(set(installed) == {p for p in manifest["sources"] if p.startswith("installed/")},
              "installed source bindings differ")
    for path, expected in manifest["sources"].items():
        actual = (file_hash(installed[path]) if path.startswith("installed/") else
                  hashlib.sha256(git_bytes(sao_root, profile["commit"], path)).hexdigest())
        A.require(actual == expected, "producer source hash differs: " + path)
    value = A.seal({"schema": IMPORT_SCHEMA, "schemaVersion": 1, "sourceId": source_id,
                   "source": profile, "capture": capture, "manifest": manifest,
                   "verification": {"repositorySources": "exact-commit-blobs",
                                    "installedSources": "exact-local-bytes"}})
    validate_import(value)
    return value


def validate_import(value):
    A.unseal(value, IMPORT_SCHEMA)
    A.fields(value, {"schema", "schemaVersion", "sourceId", "source", "capture", "manifest",
                     "verification", "contentSha256"}, "conversation import")
    profile = source_profile(value["sourceId"])
    A.require(value["source"] == profile, "reviewed source identity differs")
    A.require(A.digest(value["capture"]) == profile["captureSha256"]
              and value["manifest"]["contentSha256"] == profile["manifestSha256"],
              "reviewed capture/manifest differs")
    A.require(value["verification"] == {"repositorySources": "exact-commit-blobs",
                                        "installedSources": "exact-local-bytes"},
              "source verification receipt differs")
    validate_capture(value["capture"], value["manifest"])
    return value


def seal_task(body):
    return A.seal({"schema": TASK_SCHEMA, "schemaVersion": TASK_VERSION, **body})


def propose(imported, row_id, frame):
    capture = validate_import(imported)["capture"]
    context = capture["context"]
    value = seal_task({"rowId": row_id, "task": "understander",
        "input": {"catalogue": copy.deepcopy(capture["catalogue"]),
                  "context": copy.deepcopy(context),
                  "sourceImportSha256": imported["contentSha256"],
                  "utteranceRoles": {"speakerRef": context["listenerRef"],
                                     "listenerRef": context["personId"]}},
        "output": copy.deepcopy(frame), "requiredClaimRefs": list(frame["claimRefs"])})
    validate_task(value, imported=imported)
    return value


def validate_task(value, evidence=None, imported=None):
    A.require(isinstance(value, dict) and value.get("schema") == TASK_SCHEMA
              and type(value.get("schemaVersion")) is int and value["schemaVersion"] == TASK_VERSION,
              "requires typed task evidence version 2")
    A.fields(value, {"schema", "schemaVersion", "rowId", "task", "input", "output",
                     "requiredClaimRefs", "contentSha256"}, "typed task")
    body = dict(value)
    A.hash_value(body.pop("contentSha256"), "task seal")
    A.require(A.digest(body) == value["contentSha256"], "task content hash differs")
    A.identifier(value["rowId"], "rowId")
    A.require(value["task"] == "understander", "unsupported typed task")
    inputs = value["input"]
    A.fields(inputs, {"catalogue", "context", "sourceImportSha256", "utteranceRoles"}, "task input")
    imported = imported or (evidence or E.Store()).read(inputs["sourceImportSha256"])
    capture = validate_import(imported)["capture"]
    A.require(inputs["sourceImportSha256"] == imported["contentSha256"], "source import differs")
    A.require(A.digest(inputs["catalogue"]) == A.digest(capture["catalogue"])
              and A.digest(inputs["context"]) == A.digest(capture["context"]), "task input differs from capture")
    A.require(inputs["utteranceRoles"] == {"speakerRef": capture["context"]["listenerRef"],
                                           "listenerRef": capture["context"]["personId"]},
              "utterance roles differ")
    frame = value["output"]
    A.fields(frame, {"speechAct", "claimRefs", "requestedAction", "stance", "uncertainty", "listenerRef"},
             "understander frame")
    A.require(isinstance(frame["speechAct"], str)
              and frame["speechAct"] in {"question", "statement", "request", "offer", "threat"},
              "unknown speech act")
    _, refs = R.validate_catalogue(inputs["catalogue"])
    required = R.ordered_refs(frame["claimRefs"], "frame claimRefs")
    A.require(required == [ref for ref in refs if ref in required], "unknown or unordered task claim")
    A.require(value["requiredClaimRefs"] == required, "required claims differ from frame")
    # C77 captures knowledge, not executable options. Action-bearing frames
    # require a future source contract supplying exact executable references.
    A.require(frame["requestedAction"] is None, "capture has no executable-action evidence")
    A.require(frame["listenerRef"] == inputs["utteranceRoles"]["listenerRef"], "intended listener differs")
    A.fields(frame["stance"], {"label", "targetRef"}, "directed stance")
    A.identifier(frame["stance"]["label"], "stance label")
    A.require(frame["stance"]["targetRef"] == frame["listenerRef"], "stance target differs")
    A.require(J.finite_number(frame["uncertainty"]) and 0 <= frame["uncertainty"] <= 1,
              "uncertainty must be finite in [0,1]")
    return value


def task_conditioning(row, evidence=None):
    validate_task(row, evidence)
    return {"status": "ineligible", "exclusions": [
        "authored-bodyless-capture-has-unavailable-native-inputs",
        "task-dataset-splits-and-evaluation-not-built"]}


def save_evidence(value, root=None):
    A.require(isinstance(value, dict), "evidence must be an object")
    body = dict(value)
    declared = body.pop("contentSha256", None)
    digest = A.digest(body)
    A.require("contentSha256" not in value or declared == digest,
              "evidence content hash differs")
    root = Path(root) if root is not None else E.ROOT
    root.mkdir(parents=True, exist_ok=True)
    path = root / (digest + ".json")
    data = A.encoded(value) + b"\n"
    if path.exists():
        A.require(A.digest(A.read(path)) == A.digest(value), "evidence collision")
        return digest
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=root, suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        # Atomic publication without replacement, including concurrent writers.
        try:
            os.link(temporary, path)
        except FileExistsError:
            A.require(A.digest(A.read(path)) == A.digest(value), "evidence collision")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return digest


def approve(row, receipt_hash, snapshot_id, evidence=None):
    evidence = evidence or E.Store()
    validate_task(row, evidence)
    evidence.decision(receipt_hash, row["contentSha256"])
    A.identifier(snapshot_id, "task snapshot ID")
    return A.seal({"schema": "speakeasy-task-evidence-snapshot", "schemaVersion": 1,
                   "snapshotId": snapshot_id, "task": "understander", "rows": [{
                       "rowId": row["rowId"], "rowContentSha256": row["contentSha256"],
                       "approvalReceiptSha256": receipt_hash}]})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-task", type=Path)
    mode.add_argument("--import-source")
    mode.add_argument("--approve-task", type=Path)
    parser.add_argument("--sao-root", type=Path)
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--receipt-hash")
    parser.add_argument("--snapshot-id")
    parser.add_argument("--evidence-root", type=Path, default=E.ROOT)
    args = parser.parse_args()
    try:
        evidence = E.Store(args.evidence_root)
        if args.import_source:
            A.require(args.sao_root is not None and args.game_root is not None,
                      "import requires --sao-root and --game-root")
            names = ("projectzomboid.jar", "stdlib.lua", "media/lua/shared/TimedActions/ISReadABook.lua")
            value = import_capture(args.sao_root, args.import_source,
                                   {"installed/" + p: args.game_root / p for p in names})
            print("Verified source import: " + save_evidence(value, args.evidence_root))
        elif args.approve_task:
            value = approve(A.read(args.approve_task), args.receipt_hash, args.snapshot_id, evidence)
            print("Approved task evidence snapshot: " + save_evidence(value, args.evidence_root))
        else:
            row = validate_task(A.read(args.validate_task), evidence)
            print("Valid typed proposal; approval remains independent: " + row["contentSha256"])
    except (J.ContractError, OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, "REFUSED: " + str(error) + "\n")


if __name__ == "__main__":
    main()
