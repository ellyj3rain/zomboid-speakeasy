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
import sys
import time
import uuid

import decision_authoring as A
import cognition_contract as Cognition
import cognition_episodes as CognitionEpisodes
import cognition_review as CognitionReview
from world_camera import ActivityCamera


# Local manifests are immutable/atomic and cheap to stat. Ten milliseconds keeps
# bridge scheduling below one native capture interval without busy-spinning.
POLL_SECONDS = 0.010
ARCHIVE_SCAN_SECONDS = 0.5
MAX_FEEDS = 4
SESSION_SCHEMA = "sao-study-session/1"
SESSION_COMMAND_SCHEMA = "sao-study-session-command/1"


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


def study_view(path):
    """Read the public, path-free state of one durable native study session."""
    if path is None:
        return None
    value = read(path)
    required = {"schema", "id", "label", "status", "attempt", "attemptDurationSeconds",
                "autoContinue", "worldHours", "accumulatedWorldHours", "canCheckpoint",
                "canContinue", "updatedAtUnixMs", "datasetAdmission", "behavioralVerdict",
                "lastStopReason", "feedGeneration", "processedCommands"}
    A.require(isinstance(value, dict) and set(value) == required and value["schema"] == SESSION_SCHEMA,
              "study session fields differ")
    session_id = str(uuid.UUID(value["id"]))
    A.require(session_id == value["id"] and isinstance(value["label"], str)
              and 0 < len(value["label"]) <= 160, "study session identity differs")
    A.require(value["status"] in ("starting", "running", "saved", "continuing", "failed")
              and type(value["attempt"]) is int and value["attempt"] >= 0,
              "study session status differs")
    duration = value["attemptDurationSeconds"]
    A.require(type(duration) is int and 30 <= duration <= 604800
              and type(value["autoContinue"]) is bool
              and type(value["canCheckpoint"]) is bool
              and type(value["canContinue"]) is bool, "study session settings differ")
    number(value["worldHours"], 0, 2**53 - 1)
    number(value["accumulatedWorldHours"], 0, 2**53 - 1)
    A.require(type(value["updatedAtUnixMs"]) is int and 0 <= value["updatedAtUnixMs"] <= 2**53 - 1
              and value["datasetAdmission"] == "unreviewed" and value["behavioralVerdict"] is None,
              "study session review state differs")
    A.require(value["lastStopReason"] is None or isinstance(value["lastStopReason"], str)
              and len(value["lastStopReason"]) <= 80, "study stop reason differs")
    A.require(value["canCheckpoint"] == (value["status"] == "running")
              and value["canContinue"] == (value["status"] == "saved"),
              "study session controls differ")
    return {key: value[key] for key in ("id", "label", "status", "attempt",
        "attemptDurationSeconds", "autoContinue", "worldHours", "accumulatedWorldHours",
        "canCheckpoint", "canContinue", "updatedAtUnixMs", "lastStopReason")}


def publish_session_command(root, command, session, sequence):
    """Publish one allowlisted lifecycle request for the study supervisor."""
    A.require(root is not None and root.is_dir() and not root.is_symlink(),
              "study session command path unavailable")
    required = {"schema", "sessionId", "sequence", "action"}
    action = command.get("action")
    if action == "configure":
        A.require(set(command) == required | {"attemptDurationSeconds", "autoContinue"}
                  and type(command["attemptDurationSeconds"]) is int
                  and 30 <= command["attemptDurationSeconds"] <= 604800
                  and type(command["autoContinue"]) is bool,
                  "invalid study session settings")
    else:
        A.require(action == "continue" and set(command) == required,
                  "unsupported study session request")
    event = {"schema": SESSION_COMMAND_SCHEMA, "sessionId": session,
             "sequence": sequence, "action": action}
    if action == "configure":
        event.update(attemptDurationSeconds=command["attemptDurationSeconds"],
                     autoContinue=command["autoContinue"])
    name = f"{session}-{sequence:016d}.json"
    target = root / name
    if target.exists():
        A.require(read(target, 8192) == event, "study session command identity reused")
    else:
        atomic(target, encoded(event))
    return event


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


def register_feed(registry, view_id, label, project_ref, destination, session):
    """Atomically rebind one stable Mousecat view to this producer session."""
    A.require(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", view_id) is not None,
              "invalid Mousecat view id")
    A.require(isinstance(label, str) and 0 < len(label) <= 160, "invalid Mousecat view label")
    A.require(project_ref is None or isinstance(project_ref, str) and 0 < len(project_ref) <= 160,
              "invalid Mousecat project reference")
    registry.parent.mkdir(parents=True, exist_ok=True)
    lock = registry.with_name(registry.name + ".lock")
    with lock.open("a+b") as lease:
        if lease.seek(0, 2) == 0:
            lease.write(b"0"); lease.flush()
        lease.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(lease.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lease, fcntl.LOCK_EX)
        try:
            rows = read(registry) if registry.exists() else []
            A.require(isinstance(rows, list) and len(rows) <= 32, "invalid Mousecat registry")
            row = {"id": view_id, "label": label, "directory": str(destination), "sessionId": session}
            if project_ref is not None:
                row["projectRef"] = project_ref
            rows = [row, *(value for value in rows if isinstance(value, dict) and value.get("id") != view_id)]
            A.require(len(rows) <= 32, "Mousecat registry is full")
            atomic(registry, encoded(rows))
        finally:
            lease.seek(0)
            if os.name == "nt":
                msvcrt.locking(lease.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lease, fcntl.LOCK_UN)


