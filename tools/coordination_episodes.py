#!/usr/bin/env python3
"""Validate causal SAO episodes and compile their coordination observations.

The episode remains the unit of provenance even when it contains no decision.
Decision rows are projected through the explicitly supplied ZAO owner, joined
on the complete v3 namespace, and compiled by the existing coordination task
contract.  Every output remains a candidate observation; this tool performs no
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
VERSION = 1
EPISODE_FIELDS = {
    "schema", "schemaVersion", "episodeId", "horizonDays", "seed",
    "drawCount", "checkpoints", "trajectory", "terminal", "source",
    "standing", "exclusions", "replay", "episodeSha256",
}
TRAJECTORY_FIELDS = {
    "dailySnapshots", "socialEvents", "companies", "deathCauses",
    "decisionCapture",
}


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


def finite(value: Any, where: str) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value), f"{where} must be finite")
    return float(value)


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
    require(isinstance(trajectory, dict) and set(trajectory) == TRAJECTORY_FIELDS,
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
    for event_index, event in enumerate(events, 1):
        key = Join.validate_sao_row(event, path, line)
        require(key[0] == episode_id and key[1] == episode_id,
                f"{where}: decision {event_index} run/county differs from episode")
        hour = finite(key[-1], f"{where}: decision {event_index} hour")
        require(0 <= hour <= horizon * 24,
                f"{where}: decision {event_index} lies outside the episode horizon")
        require(key not in namespaces,
                f"{where}: duplicate decision namespace {key!r}")
        namespaces.add(key)

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
        "source": {
            "episodeFileSha256": file_sha256(episode_path),
            "zaoProjectorSha256": projector_hash,
            "coordinationEpisodeCompilerSha256": file_sha256(Path(__file__)),
            "coordinationTaskCompilerSha256": file_sha256(Path(Tasks.__file__)),
            "crossModuleCompilerSha256": file_sha256(Path(Join.__file__)),
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
