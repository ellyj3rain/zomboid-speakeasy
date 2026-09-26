#!/usr/bin/env python3
"""Compile authored coordination scenes for operator review before admission.

Scene coordinates and time are illustrations. The decision input is explicit;
neither a scene frame nor a proposed answer is an observed simulation result.
Mousecat owns presentation and evaluation. Existing evidence owners verify its
exact returned decision before this module can emit an offline teaching row.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys

import coordination_data as Data
import coordination_tasks as Tasks
import cross_module_rows as Join
import decision_authoring as A
import training_evidence as Evidence

SCENARIO = "speakeasy-authored-coordination-scenario"
REVIEW = "speakeasy-scenario-teaching-review"
ROW = "speakeasy-approved-teaching-row"
SCOPE = "offline-coordination-response-kind"
EFFECTS = [
    "Admit this exact authored situation and proposed response kind as one offline teaching example.",
    "Keep the scene, rationale and authorship available for audit and outside the learned input.",
]
EXCLUSIONS = [
    "This is an authored hypothetical, not a recorded simulation or a population frequency estimate.",
    "The response is a teaching proposal; no later action, delivery or outcome is asserted.",
    "Approval does not approve response wording, execution terms, evaluation quality or a game runtime model.",
]


def text(value, where, maximum=4096):
    A.require(isinstance(value, str) and value == value.strip()
              and 0 < len(value) <= maximum, f"{where} must be bounded nonempty text")
    return value


def sequence(value, where, maximum, minimum=1):
    A.require(isinstance(value, list) and minimum <= len(value) <= maximum,
              f"{where} requires {minimum}-{maximum} entries")
    return value


def unique_records(value, where, maximum):
    sequence(value, where, maximum)
    A.require(all(isinstance(row, dict) for row in value), where + " requires records")
    ids = [text(row.get("id"), where + " id", 80) for row in value]
    A.require(len(ids) == len(set(ids)), where + " ids must be unique")
    return {row["id"]: row for row in value}


def validate_input(value):
    """Reuse the production task's appraisal rules without claiming production provenance."""
    A.fields(value, {"schema", "schemaVersion", "route", "process", "actor",
                     "decisionTime"}, "teaching input")
    A.schema(value, "speakeasy-coordination-response-input")
    A.require(value["route"] == "coordination-response", "unsupported teaching route")
    A.fields(value["process"], {"kind"}, "process")
    text(value["process"]["kind"], "process kind", 80)
    actor = value["actor"]
    A.fields(actor, {"executor", "bodyOwner"}, "execution identity")
    decision = value["decisionTime"]
    A.fields(decision, {"proposal", "reception", "currentWork", "competingPriorities",
                       "capabilities", "feasibleOptions"}, "decision input")
    proposal = decision["proposal"]
    Tasks.fields(proposal, {"purpose", "scope", "requiredCapabilities"},
                 {"purpose", "scope", "requiredCapabilities", "destination"}, "proposal")
    text(proposal["purpose"], "proposal purpose", 320)
    A.fields(proposal["scope"], {"category", "quantity"}, "proposal scope")
    text(proposal["scope"]["category"], "proposal category", 80)
    Tasks.finite(proposal["scope"]["quantity"], "proposal quantity")
    A.require(proposal["scope"]["quantity"] > 0, "proposal quantity must be positive")
    if "destination" in proposal:
        destination = proposal["destination"]
        A.fields(destination, {"minX", "maxX", "minY", "maxY", "z"}, "destination")
        for key, number in destination.items():
            Tasks.finite(number, "destination " + key)
        A.require(destination["minX"] <= destination["maxX"]
                  and destination["minY"] <= destination["maxY"], "destination bounds reversed")
    reception = decision["reception"]
    A.fields(reception, {"channel", "evidence"}, "authored reception")
    A.require(reception["channel"] == "spoken"
              and reception["evidence"] == {"kind": "authored-hypothesis"},
              "authored reception must declare its hypothetical basis")
    A.fields(decision["currentWork"], {"activity", "owner"}, "current work")
    priorities = decision["competingPriorities"]
    A.fields(priorities, {"competingPressure", "relationship", "interests", "constraints",
                         "owners"}, "competing priorities")
    pressure = priorities["competingPressure"]
    A.fields(pressure, {"value", "available", "owner"}, "competing pressure")
    A.require(type(pressure["available"]) is bool, "pressure availability must be boolean")
    if pressure["available"]:
        Tasks.finite(pressure["value"], "competing pressure")
    else:
        A.require(pressure["value"] is None, "unavailable pressure must be null")
    A.fields(priorities["owners"], {"ownNeed", "relationship", "interests", "constraints"},
             "priority owners")
    A.require(pressure["owner"] == priorities["owners"]["ownNeed"], "pressure owner differs")
    capabilities = decision["capabilities"]
    A.fields(capabilities, {"values", "owner", "availability"}, "capabilities")
    options = sequence(decision["feasibleOptions"], "feasible responses", 7)
    owners = {**priorities["owners"], "currentActivity": decision["currentWork"]["owner"],
              "capabilities": capabilities["owner"]}
    private = {"owner": "authored-hypothesis", **actor,
               "currentActivity": decision["currentWork"]["activity"],
               "capabilities": capabilities["values"], "constraints": priorities["constraints"],
               "interests": priorities["interests"], "inputOwners": owners,
               "relationship": priorities["relationship"], "ownNeed": pressure["value"] or 0,
               "destinationKnown": "destination" in proposal, "feasibleOptions": options,
               "choice": options[0], "reconsider": False}
    Tasks.private_appraisal(private, proposal, "authored-actor")
    A.require(pressure["available"] == priorities["constraints"]["ownNeedAvailable"],
              "pressure availability differs from constraints")
    expected = "available" if priorities["constraints"]["executionOwnerAvailable"] else "unavailable"
    A.require(capabilities["availability"] == expected, "capability availability differs")
    forbidden = Tasks.HIDDEN_PRIVATE_CONSTRAINT_FIELDS | {
        "choice", "laterOutcome", "actorKind", "sourceLineage", "split", "rationale", "target"}
    A.require(not (forbidden & Tasks.nested_field_names(value)), "hidden or teaching fields in input")
    A.require(Data.model_input(value) == value, "input differs from shared coordination projection")
    return value


