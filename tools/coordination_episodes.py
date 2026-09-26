#!/usr/bin/env python3
"""Validate causal SAO episodes and compile their coordination observations.

The episode remains the unit of provenance even when it contains no decision.
Decision rows are projected through the explicitly supplied ZAO owner, joined
on the complete v3 namespace, and compiled by the existing coordination task
contract.  C85 process observations retain the public path from a raised matter
through contact, reception, response and enacted work, so a zero-decision run
still identifies the first unobserved stage without exposing actor-private
inputs.  Every output remains a candidate observation; this tool performs no
review, dataset admission, training, or runtime activation.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import ModuleType
from typing import Any

import coordination_tasks as Tasks
import cross_module_rows as Join


SCHEMA = "speakeasy-causal-episode-intake"
VERSION = 2
EPISODE_FIELDS = {
    "schema", "schemaVersion", "episodeId", "horizonDays", "seed",
    "drawCount", "checkpoints", "trajectory", "terminal", "source",
    "standing", "exclusions", "replay", "episodeSha256",
}
LEGACY_TRAJECTORY_FIELDS = {
    "dailySnapshots", "socialEvents", "companies", "deathCauses",
    "decisionCapture",
}
TRAJECTORY_FIELDS = LEGACY_TRAJECTORY_FIELDS | {"processObservation"}
CAPTURE_FIELDS = {
    "schema", "schemaVersion", "status", "attemptedEvents", "eventCount",
    "captureFailureCount", "failures", "events",
}
PROCESS_OBSERVATION_FIELDS = {
    "schema", "schemaVersion", "processCount", "kindCounts", "statusCounts",
    "addressedCount", "receptionCount", "responseCount",
    "returnedResponseCount", "currentUnheardCount", "currentUnansweredCount",
    "contactAttemptCount", "contactArrivalCount", "activeContactAttemptCount",
    "contactOutcomeCounts", "contactOwnerCounts", "responseCounts", "processes",
}
PROCESS_REQUIRED_FIELDS = {
    "processId", "kind", "originatorId", "originatorBodyOwner", "status",
    "revision", "revisionCount", "addressedCount", "currentReceivedCount",
    "currentRespondedCount", "currentUnheardCount", "currentUnansweredCount",
    "receptionCount", "responseCount", "returnedResponseCount", "responses",
    "commitments", "workOutcomes", "contactAttemptCount",
    "contactArrivalCount", "activeContactAttemptCount", "contactOutcomes",
    "contactOwners", "eventCount",
}
PROCESS_OPTIONAL_FIELDS = {
    "organizationId", "createdAt", "revisedAt", "closedAt", "closureReason",
}
PROCESS_COUNT_FIELDS = (
    "addressedCount", "currentReceivedCount", "currentRespondedCount",
    "currentUnheardCount", "currentUnansweredCount", "receptionCount",
    "responseCount", "returnedResponseCount", "contactAttemptCount",
    "contactArrivalCount", "activeContactAttemptCount", "eventCount",
)
PROCESS_MAP_FIELDS = (
    "responses", "commitments", "workOutcomes", "contactOutcomes",
    "contactOwners",
)
PUBLIC_PROGRESSION = (
    ("matter", "processCount"),
    ("addressing", "addressedCount"),
    ("contact-attempt", "contactAttemptCount"),
    ("address-arrival", "contactArrivalCount"),
    ("reception", "receptionCount"),
    ("response", "responseCount"),
    ("returned-response", "returnedResponseCount"),
    ("commitment", "commitmentCount"),
    ("work-outcome", "workOutcomeCount"),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Join.ContractError(message)


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise Join.ContractError(f"non-canonical episode value: {error}") from error


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def compiler_sha256(path: Path) -> str:
    """Bind compiler text independently of Git's checkout newline policy."""
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def finite(value: Any, where: str) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value), f"{where} must be finite")
    return float(value)


def nonnegative_integer(value: Any, where: str) -> int:
    require(type(value) is int and value >= 0,
            f"{where} must be a nonnegative integer")
    return value


def count_map(value: Any, where: str) -> dict[str, int]:
    require(isinstance(value, dict), f"{where} must be an object")
    output: dict[str, int] = {}
    for key, count in value.items():
        require(Join.nonempty_string(key), f"{where} has an unnamed key")
        require(key not in Tasks.HIDDEN_PRIVATE_CONSTRAINT_FIELDS,
                f"{where} contains a private field: {key}")
        output[key] = nonnegative_integer(count, f"{where}.{key}")
    return output