def panel_overlay(person, captured_at_unix_ms):
    """Project only frame-aligned, source-reported facts into the observatory."""
    sections = {section["id"]: section for section in person.get("sections", [])}
    groups = []

    def add(group_id, label, rows):
        rows = [{"label": str(row["label"])[:160], "value": str(row["value"])[:384]}
                for row in rows[:4]]
        if rows:
            groups.append({"id": group_id, "label": label, "rows": rows})

    add("activity", "Activity", sections.get("actions", {}).get("rows", []))
    add("attention", "Attention", sections.get("attention", {}).get("rows", []))
    memory = []
    for line in str(person.get("summary", "")).splitlines():
        for prefix, label in (("Remembered person locations: ", "People"),
                              ("Stored threat memories: ", "Threats"),
                              ("Unclassified sounds: ", "Sounds")):
            if line.startswith(prefix):
                memory.append({"label": label, "value": line[len(prefix):]})
                break
    add("memory", "Memory", memory)
    needs = sections.get("needs", {}).get("rows", [])
    selected_needs = [row for row in needs
                      if row.get("label") in ("Hunger", "Thirst", "Fatigue", "Health (%)")]
    add("needs", "Needs", selected_needs)
    return {"personId": person["id"], "capturedAtUnixMs": captured_at_unix_ms, "groups": groups}


def remember_feed(feeds, camera, frame, people, overlay_captured_at=None, limit=MAX_FEEDS):
    """Retain recent engine-rendered activity views without claiming simultaneity."""
    ids = list(camera.get("personIds", []))
    if not ids:
        return
    primary = ids[0]
    labels = {person["id"]: person["label"] for person in people}
    label = labels.get(primary, primary)
    if len(ids) > 1:
        label += f" + {len(ids) - 1} nearby"
    person = next((person for person in people if person["id"] == primary), None)
    value = {"id": primary, "label": label[:160], "capturedAtUnixMs": frame["capturedAtUnixMs"],
             "image": dict(frame["image"]), "camera": {"mode": camera["mode"],
             "personIds": ids[:5], "summary": str(camera.get("summary", ""))[:512]}}
    # A newly published inspection can briefly lead the latest renderer frame.
    # Never paint that later state over earlier pixels; the next frame can carry it.
    if (person is not None and type(overlay_captured_at) is int
            and overlay_captured_at <= frame["capturedAtUnixMs"]):
        overlay = panel_overlay(person, overlay_captured_at)
        if overlay["groups"]:
            value["overlay"] = overlay
    feeds.pop(primary, None)
    feeds[primary] = value
    while len(feeds) > limit:
        feeds.pop(next(iter(feeds)))


def number(value, low, high):
    A.require(type(value) in (int, float) and math.isfinite(value) and low <= value <= high,
              "invalid observer coordinate or scalar")
    return value


def viewport_view(state, frame=None):
    """Native projection metadata belongs only to its captured command epoch."""
    value = state.get("viewport")
    if value is None:
        return None
    A.require(isinstance(value, dict) and set(value) == {"zoom", "targetZoom", "zoomLevels"},
              "invalid native viewport fields")
    levels = value["zoomLevels"]
    A.require(isinstance(levels, list) and 0 < len(levels) <= 64, "invalid native zoom levels")
    for index, level in enumerate(levels):
        number(level, math.nextafter(0, math.inf), 16)
        A.require(index == 0 or level > levels[index - 1], "native zoom levels must increase")
    zoom = number(value["zoom"], levels[0], levels[-1])
    target = number(value["targetZoom"], levels[0], levels[-1])
    A.require(any(abs(target - level) < 0.0001 for level in levels), "native zoom target is not a configured level")
    if frame is not None and (type(frame.get("observerSequence")) is not int
                             or frame["observerSequence"] != state.get("sequence")):
        return None
    return {"zoom": zoom, "targetZoom": target, "zoomLevels": list(levels)}


