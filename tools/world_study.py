#!/usr/bin/env python3
"""Prepare source-verified native observations for Mousecat inspection.

The explicitly supplied SAO owner validates the native run in a separate process.
This MIT tool projects data; it copies no owner implementation and emits no
training input, teaching target, approval or dataset admission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import decision_authoring as A


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8") + b"\n"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bounded(value, limit):
    result = str(value).replace("\r", "")
    return result if len(result) <= limit else result[:limit-24] + "... [display shortened]"


def project(frame):
    """Display recorded geometry and positions without filling unavailable space."""
    primitives, entities, seen = [], [], set()
    for window in frame["windows"]:
        for square in window["squares"]:
            position = (square["x"], square["y"], square["z"])
            if position in seen:
                continue
            seen.add(position)
            x, y, z = position
            z *= 3  # Display floor separation, not an inferred physical measurement.
            if square["floor"]:
                primitives.append({"position": [x+0.5, y+0.5, z-0.06], "extent": [0.49, 0.49, 0.06],
                    "color": [0.19, 0.29, 0.22] if square["outside"] else [0.45, 0.42, 0.34]})
            if square["solid"] or square["solidTrans"]:
                primitives.append({"position": [x+0.5, y+0.5, z+0.7], "extent": [0.34, 0.34, 0.7],
                                   "color": [0.37, 0.43, 0.36]})
            for obj in square["objects"]:
                if "open" in obj and "north" in obj:
                    # Thin object markers preserve observed orientation/open state.
                    primitives.append({"position": [x+0.5 if obj["north"] else x,
                                                       y if obj["north"] else y+0.5, z+0.9],
                        "extent": [0.45, 0.04, 0.9] if obj["north"] else [0.04, 0.45, 0.9],
                        "color": [0.25, 0.65, 0.45] if obj["open"] else [0.65, 0.38, 0.24]})
    missing_positions = 0
    for person in sorted(frame["people"], key=lambda p: (p["positionSource"] != "native-body", p["id"])):
        if not {"x", "y", "z"} <= set(person):
            missing_positions += 1
            continue
        record, context = person["record"], person["context"]
        label = " ".join(str(record.get(k, "")) for k in ("forename", "surname")).strip() or person["id"]
        controller = context["controller"].get("state", "unavailable")
        details = [f"{person['id']} | {record.get('occupation', 'occupation unavailable')} | state: {controller}",
                   f"Native position: {person['x']:.2f}, {person['y']:.2f}, floor {person['z']}",
                   f"Controller captured: {context['controllerAvailable']} | beliefs captured: {context['perceptionAvailable']}"]
        graph = record.get("worldGraph", {})
        if graph:
            details.append(f"Recorded activity: {graph.get('work', 'unavailable')}; "
                           f"branch: {graph.get('branch', 'unavailable')}; pressure: {graph.get('pressure', 'unavailable')}")
        isolation = graph.get("isolation", {})
        if isolation:
            details.append(f"Known people: {isolation.get('knownPeople', 'unavailable')}; "
                           f"recent contacts: {isolation.get('recentPeople', 'unavailable')}; "
                           f"group size: {isolation.get('groupSize', 'unavailable')}")
        for key, caption in (("lessonsKnown", "Retained lessons"), ("traitEchoes", "Recorded trait effects")):
            if key in record:
                values = record[key]
                details.append(caption + ": " + bounded(
                    "; ".join(f"{k} ({v:.3g})" if isinstance(v, (int, float)) else f"{k}: {v}"
                              for k, v in sorted(values.items())), 400))
        if context["perceptionAvailable"]:
            beliefs = context["beliefs"]
            for key, caption in (("people", "People in personal awareness"), ("zombies", "Perceived threats"),
                                 ("places", "Known places")):
                values = beliefs.get(key, {})
                details.append(f"{caption}: {len(values)}")
                for name, belief in list(sorted(values.items()))[:5]:
                    if isinstance(belief, dict):
                        details.append(bounded(f"  {name}: {belief.get('source', belief.get('src', 'source unavailable'))}; "
                            f"{belief.get('condition', 'condition unavailable')}; "
                            f"at {belief.get('atHours', 'time unavailable')}", 160))
                if len(values) > 5:
                    details.append(f"  {len(values)-5} more in the source frame")
        entities.append({"id": person["id"], "label": bounded(label, 160),
            "position": [person["x"], person["y"], person["z"] * 3],
            "positionSource": "active-body" if person["positionSource"] == "native-body" else "durable-state",
            "details": bounded("\n".join(details), 4096)})
    coverage, population = frame["coverage"], frame["population"]
    summary = (f"{coverage['loadedSquares']}/{coverage['requestedSquares']} squares observed; "
               f"{coverage['unavailableSquares']} unavailable. "
               f"{population['captured']}/{population['total']} people captured; "
               f"{population['represented']} represented, {population['dead']} dead. "
               f"{len(frame['processes'])}/{coverage['totalProcesses']} processes; "
               f"{coverage['omittedFieldCount']} fields omitted; {missing_positions} positions unavailable.")
    A.require(len(primitives) <= 100000 and len(entities) <= 100000, "Mousecat frame budget exceeded")
    return {"schema": "mousecat.world-frame/1", "hours": frame["hours"], "coverage": summary,
            "primitives": primitives, "entities": entities}


def export(run, package, owner, destination):
    run, package, owner, destination = (Path(p).resolve() for p in (run, package, owner, destination))
    A.require(owner.is_file() and owner.name == "world_lab_run.py", "explicit SAO run validator required")
    A.require(not destination.exists(), "output already exists")
    A.require(not destination.is_relative_to(run) and not destination.is_relative_to(package),
              "output must be outside native inputs")
    checked = subprocess.run([sys.executable, str(owner), str(package), "--out", str(run), "--verify"],
                             capture_output=True, text=True, encoding="utf-8", timeout=180)
    A.require(checked.returncode == 0, "SAO rejected native run: " + checked.stderr[-1600:])
    receipt = A.loads(checked.stdout)
    A.require(receipt["status"] == "completed" and receipt["datasetAdmission"] == "unreviewed",
              "native observation standing differs")
    definition_bytes = (package / "definition.json").read_bytes()
    definition = A.loads(definition_bytes.decode("utf-8"))
    prefix = "Study-" + sha(encoded({"definition": receipt["definitionSha256"],
                                   "observations": receipt["observations"]}))[:16]
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".study-preview-", dir=destination.parent))
    try:
        evidence, frames = {}, []
        for index, (relative, expected) in enumerate(sorted(receipt["observations"].items())):
            path = (run / "cache" / relative).resolve()
            A.require(path.is_relative_to(run / "cache/Lua/StudyWorld"), "unsafe native observation path")
            raw = path.read_bytes()
            A.require(sha(raw) == expected, "observation changed during intake")
            frame = A.loads(raw.decode("utf-8"))
            A.require(frame["datasetAdmission"] == "unreviewed", "frame standing differs")
            raw_name = f"{prefix}-source-{index:06d}.json"
            (staging / raw_name).write_bytes(raw)
            evidence[raw_name] = expected
            projected = encoded(project(frame))
            A.require(len(projected) <= 64 * 1024 * 1024, "Mousecat frame byte budget exceeded")
            name = f"{prefix}-frame-{index:06d}.json"
            (staging / name).write_bytes(projected)
            frames.append({"file": name, "sha256": sha(projected), "hours": frame["hours"]})
        A.require(0 < len(frames) <= 10000, "Mousecat replay frame budget exceeded")
        window = definition["observation"]["windows"][0]
        replay = {"schema": "mousecat.world-replay/1", "title": "Native study: " + definition["id"],
            "sourceDescription": "Recorded PZ world and copied mods. Geometry markers show observed tile flags. "
                "Camera movement changes only this view. Full private records remain in source frames.",
            "datasetAdmission": "unreviewed",
            "origin": [window["x"] + window["width"] / 2, window["y"] + window["height"] / 2, window["z"] * 3],
            "frames": frames}
        replay_bytes = encoded(replay)
        replay_name = prefix + ".replay.json"
        (staging / replay_name).write_bytes(replay_bytes)
        # Preserve the completed source receipt and definition exactly. Raw state
        # is audit material, never an implicit model input or approved example.
        for suffix, raw in (("run", (run / "run.json").read_bytes()), ("definition", definition_bytes)):
            name = prefix + "-" + suffix + ".json"
            (staging / name).write_bytes(raw)
            evidence[name] = sha(raw)
        source_report = A.loads((staging / (prefix + "-run.json")).read_text(encoding="utf-8"))
        A.require(source_report == receipt, "run changed during intake")
        manifest = {"schema": "speakeasy-native-study-preview/1", "datasetAdmission": "unreviewed",
            "sourceKind": "native-runtime-observation", "packageSha256": receipt["packageSha256"],
            "validatorSha256": sha(owner.read_bytes()),
            "projectorSha256": sha(Path(__file__).read_text(encoding="utf-8").encode("utf-8")),
            "replay": {"file": replay_name, "sha256": sha(replay_bytes)}, "sources": evidence,
            "trainingRows": 0, "teachingTargets": 0,
            "projection": {"horizontal": "engine tiles", "up": "engine floor times three display tiles",
                           "geometry": "observed tile and object flags", "unobserved": "empty space"}}
        (staging / (prefix + ".preview.json")).write_bytes(encoded(manifest))
        staging.rename(destination)
        return manifest
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--sao-validator", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(export(args.run, args.package, args.sao_validator, args.out), indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print("world_study: " + str(error), file=sys.stderr)
        sys.exit(1)