def add_counts(target: dict[str, int], source: dict[str, int]) -> None:
    for key, value in source.items():
        target[key] = target.get(key, 0) + value


def first_unobserved_stage(counts: dict[str, int]) -> str | None:
    """Return the start of the terminal zero suffix after observed progress.

    Some process kinds can bypass physical contact, so an internal zero followed
    by a later nonzero value is not called a break.  This reports only the first
    stage after which this episode observed nothing further.
    """
    values = [counts[field] for _, field in PUBLIC_PROGRESSION]
    if not any(values):
        return "matter"
    for index, (name, _) in enumerate(PUBLIC_PROGRESSION):
        if values[index] == 0 and any(values[:index]) and not any(values[index:]):
            return name
    return None


def validate_process_observation(value: Any, where: str) -> dict[str, Any]:
    require(isinstance(value, dict) and set(value) == PROCESS_OBSERVATION_FIELDS,
            f"{where}: process observation fields differ")
    require(value["schema"] == "sao-shared-process-observation"
            and type(value["schemaVersion"]) is int
            and value["schemaVersion"] == 1,
            f"{where}: requires sao-shared-process-observation version 1")
    # The producer's Lua encoder writes an empty table as an object. Preserve
    # the sealed source bytes and normalize only this local iteration view.
    processes = Tasks.lua_sequence(value["processes"], f"{where}: processes")
    nonnegative_integer(value["processCount"], f"{where}.processCount")
    require(value["processCount"] == len(processes),
            f"{where}: processCount differs from processes")

    aggregate = {field: 0 for field in PROCESS_COUNT_FIELDS}
    aggregate_maps = {field: {} for field in PROCESS_MAP_FIELDS}
    kinds: dict[str, int] = {}
    statuses: dict[str, int] = {}
    originator_owners: dict[str, int] = {}
    process_ids: set[str] = set()
    for index, process in enumerate(processes):
        item_where = f"{where}.processes[{index}]"
        require(isinstance(process, dict)
                and PROCESS_REQUIRED_FIELDS <= set(process)
                and set(process) <= PROCESS_REQUIRED_FIELDS | PROCESS_OPTIONAL_FIELDS,
                f"{item_where}: process fields differ")
        for field in ("processId", "kind", "originatorId",
                      "originatorBodyOwner", "status"):
            require(Join.nonempty_string(process[field]),
                    f"{item_where}.{field} must be nonempty")
        require(process["processId"] not in process_ids,
                f"{item_where}: duplicate processId {process['processId']}")
        process_ids.add(process["processId"])
        require(type(process["revision"]) is int and process["revision"] >= 1
                and type(process["revisionCount"]) is int
                and process["revisionCount"] >= process["revision"],
                f"{item_where}: revision standing differs")
        for field in PROCESS_COUNT_FIELDS:
            aggregate[field] += nonnegative_integer(
                process[field], f"{item_where}.{field}")
        for field in PROCESS_MAP_FIELDS:
            counts = count_map(process[field], f"{item_where}.{field}")
            add_counts(aggregate_maps[field], counts)
        for field in PROCESS_OPTIONAL_FIELDS & set(process):
            if field.endswith("At"):
                finite(process[field], f"{item_where}.{field}")
            else:
                require(Join.nonempty_string(process[field]),
                        f"{item_where}.{field} must be nonempty")

        require(process["currentReceivedCount"] + process["currentUnheardCount"]
                == process["addressedCount"],
                f"{item_where}: current heard/unheard counts differ")
        require(process["currentRespondedCount"]
                + process["currentUnansweredCount"]
                == process["currentReceivedCount"],
                f"{item_where}: current response/unanswered counts differ")
        require(process["returnedResponseCount"] <= process["responseCount"],
                f"{item_where}: returned responses exceed responses")
        require(process["currentReceivedCount"] <= process["receptionCount"]
                and process["currentRespondedCount"] <= process["responseCount"]
                and process["responseCount"] <= process["receptionCount"],
                f"{item_where}: current and retained response counts differ")
        require(process["contactArrivalCount"] <= process["contactAttemptCount"]
                and process["activeContactAttemptCount"]
                <= process["contactAttemptCount"],
                f"{item_where}: contact progression counts differ")
        require(sum(process["responses"].values()) == process["responseCount"],
                f"{item_where}: response map differs")
        require(sum(process["contactOutcomes"].values())
                == process["contactAttemptCount"],
                f"{item_where}: contact outcome map differs")
        require(sum(process["contactOwners"].values())
                == process["contactAttemptCount"],
                f"{item_where}: contact owner map differs")
        require(process["activeContactAttemptCount"]
                == sum(process["contactOutcomes"].get(status, 0)
                       for status in ("travelling", "waiting")),
                f"{item_where}: active contact count differs from outcomes")
        kinds[process["kind"]] = kinds.get(process["kind"], 0) + 1
        statuses[process["status"]] = statuses.get(process["status"], 0) + 1
        owner = process["originatorBodyOwner"]
        originator_owners[owner] = originator_owners.get(owner, 0) + 1

    top_counts = {
        field: nonnegative_integer(value[field], f"{where}.{field}")
        for field in (
            "addressedCount", "receptionCount", "responseCount",
            "returnedResponseCount", "currentUnheardCount",
            "currentUnansweredCount", "contactAttemptCount",
            "contactArrivalCount", "activeContactAttemptCount",
        )
    }
    for field, count in top_counts.items():
        require(count == aggregate[field], f"{where}: {field} aggregate differs")
    require(count_map(value["kindCounts"], f"{where}.kindCounts") == kinds,
            f"{where}: kindCounts aggregate differs")
    require(count_map(value["statusCounts"], f"{where}.statusCounts") == statuses,
            f"{where}: statusCounts aggregate differs")
    for top, child in (("responseCounts", "responses"),
                       ("contactOutcomeCounts", "contactOutcomes"),
                       ("contactOwnerCounts", "contactOwners")):
        require(count_map(value[top], f"{where}.{top}") == aggregate_maps[child],
                f"{where}: {top} aggregate differs")

    counts = {
        "processCount": len(processes),
        **top_counts,
        "currentReceivedCount": aggregate["currentReceivedCount"],
        "currentRespondedCount": aggregate["currentRespondedCount"],
        "commitmentCount": sum(aggregate_maps["commitments"].values()),
        "workOutcomeCount": sum(aggregate_maps["workOutcomes"].values()),
    }
    return {
        "available": True,
        "counts": counts,
        "firstUnobservedStage": first_unobserved_stage(counts),
        "kindCounts": kinds,
        "statusCounts": statuses,
        "originatorOwnerCounts": originator_owners,
        "responseCounts": aggregate_maps["responses"],
        "commitmentCounts": aggregate_maps["commitments"],
        "workOutcomeCounts": aggregate_maps["workOutcomes"],
        "contactOutcomeCounts": aggregate_maps["contactOutcomes"],
        "contactOwnerCounts": aggregate_maps["contactOwners"],
        "processIds": sorted(process_ids),
    }


