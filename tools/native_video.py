"""Validate and relay immutable native fMP4 fragments without changing clocks."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import time
import uuid

MAX_MEDIA = 16 * 1024 * 1024
MAX_INIT = 2 * 1024 * 1024


def require(ok, message):
    if not ok:
        raise ValueError(message)


def fields(value, required):
    require(isinstance(value, dict) and set(value) == set(required.split()), "native video fields differ")


def integer(value, minimum=0, maximum=2**53 - 1):
    require(type(value) is int and minimum <= value <= maximum, "native video integer differs")


def number(value, minimum=0, maximum=2**53 - 1):
    require(type(value) in (int, float) and math.isfinite(value) and minimum <= value <= maximum,
            "native video number differs")


def text(value, maximum, nonempty=False):
    require(isinstance(value, str) and len(value) <= maximum and (not nonempty or value)
            and not re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value), "native video text differs")


def validate(value, *, now=None, schema="sao-study-video/1"):
    fields(value, "schema streamId state mimeType codecs width height fps init segments stats message")
    require(value["schema"] == schema and str(uuid.UUID(value["streamId"])) == value["streamId"],
            "native video identity differs")
    require(value["state"] in ("starting", "running", "ended", "failed") and value["mimeType"] == "video/mp4",
            "native video state differs")
    integer(value["fps"], 30, 120)
    integer(value["width"], 0, 4096); integer(value["height"], 0, 2160)
    text(value["message"], 512)
    require(not re.search(r"(?:[A-Za-z]:[\\/]|file://|/(?:Users|home|tmp)/)", value["message"]),
            "native video message contains a local path")
    fields(value["stats"], "capturedFrames encodedFrames droppedFrames")
    for count in value["stats"].values(): integer(count)
    require(value["stats"]["encodedFrames"] + value["stats"]["droppedFrames"] <= value["stats"]["capturedFrames"],
            "native video counts differ")
    init = value["init"]
    if init is None:
        require(value["codecs"] is None and value["state"] != "running" and not value["segments"],
                "native video has no initialization")
    else:
        fields(init, "file sha256")
        require(init["file"] == f"video-{value['streamId']}-init.mp4"
                and isinstance(value["codecs"], str) and re.fullmatch(r"avc1\.[0-9a-f]{6}", value["codecs"])
                and value["width"] > 0 and value["height"] > 0, "native video initialization differs")
        require(re.fullmatch(r"[0-9a-f]{64}", init["sha256"]) is not None, "native video hash differs")
    segments = value["segments"]
    require(isinstance(segments, list) and len(segments) <= 8, "native video retention differs")
    previous = None
    clock = int(time.time() * 1000) if now is None else now
    for segment in segments:
        fields(segment, "sequence file sha256 ptsStartMs durationMs capturedAtUnixMs endCapturedAtUnixMs observerSequence worldHours endWorldHours firstFrameSequence lastFrameSequence sites")
        integer(segment["sequence"], 1)
        require(segment["file"] == f"video-{value['streamId']}-{segment['sequence']:016d}.m4s"
                and re.fullmatch(r"[0-9a-f]{64}", segment["sha256"]) is not None, "native video fragment identity differs")
        for key in ("ptsStartMs", "worldHours", "endWorldHours"): number(segment[key])
        number(segment["durationMs"], math.nextafter(0, 1), 60000)
        for key in ("capturedAtUnixMs", "endCapturedAtUnixMs", "observerSequence", "firstFrameSequence", "lastFrameSequence"):
            integer(segment[key], 1 if key in ("firstFrameSequence", "lastFrameSequence") else 0)
        require(segment["capturedAtUnixMs"] <= segment["endCapturedAtUnixMs"] <= clock + 2000
                and segment["worldHours"] <= segment["endWorldHours"]
                and segment["firstFrameSequence"] <= segment["lastFrameSequence"] <= value["stats"]["capturedFrames"],
                "native video sample clocks differ")
        if previous:
            require(segment["sequence"] > previous["sequence"]
                    and segment["ptsStartMs"] >= previous["ptsStartMs"] + previous["durationMs"] - 1
                    and segment["capturedAtUnixMs"] >= previous["endCapturedAtUnixMs"]
                    and segment["worldHours"] >= previous["endWorldHours"]
                    and segment["firstFrameSequence"] > previous["lastFrameSequence"], "native video fragment order differs")
        sites = segment["sites"]
        require(isinstance(sites, list) and len(sites) <= 4, "native video sites differ")
        ids, slots, rectangles = set(), set(), []
        for site in sites:
            fields(site, "id label slot x y z left top width height zoom targetZoom")
            require(isinstance(site["id"], str) and re.fullmatch(r"[a-z][a-z0-9-]{0,47}", site["id"])
                    and site["id"] not in ids, "native video site identity differs")
            ids.add(site["id"]); text(site["label"], 160, True)
            integer(site["slot"], 0, 3); require(site["slot"] not in slots, "native video slot duplicated"); slots.add(site["slot"])
            number(site["x"], -2**31, 2**31); number(site["y"], -2**31, 2**31)
            number(site["z"], -32, math.nextafter(32, -math.inf))
            for key in ("left", "top"): integer(site[key])
            for key in ("width", "height"): integer(site[key], 1)
            require(site["left"] + site["width"] <= value["width"] and site["top"] + site["height"] <= value["height"],
                    "native video crop exceeds pixels")
            rectangle = (site["left"], site["top"], site["left"] + site["width"], site["top"] + site["height"])
            require(all(rectangle[2] <= other[0] or rectangle[0] >= other[2] or rectangle[3] <= other[1] or rectangle[1] >= other[3]
                        for other in rectangles), "native video crop overlaps")
            rectangles.append(rectangle)
            number(site["zoom"], .01, 100); number(site["targetZoom"], .01, 100)
        previous = segment
    return value


def boxes(data, start=0, end=None):
    end = len(data) if end is None else end
    result = []
    while start < end:
        require(start + 8 <= end, "native video truncated box")
        size, kind = struct.unpack_from(">I4s", data, start); header = 8
        if size == 1:
            require(start + 16 <= end, "native video truncated extended box")
            size = struct.unpack_from(">Q", data, start + 8)[0]; header = 16
        require(size >= header and start + size <= end, "native video incomplete box")
        result.append((kind.decode("ascii"), start, start + header, start + size))
        start += size
    return result


def init_info(data, video):
    root = boxes(data)
    require([box[0] for box in root] == ["ftyp", "moov"], "native video initialization boxes differ")
    children = boxes(data, root[1][2], root[1][3])
    require(any(box[0] == "mvex" for box in children), "native video is not fragmented")
    tracks = [box for box in children if box[0] == "trak"]
    require(len(tracks) == 1, "native video track count differs")
    def child(parent, kind, skip=0):
        found = [box for box in boxes(data, parent[2] + skip, parent[3]) if box[0] == kind]
        require(len(found) == 1, "native video initialization track differs")
        return found[0]
    mdia = child(tracks[0], "mdia"); mdhd = child(mdia, "mdhd")
    require(mdhd[3] - mdhd[2] >= 4, "native video media time truncated")
    version = data[mdhd[2]]
    require(version in (0, 1), "native video media time version differs")
    offset = mdhd[2] + (20 if version else 12)
    require(offset + 4 <= mdhd[3], "native video media time truncated")
    timescale = struct.unpack_from(">I", data, offset)[0]; require(timescale > 0, "native video timescale differs")
    stbl = child(child(mdia, "minf"), "stbl"); stsd = child(stbl, "stsd")
    require(stsd[2] + 8 <= stsd[3] and struct.unpack_from(">I", data, stsd[2] + 4)[0] == 1,
            "native video sample description differs")
    avc1 = child(stsd, "avc1", 8); require(avc1[2] + 78 <= avc1[3], "native video sample entry truncated")
    width, height = struct.unpack_from(">HH", data, avc1[2] + 24)
    require((width, height) == (video["width"], video["height"]), "native video dimensions differ")
    avcc = child(avc1, "avcC", 78)
    require(avcc[3] - avcc[2] >= 7 and data[avcc[2]] == 1
            and "avc1." + data[avcc[2] + 1:avcc[2] + 4].hex() == video["codecs"], "native video codec differs")
    mvex = child(root[1], "mvex"); trex = child(mvex, "trex")
    require(trex[3] - trex[2] == 24, "native video defaults differ")
    track, _, duration, size, flags = struct.unpack_from(">IIIII", data, trex[2] + 4)
    return {"timescale": timescale, "track": track, "duration": duration, "size": size, "flags": flags}


def media_info(data, descriptor, defaults):
    root = boxes(data)
    require([box[0] for box in root] == ["moof", "mdat"], "native video media boxes differ")
    moof, mdat = root
    trafs = [box for box in boxes(data, moof[2], moof[3]) if box[0] == "traf"]
    require(len(trafs) == 1, "native video fragment tracks differ")
    children = boxes(data, trafs[0][2], trafs[0][3]); by_kind = {box[0]: box for box in children}
    require(len(children) == len(by_kind) and set(by_kind) == {"tfhd", "tfdt", "trun"}, "native video fragment structure differs")
    tfhd = by_kind["tfhd"]; flags = int.from_bytes(data[tfhd[2] + 1:tfhd[2] + 4], "big")
    require(tfhd[3] - tfhd[2] >= 8 and flags & 0x20000 and not flags & 1, "native video base offset differs")
    require(struct.unpack_from(">I", data, tfhd[2] + 4)[0] == defaults["track"], "native video track identity differs")
    cursor = tfhd[2] + 8; duration, size, sample_flags = defaults["duration"], defaults["size"], defaults["flags"]
    for bit, key in ((2, "description"), (8, "duration"), (16, "size"), (32, "flags")):
        if flags & bit:
            require(cursor + 4 <= tfhd[3], "native video defaults truncated")
            item = struct.unpack_from(">I", data, cursor)[0]; cursor += 4
            if key == "duration": duration = item
            if key == "size": size = item
            if key == "flags": sample_flags = item
    require(cursor == tfhd[3], "native video defaults tail differs")
    tfdt = by_kind["tfdt"]
    require(tfdt[3] - tfdt[2] >= 4, "native video decode time truncated")
    version = data[tfdt[2]]
    require(version in (0, 1) and tfdt[3] - tfdt[2] == (12 if version else 8), "native video decode time differs")
    pts = struct.unpack_from(">Q" if version else ">I", data, tfdt[2] + 4)[0]
    trun = by_kind["trun"]; require(trun[3] - trun[2] >= 8, "native video sample run truncated")
    run_flags = int.from_bytes(data[trun[2] + 1:trun[2] + 4], "big")
    count = struct.unpack_from(">I", data, trun[2] + 4)[0]; require(1 <= count <= 7200, "native video sample count differs")
    cursor = trun[2] + 8; first_flags = None
    require(run_flags & 1, "native video sample offset missing")
    require(cursor + 4 <= trun[3], "native video sample offset truncated")
    data_offset = struct.unpack_from(">i", data, cursor)[0]; cursor += 4
    require(moof[1] + data_offset == mdat[2], "native video sample offset differs")
    if run_flags & 4:
        require(cursor + 4 <= trun[3], "native video first sample truncated")
        first_flags = struct.unpack_from(">I", data, cursor)[0]; cursor += 4
    sizes, durations, first = 0, 0, None
    for index in range(count):
        current_duration, current_size, current_flags = duration, size, first_flags if index == 0 and first_flags is not None else sample_flags
        for bit, key in ((256, "duration"), (512, "size"), (1024, "flags"), (2048, "composition")):
            if run_flags & bit:
                require(cursor + 4 <= trun[3], "native video samples truncated")
                item = struct.unpack_from(">I", data, cursor)[0]; cursor += 4
                if key == "duration": current_duration = item
                if key == "size": current_size = item
                if key == "flags": current_flags = item
                if key == "composition": require(item == 0, "native video reordered samples refused")
        require(current_duration > 0 and current_size > 0, "native video empty sample")
        if first is None: first = current_flags
        sizes += current_size; durations += current_duration
    require(cursor == trun[3] and sizes == mdat[3] - mdat[2], "native video sample payload differs")
    require(first is not None and not first & 0x10000 and (first >> 24) & 3 == 2, "native video fragment is not independently decodable")
    require(abs(pts * 1000 / defaults["timescale"] - descriptor["ptsStartMs"]) <= 1
            and abs(durations * 1000 / defaults["timescale"] - descriptor["durationMs"]) <= 1,
            "native video metadata time differs")
    require(count <= descriptor["lastFrameSequence"] - descriptor["firstFrameSequence"] + 1,
            "native video receipt order differs")
    return count


class VideoRelay:
    """Copy only verified descriptors; a malformed video never poisons PNG fallback."""
    def __init__(self, source: Path, destination: Path):
        self.source, self.destination = source.resolve(), destination.resolve()
        self.cache = {}
        self.defaults = {}
        self.previous = None

    def data(self, descriptor, maximum):
        path = self.source / descriptor["file"]
        require(path.parent == self.source and not path.is_symlink() and path.is_file()
                and path.resolve().parent == self.source and path.stat().st_size <= maximum,
                "unsafe native video file")
        data = path.read_bytes()
        require(len(data) <= maximum and hashlib.sha256(data).hexdigest() == descriptor["sha256"],
                "native video hash differs")
        return data

    def publish(self, value, *, now=None):
        validate(value, now=now)
        previous = self.previous
        if previous is not None and previous["streamId"] == value["streamId"]:
            require(previous["init"] is None or previous["init"] == value["init"], "native video initialization reused")
            if previous["init"] is not None:
                require(all(previous[key] == value[key] for key in ("codecs", "width", "height", "fps")),
                        "native video format reused")
            require(all(value["stats"][key] >= previous["stats"][key] for key in previous["stats"]),
                    "native video counts regressed")
            if previous["segments"]:
                require(value["segments"] and value["segments"][-1]["sequence"] >= previous["segments"][-1]["sequence"],
                        "native video receipt regressed")
            if previous["state"] in ("ended", "failed"):
                require(value["state"] == previous["state"], "native video state regressed")
        descriptors = ([value["init"]] if value["init"] else []) + value["segments"]
        for descriptor in descriptors:
            key = descriptor["file"]
            digest = descriptor["sha256"]
            identity = (digest, json.dumps(descriptor, sort_keys=True, separators=(",", ":")))
            require(key not in self.cache or self.cache[key] == identity, "native video filename reused")
            if key in self.cache: continue
            data = self.data(descriptor, MAX_INIT if descriptor is value["init"] else MAX_MEDIA)
            if descriptor is value["init"]:
                self.defaults[value["streamId"]] = init_info(data, value)
            else:
                media_info(data, descriptor, self.defaults[value["streamId"]])
            path = self.destination / key
            temporary = path.with_name(path.name + ".tmp")
            temporary.write_bytes(data); os.replace(temporary, path)
            self.cache[key] = identity
        # Keep a short predecessor grace window for already issued requests.
        # Memory and disk are bounded to the current init plus 24 recent media.
        protected = {descriptor["file"] for descriptor in descriptors}
        while len(self.cache) > 25:
            old = next((key for key in self.cache if key not in protected), None)
            if old is None: break
            self.cache.pop(old); (self.destination / old).unlink(missing_ok=True)
        if len(self.defaults) > 2:
            self.defaults = {value["streamId"]: self.defaults[value["streamId"]]} if value["streamId"] in self.defaults else {}
        self.previous = json.loads(json.dumps(value))
        return value | {"schema": "mousecat.native-video/1"}


def acknowledged_frame(video, fallback):
    """Camera acknowledgment uses exact native epochs, independently of PNG cadence."""
    stable = next((segment for segment in reversed((video or {}).get("segments", [])) if segment["sites"]), None)
    if stable is None or stable["endCapturedAtUnixMs"] < fallback["capturedAtUnixMs"]:
        return fallback, None
    return {"observerSequence": stable["observerSequence"], "capturedAtUnixMs": stable["endCapturedAtUnixMs"]}, stable["sites"]