def validate_scenario(value):
    A.unseal(value, SCENARIO)
    A.fields(value, {"schema", "schemaVersion", "id", "lineageId", "revision", "title",
                     "summary", "authorship", "scene", "decision", "teaching", "contentSha256"},
             "authored scenario")
    for key, maximum in {"id": 80, "lineageId": 160, "title": 320,
                         "summary": 4096, "authorship": 1024}.items():
        text(value[key], key, maximum)
    A.require(type(value["revision"]) is int and value["revision"] > 0, "invalid scenario revision")
    scene = value["scene"]
    A.fields(scene, {"coordinateSystem", "locations", "actors", "frames"}, "scene")
    A.require(scene["coordinateSystem"] == "schematic", "scene coordinates must be schematic")
    locations = unique_records(scene["locations"], "locations", 24)
    for location in locations.values():
        A.fields(location, {"id", "label", "x", "y"}, "location")
        text(location["label"], "location label", 96)
        for coordinate in (location["x"], location["y"]):
            Tasks.finite(coordinate, "schematic coordinate")
            A.require(0 <= coordinate <= 100, "schematic coordinates must be within 0-100")
    actors = unique_records(scene["actors"], "actors", 12)
    for actor in actors.values():
        A.fields(actor, {"id", "label"}, "actor")
        text(actor["label"], "actor label", 96)
    frames = unique_records(scene["frames"], "frames", 24)
    previous = -1
    for frame in frames.values():
        A.fields(frame, {"id", "label", "elapsedSeconds", "states", "communications"}, "frame")
        text(frame["label"], "frame label", 160)
        Tasks.finite(frame["elapsedSeconds"], "frame time")
        A.require(frame["elapsedSeconds"] > previous, "frame times must increase from zero or later")
        previous = frame["elapsedSeconds"]
        sequence(frame["states"], "actor states", 12)
        state_ids = [state.get("actorId") for state in frame["states"]]
        A.require(len(state_ids) == len(set(state_ids)) and set(state_ids) == set(actors),
                  "each frame must represent every actor exactly once")
        for state in frame["states"]:
            A.fields(state, {"actorId", "locationId", "activity", "knowledge"}, "actor state")
            A.require(state["locationId"] in locations, "actor location absent")
            text(state["activity"], "actor activity", 320)
            for fact in sequence(state["knowledge"], "personal knowledge", 16, 0):
                text(fact, "personal knowledge", 1024)
        sequence(frame["communications"], "communications", 24, 0)
        ids = set()
        for communication in frame["communications"]:
            A.fields(communication, {"id", "fromId", "toId", "status", "summary"}, "communication")
            cid = text(communication["id"], "communication id", 80)
            A.require(cid not in ids, "duplicate communication")
            ids.add(cid)
            A.require(communication["fromId"] in actors and communication["toId"] in actors
                      and communication["fromId"] != communication["toId"], "communication actor absent")
            A.require(communication["status"] in ("heard", "unheard"), "invalid reception status")
            text(communication["summary"], "communication summary", 1024)
    decision = value["decision"]
    A.fields(decision, {"frameId", "actorId", "communicationId", "input"}, "scenario decision")
    A.require(decision["frameId"] == scene["frames"][-1]["id"],
              "preview must stop at the decision; later outcomes need a separate observation")
    frame = frames[decision["frameId"]]
    A.require(decision["actorId"] in actors, "decision actor absent")
    communications = [row for row in frame["communications"] if row["id"] == decision["communicationId"]]
    A.require(len(communications) == 1 and communications[0]["toId"] == decision["actorId"]
              and communications[0]["status"] == "heard", "decision requires an explicitly heard proposal")
    validate_input(decision["input"])
    state = next(row for row in frame["states"] if row["actorId"] == decision["actorId"])
    A.require(state["activity"] == decision["input"]["decisionTime"]["currentWork"]["activity"],
              "scene activity differs from model input")
    A.fields(value["teaching"], {"response", "rationale"}, "teaching proposal")
    A.require(value["teaching"]["response"] in decision["input"]["decisionTime"]["feasibleOptions"],
              "teaching response is not feasible")
    text(value["teaching"]["rationale"], "teaching rationale")
    A.require(len(A.encoded(value)) <= 48 * 1024, "scenario exceeds preview size limit")
    return value