def read_episodes(path: Path) -> list[dict[str, Any]]:
    require(path.is_file(), f"episode input is not a file: {path}")
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as error:
                    raise Join.ContractError(
                        f"{path}:{line_number}: invalid JSON: {error.msg}") from error
                require(isinstance(row, dict),
                        f"{path}:{line_number}: episode must be an object")
                rows.append(row)
    except UnicodeError as error:
        raise Join.ContractError(f"{path}: episode input is not UTF-8") from error
    require(bool(rows), f"{path}: episode input contains no rows")
    return rows


def validate_episode(row: dict[str, Any], path: Path, line: int) -> tuple[
        dict[str, Any], list[dict[str, Any]]]:
    where = f"{path}:{line}"
    require(set(row) == EPISODE_FIELDS,
            f"{where}: episode fields differ: "
            f"missing={sorted(EPISODE_FIELDS - set(row))} "
            f"extra={sorted(set(row) - EPISODE_FIELDS)}")
    require(row["schema"] == "sao-causal-episode"
            and row["schemaVersion"] == 1,
            f"{where}: requires sao-causal-episode schema version 1")
    episode_id = row["episodeId"]
    require(Join.nonempty_string(episode_id),
            f"{where}: episodeId must be nonempty")
    horizon = row["horizonDays"]
    require(type(horizon) is int and horizon > 0,
            f"{where}: horizonDays must be a positive integer")
    require(Join.nonempty_string(row["seed"]), f"{where}: seed must be nonempty")
    require(type(row["drawCount"]) is int and row["drawCount"] >= 0,
            f"{where}: drawCount must be a nonnegative integer")
    require(row["standing"] == "candidate-observation",
            f"{where}: episode standing must remain candidate-observation")
    require(isinstance(row["exclusions"], list)
            and all(Join.nonempty_string(value) for value in row["exclusions"]),
            f"{where}: exclusions must be a string list")

    sealed = copy.deepcopy(row)
    seal = sealed.pop("episodeSha256")
    require(isinstance(seal, str) and seal == digest(sealed),
            f"{where}: episode content seal differs")

    replay = row["replay"]
    require(isinstance(replay, dict)
            and replay.get("exact") is True
            and replay.get("runs") == 2
            and Join.nonempty_string(replay.get("reset"))
            and Join.nonempty_string(replay.get("comparison"))
            and isinstance(replay.get("simulationSha256"), str)
            and len(replay["simulationSha256"]) == 64,
            f"{where}: isolated exact replay evidence is incomplete")

    trajectory = row["trajectory"]
    require(isinstance(trajectory, dict)
            and set(trajectory) in (LEGACY_TRAJECTORY_FIELDS, TRAJECTORY_FIELDS),
            f"{where}: trajectory fields differ")
    snapshots = trajectory["dailySnapshots"]
    require(isinstance(snapshots, dict), f"{where}: dailySnapshots must be an object")
    checkpoints = row["checkpoints"]
    require(isinstance(checkpoints, list) and checkpoints,
            f"{where}: checkpoints must be nonempty")
    days: list[int] = []
    observed_hours: list[float] = []
    for index, checkpoint in enumerate(checkpoints):
        require(isinstance(checkpoint, dict) and set(checkpoint) == {"day", "snapshot"},
                f"{where}: checkpoint {index} fields differ")
        day, snapshot = checkpoint["day"], checkpoint["snapshot"]
        require(type(day) is int and 0 <= day <= horizon,
                f"{where}: checkpoint {index} day is outside the horizon")
        require(isinstance(snapshot, dict)
                and snapshot.get("completedDay") == day
                and snapshots.get(str(day)) == snapshot,
                f"{where}: checkpoint {day} is not the recorded causal prefix")
        days.append(day)
        observed_hours.append(finite(snapshot.get("observedHour"),
                                     f"{where}: checkpoint {day} observedHour"))
    require(days == sorted(set(days)) and days[0] == 0 and days[-1] == horizon,
            f"{where}: checkpoints must be unique, ordered, and include start/finish")
    require(observed_hours == sorted(observed_hours),
            f"{where}: checkpoint observation time moved backwards")

    source = row["source"]
    require(isinstance(source, dict)
            and source.get("saveName") == episode_id
            and source.get("requestedDays") == horizon
            and isinstance(source.get("jointPathogen"), bool),
            f"{where}: episode source identity/horizon is inconsistent")
    terminal = row["terminal"]
    require(isinstance(terminal, dict)
            and terminal.get("alive") == checkpoints[-1]["snapshot"].get("alive")
            and terminal.get("dead") == checkpoints[-1]["snapshot"].get("dead"),
            f"{where}: terminal population differs from the final checkpoint")

    capture = trajectory["decisionCapture"]
    require(isinstance(capture, dict)
            and set(capture) in (CAPTURE_FIELDS,
                                 CAPTURE_FIELDS | {"processObservation"})
            and capture.get("schema") == "sao-coordination-decision-capture"
            and capture.get("schemaVersion") == 1
            and capture.get("status") == "observed",
            f"{where}: decision capture is unavailable")
    events = capture.get("events")
    require(isinstance(events, list), f"{where}: decision events must be a list")
    require(capture.get("eventCount") == len(events)
            and type(capture.get("attemptedEvents")) is int
            and capture["attemptedEvents"] >= len(events)
            and capture.get("captureFailureCount") == 0
            and capture.get("failures") in ([], {}),
            f"{where}: decision capture counts or failures differ")
    namespaces: set[tuple[Any, ...]] = set()
    process_summary = ({"available": False, "reason": "legacy-source-omitted"}
                       if "processObservation" not in trajectory else
                       validate_process_observation(
                           trajectory["processObservation"],
                           f"{where}.trajectory.processObservation"))
    if process_summary["available"]:
        require(capture.get("processObservation")
                == trajectory["processObservation"],
                f"{where}: process observation copies differ")
    else:
        require("processObservation" not in capture,
                f"{where}: capture-only process observation is unsupported")
    observed_processes = set(process_summary.get("processIds", []))
    captured_responses: set[tuple[Any, ...]] = set()
    captured_by_process: dict[str, int] = {}
    for event_index, event in enumerate(events, 1):
        key = Join.validate_sao_row(event, path, line)
        require(key[0] == episode_id and key[1] == episode_id,
                f"{where}: decision {event_index} run/county differs from episode")
        hour = finite(key[-1], f"{where}: decision {event_index} hour")
        require(0 <= hour <= horizon * 24,
                f"{where}: decision {event_index} lies outside the episode horizon")
        require(key not in namespaces,
                f"{where}: duplicate decision namespace {key!r}")
        if process_summary["available"]:
            enacted = event.get("enactedProcess", {})
            process_id = enacted.get("processId")
            require(process_id in observed_processes,
                    f"{where}: decision {event_index} process is not observed")
            # SAO replaces a captured appraisal for this actor/proposal pair
            # when the person reconsiders; distinct namespace IDs cannot turn
            # that same response into multiple independent observations.
            response_key = (process_id, enacted.get("processRevision"), key[2])
            require(response_key not in captured_responses,
                    f"{where}: duplicate captured process/actor/revision")
            captured_responses.add(response_key)
            captured_by_process[process_id] = captured_by_process.get(process_id, 0) + 1
        namespaces.add(key)

    if process_summary["available"]:
        for process in trajectory["processObservation"]["processes"]:
            require(captured_by_process.get(process["processId"], 0)
                    <= process["responseCount"],
                    f"{where}: decisions exceed responses for {process['processId']}")

    summary = {
        "episodeId": episode_id,
        "episodeSha256": seal,
        "horizonDays": horizon,
        "seed": row["seed"],
        "jointPathogen": source["jointPathogen"],
        "checkpointDays": days,
        "decisionCount": len(events),
        "decisionHours": [event["namespace"]["hour"] for event in events],
        "laterOutcomeHours": [event["enactedProcess"]["laterOutcome"]["asOfHour"]
                              for event in events],
        "processObservation": process_summary,
        "terminal": {"alive": terminal["alive"], "dead": terminal["dead"]},
        "replaySimulationSha256": replay["simulationSha256"],
    }
    return summary, events


