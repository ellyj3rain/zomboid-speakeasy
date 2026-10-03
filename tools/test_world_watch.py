import hashlib
import json
import copy
import os
import struct
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import world_watch as W


class ObserverCommands(unittest.TestCase):
    def test_current_camera_controls_survive_an_older_image_epoch(self):
        viewport = dict(zoom=1, targetZoom=1.25, zoomLevels=[.5, 1, 1.25, 2])
        state = dict(sequence=12, updatedAtUnixMs=2000, viewport=viewport)
        frame = dict(observerSequence=11, capturedAtUnixMs=1700)
        self.assertIsNone(W.viewport_view(state, frame))
        self.assertEqual(W.camera_controls(state), dict(capturedAtUnixMs=2000, viewport=viewport))
        self.assertIsNone(W.camera_controls({}))
        self.assertIsNone(W.camera_controls(dict(viewport=viewport)))
        for clock in (True, -1, 1.5, 2**53):
            with self.subTest(clock=clock), self.assertRaises(ValueError):
                W.camera_controls(state | dict(updatedAtUnixMs=clock))
        with self.assertRaises(ValueError):
            W.camera_controls(state | dict(viewport=viewport | dict(targetZoom=3)))

    def test_independent_observer_layout_preserves_world_definition(self):
        definition = dict(extent=dict(minCellX=0,minCellY=0,cellsX=2,cellsY=2),
                          observation=dict(sites=[dict(id='original',label='Original',x=64,y=64,z=0)]))
        original = copy.deepcopy(definition)
        layout = dict(schema='sao-study-observer-layout/1',sites=[
            dict(id='west',label='West',x=64,y=64,z=0),dict(id='east',label='East',x=256,y=64,z=0)])
        def receipt(value):
            return dict(observerLayout=value,observerLayoutSha256=hashlib.sha256(json.dumps(value,
                ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()).hexdigest())
        result = W.observer_definition(receipt(layout),definition)
        self.assertEqual(result['observation']['sites'],layout['sites'])
        self.assertEqual(definition,original)
        self.assertIs(W.observer_definition({},definition),definition)
        bad=receipt(copy.deepcopy(layout));bad['observerLayout']['sites'][0]['x']+=1
        with self.assertRaises(ValueError): W.observer_definition(bad,definition)
        for change in (dict(x=True),dict(x=512),dict(x=511.999999),dict(z=32),dict(id='east'),
                       dict(x=256.000001,y=64,z=0),dict(label='bad\nlabel')):
            bad=copy.deepcopy(layout);bad['sites'][0].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError): W.observer_definition(receipt(bad),definition)
        for key in ('observerLayout','observerLayoutSha256'):
            bad=receipt(layout);del bad[key]
            with self.assertRaises(ValueError): W.observer_definition(bad,definition)

    def setUp(self):
        self.session = "b3c4b15c-9564-4424-83b1-30ca3e3aab8c"
        self.state = {"viewX": 128, "viewY": 128, "viewZ": 0}
        self.people = [{"id": "person-1", "x": 200, "y": 190, "z": 0}]

    @staticmethod
    def layout_receipt(sites):
        layout = dict(schema="sao-study-observer-layout/1", sites=sites)
        return dict(observerLayout=layout, observerLayoutSha256=hashlib.sha256(json.dumps(
            layout, ensure_ascii=True, allow_nan=False, sort_keys=True,
            separators=(",", ":")).encode()).hexdigest())

    def test_subject_layout_keeps_seal_and_rejects_invalid_or_duplicate_assignments(self):
        definition = dict(extent=dict(minCellX=0, minCellY=0, cellsX=2, cellsY=2),
                          observation=dict(sites=[]))
        sites = [dict(id="west", label="Phillip McKinley", x=100, y=100, z=0, subjectId="sao-1"),
                 dict(id="east", label="Barney Billingsley", x=104, y=100, z=0, subjectId="sao-2")]
        original = copy.deepcopy(definition)
        self.assertEqual(W.observer_definition(self.layout_receipt(sites), definition)["observation"]["sites"], sites)
        self.assertEqual(definition, original)
        self.assertEqual(len(W.observer_definition(self.layout_receipt(sites[:1]), definition)["observation"]["sites"]), 1)
        for invalid in (None, True, "", "sao 1", "bad\n", "é", "x" * 129, "sao-2"):
            bad = copy.deepcopy(sites)
            bad[0]["subjectId"] = invalid
            with self.subTest(subjectId=invalid), self.assertRaises(ValueError):
                W.observer_definition(self.layout_receipt(bad), definition)
        unsealed = self.layout_receipt(copy.deepcopy(sites))
        unsealed["observerLayout"]["sites"][0]["subjectId"] = "changed"
        with self.assertRaises(ValueError):
            W.observer_definition(unsealed, definition)

    def test_bound_cameras_do_not_converge_on_urgent_people_or_a_nearby_group(self):
        bounds = (0, 0, 511, 511)
        sites = [dict(id="west", x=100, y=100, z=0, subjectId="sao-1"),
                 dict(id="east", x=104, y=100, z=0, subjectId="sao-2")]
        cameras = [W.site_camera(site, bounds) for site in sites]
        people = [dict(id="sao-1", x=100, y=100, z=0, record=dict(forename="Phillip", surname="McKinley")),
                  dict(id="sao-2", x=104, y=100, z=0, record=dict(forename="Barney", surname="Billingsley", lastLivingHealth=.3)),
                  dict(id="neighbor", x=102, y=100, z=0)]
        original = copy.deepcopy(people)
        states = [dict(paused=False, viewX=0, viewY=0, viewZ=0) for _ in sites]
        for index in range(8):
            for site, camera, state in zip(sites, cameras, states):
                plan = camera.plan(people, 2 + index * .1, state, W.site_bounds(site, bounds), index * 4)
                if plan:
                    state.update(plan)
                self.assertEqual(camera.subjects, [site["subjectId"]])
                person = next(person for person in people if person["id"] == site["subjectId"])
                self.assertEqual(state["viewX"], person["x"])
                self.assertEqual(camera.view(people)["personIds"], [site["subjectId"]])
        self.assertEqual(people, original)
        people[0].update(x=260, y=270, z=1)
        moved = cameras[0].plan(people, 3, states[0], W.site_bounds(sites[0], bounds), 40)
        self.assertEqual(moved, dict(viewX=260, viewY=270, viewZ=1, residencyX=260, residencyY=270, residencyZ=1))
        self.assertEqual(W.site_bounds(sites[0], bounds), bounds)
        legacy = dict(id="area", x=100, y=100, z=0)
        self.assertEqual(type(W.site_camera(legacy, bounds)), W.ActivityCamera)
        self.assertEqual(W.site_bounds(legacy, bounds), (68, 68, 132, 132))

    def test_subject_camera_pause_manual_resume_and_unavailable_are_safe(self):
        bounds = (0, 0, 511, 511)
        camera = W.SubjectCamera("person-1", bounds)
        state = dict(paused=False, viewX=0, viewY=0, viewZ=0)
        self.assertIsNotNone(camera.plan(self.people, 2, state, bounds, 0))
        camera.manual()
        self.assertIsNone(camera.plan(self.people, 2.1, state, bounds, 4))
        self.assertEqual(camera.view(self.people)["personIds"], [])
        camera.resume()
        self.assertEqual(camera.subject_id, "person-1")
        self.assertIsNone(camera.plan(self.people, 3, state | dict(paused=True), bounds, 5))
        self.assertIsNone(camera.plan(self.people, 3, state | dict(failure="failed"), bounds, 6))
        self.assertIsNotNone(camera.plan(self.people, 3, state, bounds, 7))
        for people, reason in (([], "not observed"),
                               ([self.people[0] | dict(record=dict(dead=True))], "recorded dead"),
                               ([self.people[0] | dict(x=600)], "outside observed world"),
                               ([self.people[0] | dict(x=float("nan"))], "position unavailable")):
            people = [*people, dict(id="alternate", x=20, y=20, z=0)]
            with self.subTest(reason=reason):
                self.assertIsNone(camera.plan(people, 4, state | dict(paused=True), bounds, 8))
                view = camera.view(people)
                self.assertEqual(view["personIds"], [])
                self.assertIn(reason, view["summary"])
                self.assertNotIn("Following", view["summary"])
                camera.resume()
                self.assertIsNone(camera.plan(people, 4, state, bounds, 9))
                self.assertEqual(camera.subject_id, "person-1")
        self.assertIsNotNone(camera.plan(self.people, 5, state, bounds, 10))
        self.assertEqual(camera.subjects, ["person-1"])

    def test_subject_identity_requires_applied_captured_pose_but_not_latest_archive_pose(self):
        camera = W.SubjectCamera("person-1", (0, 0, 511, 511))
        plan = camera.plan(self.people, 2, dict(paused=False, viewX=0, viewY=0, viewZ=0), camera.bounds, 0)
        value = camera.view(self.people)
        capture = dict(native=7, applied=True, position=plan)
        frame, pose = dict(observerSequence=7), dict(x=200, y=190, z=0)
        self.people[0]["x"] = 204  # A later source sample must not relabel earlier pixels.
        self.assertEqual(W.subject_view(camera, value, capture, self.people, frame, pose)["personIds"], ["person-1"])
        self.assertEqual(W.subject_view(camera, value | dict(personIds=["neighbor"]), capture,
                                       self.people, frame, pose)["personIds"], [])
        for wrong_capture, wrong_frame, wrong_pose in ((capture | dict(applied=False), frame, pose),
                (capture, dict(observerSequence=6), pose), (capture, dict(observerSequence=True), pose),
                (capture, frame, pose | dict(x=204)), (capture, frame, pose | dict(z=1))):
            with self.subTest(capture=wrong_capture, frame=wrong_frame, pose=wrong_pose):
                self.assertEqual(W.subject_view(camera, value, wrong_capture, self.people,
                                              wrong_frame, wrong_pose)["personIds"], [])
        unavailable = W.subject_view(camera, value, capture, [], frame, pose)
        self.assertEqual(unavailable["personIds"], [])
        self.assertNotIn("Following", unavailable["summary"])
        county_capture = dict(native=9, applied=True, position=dict(viewX=10001.005859375, viewY=9000.123046875, viewZ=1))
        self.assertTrue(W.camera_capture_matches(county_capture, dict(observerSequence=9),
                                                dict(x=10001.006, y=9000.123, z=1)))
        self.assertFalse(W.camera_capture_matches(county_capture, dict(observerSequence=9),
                                                 dict(x=10001.007, y=9000.123, z=1)))

    def subject_watch_fixture(self, root, sites):
        run, package, out = root / "run", root / "package", root / "feed"
        (run / "native-view").mkdir(parents=True)
        package.mkdir()
        receipt = dict(host="observer", datasetAdmission="unreviewed", sessionId=self.session,
                       definitionSha256="fixture", status="running") | self.layout_receipt(sites)
        W.atomic(run / "run.json", W.encoded(receipt))
        W.atomic(package / "package.json", W.encoded(dict(definitionSha256="fixture")))
        W.atomic(package / "definition.json", W.encoded(dict(
            extent=dict(minCellX=0, minCellY=0, cellsX=2, cellsY=2), observation=dict(sites=[]))))
        state = dict(detached=True, sequence=0, rejectedSequence=-1, hours=2, paused=False,
                     viewX=sites[0]["x"], viewY=sites[0]["y"], viewZ=sites[0]["z"],
                     sites=[dict(id=site["id"], viewX=site["x"], viewY=site["y"], viewZ=site["z"])
                            for site in sites])
        people = [dict(id=site["subjectId"], x=site["x"], y=site["y"], z=site["z"],
                       record=dict(forename=site["label"], lastLivingHealth=.3 if index else 1))
                  for index, site in enumerate(sites)]
        observation = dict(datasetAdmission="unreviewed", definitionSha256="fixture", people=people,
                           population=dict(total=len(people)), hours=2)
        live = run / "cache/Lua/StudyWorldLive.json"
        live.parent.mkdir(parents=True)
        frame = dict(sequence=0, observerSequence=0, capturedAtUnixMs=1000)

        def publish(native_sequence=None, location=None):
            if native_sequence is not None:
                state["sequence"] = native_sequence
            if location:
                site_id, x, y, z = location
                target = next(value for value in state["sites"] if value["id"] == site_id)
                target.update(viewX=x, viewY=y, viewZ=z)
                if site_id == sites[0]["id"]:
                    state.update(viewX=x, viewY=y, viewZ=z)
            frame.update(sequence=frame["sequence"] + 1, observerSequence=state["sequence"],
                         capturedAtUnixMs=frame["capturedAtUnixMs"] + 100)
            filename = f"study-live-{frame['sequence']:016d}.png"
            def image(name, width, marker):
                data = b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + struct.pack(">II", width, 540) + bytes([marker])
                (run / "native-view" / name).write_bytes(data)
                return dict(file=name, sha256=hashlib.sha256(data).hexdigest(), width=width, height=540)
            frame["image"] = image(filename, 960 * len(sites), 0)
            if len(sites) > 1:
                frame["views"] = [dict(id=site["id"], label=site["label"], slot=index,
                    x=state["sites"][index]["viewX"], y=state["sites"][index]["viewY"],
                    z=state["sites"][index]["viewZ"], left=960 * index, top=0,
                    image=image(filename.replace(".png", f"-site{index}.png"), 960, index + 1))
                    for index, site in enumerate(sites)]
            W.atomic(run / "observer-state.json", W.encoded(state))
            W.atomic(run / "native-view/native.json", W.encoded(frame))
            W.atomic(live, W.encoded(observation))
        publish()
        return run, package, out, receipt, state, observation, publish

    def test_two_subject_feeds_acknowledge_independently_and_resume_the_same_person(self):
        with tempfile.TemporaryDirectory() as name:
            sites = [dict(id="west", label="Phillip McKinley", x=100, y=100, z=0, subjectId="sao-1"),
                     dict(id="east", label="Barney Billingsley", x=104, y=100, z=0, subjectId="sao-2")]
            run, package, out, receipt, state, observation, publish = self.subject_watch_fixture(Path(name), sites)
            ticks = []
            now = [0]
            def tick(_):
                ticks.append(len(ticks) + 1)
                now[0] += 1
                views = {feed["id"]: feed for feed in W.read(out / "latest.json")["feeds"]}
                west, east = views["site:west"], views["site:east"]
                control = (run / "observer-control.properties").read_text()
                step = len(ticks)
                if step == 1:
                    self.assertEqual((west["camera"]["personIds"], east["camera"]["personIds"]), ([], []))
                    self.assertIn("siteId=west", control)
                    publish(1)
                elif step == 2:
                    self.assertEqual((west["camera"]["personIds"], east["camera"]["personIds"]), (["sao-1"], []))
                    self.assertIn("siteId=east", control)
                    publish(2)
                elif step == 3:
                    self.assertEqual((west["camera"]["personIds"], east["camera"]["personIds"]), (["sao-1"], ["sao-2"]))
                    self.assertEqual((west["label"], east["label"]), ("Phillip McKinley", "Barney Billingsley"))
                    W.atomic(out / "commands/0000000000000001.json", W.encoded(self.command("pan", siteId="west", dx=8, dy=0)))
                elif step == 4:
                    self.assertEqual(west["camera"]["mode"], "manual")
                    self.assertEqual(east["camera"]["personIds"], ["sao-2"])
                    self.assertIn("siteId=west", control)
                    self.assertIn("viewX=108", control)
                    publish(3, ("west", 108, 100, 0))
                    W.atomic(out / "commands/0000000000000002.json", W.encoded(self.command("auto", siteId="west") | dict(sequence=2)))
                elif step == 5:
                    self.assertEqual(west["camera"]["personIds"], [])
                    self.assertEqual(east["camera"]["personIds"], ["sao-2"])
                elif step == 6:
                    self.assertEqual(east["camera"]["personIds"], ["sao-2"])
                elif step == 7:
                    self.assertIn("sequence=4", control)
                    self.assertIn("siteId=west", control)
                    self.assertIn("viewX=100", control)
                    self.assertIn("residencyX=100", control)
                    publish(4, ("west", 100, 100, 0))
                elif step == 8:
                    self.assertEqual((west["camera"]["personIds"], east["camera"]["personIds"]), (["sao-1"], ["sao-2"]))
                    observation["people"][0]["x"] = 260
                    observation["hours"] = 2.1
                    publish()
                elif step == 9:
                    self.assertIn("sequence=5", control)
                    self.assertIn("siteId=west", control)
                    self.assertIn("viewX=260", control)
                    self.assertIn("residencyX=260", control)
                    publish(5, ("west", 260, 100, 0))
                elif step == 10:
                    self.assertEqual((west["camera"]["personIds"], east["camera"]["personIds"]), (["sao-1"], ["sao-2"]))
                    observation["people"] = observation["people"][1:]
                    publish()
                elif step == 11:
                    self.assertEqual(west["camera"]["personIds"], [])
                    self.assertIn("not observed", west["camera"]["summary"])
                    self.assertNotIn("Following", west["camera"]["summary"])
                    self.assertEqual(east["camera"]["personIds"], ["sao-2"])
                    receipt["status"] = "completed"
                    W.atomic(run / "run.json", W.encoded(receipt))
                else:
                    self.fail("subject bridge stalled")
            with patch.object(W.time, "sleep", side_effect=tick), patch.object(W.time, "monotonic", side_effect=lambda: now[0]):
                self.assertEqual(W.watch(run, package, out, site_controls=True), 0)
            journal = [json.loads(line) for line in (out / "camera.jsonl").read_text().splitlines()]
            self.assertEqual([(row["siteId"], row["assignedSubjectId"]) for row in journal],
                             [("west", "sao-1"), ("east", "sao-2"), ("west", "sao-1"), ("west", "sao-1")])
            self.assertTrue(all(row["personIds"] == [row["assignedSubjectId"]] for row in journal))
            self.assertTrue(all(row["datasetAdmission"] == "unreviewed" for row in journal))

    def test_single_subject_layout_does_not_fall_back_to_activity_rotation(self):
        with tempfile.TemporaryDirectory() as name:
            site = dict(id="west", label="Phillip McKinley", x=100, y=100, z=0, subjectId="sao-1")
            run, package, out, receipt, state, observation, publish = self.subject_watch_fixture(Path(name), [site])
            observation["people"].append(dict(id="urgent", x=104, y=100, z=0, record=dict(lastLivingHealth=.2)))
            publish()
            ticks = []
            def tick(_):
                ticks.append(len(ticks))
                snap = W.read(out / "latest.json")
                if len(ticks) == 1:
                    self.assertEqual(snap["camera"]["personIds"], [])
                    self.assertIn("viewX=100", (run / "observer-control.properties").read_text())
                    publish(1)
                elif len(ticks) == 2:
                    self.assertEqual(snap["camera"]["personIds"], ["sao-1"])
                    self.assertIn("Following Phillip McKinley", snap["camera"]["summary"])
                    self.assertEqual(snap["feeds"][0]["camera"]["personIds"], ["sao-1"])
                    observation["people"][0]["record"]["dead"] = True
                    publish()
                elif len(ticks) == 3:
                    self.assertEqual(snap["camera"]["personIds"], [])
                    self.assertIn("recorded dead", snap["camera"]["summary"])
                    self.assertNotIn("feeds", snap)
                    receipt["status"] = "completed"
                    W.atomic(run / "run.json", W.encoded(receipt))
                else:
                    self.fail("single subject bridge stalled")
            with patch.object(W.time, "sleep", side_effect=tick):
                self.assertEqual(W.watch(run, package, out), 0)
            journal = [json.loads(line) for line in (out / "camera.jsonl").read_text().splitlines()]
            self.assertEqual((journal[0]["siteId"], journal[0]["assignedSubjectId"]), ("west", "sao-1"))

    def test_subject_zoom_preserves_follow_and_other_site_projection_through_motion(self):
        with tempfile.TemporaryDirectory() as name:
            sites = [dict(id="west", label="Phillip McKinley", x=100, y=100, z=0, subjectId="sao-1"),
                     dict(id="east", label="Barney Billingsley", x=104, y=100, z=0, subjectId="sao-2")]
            run, package, out, receipt, state, observation, publish = self.subject_watch_fixture(Path(name), sites)
            viewport = dict(zoom=1, targetZoom=1, zoomLevels=[.5, 1, 1.25, 1.5])
            state["viewport"] = copy.deepcopy(viewport)
            for site in state["sites"]:
                site["viewport"] = copy.deepcopy(viewport)
            publish()
            ticks, now = [], [0]
            def tick(_):
                ticks.append(len(ticks) + 1)
                now[0] += 1
                snap = W.read(out / "latest.json")
                views = {feed["id"]: feed for feed in snap["feeds"]}
                west, east = views["site:west"], views["site:east"]
                control = (run / "observer-control.properties").read_text()
                step = len(ticks)
                if step == 1:
                    publish(1)
                elif step == 2:
                    publish(2)
                elif step == 3:
                    self.assertEqual((west["camera"]["personIds"], east["camera"]["personIds"]), (["sao-1"], ["sao-2"]))
                    W.atomic(out / "commands/0000000000000001.json", W.encoded(self.command("zoom", siteId="west", value=1)))
                elif step == 4:
                    self.assertEqual(control, "sequence=3\nsiteId=west\nzoomStep=1\n")
                    self.assertEqual((west["camera"]["mode"], east["camera"]["mode"]), ("automatic", "automatic"))
                    self.assertEqual((west["camera"]["personIds"], east["camera"]["personIds"]), (["sao-1"], ["sao-2"]))
                    state["sites"][0]["viewport"].update(zoom=1.25, targetZoom=1.25)
                    state["viewport"].update(zoom=1.25, targetZoom=1.25)
                    publish(3)
                elif step == 5:
                    self.assertEqual((west["viewport"]["zoom"], east["viewport"]["zoom"]), (1.25, 1))
                    self.assertEqual((west["camera"]["personIds"], east["camera"]["personIds"]), (["sao-1"], ["sao-2"]))
                    observation["people"][0]["x"] = 120
                    observation["hours"] = 2.1
                    publish()
                elif step == 6:
                    self.assertIn("sequence=4", control)
                    self.assertIn("siteId=west", control)
                    self.assertIn("viewX=120", control)
                    self.assertNotIn("zoom", control.lower())
                    self.assertEqual(east["camera"]["personIds"], ["sao-2"])
                    publish(4, ("west", 120, 100, 0))
                elif step == 7:
                    self.assertEqual((west["viewport"]["zoom"], east["viewport"]["zoom"]), (1.25, 1))
                    self.assertEqual((west["camera"]["mode"], east["camera"]["mode"]), ("automatic", "automatic"))
                    self.assertEqual((west["camera"]["personIds"], east["camera"]["personIds"]), (["sao-1"], ["sao-2"]))
                    self.assertEqual(snap["lastCommandSequence"], 1)
                    receipt["status"] = "completed"
                    W.atomic(run / "run.json", W.encoded(receipt))
                else:
                    self.fail("subject zoom bridge stalled")
            with patch.object(W.time, "sleep", side_effect=tick), patch.object(W.time, "monotonic", side_effect=lambda: now[0]):
                self.assertEqual(W.watch(run, package, out, site_controls=True), 0)

    def test_regional_pixels_are_bound_to_distinct_native_rectangles_and_sites(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            filename = "study-live-0000000000000001.png"
            frame = dict(image=dict(file=filename, width=1920, height=1080), views=[])
            sites = []
            for index, (left, top) in enumerate(((0, 0), (960, 0), (0, 540))):
                data = b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + struct.pack(">II", 960, 540) + bytes([index])
                image_name = filename.replace(".png", f"-site{index}.png")
                (root / image_name).write_bytes(data)
                image = dict(file=image_name, sha256=hashlib.sha256(data).hexdigest(), width=960, height=540)
                site = dict(id=f"area-{index}", label=f"Area {index}", x=64 + 128 * index, y=64, z=0)
                sites.append(site)
                frame["views"].append(site | dict(slot=index, left=left, top=top, image=image))
            definition = dict(observation=dict(sites=sites))
            self.assertEqual(len(W.native_views(root, frame, definition, (0, 0, 511, 511))), 3)
            for change in (dict(id="area-0"), dict(left=0, top=0), dict(slot=0), dict(x=999)):
                corrupt = copy.deepcopy(frame); corrupt["views"][1].update(change)
                with self.subTest(change=change), self.assertRaises(ValueError):
                    W.native_views(root, corrupt, definition, (0, 0, 511, 511))
            corrupt = copy.deepcopy(frame); corrupt["views"][2]["image"]["sha256"] = "0" * 64
            with self.assertRaises(ValueError): W.native_views(root, corrupt, definition, (0, 0, 511, 511))
            with self.assertRaises(ValueError): W.native_views(root, dict(image=frame["image"]), definition, (0, 0, 511, 511))
            self.assertEqual(W.native_views(root, dict(image=frame["image"]), {}, (0, 0, 511, 511)), [])

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

    def test_regional_commands_target_declared_native_slot_only(self):
        self.state["sites"] = [dict(id="farm", viewX=300, viewY=310, viewZ=0,
                                   viewport=dict(zoom=1, targetZoom=1, zoomLevels=[0.5, 1, 2]))]
        before = copy.deepcopy(self.state)
        result = self.translate(self.command("pan", siteId="farm", dx=8, dy=0)).decode()
        self.assertIn("siteId=farm", result); self.assertIn("viewX=308", result)
        self.assertNotIn("residency", result)
        self.assertIn("siteId=farm", self.translate(self.command("zoom", siteId="farm", value=1)).decode())
        self.assertEqual(self.state, before)
        for action, values in (("pan", dict(siteId="missing", dx=1, dy=0)),
                               ("pause", dict(siteId="farm")), ("zoom", dict(siteId="../farm", value=1))):
            with self.assertRaises(ValueError): self.translate(self.command(action, **values))

    def test_native_zoom_changes_only_native_projection(self):
        self.state["viewport"] = dict(zoom=1.0, targetZoom=1.0, zoomLevels=[0.5, 1, 1.5, 2.5])
        before = copy.deepcopy((self.state, self.people))
        for step in (-1, 1):
            self.assertEqual(self.translate(self.command("zoom", value=step)).decode(),
                             f"sequence=1\nzoomStep={step}\n")
        self.assertEqual((self.state, self.people), before)
        for invalid in (0, 2, -2, True, 1.5, "1", None):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.translate(self.command("zoom", value=invalid))
        with self.assertRaises(ValueError):
            self.translate(self.command("zoom", value=1, speed=3))
        del self.state["viewport"]
        with self.assertRaises(ValueError):
            self.translate(self.command("zoom", value=1))

    def test_native_viewport_is_bound_to_exact_captured_command(self):
        value = dict(zoom=1.5, targetZoom=1.5, zoomLevels=[0.5, 1, 1.5, 2.5])
        state = dict(sequence=12, viewport=value)
        self.assertEqual(W.viewport_view(state, dict(observerSequence=12)), value)
        for frame in ({}, dict(observerSequence=11), dict(observerSequence=13), dict(observerSequence=True)):
            self.assertIsNone(W.viewport_view(state, frame))
        for change in (dict(zoom=float("nan")), dict(zoom=True), dict(targetZoom=3), dict(targetZoom=1.2),
                       dict(zoomLevels=[]), dict(zoomLevels=[1, 0.5]), dict(zoomLevels=[1, 1]),
                       dict(zoomLevels=[0, 1]), dict(zoomLevels=[0.5, 1, 17]), dict(extra="untrusted")):
            with self.subTest(change=change), self.assertRaises(ValueError):
                W.viewport_view(dict(sequence=12, viewport=value | change), dict(observerSequence=12))
        copy_value = W.viewport_view(state)
        copy_value["zoomLevels"].append(4)
        self.assertEqual(state["viewport"], value)

    def test_watch_acknowledges_native_zoom_and_waits_for_its_image(self):
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
            state = dict(detached=True, sequence=0, rejectedSequence=-1, hours=2, paused=True,
                         speed=3, viewX=128, viewY=128, viewZ=0,
                         viewport=dict(zoom=1, targetZoom=1, zoomLevels=[0.5, 1, 1.5, 2.5]))
            W.atomic(run / "observer-state.json", W.encoded(state))
            filename = "study-live-0000000000000001.png"
            data = b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + struct.pack(">II", 960, 540)
            (run / "native-view" / filename).write_bytes(data)
            frame = dict(sequence=1, observerSequence=0, capturedAtUnixMs=1,
                         image=dict(file=filename, sha256=hashlib.sha256(data).hexdigest(), width=960, height=540))
            W.atomic(run / "native-view/native.json", W.encoded(frame))
            ticks = []
            def tick(_):
                ticks.append(len(ticks))
                if len(ticks) == 1:
                    self.assertEqual(W.read(out / "latest.json")["viewport"]["zoom"], 1)
                    W.atomic(out / "commands/0000000000000001.json", W.encoded(self.command("zoom", value=1)))
                elif len(ticks) == 2:
                    self.assertEqual((run / "observer-control.properties").read_text(), "sequence=1\nzoomStep=1\n")
                    self.assertEqual(W.read(out / "latest.json")["lastCommandSequence"], 0)
                    state["sequence"] = 1
                    state["viewport"].update(zoom=1.5, targetZoom=1.5)
                    W.atomic(run / "observer-state.json", W.encoded(state))
                elif len(ticks) == 3:
                    view = W.read(out / "latest.json")
                    self.assertEqual(view["commandResult"]["status"], "applied")
                    self.assertNotIn("viewport", view)  # Native acknowledgement alone is not an image.
                    frame.update(sequence=2, observerSequence=1)
                    W.atomic(run / "native-view/native.json", W.encoded(frame))
                    receipt["status"] = "completed"
                    W.atomic(run / "run.json", W.encoded(receipt))
                else:
                    self.fail("native zoom bridge stalled")
            with patch.object(W.time, "sleep", side_effect=tick):
                self.assertEqual(W.watch(run, package, out), 0)
            view = W.read(out / "latest.json")
            self.assertEqual(view["viewport"]["zoom"], 1.5)
            self.assertEqual(view["camera"]["mode"], "automatic")
            self.assertEqual((state["paused"], state["speed"], state["viewX"]), (True, 3, 128))

    def test_focus_changes_observer_region_and_view_only(self):
        result = self.translate(self.command("focus", personId="person-1")).decode()
        self.assertIn("viewX=200", result)
        self.assertIn("residencyX=200", result)
        self.assertNotIn("person-1", result)

    def test_selection_and_panels_preserve_camera_and_clock(self):
        selected = self.translate(self.command("select", personId="person-1")).decode()
        self.assertEqual(selected, "selectedPersonId=person-1\nsequence=1\n")
        panel = self.translate(self.command("panel", personId="person-1", panelId="person-inspection", visible=True)).decode()
        self.assertEqual(panel, "panelId=person-inspection\npanelPersonId=person-1\npanelVisible=true\nsequence=1\n")
        for value in (self.command("select", personId="missing"),
                      self.command("select", personId="person-1", speed=3),
                      self.command("panel", personId="person-1", panelId="arbitrary", visible=True),
                      self.command("panel", personId="person-1", panelId="person-inspection", visible=1)):
            with self.subTest(value=value), self.assertRaises(ValueError): self.translate(value)

    def test_person_id_is_one_literal_java_property(self):
        self.people = [{"id": "a=é\\b"}]
        value = self.translate(self.command("select", personId=self.people[0]["id"])).decode()
        self.assertIn("selectedPersonId=a\\u003d\\u00e9\\u005cb\n", value)

    def test_independently_timed_inspection_and_stage_fields(self):
        value = dict(sequence=3, capturedAtUnixMs=1000, worldHours=2, status="available", message="",
                     omittedPeople=0, omittedEvents=0, selectedPersonId="person-1", people={"person-1": {
                     "sections": [dict(id="needs", label="Needs", source="native", perspective="physical",
                                       status="available", message="", rows=[dict(label="Hunger", value="0.5")])],
                     "events": [dict(id="line-1", capturedAtUnixMs=900, worldHours=1.9, source="Voice",
                                     stage="emitted", summary="Exact line", actorId="person-1")]}})
        before = copy.deepcopy(value)
        header, detail = W.inspection_view(value, self.people)
        self.assertEqual(value, before)
        self.assertEqual(header["capturedAtUnixMs"], 1000)
        self.assertEqual(detail["person-1"]["events"][0]["stage"], "emitted")
        value["status"] = "failed"; value["message"] = "native read failed"
        failed, _ = W.inspection_view(value, self.people)
        self.assertEqual(failed["capturedAtUnixMs"], 1000)
        for mutate in (lambda v: v["people"]["person-1"]["events"][0].update(inferredHearers=["unknown"]),
                       lambda v: v["people"]["person-1"]["events"][0].update(capturedAtUnixMs=1001),
                       lambda v: v.update(selectedPersonId="missing"),
                       lambda v: v["people"]["person-1"]["sections"][0].update(rows=[{"label":"x","value":0.5}])):
            bad = copy.deepcopy(value); mutate(bad)
            with self.assertRaises(ValueError): W.inspection_view(bad, self.people)
        self.assertEqual(W.inspection_view(None, self.people), (None, {}))
        initial = dict(sequence=0, capturedAtUnixMs=0, worldHours=0, status="failed", message="first read failed",
                       omittedPeople=0, omittedEvents=0, people={})
        self.assertEqual(W.inspection_view(initial, self.people)[0]["status"], "failed")
        initial["status"] = "available"
        with self.assertRaises(ValueError): W.inspection_view(initial, self.people)

    def test_lua_empty_arrays_and_stored_memory_label(self):
        value = dict(sequence=1, capturedAtUnixMs=1, worldHours=2, status="available", message="",
                     omittedPeople=0, omittedEvents=0, people={"person-1": {"sections": {}, "events": {}}})
        _, detail = W.inspection_view(value, self.people)
        self.assertEqual(detail["person-1"], {"sections": [], "events": []})
        view = W.people_view([self.people[0] | {"context": {"perceptionAvailable": True, "beliefCounts": {"people": 2, "zombies": 3}}}], detail)
        self.assertIn("Remembered person locations: 2", view[0]["summary"])
        self.assertIn("Stored threat memories: 3", view[0]["summary"])
        self.assertEqual(view[0]["events"], [])

    def test_existing_thirteen_section_native_inspection_preserves_bounds(self):
        section_ids = ("needs", "life", "attention", "medication", "preparation", "horse", "mobile",
                       "planning", "inventory", "pressure", "currentAction", "sourceWork", "processes")
        sections = [dict(id=key, label=key, source="native", perspective="observed",
                         status="available", message="", rows=[dict(label="State", value="Recorded")])
                    for key in section_ids]
        value = dict(sequence=1, capturedAtUnixMs=1000, worldHours=2, status="available", message="",
                     omittedPeople=0, omittedEvents=0, people={"person-1": dict(sections=sections, events=[])})
        header, details = W.inspection_view(value, self.people)
        projected = W.people_view(self.people, details)
        self.assertEqual(header["status"], "available")
        self.assertEqual([s["id"] for s in projected[0]["sections"]], list(section_ids))
        for count in (14, 15, 16):
            value["people"]["person-1"]["sections"].append(sections[0] | dict(id=f"additional-{count}"))
        W.inspection_view(value, self.people)
        value["people"]["person-1"]["sections"].append(sections[0] | dict(id="additional-17"))
        with self.assertRaisesRegex(ValueError, "collection limit"):
            W.inspection_view(value, self.people)
        value["people"]["person-1"]["sections"] = sections[:13]
        value["people"]["person-1"]["sections"][0]["rows"] *= 49
        with self.assertRaisesRegex(ValueError, "collection limit"):
            W.inspection_view(value, self.people)

    def test_recorded_reason_is_visible_without_inferred_intent(self):
        section = dict(id="pressure", label="Pressure", source="Controller", perspective="Recorded decision",
                       status="available", message="", rows=[dict(label="detail", value="waits for daylight")])
        details = {self.people[0]["id"]: {"sections": [section], "events": []}}
        before = copy.deepcopy(details)
        view = W.people_view(self.people, details)
        self.assertIn("Recorded reason: waits for daylight", view[0]["summary"])
        self.assertEqual(details, before)
        section["status"] = "failed"
        self.assertNotIn("Recorded reason:", W.people_view(self.people, details)[0]["summary"])
        self.assertNotIn("Recorded reason:", W.people_view(self.people)[0]["summary"])

    def test_forged_or_out_of_order_commands_are_refused(self):
        invalid = [self.command("teleport", personId="person-1"),
                   self.command("pan", dx=9, dy=0), self.command("speed", value=True),
                   self.command("focus", personId="missing"), self.command("stop", path="../save"),
                   self.command("pause") | {"sessionId": "other"},
                   self.command("resume") | {"sequence": 2}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.translate(value)

    def test_durable_session_projection_and_lifecycle_requests_remain_review_only(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); state_path = root / "study-session.json"; commands = root / "commands"
            commands.mkdir()
            study_id = "95d05f2c-9d8b-4f3e-a867-d4744073d7be"
            state = dict(schema="sao-study-session/1", id=study_id, label="Survival simulation",
                         status="saved", attempt=3, attemptDurationSeconds=7200, autoContinue=False,
                         worldHours=38.25, accumulatedWorldHours=36.25, canCheckpoint=False,
                         canContinue=True, updatedAtUnixMs=1000, datasetAdmission="unreviewed",
                         behavioralVerdict=None, lastStopReason="wall-time-limit", feedGeneration=4,
                         processedCommands=[])
            W.atomic(state_path, W.encoded(state))
            view = W.study_view(state_path)
            self.assertEqual(view["attemptDurationSeconds"], 7200)
            self.assertTrue(view["canContinue"])
            self.assertNotIn("datasetAdmission", view)
            configure = self.command("configure", attemptDurationSeconds=10800, autoContinue=True)
            event = W.publish_session_command(commands, configure, self.session, 1)
            self.assertEqual(event["schema"], "sao-study-session-command/1")
            self.assertEqual(event["attemptDurationSeconds"], 10800)
            self.assertEqual(len(list(commands.glob("*.json"))), 1)
            self.assertEqual(W.publish_session_command(commands, configure, self.session, 1), event)
            continuation = self.command("continue") | {"sequence": 2}
            W.publish_session_command(commands, continuation, self.session, 2)
            self.assertEqual(len(list(commands.glob("*.json"))), 2)
            for invalid in (self.command("continue", path="run"),
                            self.command("configure", attemptDurationSeconds=29, autoContinue=False),
                            self.command("configure", attemptDurationSeconds=3600, autoContinue=1)):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    W.publish_session_command(commands, invalid, self.session, invalid["sequence"])
            state["datasetAdmission"] = "approved"
            W.atomic(state_path, W.encoded(state))
            with self.assertRaises(ValueError):
                W.study_view(state_path)

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
            command_written = state_changed = False
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
                nonlocal clock_us, next_capture_us, command_written, state_changed
                snapshot = original_read(out / "latest.json")
                observed.add(snapshot["image"]["file"])
                # Faster bridge polls may legitimately re-read the current
                # 20 Hz frame; it must never lag a full producer interval.
                self.assertLessEqual(clock_us / 1000 - snapshot["capturedAtUnixMs"], 50)
                clock_us += round(seconds * 1_000_000)
                # A native publisher advances independently at 20 Hz. A slow
                # bridge only sees its latest frame, making missed frames real.
                while next_capture_us <= clock_us and next_capture_us < 1_000_000:
                    publish_frame(next_capture_us // 50_000 + 1, next_capture_us // 1000)
                    next_capture_us += 50_000
                if not command_written and clock_us >= 25_000:
                    original_atomic(out / "commands/0000000000000001.json", W.encoded(self.command("pause")))
                    command_written = True
                if not state_changed and clock_us >= 75_000:
                    self.assertIn("sequence=1", (run / "observer-control.properties").read_text())
                    state["sequence"] = 1
                    original_atomic(run / "observer-state.json", W.encoded(state))
                    observation["people"] = [self.people[0] | {"record": {"forename": "Ada"}}]
                    observation["hours"] = 2.1
                    original_atomic(live, W.encoded(observation))
                    state_changed = True
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

    def test_registry_rebinds_one_stable_view_without_removing_other_views(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            registry, first, second = root / "registry.json", root / "first", root / "second"
            W.atomic(registry, W.encoded([{"id": "other", "label": "Other", "directory": str(root / "other"),
                                           "sessionId": self.session}]))
            W.register_feed(registry, "survival-observatory", "Survival simulation",
                            "project:survivor-awareness", first, self.session)
            rows = W.read(registry)
            self.assertEqual([row["id"] for row in rows], ["survival-observatory", "other"])
            self.assertEqual(rows[0]["directory"], str(first))
            successor = "95d05f2c-9d8b-4f3e-a867-d4744073d7be"
            W.register_feed(registry, "survival-observatory", "Survival simulation",
                            "project:survivor-awareness", second, successor)
            rows = W.read(registry)
            self.assertEqual(len(rows), 2)
            self.assertEqual((rows[0]["sessionId"], rows[0]["directory"]), (successor, str(second)))

    def test_successor_rebind_waits_for_its_first_complete_snapshot(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            run, package, out, receipt, _, _, _ = self.watch_fixture(root)
            registry = root / "registry.json"
            predecessor = "95d05f2c-9d8b-4f3e-a867-d4744073d7be"
            W.atomic(registry, W.encoded([{"id": "survival-observatory", "label": "Survival simulation",
                "directory": str(root / "predecessor"), "sessionId": predecessor}]))
            filename = "study-live-0000000000000001.png"
            data = b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + struct.pack(">II", 960, 540)
            (run / "native-view" / filename).write_bytes(data)
            W.atomic(run / "native-view/native.json", W.encoded(dict(sequence=1, observerSequence=0,
                capturedAtUnixMs=1, image=dict(file=filename, sha256=hashlib.sha256(data).hexdigest(),
                                                width=960, height=540))))
            receipt["status"] = "completed"
            W.atomic(run / "run.json", W.encoded(receipt))
            original = W.register_feed

            def checked(*args):
                self.assertEqual(W.read(registry)[0]["sessionId"], predecessor)
                first = W.read(out / "latest.json")
                self.assertEqual((first["sessionId"], first["image"]["file"]), (self.session, filename))
                return original(*args)

            with patch.object(W, "register_feed", side_effect=checked) as register:
                self.assertEqual(W.watch(run, package, out, registry), 0)
            register.assert_called_once()
            self.assertEqual(W.read(registry)[0]["sessionId"], self.session)

    def test_saved_feed_applies_settings_then_requests_continuation(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            run, package, out, receipt, _, _, _ = self.watch_fixture(root)
            native = run / "native-view"
            filename = "study-live-0000000000000001.png"
            data = b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + struct.pack(">II", 960, 540)
            (native / filename).write_bytes(data)
            W.atomic(native / "native.json", W.encoded(dict(sequence=1, observerSequence=0,
                capturedAtUnixMs=1, image=dict(file=filename, sha256=hashlib.sha256(data).hexdigest(),
                                                width=960, height=540))))
            receipt["status"] = "completed"
            W.atomic(run / "run.json", W.encoded(receipt))
            state_path, session_commands = root / "study-session.json", root / "session-commands"
            session_commands.mkdir()
            W.atomic(state_path, W.encoded(dict(schema="sao-study-session/1", id=str(uuid.uuid4()),
                label="Survival simulation", status="saved", attempt=1, attemptDurationSeconds=3600,
                autoContinue=False, worldHours=4, accumulatedWorldHours=2, canCheckpoint=False,
                canContinue=True, updatedAtUnixMs=1000, datasetAdmission="unreviewed",
                behavioralVerdict=None, lastStopReason="wall-time-limit", feedGeneration=1,
                processedCommands=[])))
            sleeps = 0

            def request_next(_):
                nonlocal sleeps
                sleeps += 1
                if sleeps == 1:
                    self.assertEqual(W.read(out / "latest.json")["study"]["status"], "saved")
                    W.atomic(out / "commands/0000000000000001.json", W.encoded(
                        self.command("configure", attemptDurationSeconds=7200, autoContinue=True)))
                elif sleeps == 2:
                    self.assertEqual(W.read(out / "latest.json")["commandResult"]["sequence"], 1)
                    W.atomic(out / "commands/0000000000000002.json", W.encoded(
                        self.command("continue") | {"sequence": 2}))
                self.assertLessEqual(sleeps, 3)

            with patch.object(W.time, "sleep", side_effect=request_next):
                self.assertEqual(W.watch(run, package, out, session_state=state_path,
                                         session_commands=session_commands), 0)
            final = W.read(out / "latest.json")
            self.assertEqual(final["commandResult"], {"sequence": 2, "status": "applied",
                                                       "message": "Session continuation requested"})
            events = [W.read(path) for path in sorted(session_commands.glob("*.json"))]
            self.assertEqual([event["action"] for event in events], ["configure", "continue"])
            self.assertEqual(W.read(out / "session.json")["trainingRows"], 0)

    def test_recent_activity_feeds_are_distinct_bounded_native_frames(self):
        feeds = {}
        for index in range(6):
            person = {"id": f"person-{index}", "label": f"Person {index}",
                      "summary": "Remembered person locations: 2\nStored threat memories: 3\nUnclassified sounds: 4",
                      "sections": [
                          {"id": "actions", "rows": [{"label": "Controller state", "value": "ROAM"}]},
                          {"id": "attention", "rows": [{"label": "Phase", "value": "orienting"}]},
                          {"id": "needs", "rows": [{"label": "Hunger", "value": "0.120"},
                                                       {"label": "Endurance", "value": "0.900"},
                                                       {"label": "Health (%)", "value": "100.00"}]},
                      ]}
            frame = {"capturedAtUnixMs": 1000 + index, "image": {
                "file": f"study-live-{index + 1:016d}.png", "sha256": f"{index:064x}", "width": 960, "height": 540}}
            camera = {"mode": "automatic", "personIds": [person["id"]], "summary": f"Watching Person {index}"}
            W.remember_feed(feeds, camera, frame, [person], 900 + index)
        self.assertEqual(list(feeds), ["person-2", "person-3", "person-4", "person-5"])
        self.assertEqual([value["capturedAtUnixMs"] for value in feeds.values()], [1002, 1003, 1004, 1005])
        self.assertEqual([group["id"] for group in feeds["person-5"]["overlay"]["groups"]],
                         ["activity", "attention", "memory", "needs"])
        self.assertEqual(feeds["person-5"]["overlay"]["capturedAtUnixMs"], 905)
        self.assertEqual(feeds["person-5"]["overlay"]["groups"][2]["rows"], [
            {"label": "People", "value": "2"}, {"label": "Threats", "value": "3"},
            {"label": "Sounds", "value": "4"}])
        self.assertEqual(feeds["person-5"]["overlay"]["groups"][3]["rows"], [
            {"label": "Hunger", "value": "0.120"}, {"label": "Health (%)", "value": "100.00"}])
        before = copy.deepcopy(feeds)
        W.remember_feed(feeds, {"mode": "manual", "personIds": [], "summary": "Manual"}, frame, [person], 905)
        self.assertEqual(feeds, before)

    def test_activity_feed_never_overlays_state_sampled_after_its_pixels(self):
        feeds = {}
        person = {"id": "person-1", "label": "Person 1", "summary": "",
                  "sections": [{"id": "attention", "rows": [{"label": "Phase", "value": "turn"}]}]}
        frame = {"capturedAtUnixMs": 1000, "image": {
            "file": "study-live-0000000000000001.png", "sha256": "0" * 64, "width": 960, "height": 540}}
        camera = {"mode": "automatic", "personIds": [person["id"]], "summary": "Watching Person 1"}
        W.remember_feed(feeds, camera, frame, [person], 1001)
        self.assertNotIn("overlay", feeds[person["id"]])

    def test_dense_quiet_group_gives_each_person_a_turn(self):
        camera = W.ActivityCamera()
        people = [{"id": str(i), "x": 40, "y": 40, "z": 0} for i in range(8)]
        seen = set()
        for i in range(20):
            camera.plan(people, 2+i*.1, dict(paused=False, viewX=40, viewY=40, viewZ=0),
                        (0,0,511,511), i * (camera.DWELL + 1))
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
                        if not reject:
                            self.assertIn("sequence=1\n", (run / "observer-control.properties").read_text())
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
        self.assertIsNone(camera.plan(people, 2, state, bounds, camera.DWELL / 2))
        second = camera.plan(people, 2.1, state, bounds, camera.DWELL + 1)
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

    def test_close_group_rotates_every_person_as_primary(self):
        camera = W.ActivityCamera()
        people = [{"id": str(i), "x": 40 + i * .1, "y": 40, "z": 0,
                   "positionSource": "native-body"} for i in range(6)]
        state = dict(paused=False, viewX=40, viewY=40, viewZ=0)
        primaries = []
        for index in range(6):
            plan = camera.plan(people, 2 + index * .1, state, (0, 0, 511, 511),
                               index * (camera.DWELL + 1))
            self.assertIsNotNone(plan)
            state.update({key: plan[key] for key in ("viewX", "viewY", "viewZ")})
            primaries.append(camera.subjects[0])
        self.assertEqual(set(primaries), {person["id"] for person in people})

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

    def test_activity_camera_prioritizes_observed_harm_and_critical_needs(self):
        state = dict(paused=False, viewX=0, viewY=0, viewZ=0)
        bounds = (0, 0, 511, 511)
        for expected, people, reason in [
            ("injured", [
                {"id": "quiet", "x": 20, "y": 20, "z": 0, "record": {"lastLivingHealth": 1}},
                {"id": "injured", "x": 220, "y": 20, "z": 0,
                 "record": {"lastLivingHealth": .42, "woundCarried": 2}}], "severe injury"),
            ("thirsty", [
                {"id": "quiet", "x": 20, "y": 20, "z": 0},
                {"id": "thirsty", "x": 220, "y": 20, "z": 0,
                 "record": {"pharmacology": {"observed": {"stats": {
                     "THIRST": .88, "HUNGER": .2, "FATIGUE": .1, "ENDURANCE": .7}}}}}],
             "critical survival need")]:
            with self.subTest(expected=expected):
                camera = W.ActivityCamera()
                self.assertIsNotNone(camera.plan(people, 2, state, bounds, 0))
                self.assertEqual(camera.subjects, [expected])
                self.assertIn(reason, camera.view(people)["summary"])

    def test_activity_camera_prioritizes_rapid_movement_relative_to_known_danger(self):
        camera = W.ActivityCamera(); bounds = (0, 0, 511, 511)
        people = [{"id": "quiet", "x": 200, "y": 200, "z": 0},
                  {"id": "moving", "x": 20, "y": 40, "z": 0,
                   "context": {"beliefs": {"zombies": {"z1": {"x": 50, "y": 40, "z": 0}}}}}]
        camera.update(people, 2, bounds)
        people[1]["x"] = 24
        plan = camera.plan(people, 2.1, dict(paused=False, viewX=0, viewY=0, viewZ=0), bounds, 0)
        self.assertIsNotNone(plan)
        self.assertEqual(camera.subjects, ["moving"])
        self.assertIn("rapid movement relative to danger", camera.view(people)["summary"])


if __name__ == "__main__":
    unittest.main()