def translate(command, session, sequence, state, people, bounds, native_sequence=None):
    """An allowlisted camera/time command, independent of character actions."""
    fields = {"schema", "sessionId", "sequence", "action"}
    A.require(isinstance(command, dict) and fields <= command.keys(), "missing command fields")
    A.require(command["schema"] == "mousecat.native-view-command/1"
              and command["sessionId"] == session and type(command["sequence"]) is int
              and command["sequence"] == sequence, "command session or sequence differs")
    action = command["action"]
    site_id = command.get("siteId")
    if site_id is not None:
        A.require(action in ("pan", "focus", "zoom", "auto"), "site target requires a camera action")
        site = next((site for site in state.get("sites", []) if site.get("id") == site_id), None)
        A.require(site is not None, "native site unavailable")
        state = state | site
        fields = fields | {"siteId"}
    optional = {"pause": set(), "resume": set(), "speed": {"value"}, "pan": {"dx", "dy"},
                "focus": {"personId"}, "stop": set(), "checkpoint": set(), "auto": set(), "select": {"personId"},
                "panel": {"panelId", "personId", "visible"}, "zoom": {"value"},
                "cognition": {"opponentShare", "opportunitiesPerHour", "maxDepth"}}
    A.require(isinstance(action, str) and action in optional
              and set(command) == fields | optional[action], "unsupported observer command")
    result = {"sequence": sequence if native_sequence is None else native_sequence}
    if site_id is not None:
        result["siteId"] = site_id
    if action in ("pause", "resume"):
        result["paused"] = str(action == "pause").lower()
    elif action == "speed":
        A.require(type(command["value"]) is int and command["value"] in (1, 2, 3), "unsupported speed")
        result["speed"] = command["value"]
    elif action == "zoom":
        A.require(type(command["value"]) is int and command["value"] in (-1, 1), "invalid native zoom step")
        A.require(viewport_view(state) is not None, "native zoom unavailable")
        result["zoomStep"] = command["value"]
    elif action == "cognition":
        number(command["opponentShare"], 0, 1)
        A.require(type(command["opportunitiesPerHour"]) is int and 1 <= command["opportunitiesPerHour"] <= 60
                  and type(command["maxDepth"]) is int and 1 <= command["maxDepth"] <= 4,
                  "invalid cognitive opportunity budget")
        result.update({key: command[key] for key in ("opponentShare", "opportunitiesPerHour", "maxDepth")})
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
    elif action in ("stop", "checkpoint"):
        result["stop"] = "true"
    elif action in ("select", "panel"):
        person = command["personId"]
        A.require(isinstance(person, str) and 0 < len(person) <= 128
                  and not any(ord(c) < 32 or ord(c) == 127 for c in person)
                  and any(p["id"] == person for p in people), "person unavailable for inspection")
        if action == "select":
            result["selectedPersonId"] = person
        else:
            A.require(command["panelId"] == "person-inspection" and type(command["visible"]) is bool,
                      "unsupported person inspection panel")
            result.update(panelId="person-inspection", panelPersonId=person,
                          panelVisible=str(command["visible"]).lower())
    # Java Properties.load(InputStream) is Latin-1 with Unicode escapes. Encode
    # literal separators/backslashes too, so source-owned IDs remain one value.
    def property_value(value):
        raw = str(value).encode("utf-16-be")
        return "".join(chr(n) if 33 <= n < 127 and chr(n) not in "\\=:#!" else f"\\u{n:04x}"
                       for n in (int.from_bytes(raw[i:i+2], "big") for i in range(0, len(raw), 2)))
    return ("".join(f"{key}={property_value(value)}\n" for key, value in sorted(result.items()))).encode("ascii")


def image_data(root, frame):
    image = frame["image"]
    name = image["file"]
    A.require(isinstance(name, str) and re.fullmatch(r"study-live-\d{16}(?:-site[0-3])?\.png", name), "unsafe image filename")
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


def observer_definition(receipt, definition):
    """Use a sealed viewing layout without changing simulation/archive identity."""
    present = {key for key in ("observerLayout", "observerLayoutSha256") if key in receipt}
    A.require(len(present) in (0, 2), "observer layout receipt is incomplete")
    if not present:
        return definition
    value = receipt["observerLayout"]
    A.require(isinstance(value, dict) and set(value) == {"schema", "sites"}
              and value["schema"] == "sao-study-observer-layout/1", "observer layout schema differs")
    sealed = json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True,
                        separators=(",", ":")).encode("utf-8")
    A.require(hashlib.sha256(sealed).hexdigest() == receipt["observerLayoutSha256"],
              "observer layout seal differs")
    sites = value["sites"]
    A.require(isinstance(sites, list) and 1 <= len(sites) <= 4, "expected 1..4 observer areas")
    extent = definition["extent"]
    left, top = extent["minCellX"] * 256, extent["minCellY"] * 256
    right, bottom = left + extent["cellsX"] * 256, top + extent["cellsY"] * 256
    identities, positions = set(), set()
    for site in sites:
        A.require(isinstance(site, dict) and set(site) == {"id", "label", "x", "y", "z"},
                  "observer area fields differ")
        A.require(isinstance(site["id"], str) and re.fullmatch(r"[a-z][a-z0-9-]{0,47}", site["id"])
                  and site["id"] not in identities, "invalid or duplicate observer area id")
        A.require(isinstance(site["label"], str) and 0 < len(site["label"]) <= 160
                  and all(32 <= ord(char) < 127 for char in site["label"]), "invalid observer area label")
        number(site["x"], left, math.nextafter(right, -math.inf))
        number(site["y"], top, math.nextafter(bottom, -math.inf))
        number(site["z"], -32, math.nextafter(32, -math.inf))
        position = tuple(struct.unpack(">f", struct.pack(">f", site[key]))[0] for key in ("x", "y", "z"))
        A.require(left <= position[0] < right and top <= position[1] < bottom and -32 <= position[2] < 32,
                  "native observer coordinates leave world bounds")
        A.require(position not in positions, "observer areas share a native position")
        identities.add(site["id"]); positions.add(position)
    return definition | {"observation": definition["observation"] | {"sites": sites}}