def review_subject(scenario):
    validate_scenario(scenario)
    return A.seal({"schema": REVIEW, "schemaVersion": 1, "scenario": scenario,
                   "modelInputSha256": A.digest(scenario["decision"]["input"]),
                   "targetScope": SCOPE, "approvalEffects": EFFECTS,
                   "remainingExclusions": EXCLUSIONS})


def validate_review(value):
    A.unseal(value, REVIEW)
    A.require(value == review_subject(value["scenario"]), "review differs from exact scenario and scope")
    return value


def scene_preview(subject):
    validate_review(subject)
    scenario = subject["scenario"]
    preview = {"schema": "mousecat.scene-preview/1",
            "provenance": {"kind": "authored", "label": scenario["authorship"]},
            **copy.deepcopy(scenario["scene"]),
            "decision": {key: scenario["decision"][key] for key in ("frameId", "actorId")}}
    A.require(len(A.encoded(preview)) <= 40 * 1024, "scene exceeds Mousecat preview size limit")
    return preview


def review_invocation(subject, session_id, invocation_id, occurred_at):
    validate_review(subject)
    scenario = subject["scenario"]
    value = scenario["decision"]["input"]
    fields = [("Process", value["process"]), ("Execution ownership", value["actor"])]
    fields.extend((key, entry) for key, entry in value["decisionTime"].items())
    actual = [{"label": label, "value": json.dumps(entry, ensure_ascii=False, sort_keys=True)}
              for label, entry in fields]
    A.require(all(len(entry["value"]) <= 4096 for entry in actual),
              "input exceeds Mousecat review field size")
    packet = {
        "action": "invoke", "skillRef": "crucible", "frameworkRef": "recursive-deliberation",
        "projectRef": "project:zomboid-speakeasy",
        "source": {"host": "codex", "sessionId": text(session_id, "session id"),
                   "invocationId": text(invocation_id, "invocation id")},
        "title": "Evaluate a teaching scenario",
        "intake": {"seams": [{
            "id": scenario["id"] + "-r" + str(scenario["revision"]),
            "occurredAt": text(occurred_at, "review time"), "shape": "decision",
            "title": scenario["title"],
            "prompt": "Does this situation and proposed response make a useful teaching example?",
            "evidenceRef": "speakeasy:content-sha256:" + subject["contentSha256"],
            "selectionMode": "single", "allowFreeform": True,
            "options": [
                {"label": "Approve this example", "value": "approved",
                 "description": "Admit only this exact authored situation and response kind for offline teaching."},
                {"label": "Revise this example", "value": "revision-requested",
                 "description": "Keep it out of the dataset and describe the situation or response you want corrected."},
                {"label": "Reject this example", "value": "rejected",
                 "description": "Keep this example out of the dataset."}],
            "mlReview": {
                "schema": "mousecat.ml-review/1", "subject": scenario["title"],
                "scenario": scenario["summary"], "scenePreview": scene_preview(subject),
                "systemRole": "Speakeasy supplies explicit decision-time inputs and a proposed response kind. The scene is review context; its animation, names and narrative are not learned input.",
                "causalPath": [
                    {"label": "Authored situation", "value": "Inspect the people, their activities and their available information before and at contact."},
                    {"label": "Your evaluation", "value": "Evaluate the situation together with the proposed response. Corrections create a new exact review."},
                    {"label": "Offline teaching", "value": "An unqualified approval allows one input/response example. Later training and runtime evaluation remain separate work."}],
                "playerImpact": "This teaches individual responses to requests from current circumstances. The preview stops at the decision and establishes no completed work or successful cooperation.",
                "decisionPrecedent": "Your answer governs this exact scenario revision and proposed response. A change to the scene, input or target requires your evaluation again.",
                "actualInput": actual,
                "proposedLearning": [{"label": "Proposed response: " + scenario["teaching"]["response"],
                                      "value": scenario["teaching"]["rationale"]}],
                "approvalEffects": list(EFFECTS), "remainingExclusions": list(EXCLUSIONS),
                "evidence": [{"label": "Exact scenario and target", "value": subject["contentSha256"]},
                             {"label": "Exact model input", "value": subject["modelInputSha256"]}],
            },
        }]},
    }
    context = packet["intake"]["seams"][0]["mlReview"]
    A.require(len(A.encoded(context)) <= 48 * 1024, "review exceeds Mousecat context size limit")
    return packet