def load_projector(path: Path) -> ModuleType:
    require(path.is_file(), f"ZAO projector is not a file: {path}")
    name = "zao_episode_projector_" + file_sha256(path)[:16]
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None,
            "ZAO projector could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(callable(getattr(module, "states_for", None)),
            "ZAO projector does not expose states_for")
    return module


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical_bytes(row) + b"\n" for row in rows)


def compile_bundle(episode_path: Path, projector_path: Path | None) -> tuple[
        list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]],
        list[dict[str, Any]], dict[str, Any]]:
    episodes = read_episodes(episode_path)
    summaries: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    ids: set[str] = set()
    namespaces: set[tuple[Any, ...]] = set()
    for line, episode in enumerate(episodes, 1):
        summary, rows = validate_episode(episode, episode_path, line)
        require(summary["episodeId"] not in ids,
                f"{episode_path}:{line}: duplicate episodeId {summary['episodeId']}")
        ids.add(summary["episodeId"])
        for row in rows:
            key = tuple(row["namespace"][field] for field in Join.NAMESPACE_FIELDS)
            require(key not in namespaces,
                    f"{episode_path}:{line}: duplicate decision namespace {key!r}")
            namespaces.add(key)
            decisions.append(copy.deepcopy(row))
        summaries.append(summary)

    states: list[dict[str, Any]] = []
    tasks: list[dict[str, Any]] = []
    projector_hash = None
    if decisions:
        require(projector_path is not None,
                "episodes with decisions require the current ZAO state projector")
        projector = load_projector(projector_path)
        projected = projector.states_for(copy.deepcopy(decisions))
        require(isinstance(projected, list) and len(projected) == len(decisions),
                "ZAO projector did not return one state per decision")
        states = projected
        projector_hash = file_sha256(projector_path)
        with tempfile.TemporaryDirectory(prefix="speakeasy-episode-join-") as tmp:
            root = Path(tmp)
            sao_path, zao_path, join_path = (root / "decisions.jsonl",
                                              root / "zao-state.jsonl",
                                              root / "joined.jsonl")
            sao_path.write_bytes(jsonl_bytes(decisions))
            zao_path.write_bytes(jsonl_bytes(states))
            joined = Join.joined_rows(sao_path, zao_path, join_path)
            tasks = [Tasks.compile_task(row) for row in joined]
    elif projector_path is not None:
        projector_hash = file_sha256(projector_path)

    decision_hours = [hour for item in summaries for hour in item["decisionHours"]]
    outcome_hours = [hour for item in summaries for hour in item["laterOutcomeHours"]]
    observed = [item["processObservation"] for item in summaries
                if item["processObservation"]["available"]]
    process_totals = {field: sum(item["counts"][field] for item in observed)
                      for _, field in PUBLIC_PROGRESSION}
    for field in ("currentReceivedCount", "currentRespondedCount",
                  "currentUnheardCount", "currentUnansweredCount",
                  "activeContactAttemptCount"):
        process_totals[field] = sum(item["counts"][field] for item in observed)
    first_unobserved: dict[str, int] = {}
    originator_owners: dict[str, int] = {}
    contact_owners: dict[str, int] = {}
    for item in observed:
        stage = item["firstUnobservedStage"] or "none"
        first_unobserved[stage] = first_unobserved.get(stage, 0) + 1
        add_counts(originator_owners, item["originatorOwnerCounts"])
        add_counts(contact_owners, item["contactOwnerCounts"])
    manifest = {
        "schema": SCHEMA,
        "schemaVersion": VERSION,
        "standing": "candidate-observation",
        "episodeCount": len(episodes),
        "emptyEpisodeCount": sum(item["decisionCount"] == 0 for item in summaries),
        "decisionCount": len(decisions),
        "taskCount": len(tasks),
        "episodes": summaries,
        "horizons": {
            "decisionHours": decision_hours,
            "laterOutcomeHours": outcome_hours,
            "separate": all(later >= decision for decision, later in
                            zip(decision_hours, outcome_hours, strict=True)),
        },
        "processObservation": {
            "availableEpisodeCount": len(observed),
            "legacyEpisodeCount": len(summaries) - len(observed),
            "totals": process_totals,
            "firstUnobservedStageCounts": first_unobserved,
            "originatorOwnerCounts": originator_owners,
            "contactOwnerCounts": contact_owners,
            "privacy": "public-causal-topology-only",
            "use": "episode-audit-only",
        },
        "source": {
            "episodeFileSha256": file_sha256(episode_path),
            "zaoProjectorSha256": projector_hash,
            "compilerHashEncoding": "utf-8-lf",
            "coordinationEpisodeCompilerSha256": compiler_sha256(Path(__file__)),
            "coordinationTaskCompilerSha256": compiler_sha256(Path(Tasks.__file__)),
            "crossModuleCompilerSha256": compiler_sha256(Path(Join.__file__)),
        },
        "exclusions": [
            "independent-task-review-not-recorded",
            "training-admission-not-recorded",
            "learned-runtime-not-authoritative",
            "loaded-gameplay-unobserved",
        ],
    }
    manifest["contentSha256"] = digest(manifest)
    return episodes, decisions, states, tasks, manifest