def native_views(root, frame, definition, bounds):
    """Validate separate native split-screen pixels against authored site identities."""
    declared = definition.get("observation", {}).get("sites", [])
    if "views" not in frame:
        A.require(len(declared) <= 1, "native regional viewports missing")
        return []
    raw = frame["views"]
    A.require(isinstance(raw, list) and 2 <= len(raw) <= 4 and len(raw) == len(declared),
              "native regional viewport count differs")
    result, rectangles = [], []
    width, height = frame["image"]["width"], frame["image"]["height"]
    for index, (value, site) in enumerate(zip(raw, declared)):
        A.require(isinstance(value, dict) and set(value) == {"id", "label", "slot", "x", "y", "z", "left", "top", "image"},
                  "native regional viewport fields differ")
        A.require(value["id"] == site["id"] and value["label"] == site["label"]
                  and type(value["slot"]) is int and value["slot"] == index, "native regional identity differs")
        number(value["x"], bounds[0], bounds[2]); number(value["y"], bounds[1], bounds[3]); number(value["z"], -32, math.nextafter(32, -math.inf))
        image = value["image"]
        A.require(isinstance(image, dict) and set(image) == {"file", "sha256", "width", "height"}, "regional image fields differ")
        expected_name = frame["image"]["file"].removesuffix(".png") + f"-site{index}.png"
        A.require(image["file"] == expected_name, "regional image sequence differs")
        left, top = value["left"], value["top"]
        A.require(type(left) is int and type(top) is int and left >= 0 and top >= 0
                  and type(image["width"]) is int and type(image["height"]) is int
                  and left + image["width"] <= width and top + image["height"] <= height,
                  "regional rectangle leaves native framebuffer")
        rect = (left, top, left + image["width"], top + image["height"])
        A.require(all(rect[2] <= old[0] or old[2] <= rect[0] or rect[3] <= old[1] or old[3] <= rect[1]
                      for old in rectangles), "native regional rectangles overlap")
        rectangles.append(rect)
        image_data(root, {"image": image})
        result.append(value)
    return result


def inspection_view(value, people):
    """Source-owned scalar facts, independently timed and bounded for the viewer."""
    if value is None:
        return None, {}
    A.require(isinstance(value, dict), "invalid inspection")
    header_keys = {"sequence", "capturedAtUnixMs", "worldHours", "status", "message", "omittedPeople", "omittedEvents"}
    A.require(header_keys <= value.keys() and set(value) <= header_keys | {"people", "selectedPersonId"}, "unknown inspection fields")
    def text_field(obj, key, limit, empty=True):
        text = obj.get(key)
        A.require(isinstance(text, str) and len(text) <= limit and (empty or text)
                  and not any((ord(c) < 32 and c not in "\n\t") or ord(c) == 127 for c in text), "invalid inspection text: " + key)
        return text
    def status(obj):
        A.require(obj.get("status") in ("available", "unavailable", "failed"), "invalid inspection status")
    for key, minimum in (("sequence", 0), ("capturedAtUnixMs", 0), ("omittedPeople", 0), ("omittedEvents", 0)):
        A.require(type(value[key]) is int and minimum <= value[key] <= 2**53-1, "invalid inspection counter")
    number(value["worldHours"], 0, 2**53-1)
    status(value); text_field(value, "message", 1024)
    A.require(value["sequence"] > 0 or (value["capturedAtUnixMs"] == 0 and value["status"] != "available"),
              "unsampled inspection claimed current data")
    header = {key: value[key] for key in header_keys}
    ids = {p["id"] for p in people}
    selected = value.get("selectedPersonId")
    if selected is not None:
        A.require(selected in ids, "selected inspection person missing")
        header["selectedPersonId"] = selected
    raw = value.get("people", {})
    A.require(isinstance(raw, dict) and len(raw) <= 16 and set(raw) <= ids, "inspection detail person differs")
    def array(raw, limit):
        if raw == {}: raw = []  # Empty Lua tables have no implicit JSON array type.
        A.require(isinstance(raw, list) and len(raw) <= limit, "inspection collection limit")
        return raw
    details, budget = {}, 256 * 1024
    for person in sorted(raw, key=lambda key: (key != selected, key)):
        detail = raw[person]
        A.require(isinstance(detail, dict) and {"sections", "events"} <= detail.keys()
                  and set(detail) <= {"sections", "events", "cognition"}, "inspection detail fields")
        sections, events, seen = [], [], set()
        for section in array(detail["sections"], 16):
            A.require(isinstance(section, dict) and set(section) == {"id", "label", "source", "perspective", "status", "message", "rows"}, "inspection section fields")
            for key, limit in (("id", 128), ("label", 160), ("source", 160), ("perspective", 160), ("message", 1024)):
                text_field(section, key, limit, key == "message")
            A.require(section["id"] not in seen, "duplicate inspection section"); seen.add(section["id"])
            status(section)
            rows = []
            for row in array(section["rows"], 48):
                A.require(isinstance(row, dict) and set(row) == {"label", "value"}, "inspection row fields")
                text_field(row, "label", 160); text_field(row, "value", 384)
                rows.append(dict(row))
            sections.append(section | {"rows": rows})
        seen = set()
        for event in array(detail["events"], 24):
            required = {"id", "capturedAtUnixMs", "worldHours", "source", "stage", "summary"}
            A.require(isinstance(event, dict) and required <= event.keys()
                      and set(event) <= required | {"actorId", "recipientId", "correlationId"}, "inspection event fields")
            for key, limit in (("id", 128), ("source", 160), ("stage", 128), ("summary", 1024)):
                text_field(event, key, limit)
            A.require(event["id"] not in seen, "duplicate inspection event"); seen.add(event["id"])
            A.require(type(event["capturedAtUnixMs"]) is int and 0 <= event["capturedAtUnixMs"] <= value["capturedAtUnixMs"], "inspection event time")
            number(event["worldHours"], 0, value["worldHours"])
            for key in ("actorId", "recipientId", "correlationId"):
                if key in event: text_field(event, key, 128, False)
            events.append(dict(event))
        normalized = {"sections": sections, "events": events}
        if "cognition" in detail:
            Cognition.require("worldHours" in header, "cognition lacks source observation clock")
            normalized["cognition"] = Cognition.projection(detail["cognition"], person, max_hours=header["worldHours"])
        cost = len(encoded(normalized))
        if cost <= budget:
            details[person] = normalized; budget -= cost
        else:
            header["omittedPeople"] += 1; header["omittedEvents"] += len(events)
    return header, details