def admit(subject, receipt, store):
    """A saved operator result is required; an authored approval Boolean has no standing."""
    validate_review(subject)
    A.hash_value(receipt, "review receipt")
    store.decision(receipt, subject["contentSha256"])
    scenario = subject["scenario"]
    return A.seal({"schema": ROW, "schemaVersion": 1,
                   "rowId": scenario["id"] + ":" + str(scenario["revision"]),
                   "sourceLineage": scenario["lineageId"],
                   "input": copy.deepcopy(scenario["decision"]["input"]),
                   "target": {"response": scenario["teaching"]["response"]},
                   "provenance": {"kind": "authored", "scenarioSha256": scenario["contentSha256"],
                                  "reviewSubjectSha256": subject["contentSha256"],
                                  "approvalReceiptSha256": receipt},
                   "admission": {"scope": SCOPE, "status": "approved-offline-teaching"}})


def write_new(path, value):
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False).encode("utf-8") + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(payload)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    preview = sub.add_parser("preview")
    preview.add_argument("--scenario", type=Path, required=True)
    preview.add_argument("--out", type=Path, required=True)
    check = sub.add_parser("validate")
    check.add_argument("path", type=Path)
    admission = sub.add_parser("admit")
    admission.add_argument("--review", type=Path, required=True)
    admission.add_argument("--receipt", required=True)
    admission.add_argument("--evidence-root", type=Path, default=Evidence.ROOT)
    admission.add_argument("--out", type=Path, required=True)
    invocation = sub.add_parser("review")
    invocation.add_argument("--review", type=Path, required=True)
    invocation.add_argument("--session-id", required=True)
    invocation.add_argument("--invocation-id", required=True)
    invocation.add_argument("--occurred-at", required=True)
    invocation.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "preview":
            value = review_subject(A.read(args.scenario))
            write_new(args.out, value)
        elif args.command == "validate":
            value = A.read(args.path)
            (validate_review if value.get("schema") == REVIEW else validate_scenario)(value)
        elif args.command == "review":
            value = review_invocation(A.read(args.review), args.session_id,
                                      args.invocation_id, args.occurred_at)
            write_new(args.out, value)
        else:
            value = admit(A.read(args.review), args.receipt, Evidence.Store(args.evidence_root))
            write_new(args.out, value)
    except (Join.ContractError, OSError, ValueError, TypeError, KeyError) as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 2
    print(value.get("schema", "mousecat.skill invocation") + ": " + value.get("contentSha256", A.digest(value)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
