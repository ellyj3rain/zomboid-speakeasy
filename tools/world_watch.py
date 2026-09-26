#!/usr/bin/env python3
"""Bridge an explicitly selected native observer run to Mousecat's data protocol.

The engine supplies pixels and simulation state. This process translates a small
observer command vocabulary and never admits observations to a training dataset.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import time
import uuid

import decision_authoring as A
from world_camera import ActivityCamera


POLL_SECONDS = 0.025
ARCHIVE_SCAN_SECONDS = 0.5


class TransientRead(Exception):
    """A producer has not finished publishing a JSON observation."""


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def read(path, limit=1024 * 1024):
    A.require(path.stat().st_size <= limit, "oversized observer data")
    try:
        return A.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as error:
        raise TransientRead(str(path)) from error
    except A.Join.ContractError as error:
        if isinstance(error.__cause__, json.JSONDecodeError):
            raise TransientRead(str(path)) from error
        raise


class JsonSnapshot:
    """Cache one parsed file until its filesystem identity changes.

    Failed or concurrent writes never enter the cache. Each input stream owns
    one instance, so archived observation paths cannot grow retained memory.
    """
    def __init__(self):
        self.key = self.value = None
        self.revision = 0

    @staticmethod
    def identity(path):
        stat = path.stat()
        return (path, stat.st_mtime_ns, stat.st_size, stat.st_ino)

    def read(self, path, limit=1024 * 1024):
        key = self.identity(path)
        A.require(key[2] <= limit, "oversized observer data")
        if key != self.key:
            value = read(path, limit)
            if self.identity(path) != key:
                raise TransientRead(str(path))
            self.key, self.value = key, value
            self.revision += 1
        return self.value


def atomic(path, data):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def number(value, low, high):
    A.require(type(value) in (int, float) and math.isfinite(value) and low <= value <= high,
              "invalid observer coordinate or scalar")
    return value


def translate(command, session, sequence, state, people, bounds, native_sequence=None):
    """An allowlisted camera/time command, independent of character actions."""
    fields = {"schema", "sessionId", "sequence", "action"}
    A.require(isinstance(command, dict) and fields <= command.keys(), "missing command fields")
    A.require(command["schema"] == "mousecat.native-view-command/1"
              and command["sessionId"] == session and type(command["sequence"]) is int
              and command["sequence"] == sequence, "command session or sequence differs")
    action = command["action"]
    optional = {"pause": set(), "resume": set(), "speed": {"value"}, "pan": {"dx", "dy"},
                "focus": {"personId"}, "stop": set(), "auto": set()}
    A.require(isinstance(action, str) and action in optional
              and set(command) == fields | optional[action], "unsupported observer command")
    result = {"sequence": sequence if native_sequence is None else native_sequence}
    if action in ("pause", "resume"):
        result["paused"] = str(action == "pause").lower()
    elif action == "speed":
        A.require(type(command["value"]) is int and command["value"] in (1, 2, 3), "unsupported speed")
        result["speed"] = command["value"]
    elif action == "pan":
        dx, dy = command["dx"], command["dy"]
        A.require(type(dx) is int and type(dy) is int and abs(dx) <= 8 and abs(dy) <= 8
                  and (dx or dy), "invalid camera step")
        result.update(viewX=number(state["viewX"] + dx, bounds[0], bounds[2]),
                      viewY=number(state["viewY"] + dy, bounds[1], bounds[3]), viewZ=state["viewZ"])
    elif action == "focus":
        person = next((p for p in people if p["id"] == command["personId"]), None)
        A.require(person is not None and {"x", "y", "z"} <= person.keys(), "person location unavailable")
        x, y, z = (number(person[k], low, high) for k, low, high in
                   (("x", bounds[0], bounds[2]), ("y", bounds[1], bounds[3]), ("z", -32, math.nextafter(32, -math.inf))))
        result.update(viewX=x, viewY=y, viewZ=z, residencyX=x, residencyY=y, residencyZ=z)
    elif action == "stop":
        result["stop"] = "true"
    return ("".join(f"{key}={value}\n" for key, value in sorted(result.items()))).encode("ascii")


def image_data(root, frame):
    image = frame["image"]
    name = image["file"]
    A.require(isinstance(name, str) and re.fullmatch(r"study-live-\d{16}\.png", name), "unsafe image filename")
    path = root / name
    A.require(path.resolve().parent == root.resolve() and not path.is_symlink(), "image leaves native directory")
    A.require(24 <= path.stat().st_size <= 16 * 1024 * 1024, "image byte limit")
    data = path.read_bytes()
    A.require(data[:8] == b"\x89PNG\r\n\x1a\n" and hashlib.sha256(data).hexdigest() == image["sha256"],
              "native image bytes differ")
    width, height = struct.unpack_from(">II", data, 16)
    A.require(0 < width <= 4096 and 0 < height <= 2160
              and width == image["width"] and height == image["height"], "native image dimensions differ")
    return data


def people_view(people):
    result = []
    for p in sorted(people, key=lambda v: (v.get("positionSource") != "native-body", v["id"]))[:2048]:
        record, context = p.get("record", {}), p.get("context", {})
        label = " ".join(str(record.get(k, "")) for k in ("forename", "surname")).strip() or p["id"]
        controller = context.get("controller", {})
        beliefs = context.get("beliefs", {})
        details = [str(record.get("occupation", "Occupation unavailable")),
                   "Activity: " + str(controller.get("state", "unrepresented")),
                   "Position from " + p.get("positionSource", "unavailable"),
                   "Deceased" if record.get("dead") else "Recorded alive"]
        if all(k in p for k in ("x", "y", "z")):
            details.append(f"Location {p['x']:.1f}, {p['y']:.1f}; floor {p['z']}")
        if context.get("perceptionAvailable"):
            counts = context.get("beliefCounts", {})
            details += [f"Known people: {counts.get('people', len(beliefs.get('people', {})))}",
                        f"Perceived threats: {counts.get('zombies', len(beliefs.get('zombies', {})))}",
                        f"Unclassified sounds: {counts.get('sounds', len(beliefs.get('sounds', {})))}"]
        else:
            details.append("Personal awareness unavailable")
        result.append({"id": p["id"], "label": label[:160], "summary": "\n".join(details)[:4096]})
    return result


@contextmanager
def native_writer(root):
    """One control writer per native attempt; the OS releases a crashed lease."""
    root.mkdir(parents=True, exist_ok=True)
    with (root / "speakeasy-watch.lock").open("a+b") as lease:
        if lease.seek(0, 2) == 0:
            lease.write(b"0")
            lease.flush()
        lease.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError("this native attempt already has a camera/control bridge") from error
        try:
            yield
        finally:
            lease.seek(0)
            if os.name == "nt":
                msvcrt.locking(lease.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lease, fcntl.LOCK_UN)


def control_cursor(root, state):
    cursor = max(0, state["sequence"], state.get("rejectedSequence", -1))
    control = root / "observer-control.properties"
    if control.exists():
        A.require(control.stat().st_size <= 8192, "oversized existing native control")
        values = re.findall(r"^sequence=(\d+)$", control.read_text(encoding="ascii"), re.M)
        A.require(len(values) == 1 and int(values[0]) <= 2**53-1, "invalid existing native command sequence")
        cursor = max(cursor, int(values[0]))
    return cursor


def watch(run, package, destination):
    receipt = read(run / "run.json", 8 * 1024 * 1024)
    relative = receipt.get("observerDirectory", "")
    A.require(relative == "" or re.fullmatch(r"attempts/\d{4}", relative), "unsafe observer attempt directory")
    with native_writer(run / relative):
        return watch_locked(run, package, destination)


def watch_locked(run, package, destination):
    A.require(not destination.exists(), "select a fresh Mousecat feed directory")
    receipt = read(run / "run.json", 8 * 1024 * 1024)
    A.require(receipt.get("host") == "observer" and receipt["datasetAdmission"] == "unreviewed",
              "an explicit native observer run is required")
    session = str(uuid.UUID(receipt["sessionId"]))
    definition = read(package / "definition.json")
    package_manifest = read(package / "package.json")
    A.require(package_manifest["definitionSha256"] == receipt["definitionSha256"], "run definition differs")
    extent = definition["extent"]
    bounds = (extent["minCellX"] * 256, extent["minCellY"] * 256,
              math.nextafter((extent["minCellX"] + extent["cellsX"]) * 256, -math.inf),
              math.nextafter((extent["minCellY"] + extent["cellsY"]) * 256, -math.inf))
    destination.mkdir(parents=True)
    (destination / "commands").mkdir()
    atomic(destination / "session.json", encoded({"schema": "speakeasy-world-watch/1", "sessionId": session,
        "definitionSha256": receipt["definitionSha256"], "datasetAdmission": "unreviewed",
        "trainingRows": 0, "teachingTargets": 0}))
    relative = receipt.get("observerDirectory", "")
    A.require(relative == "" or re.fullmatch(r"attempts/\d{4}", relative), "unsafe observer attempt directory")
    observer_root = run / relative
    native_root = observer_root / "native-view"
    sequence, acknowledged, pending = 0, 0, None
    native_cursor = None
    camera = ActivityCamera()
    displayed_camera = camera.view([])
    requested_camera = None
    command_result = None
    last_observation = None
    people, observation_hours, population = [], None, {}
    displayed_people, available_ids = [], set()
    images = {}
    receipt_cache, state_cache, frame_cache, observation_cache = (JsonSnapshot() for _ in range(4))
    archive_path, next_archive_scan = None, 0.0
    last_publication = None
    while True:
        try:
            receipt = receipt_cache.read(run / "run.json", 8 * 1024 * 1024)
        except (TransientRead, PermissionError):
            time.sleep(POLL_SECONDS)
            continue
        A.require(receipt["sessionId"] == session, "run session changed")
        ended = receipt["status"] in ("completed", "incomplete", "timed-out")
        try:
            state = state_cache.read(observer_root / "observer-state.json")
            frame = frame_cache.read(native_root / "native.json")
            A.require(type(state.get("detached")) is bool, "observer participation evidence unavailable")
            if not state["detached"]:
                camera.manual()
                displayed_camera = {"mode": "manual", "personIds": [], "summary": "Observer invariant failed; stop remains available"}
                requested_camera = None
            # UI numbering belongs to this feed. Native numbering belongs to
            # the running attempt, including prior feeds and automatic moves.
            if native_cursor is None:
                native_cursor = control_cursor(observer_root, state)
            if pending is not None:
                applied = state["sequence"] == pending["native"]
                rejected = state.get("rejectedSequence") == pending["native"]
                if applied or rejected:
                    if pending["ui"] is not None:
                        acknowledged = pending["ui"]
                        command_result = {"sequence": acknowledged, "status": "applied" if applied else "rejected",
                            "message": "Observer request applied" if applied else str(state.get("error", "Native observer rejected the request"))[:512]}
                    elif rejected:
                        camera.manual()
                        camera.description = "Automatic camera stopped: " + str(state.get("error", "request rejected"))[:400]
                        displayed_camera = camera.view(people)
                        requested_camera = None
                    pending = None
            live_path = run / "cache/Lua/StudyWorldLive.json"
            if live_path.exists():
                observation_path = live_path
            else:
                now = time.monotonic()
                if now >= next_archive_scan:
                    paths = sorted((run / "cache/Lua/StudyWorld").rglob("*.json"))
                    archive_path = paths[-1] if paths else None
                    next_archive_scan = now + ARCHIVE_SCAN_SECONDS
                observation_path = archive_path
            observation_ready = observation_path is not None
            if observation_ready:
                try:
                    observation = observation_cache.read(observation_path, 64 * 1024 * 1024)
                    if observation_cache.revision != last_observation:
                        A.require(observation["datasetAdmission"] == "unreviewed"
                                  and observation["definitionSha256"] == receipt["definitionSha256"], "observation binding differs")
                        people, observation_hours, population = observation["people"], observation["hours"], observation["population"]
                        displayed_people = people_view(people)
                        available_ids = {p["id"] for p in displayed_people}
                        last_observation = observation_cache.revision
                except (FileNotFoundError, TransientRead, PermissionError):
                    # Inspection may fail while pixels and controls remain live.
                    observation_ready = False
            if requested_camera and frame.get("observerSequence", -1) >= requested_camera["native"]:
                displayed_camera = requested_camera["value"]
                requested_camera = None
            if pending is None and not ended:
                command_path = destination / "commands" / f"{acknowledged+1:016d}.json"
                if command_path.exists():
                    try:
                        command = read(command_path, 16384)
                        control = translate(command, session, acknowledged + 1, state, people, bounds, native_cursor + 1)
                    except (ValueError, KeyError, TypeError, TransientRead) as error:
                        # Commands are immutable atomic files. Reject one bad
                        # request explicitly and keep later pause/stop usable.
                        acknowledged += 1
                        command_result = {"sequence": acknowledged, "status": "rejected", "message": str(error)[:512]}
                    else:
                        if command["action"] == "auto":
                            camera.resume()
                            displayed_camera = camera.view(people)
                            acknowledged += 1
                            command_result = {"sequence": acknowledged, "status": "applied", "message": "Activity camera resumed"}
                        else:
                            if command["action"] in ("pan", "focus", "stop"):
                                camera.manual()
                                displayed_camera = camera.view(people)
                                requested_camera = None
                            atomic(observer_root / "observer-control.properties", control)
                            native_cursor += 1
                            pending = {"native": native_cursor, "ui": acknowledged + 1}
                elif observation_ready and observation_hours is not None and time.time() - observation_path.stat().st_mtime <= 5:
                    plan = camera.plan(people, observation_hours, state, bounds, time.monotonic())
                    if plan is not None:
                        native_cursor += 1
                        plan["sequence"] = native_cursor
                        atomic(observer_root / "observer-control.properties", "".join(
                            f"{key}={value}\n" for key, value in sorted(plan.items())).encode("ascii"))
                        pending = {"native": native_cursor, "ui": None}
                        requested_camera = {"native": native_cursor, "value": camera.view(people)}
                        displayed_camera = {"mode": "automatic", "personIds": [], "summary": "Moving to the next observed view"}
                        with (destination / "camera.jsonl").open("ab") as journal:
                            journal.write(encoded({"nativeSequence": native_cursor, "shot": camera.shot,
                                "observedHours": observation_hours, "personIds": camera.subjects,
                                "view": plan, "datasetAdmission": "unreviewed"}))
            publication = (frame["sequence"], acknowledged, json.dumps(displayed_camera, sort_keys=True),
                           state["paused"], state.get("failure"), observation_ready, last_observation)
            if publication != last_publication or ended:
                name = frame["image"]["file"]
                if name not in images:
                    atomic(destination / name, image_data(native_root, frame))
                    images[name] = dict(frame["image"])
                else:
                    A.require(images[name] == frame["image"], "native image filename reused with different metadata")
                sequence += 1
                display = "Native engine image"
                if state.get("displayMode") == "native-god-view":
                    display = "God view"
                    if state.get("canopyCutaway") is True:
                        display += "; canopy cutaway"
                summary = (f"World hour {state['hours']:.3f} | "
                           f"{population.get('total', 0)} people, {population.get('represented', 0)} represented. "
                           f"People observed at hour {observation_hours if observation_hours is not None else 'unavailable'}. "
                           f"{display}; full physics applies in the loaded region. Unreviewed.")
                if ended:
                    summary += " Run " + receipt["status"] + "."
                if state.get("failure"):
                    summary = "Observer failure: " + str(state["failure"])[:512] + ". " + summary
                if not observation_ready:
                    summary += " People inspection awaiting a complete observation."
                snapshot = {"schema": "mousecat.native-view/1",
                    "sessionId": session, "sequence": sequence, "capturedAtUnixMs": frame["capturedAtUnixMs"],
                    "image": frame["image"], "state": "ended" if ended else ("paused" if state["paused"] else "running"),
                    "title": "Simulation observatory", "summary": summary,
                    "people": displayed_people, "lastCommandSequence": acknowledged,
                    "camera": displayed_camera | {"personIds": [key for key in displayed_camera["personIds"] if key in available_ids]}}
                if command_result:
                    snapshot["commandResult"] = command_result
                atomic(destination / "latest.json", encoded(snapshot))
                last_publication = publication
                while len(images) > 8:
                    oldest = next(iter(images))
                    del images[oldest]
                    (destination / oldest).unlink(missing_ok=True)
        except (FileNotFoundError, TransientRead, PermissionError):
            # A native observation file can be mid-write. The last complete,
            # hash-validated frame remains on screen with its original age.
            pass
        if ended:
            return 0 if receipt["status"] == "completed" else 1
        time.sleep(POLL_SECONDS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    return watch(args.run.resolve(), args.package.resolve(), args.out.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