def people_view(people, inspection=None, selected_id=None):
    result = []
    for p in sorted(people, key=lambda v: (v["id"] != selected_id, v.get("positionSource") != "native-body", v["id"]))[:2048]:
        record, context = p.get("record", {}), p.get("context", {})
        label = " ".join(str(record.get(k, "")) for k in ("forename", "surname")).strip() or p["id"]
        controller = context.get("controller", {})
        beliefs = context.get("beliefs", {})
        details = [str(record.get("occupation", "Occupation unavailable")),
                   "Activity: " + str(controller.get("state", "unrepresented"))]
        for section in (inspection or {}).get(p["id"], {}).get("sections", []):
            if section["id"] == "pressure" and section["source"] == "Controller" and section["status"] == "available":
                reason = next((row["value"] for row in section["rows"] if row["label"] == "detail"), None)
                if reason:
                    details.append("Recorded reason: " + reason)
                break
        details += ["Position from " + p.get("positionSource", "unavailable"),
                    "Deceased" if record.get("dead") else "Recorded alive"]
        if all(k in p for k in ("x", "y", "z")):
            details.append(f"Location {p['x']:.1f}, {p['y']:.1f}; floor {p['z']}")
        if context.get("perceptionAvailable"):
            counts = context.get("beliefCounts", {})
            details += [f"Remembered person locations: {counts.get('people', len(beliefs.get('people', {})))}",
                        f"Stored threat memories: {counts.get('zombies', len(beliefs.get('zombies', {})))}",
                        f"Unclassified sounds: {counts.get('sounds', len(beliefs.get('sounds', {})))}"]
        else:
            details.append("Personal awareness unavailable")
        result.append({"id": p["id"], "label": label[:160], "summary": "\n".join(details)[:4096]}
                      | (inspection or {}).get(p["id"], {}))
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


def watch(run, package, destination, registry=None, view_id="survival-observatory",
          label="Survival simulation", project_ref=None, session_state=None,
          session_commands=None, sao_validator=None, review_outbox=None,
          review_endpoint="http://127.0.0.1:4317/mcp", site_controls=False):
    receipt = read(run / "run.json", 8 * 1024 * 1024)
    relative = receipt.get("observerDirectory", "")
    A.require(relative == "" or re.fullmatch(r"attempts/\d{4}", relative), "unsafe observer attempt directory")
    with native_writer(run / relative):
        return watch_locked(run, package, destination, registry, view_id, label, project_ref,
                            session_state, session_commands, sao_validator, review_outbox,
                            review_endpoint, site_controls)


