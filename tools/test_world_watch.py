import hashlib
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import world_watch as W


class ObserverCommands(unittest.TestCase):
    def setUp(self):
        self.session = "b3c4b15c-9564-4424-83b1-30ca3e3aab8c"
        self.state = {"viewX": 128, "viewY": 128, "viewZ": 0}
        self.people = [{"id": "person-1", "x": 200, "y": 190, "z": 0}]

    def command(self, action, **value):
        return dict(schema="mousecat.native-view-command/1", sessionId=self.session,
                    sequence=1, action=action, **value)

    def translate(self, command):
        return W.translate(command, self.session, 1, self.state, self.people, (0, 0, 511, 511))

    def test_camera_pan_does_not_move_residency_or_a_person(self):
        result = self.translate(self.command("pan", dx=8, dy=0)).decode()
        self.assertIn("viewX=136", result)
        self.assertNotIn("residency", result)
        self.assertEqual(self.people[0]["x"], 200)

    def test_focus_changes_observer_region_and_view_only(self):
        result = self.translate(self.command("focus", personId="person-1")).decode()
        self.assertIn("viewX=200", result)
        self.assertIn("residencyX=200", result)
        self.assertNotIn("person-1", result)

    def test_forged_or_out_of_order_commands_are_refused(self):
        invalid = [self.command("teleport", personId="person-1"),
                   self.command("pan", dx=9, dy=0), self.command("speed", value=True),
                   self.command("focus", personId="missing"), self.command("stop", path="../save"),
                   self.command("pause") | {"sessionId": "other"},
                   self.command("resume") | {"sequence": 2}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.translate(value)

    def test_bounds_are_enforced_at_translation(self):
        self.state["viewX"] = 511
        with self.assertRaises(ValueError):
            self.translate(self.command("pan", dx=8, dy=0))

    def test_image_identity_size_and_path(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            filename = "study-live-0000000000000001.png"
            data = b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + struct.pack(">II", 1280, 720)
            (root / filename).write_bytes(data)
            image = dict(file=filename, sha256=hashlib.sha256(data).hexdigest(), width=1280, height=720)
            self.assertEqual(W.image_data(root, {"image": image}), data)
            for change in ({"file": "../"+filename}, {"width": 40000}, {"sha256": "0"*64}):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    W.image_data(root, {"image": image | change})

    def test_partial_observation_is_transient_and_rejected_pan_does_not_block_stop(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            run, package, out = root / "run", root / "package", root / "feed"
            (run / "native-view").mkdir(parents=True)
            package.mkdir()
            receipt = dict(host="observer", datasetAdmission="unreviewed", sessionId=self.session,
                           definitionSha256="fixture", status="running")
            W.atomic(run / "run.json", W.encoded(receipt))
            W.atomic(package / "package.json", W.encoded({"definitionSha256": "fixture"}))
            W.atomic(package / "definition.json", W.encoded({"extent": {
                "minCellX": 0, "minCellY": 0, "cellsX": 2, "cellsY": 2}}))
            state = dict(detached=True, sequence=7, rejectedSequence=9, hours=2, paused=False, viewX=511, viewY=128, viewZ=0)
            W.atomic(run / "observer-state.json", W.encoded(state))
            (run / "observer-control.properties").write_text("sequence=12\npaused=true\n")
            filename = "study-live-0000000000000001.png"
            data = b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + struct.pack(">II", 960, 540)
            (run / "native-view" / filename).write_bytes(data)
            frame = dict(sequence=1, capturedAtUnixMs=1, image=dict(file=filename,
                sha256=hashlib.sha256(data).hexdigest(), width=960, height=540))
            W.atomic(run / "native-view/native.json", W.encoded(frame))
            live = run / "cache/Lua/StudyWorldLive.json"
            live.parent.mkdir(parents=True)
            live.write_bytes(b'{"unfinished":"\xc3')
            ticks = []

            def tick(_):
                ticks.append(len(ticks))
                if len(ticks) == 1:
                    W.atomic(out / "commands/0000000000000001.json", W.encoded(self.command("pan", dx=8, dy=0)))
                elif len(ticks) == 2:
                    snapshot = W.read(out / "latest.json")
                    self.assertEqual(snapshot["commandResult"]["status"], "rejected")
                    self.assertEqual((run / "observer-control.properties").read_text(), "sequence=12\npaused=true\n")
                    W.atomic(out / "commands/0000000000000002.json", W.encoded(self.command("stop") | {"sequence": 2}))
                    frame["sequence"] = 2
                    W.atomic(run / "native-view/native.json", W.encoded(frame))
                elif len(ticks) == 3:
                    self.assertIn("stop=true", (run / "observer-control.properties").read_text())
                    self.assertIn("sequence=13", (run / "observer-control.properties").read_text())
                    state["sequence"] = 13
                    W.atomic(run / "observer-state.json", W.encoded(state))
                    receipt["status"] = "completed"
                    W.atomic(run / "run.json", W.encoded(receipt))
                else:
                    self.fail("bridge stalled after a rejected command")

            with patch.object(W.time, "sleep", side_effect=tick):
                self.assertEqual(W.watch(run, package, out), 0)
            snapshot = W.read(out / "latest.json")
            self.assertEqual(snapshot["state"], "ended")
            self.assertEqual(snapshot["commandResult"], dict(sequence=2, status="applied", message="Observer request applied"))
            self.assertEqual(W.read(out / "session.json")["trainingRows"], 0)

    def test_incomplete_json_and_utf8_are_retryable(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "observation.json"
            for data in (b'{"people":', b'{"name":"\xc3'):
                path.write_bytes(data)
                with self.assertRaises(W.TransientRead):
                    W.read(path)

    def test_json_cache_invalidates_and_never_keeps_failed_or_racing_reads(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "live.json"
            W.atomic(path, W.encoded({"value": 1}))
            cache = W.JsonSnapshot()
            original_read = W.read
            with patch.object(W, "read", wraps=original_read) as reads:
                self.assertEqual(cache.read(path), {"value": 1})
                self.assertEqual(cache.read(path), {"value": 1})
                self.assertEqual(reads.call_count, 1)
                # Equal-size in-place changes still invalidate through mtime.
                stamp = path.stat().st_mtime_ns
                path.write_bytes(W.encoded({"value": 2}))
                os.utime(path, ns=(stamp, stamp + 1_000_000))
                self.assertEqual(cache.read(path), {"value": 2})
                self.assertEqual(reads.call_count, 2)
                W.atomic(path, b'{"value":')
                with self.assertRaises(W.TransientRead):
                    cache.read(path)
                self.assertEqual(cache.revision, 2)
            W.atomic(path, W.encoded({"value": 3}))

            def racing_read(file, limit):
                value = original_read(file, limit)
                W.atomic(file, W.encoded({"value": 4}))
                return value

            with patch.object(W, "read", side_effect=racing_read), self.assertRaises(W.TransientRead):
                cache.read(path)
            self.assertEqual(cache.revision, 2)
            self.assertEqual(cache.read(path), {"value": 4})
            self.assertEqual(cache.revision, 3)

    def watch_fixture(self, root):
        run, package, out = root / "run", root / "package", root / "feed"
        (run / "native-view").mkdir(parents=True)
        package.mkdir()
        receipt = dict(host="observer", datasetAdmission="unreviewed", sessionId=self.session,
                       definitionSha256="fixture", status="running")
        W.atomic(run / "run.json", W.encoded(receipt))
        W.atomic(package / "package.json", W.encoded({"definitionSha256": "fixture"}))
        W.atomic(package / "definition.json", W.encoded({"extent": {
            "minCellX": 0, "minCellY": 0, "cellsX": 2, "cellsY": 2}}))
        state = dict(detached=True, sequence=0, hours=2, paused=True, viewX=128, viewY=128, viewZ=0)
        W.atomic(run / "observer-state.json", W.encoded(state))
        live = run / "cache/Lua/StudyWorldLive.json"
        live.parent.mkdir(parents=True)
        observation = dict(datasetAdmission="unreviewed", definitionSha256="fixture", hours=2,
                           people=self.people, population=dict(total=1, represented=1))
        W.atomic(live, W.encoded(observation))
        return run, package, out, receipt, state, live, observation

    def test_bridge_delivers_20hz_without_reparsing_people_or_recopying_images(self):
        with tempfile.TemporaryDirectory() as name:
            run, package, out, receipt, state, live, observation = self.watch_fixture(Path(name))
            native = run / "native-view"
            original_read, original_atomic = W.read, W.atomic
            clock_us, next_capture_us = 0, 50_000
            observed = set()

            def publish_frame(index, captured_ms):
                filename = f"study-live-{index:016d}.png"
                data = b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + struct.pack(">II", 960, 540) + bytes([index])
                original_atomic(native / filename, data)
                original_atomic(native / "native.json", W.encoded(dict(sequence=index,
                    observerSequence=state["sequence"], capturedAtUnixMs=max(1, captured_ms),
                    image=dict(file=filename, sha256=hashlib.sha256(data).hexdigest(), width=960, height=540))))

            publish_frame(1, 0)

            def tick(seconds):
                nonlocal clock_us, next_capture_us
                snapshot = original_read(out / "latest.json")
                observed.add(snapshot["image"]["file"])
                self.assertLessEqual(clock_us / 1000 - snapshot["capturedAtUnixMs"], 25)
                clock_us += round(seconds * 1_000_000)
                # A native publisher advances independently at 20 Hz. A slow
                # bridge only sees its latest frame, making missed frames real.
                while next_capture_us <= clock_us and next_capture_us < 1_000_000:
                    publish_frame(next_capture_us // 50_000 + 1, next_capture_us // 1000)
                    next_capture_us += 50_000
                if clock_us == 25_000:
                    original_atomic(out / "commands/0000000000000001.json", W.encoded(self.command("pause")))
                if clock_us == 75_000:
                    self.assertIn("sequence=1", (run / "observer-control.properties").read_text())
                    state["sequence"] = 1
                    original_atomic(run / "observer-state.json", W.encoded(state))
                    observation["people"] = [self.people[0] | {"record": {"forename": "Ada"}}]
                    observation["hours"] = 2.1
                    original_atomic(live, W.encoded(observation))
                if clock_us >= 1_000_000:
                    receipt["status"] = "completed"
                    original_atomic(run / "run.json", W.encoded(receipt))
                self.assertLessEqual(clock_us, 1_100_000, "bridge did not stop")

            with patch.object(W.time, "sleep", side_effect=tick), \
                    patch.object(W.time, "monotonic", side_effect=lambda: clock_us / 1_000_000), \
                    patch.object(W, "read", wraps=original_read) as reads, \
                    patch.object(W, "image_data", wraps=W.image_data) as images, \
                    patch.object(W, "people_view", wraps=W.people_view) as people, \
                    patch.object(W, "atomic", wraps=original_atomic) as writes:
                self.assertEqual(W.watch(run, package, out), 0)
            observed.add(original_read(out / "latest.json")["image"]["file"])
            self.assertEqual(len(observed), 20, "bridge dropped 20 Hz producer frames")
            self.assertEqual(images.call_count, 20, "unchanged images were reread and rehashed")
            self.assertEqual(sum(call.args[0].suffix == ".png" for call in writes.call_args_list), 20)
            self.assertEqual(sum(call.args[0] == live for call in reads.call_args_list), 2)
            self.assertEqual(people.call_count, 2)
            self.assertEqual(original_read(out / "latest.json")["lastCommandSequence"], 1)
            self.assertEqual(original_read(out / "latest.json")["people"][0]["label"], "Ada")
            self.assertEqual(original_read(out / "session.json")["trainingRows"], 0)

    def test_cached_image_name_cannot_change_identity(self):
        with tempfile.TemporaryDirectory() as name:
            run, package, out, receipt, state, live, observation = self.watch_fixture(Path(name))
            filename = "study-live-0000000000000001.png"
            data = b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + struct.pack(">II", 960, 540)
            (run / "native-view" / filename).write_bytes(data)
            frame = dict(sequence=1, capturedAtUnixMs=1, image=dict(file=filename,
                sha256=hashlib.sha256(data).hexdigest(), width=960, height=540))
            W.atomic(run / "native-view/native.json", W.encoded(frame))

            def replace_identity(_):
                frame["sequence"] += 1
                frame["image"]["sha256"] = "0" * 64
                W.atomic(run / "native-view/native.json", W.encoded(frame))

            with patch.object(W.time, "sleep", side_effect=replace_identity), \
                    self.assertRaisesRegex(ValueError, "filename reused"):
                W.watch(run, package, out)

    def test_native_writer_excludes_another_bridge_and_releases_lease(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            with W.native_writer(root):
                with self.assertRaisesRegex(ValueError, "already has"):
                    with W.native_writer(root):
                        self.fail("second writer admitted")
            with W.native_writer(root):
                pass

    def test_dense_quiet_group_gives_each_person_a_turn(self):
        camera = W.ActivityCamera()
        people = [{"id": str(i), "x": 40, "y": 40, "z": 0} for i in range(8)]
        seen = set()
        for i in range(20):
            camera.plan(people, 2+i*.1, dict(paused=False, viewX=40, viewY=40, viewZ=0), (0,0,511,511), i*23)
            seen.update(camera.subjects)
        self.assertEqual(seen, {p["id"] for p in people})

    def test_automatic_subject_waits_for_pixels_and_manual_control_cancels_it(self):
        for reject in (False, True):
            with self.subTest(reject=reject), tempfile.TemporaryDirectory() as name:
                root = Path(name)
                run, package, out = root / "run", root / "package", root / "feed"
                native = run / "native-view"
                native.mkdir(parents=True)
                package.mkdir()
                receipt = dict(host="observer", datasetAdmission="unreviewed", sessionId=self.session,
                               definitionSha256="fixture", status="running")
                W.atomic(run / "run.json", W.encoded(receipt))
                W.atomic(package / "package.json", W.encoded({"definitionSha256": "fixture"}))
                W.atomic(package / "definition.json", W.encoded({"extent": {
                    "minCellX": 0, "minCellY": 0, "cellsX": 2, "cellsY": 2}}))
                state = dict(detached=True, sequence=0, hours=2, paused=False, viewX=128, viewY=128, viewZ=0)
                W.atomic(run / "observer-state.json", W.encoded(state))
                filename = "study-live-0000000000000001.png"
                data = b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + struct.pack(">II", 960, 540)
                (native / filename).write_bytes(data)
                frame = dict(sequence=1, observerSequence=0, capturedAtUnixMs=1, image=dict(file=filename,
                    sha256=hashlib.sha256(data).hexdigest(), width=960, height=540))
                W.atomic(native / "native.json", W.encoded(frame))
                live = run / "cache/Lua/StudyWorldLive.json"
                live.parent.mkdir(parents=True)
                W.atomic(live, W.encoded(dict(datasetAdmission="unreviewed", definitionSha256="fixture",
                                            people=self.people, population={}, hours=2)))
                ticks = []

                def tick(_):
                    ticks.append(len(ticks))
                    snap = W.read(out / "latest.json")
                    if len(ticks) == 1:
                        self.assertEqual(snap["camera"]["personIds"], [])
                        self.assertEqual(snap["lastCommandSequence"], 0)
                        state["rejectedSequence" if reject else "sequence"] = 1
                        W.atomic(run / "observer-state.json", W.encoded(state))
                    elif len(ticks) == 2:
                        self.assertEqual(snap["camera"]["personIds"], [])
                        frame.update(sequence=2, observerSequence=1)
                        W.atomic(native / "native.json", W.encoded(frame))
                    elif len(ticks) == 3:
                        self.assertEqual(snap["camera"]["personIds"], [] if reject else ["person-1"])
                        W.atomic(out / "commands/0000000000000001.json", W.encoded(self.command("pan", dx=1, dy=0)))
                    elif len(ticks) == 4:
                        self.assertEqual(snap["camera"]["mode"], "manual")
                        self.assertEqual(snap["camera"]["personIds"], [])
                        self.assertIn("sequence=2", (run / "observer-control.properties").read_text())
                        state["sequence"] = 2
                        W.atomic(run / "observer-state.json", W.encoded(state))
                        W.atomic(out / "commands/0000000000000002.json", W.encoded(self.command("stop") | {"sequence": 2}))
                        # A late old automatic capture cannot restore its target.
                        frame["sequence"] += 1
                        W.atomic(native / "native.json", W.encoded(frame))
                    elif len(ticks) == 5:
                        self.assertEqual(snap["camera"]["personIds"], [])
                        self.assertEqual(snap["lastCommandSequence"], 1)
                        self.assertIn("sequence=3", (run / "observer-control.properties").read_text())
                        state["sequence"] = 3
                        receipt["status"] = "completed"
                        W.atomic(run / "observer-state.json", W.encoded(state))
                        W.atomic(run / "run.json", W.encoded(receipt))
                    else:
                        self.fail("observer command loop stalled")

                with patch.object(W.time, "sleep", side_effect=tick):
                    self.assertEqual(W.watch(run, package, out), 0)

    def test_activity_camera_rotates_tracks_and_yields_without_changing_people(self):
        import copy
        camera = W.ActivityCamera()
        people = [{"id": str(i), "x": x, "y": 40, "z": 0,
                   "positionSource": "native-body", "record": {"forename": f"Person {i}"},
                   "context": {"controller": {"state": "IDLE"}}}
                  for i, x in enumerate((40, 42, 240, 242, 440))]
        original = copy.deepcopy(people)
        state = dict(paused=False, viewX=0, viewY=0, viewZ=0)
        bounds = (0, 0, 511, 511)
        first = camera.plan(people, 2, state, bounds, 0)
        subjects = tuple(camera.subjects)
        state.update({k: first[k] for k in ("viewX", "viewY", "viewZ")})
        self.assertIsNone(camera.plan(people, 2, state, bounds, 10))
        second = camera.plan(people, 2.1, state, bounds, 23)
        self.assertNotEqual(tuple(camera.subjects), subjects)
        self.assertGreater(abs(first["viewX"] - second["viewX"]), 100)
        self.assertLessEqual(len(camera.subjects), 5)
        self.assertEqual(people, original)
        camera.manual()
        self.assertIsNone(camera.plan(people, 3, state, bounds, 100))
        self.assertEqual(camera.view(people)["mode"], "manual")
        camera.resume()
        self.assertIsNone(camera.plan(people, 3, state | {"paused": True}, bounds, 101))
        self.assertIsNotNone(camera.plan(people, 3, state, bounds, 102))

    def test_activity_camera_uses_changes_and_does_not_focus_dead_or_invalid_people(self):
        camera = W.ActivityCamera()
        people = [{"id": "still", "x": 30, "y": 40, "z": 0},
                  {"id": "moving", "x": 230, "y": 40, "z": 0},
                  {"id": "dead", "x": 20, "y": 20, "z": 0, "record": {"dead": True}},
                  {"id": "invalid", "x": float("nan"), "y": 40, "z": 0}]
        bounds = (0, 0, 511, 511)
        camera.update(people, 2, bounds)
        people[1]["x"] += 3
        camera.plan(people, 2.1, dict(paused=False, viewX=0, viewY=0, viewZ=0), bounds, 0)
        self.assertEqual(camera.subjects, ["moving"])
        self.assertEqual(camera.view(people)["mode"], "automatic")


if __name__ == "__main__":
    unittest.main()