def publish(output: Path, episodes: list[dict[str, Any]],
            decisions: list[dict[str, Any]], states: list[dict[str, Any]],
            tasks: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    output = output.resolve(strict=False)
    require(not output.exists(), f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        files = {
            "episodes.jsonl": jsonl_bytes(episodes),
            "progression.jsonl": jsonl_bytes([
                {"episodeId": summary["episodeId"],
                 "processObservation": summary["processObservation"]}
                for summary in manifest["episodes"]
            ]),
            "decisions.jsonl": jsonl_bytes(decisions),
            "zao-state.jsonl": jsonl_bytes(states),
            "tasks.jsonl": jsonl_bytes(tasks),
            "manifest.json": canonical_bytes(manifest) + b"\n",
        }
        for name, data in files.items():
            path = staging / name
            with path.open("wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        os.replace(staging, output)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=Path, required=True)
    parser.add_argument("--zao-projector", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        bundle = compile_bundle(args.episodes, args.zao_projector)
        publish(args.out, *bundle)
    except (Join.ContractError, OSError, ImportError, AttributeError,
            TypeError, ValueError) as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 2
    manifest = bundle[-1]
    print(f"compiled {manifest['episodeCount']} causal episode(s), "
          f"{manifest['decisionCount']} decision(s), and "
          f"{manifest['taskCount']} candidate task(s) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