def watch_locked(run, package, destination, registry=None, view_id="survival-observatory",
                 label="Survival simulation", project_ref=None, session_state=None,
                 session_commands=None, sao_validator=None, review_outbox=None,
                 review_endpoint="http://127.0.0.1:4317/mcp", site_controls=False):
    A.require(not destination.exists(), "select a fresh Mousecat feed directory")
    receipt = read(run / "run.json", 8 * 1024 * 1024)
    A.require(receipt.get("host") == "observer" and receipt["datasetAdmission"] == "unreviewed",
              "an explicit native observer run is required")
    A.require((session_state is None) == (session_commands is None),
              "study session state and commands must be supplied together")
    A.require((sao_validator is None) == (review_outbox is None),
              "review outbox requires the native validator")
    if session_state is not None:
        A.require(session_state.is_file() and not session_state.is_symlink(),
                  "study session state unavailable")
        A.require(session_commands.is_dir() and not session_commands.is_symlink(),
                  "study session command directory unavailable")
    session = str(uuid.UUID(receipt["sessionId"]))
    definition = read(package / "definition.json")
    view_definition = observer_definition(receipt, definition)
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
    registered = registry is None
    relative = receipt.get("observerDirectory", "")
    A.require(relative == "" or re.fullmatch(r"attempts/\d{4}", relative), "unsafe observer attempt directory")
    observer_root = run / relative
    native_root = observer_root / "native-view"
    sequence, acknowledged, pending = 0, 0, None
    native_cursor = None
    camera = ActivityCamera()
    displayed_camera = camera.view([])
    declared_sites = view_definition.get("observation", {}).get("sites", [])
    area_cameras = {site["id"]: ActivityCamera() for site in declared_sites} if len(declared_sites) > 1 else {}
    area_views = {key: value.view([]) for key, value in area_cameras.items()}
    area_cursor = 0
    requested_camera = None
    command_result = None
    last_observation = None
    people, observation_hours, population = [], None, {}
    displayed_people, available_ids = [], set()
    inspection_header = None
    images = {}
    feed_slots = {}
    receipt_cache, state_cache, frame_cache, observation_cache = (JsonSnapshot() for _ in range(4))
    archive_path, next_archive_scan = None, 0.0
    last_publication = None
    regional_views, regional_revision = [], None
    exit_after_publication = False
    review_status = review_message = review_interaction = None
    next_review_attempt = 0.0
    while True:
        try:
            receipt = receipt_cache.read(run / "run.json", 8 * 1024 * 1024)
        except (TransientRead, PermissionError):
            time.sleep(POLL_SECONDS)
            continue
        A.require(receipt["sessionId"] == session, "run session changed")
        ended = receipt["status"] in ("completed", "incomplete", "timed-out")
        study = study_view(session_state)
        if ended and study is not None and study["status"] == "running":
            # The runner receipt and supervisor state use separate atomic
            # files. Do not expose their brief transition as an impossible
            # ended view with a live checkpoint control.
            time.sleep(POLL_SECONDS)
            continue
        if ended and review_outbox is not None and review_status is None:
            if receipt["status"] != "completed":
                review_status, review_message = "not-eligible", "Run did not close as verified evidence."
            else:
                review_status, review_message = "pending", "Preparing completed outcomes for human review."
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
                        try:
                            inspection_header, inspection_details = inspection_view(observation.get("inspection"), people)
                        except (ValueError, KeyError, TypeError) as error:
                            inspection_header = (inspection_header or dict(sequence=0, capturedAtUnixMs=0,
                                worldHours=0, omittedPeople=0, omittedEvents=0)) | {
                                "status": "failed", "message": str(error)[:1024]}
                            inspection_details = {}
                        displayed_people = people_view(people, inspection_details,
                                                       (inspection_header or {}).get("selectedPersonId"))
                        available_ids = {p["id"] for p in displayed_people}
                        last_observation = observation_cache.revision
                except (FileNotFoundError, TransientRead, PermissionError):
                    # Inspection may fail while pixels and controls remain live.
                    observation_ready = False
            if requested_camera and frame.get("observerSequence", -1) >= requested_camera["native"]:
                if requested_camera.get("site"):
                    area_views[requested_camera["site"]] = requested_camera["value"]
                else:
                    displayed_camera = requested_camera["value"]
                requested_camera = None
            if pending is None:
                command_path = destination / "commands" / f"{acknowledged+1:016d}.json"
                if command_path.exists():
                    try:
                        command = read(command_path, 16384)
                        action = command.get("action")
                        if action in ("configure", "continue"):
                            A.require(study is not None, "durable study session controls unavailable")
                            if action == "continue":
                                A.require(ended and study["canContinue"], "study session is not saved")
                            publish_session_command(session_commands, command, session, acknowledged + 1)
                            control = None
                        else:
                            A.require(not ended, "native attempt has ended")
                            if action == "checkpoint":
                                A.require(study is not None and study["canCheckpoint"],
                                          "study session cannot save now")
                            control = translate(command, session, acknowledged + 1, state, people,
                                                bounds, native_cursor + 1)
                    except (ValueError, KeyError, TypeError, TransientRead) as error:
                        # Commands are immutable atomic files. Reject one bad
                        # request explicitly and keep later pause/stop usable.
                        acknowledged += 1
                        command_result = {"sequence": acknowledged, "status": "rejected", "message": str(error)[:512]}
                    else:
                        if command["action"] in ("configure", "continue"):
                            acknowledged += 1
                            command_result = {"sequence": acknowledged, "status": "applied",
                                "message": "Session settings saved" if command["action"] == "configure"
                                else "Session continuation requested"}
                            exit_after_publication = command["action"] == "continue"
                        elif command["action"] == "auto":
                            selected = command.get("siteId")
                            if area_cameras:
                                for key, value in area_cameras.items():
                                    if selected is None or selected == key:
                                        value.resume(); area_views[key] = value.view(people)
                            else:
                                camera.resume()
                                displayed_camera = camera.view(people)
                            acknowledged += 1
                            command_result = {"sequence": acknowledged, "status": "applied", "message": "Activity camera resumed"}
                        else:
                            if command["action"] in ("pan", "focus", "stop", "checkpoint"):
                                selected = command.get("siteId") or (declared_sites[0]["id"] if area_cameras else None)
                                if selected in area_cameras:
                                    area_cameras[selected].manual(); area_views[selected] = area_cameras[selected].view(people)
                                else:
                                    camera.manual(); displayed_camera = camera.view(people)
                                requested_camera = None
                            atomic(observer_root / "observer-control.properties", control)
                            native_cursor += 1
                            pending = {"native": native_cursor, "ui": acknowledged + 1}
                elif not ended and requested_camera is None and observation_ready and observation_hours is not None and time.time() - observation_path.stat().st_mtime <= 5:
                    active_camera, camera_state, camera_bounds, site_id = camera, state, bounds, None
                    if area_cameras:
                        site = declared_sites[area_cursor % len(declared_sites)]
                        area_cursor += 1
                        site_id = site["id"]
                        active_camera = area_cameras[site_id]
                        camera_state = state | next((value for value in state.get("sites", []) if value["id"] == site_id), {})
                        camera_bounds = (max(bounds[0], site["x"] - 32), max(bounds[1], site["y"] - 32),
                                         min(bounds[2], site["x"] + 32), min(bounds[3], site["y"] + 32))
                    plan = active_camera.plan(people, observation_hours, camera_state, camera_bounds, time.monotonic())
                    if plan is not None:
                        if site_id: plan["siteId"] = site_id
                        native_cursor += 1
                        plan["sequence"] = native_cursor
                        atomic(observer_root / "observer-control.properties", "".join(
                            f"{key}={value}\n" for key, value in sorted(plan.items())).encode("ascii"))
                        pending = {"native": native_cursor, "ui": None}
                        requested_camera = {"native": native_cursor, "value": active_camera.view(people), "site": site_id}
                        if site_id:
                            area_views[site_id] = {"mode": "automatic", "personIds": [], "summary": "Moving to the next local observed view"}
                        else:
                            displayed_camera = {"mode": "automatic", "personIds": [], "summary": "Moving to the next observed view"}
                        with (destination / "camera.jsonl").open("ab") as journal:
                            journal.write(encoded({"nativeSequence": native_cursor, "shot": camera.shot,
                                "observedHours": observation_hours, "personIds": active_camera.subjects,
                                "view": plan, "datasetAdmission": "unreviewed"}))
            viewport = viewport_view(state, frame)
            if frame_cache.revision != regional_revision:
                regional_views = native_views(native_root, frame, view_definition, bounds)
                regional_revision = frame_cache.revision
            if regional_views and not registered and not ended:
                # Loading screens can already contain viewport-shaped black
                # rectangles. Bind a new regional study only after its real
                # world clock advances and each native area has distinct pixels.
                if (state.get("worldAdvanced") is not True or frame.get("hours", 0) <= state.get("startHours", 0)
                        or len({region["image"]["sha256"] for region in regional_views}) != len(regional_views)):
                    time.sleep(POLL_SECONDS)
                    continue
            publication = (frame["sequence"], acknowledged, json.dumps(displayed_camera, sort_keys=True),
                           json.dumps(area_views, sort_keys=True),
                           json.dumps(viewport, sort_keys=True),
                           state["paused"], state.get("failure"), observation_ready, last_observation,
                           json.dumps(study, sort_keys=True), ended, receipt["status"],
                           review_status, review_message, review_interaction)
            if publication != last_publication:
                name = frame["image"]["file"]
                if name not in images:
                    atomic(destination / name, image_data(native_root, frame))
                    images[name] = dict(frame["image"])
                else:
                    A.require(images[name] == frame["image"], "native image filename reused with different metadata")
                published_camera = displayed_camera | {
                    "personIds": [key for key in displayed_camera["personIds"] if key in available_ids]}
                for key, feed in list(feed_slots.items()) if not regional_views else []:
                    visible = [person for person in feed["camera"]["personIds"] if person in available_ids]
                    if key not in visible:
                        del feed_slots[key]
                    else:
                        feed["camera"]["personIds"] = visible
                if regional_views:
                    feed_slots.clear()
                    for region in regional_views:
                        region_image = region["image"]
                        filename = region_image["file"]
                        if filename not in images:
                            atomic(destination / filename, image_data(native_root, {"image": region_image}))
                            images[filename] = dict(region_image)
                        else:
                            A.require(images[filename] == region_image, "regional image filename reused")
                        region_camera = area_views[region["id"]] | {"personIds": [key for key in area_views[region["id"]]["personIds"] if key in available_ids]}
                        feed = {"id": "site:" + region["id"], "label": region["label"],
                                "capturedAtUnixMs": frame["capturedAtUnixMs"], "image": region_image,
                                "camera": region_camera | {"summary": region["label"] + "; " + region_camera["summary"]}}
                        if site_controls:
                            feed["siteId"] = region["id"]
                            site = next((value for value in state.get("sites", []) if value["id"] == region["id"]), None)
                            A.require(site is not None, "regional viewport state unavailable")
                            region_viewport = viewport_view(state | site, frame)
                            if region_viewport is not None: feed["viewport"] = region_viewport
                        if inspection_header and inspection_header["capturedAtUnixMs"] <= frame["capturedAtUnixMs"]:
                            person = next((value for value in displayed_people if value["id"] in region_camera["personIds"]), None)
                            if person:
                                overlay = panel_overlay(person, inspection_header["capturedAtUnixMs"])
                                if overlay["groups"]: feed["overlay"] = overlay
                        feed_slots[feed["id"]] = feed
                    published_camera = {"mode": "automatic", "personIds": [], "summary": f"{len(regional_views)} native areas; one world clock and save"}
                else:
                    remember_feed(feed_slots, published_camera, frame, displayed_people,
                                  (inspection_header or {}).get("capturedAtUnixMs"))
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
                if state.get("inspectionError"):
                    summary += " Native inspector rendering failed: " + str(state["inspectionError"])[:512]
                if not observation_ready:
                    summary += " People inspection awaiting a complete observation."
                snapshot = {"schema": "mousecat.native-view/1",
                    "sessionId": session, "sequence": sequence, "capturedAtUnixMs": frame["capturedAtUnixMs"],
                    "image": frame["image"], "state": "ended" if ended else ("paused" if state["paused"] else "running"),
                    "title": "Simulation observatory", "summary": summary,
                    "people": displayed_people, "lastCommandSequence": acknowledged,
                    "camera": published_camera}
                if feed_slots:
                    snapshot["feeds"] = list(reversed(feed_slots.values()))
                if command_result:
                    snapshot["commandResult"] = command_result
                if viewport is not None:
                    snapshot["viewport"] = viewport
                if inspection_header:
                    snapshot["inspection"] = inspection_header
                    snapshot["panels"] = [{"id": "person-inspection", "label": "Native person inspector"}]
                if study is not None:
                    snapshot["study"] = dict(study)
                    if review_status is not None:
                        snapshot["study"].update(reviewStatus=review_status,
                            reviewMessage=review_message or "")
                        if review_interaction:
                            snapshot["study"]["reviewInteractionId"] = review_interaction
                atomic(destination / "latest.json", encoded(snapshot))
                # Keep the completed predecessor bound until this successor has
                # a complete, validated frame.  The registry replacement then
                # becomes a displayable handoff rather than an unavailable gap.
                if not registered:
                    register_feed(registry, view_id, label, project_ref, destination, session)
                    registered = True
                last_publication = publication
                protected = {feed["image"]["file"] for feed in feed_slots.values()}
                while len(images) > 8 + len(protected):
                    oldest = next((key for key in images if key not in protected), None)
                    if oldest is None:
                        break
                    del images[oldest]
                    (destination / oldest).unlink(missing_ok=True)
            if (ended and receipt["status"] == "completed" and study is not None
                    and study["status"] == "saved" and review_outbox is not None
                    and review_status in ("pending", "delayed")
                    and time.monotonic() >= next_review_attempt):
                try:
                    evidence_root = review_outbox / "evidence"
                    if not evidence_root.exists():
                        CognitionEpisodes.export(run, package, sao_validator, evidence_root)
                    queued = CognitionReview.queue(evidence_root, review_outbox, review_endpoint, session)
                    review_status = queued["status"]
                    review_interaction = queued.get("interactionId")
                    review_message = (f"{queued['observedDisagreements']} completed disagreements await human disposition."
                                      if review_status in ("queued", "already-queued")
                                      else "No completed model disagreements require disposition in this attempt.")
                except (OSError, ValueError, KeyError, TypeError, CognitionReview.Mousecat.MousecatError) as error:
                    print(f"world_watch: review handoff delayed ({type(error).__name__})", file=sys.stderr)
                    review_status = "delayed"
                    review_message = "Human review delivery is delayed; durable evidence remains available for retry."
                    next_review_attempt = time.monotonic() + 1.0
        except (FileNotFoundError, TransientRead, PermissionError):
            # A native observation file can be mid-write. The last complete,
            # hash-validated frame remains on screen with its original age.
            pass
        if exit_after_publication:
            return 0
        if ended and session_state is None:
            return 0 if receipt["status"] == "completed" else 1
        # A saved session has no advancing frame clock. Keep lifecycle controls
        # responsive without retaining the live bridge's 100 Hz idle poll.
        time.sleep(0.25 if ended and session_state is not None else POLL_SECONDS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--view-id", default="survival-observatory")
    parser.add_argument("--label", default="Survival simulation")
    parser.add_argument("--project-ref")
    parser.add_argument("--session-state", type=Path,
                        help="durable SAO study-session state exposed without local paths")
    parser.add_argument("--session-commands", type=Path,
                        help="durable SAO study-session lifecycle request directory")
    parser.add_argument("--sao-validator", type=Path,
                        help="SAO world_lab_run.py used before review extraction")
    parser.add_argument("--review-outbox", type=Path,
                        help="durable cognition-review evidence and queue receipts")
    parser.add_argument("--review-endpoint", default="http://127.0.0.1:4317/mcp")
    parser.add_argument("--site-controls", action="store_true",
                        help="publish optional per-site controls for a compatible Mousecat viewer")
    args = parser.parse_args()
    return watch(args.run.resolve(), args.package.resolve(), args.out.resolve(),
                 args.registry.resolve() if args.registry else None,
                 args.view_id, args.label, args.project_ref,
                 args.session_state.resolve() if args.session_state else None,
                 args.session_commands.resolve() if args.session_commands else None,
                 args.sao_validator.resolve() if args.sao_validator else None,
                 args.review_outbox.resolve() if args.review_outbox else None,
                 args.review_endpoint, args.site_controls)


if __name__ == "__main__":
    raise SystemExit(main())
