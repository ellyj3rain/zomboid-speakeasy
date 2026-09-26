"""Controls for projection and unreviewed native-source intake."""
import copy
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import world_study as W


def fixture():
    return {"datasetAdmission": "unreviewed", "hours": 1,
        "windows": [{"squares": [{"x": 4, "y": 6, "z": 2, "floor": True, "outside": True,
            "solid": False, "solidTrans": False, "objects": [{"open": False, "north": False}]}]}],
        "people": [{"id": "p1", "x": 4, "y": 6, "z": 2, "positionSource": "native-body",
            "record": {"forename": "Test", "surname": "Person"},
            "context": {"controllerAvailable": False, "perceptionAvailable": False,
                        "controller": {}, "beliefs": {}}}], "processes": [],
        "population": {"total": 1, "captured": 1, "represented": 1, "dead": 0},
        "coverage": {"loadedSquares": 1, "requestedSquares": 4, "unavailableSquares": 3,
                     "totalProcesses": 0, "omittedFieldCount": 0}}


class WorldStudyTests(unittest.TestCase):
    def test_projection_preserves_native_and_unknown_coverage(self):
        frame = fixture()
        before = copy.deepcopy(frame)
        view = W.project(frame)
        self.assertEqual(frame, before)
        self.assertEqual(len(view["primitives"]), 2)  # One observed tile, one recorded object.
        self.assertEqual(view["primitives"][1]["position"], [4, 6.5, 6.9])
        self.assertEqual(view["entities"][0]["position"], [4, 6, 6])
        self.assertEqual(view["entities"][0]["positionSource"], "active-body")
        self.assertIn("3 unavailable", view["coverage"])
        self.assertIn("beliefs captured: False", view["entities"][0]["details"])
        frame["people"][0]["positionSource"] = "durable-record"
        self.assertEqual(W.project(frame)["entities"][0]["positionSource"], "durable-state")
        del frame["people"][0]["x"]
        self.assertEqual(W.project(frame)["entities"], [])
        self.assertIn("1 positions unavailable", W.project(frame)["coverage"])

    def test_overlapping_windows_do_not_duplicate_geometry(self):
        frame = fixture()
        frame["windows"].append(copy.deepcopy(frame["windows"][0]))
        self.assertEqual(len(W.project(frame)["primitives"]), 2)

    def test_source_intake_controls_and_zero_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package, run, owner = root / "package", root / "run", root / "world_lab_run.py"
            package.mkdir()
            observation = run / "cache/Lua/StudyWorld/session/frame.json"
            observation.parent.mkdir(parents=True)
            owner.write_text("# Explicit external owner placeholder for this controlled test.\n")
            raw = W.encoded(fixture())
            observation.write_bytes(raw)
            (package / "definition.json").write_bytes(W.encoded({"id": "fixture", "observation": {
                "windows": [{"x": 0, "y": 0, "z": 0, "width": 8, "height": 8}]}}))
            receipt = {"status": "completed", "datasetAdmission": "unreviewed", "packageSha256": "a"*64,
                "definitionSha256": "b"*64, "observations": {"Lua/StudyWorld/session/frame.json": W.sha(raw)}}
            (run / "run.json").write_bytes(W.encoded(receipt))
            accepted = types.SimpleNamespace(returncode=0, stdout=json.dumps(receipt), stderr="")
            with patch.object(W.subprocess, "run", return_value=accepted) as owner_call:
                result = W.export(run, package, owner, root / "preview")
                self.assertIn("--verify", owner_call.call_args.args[0])
                self.assertEqual((result["datasetAdmission"], result["trainingRows"], result["teachingTargets"]),
                                 ("unreviewed", 0, 0))
                with self.assertRaisesRegex(ValueError, "already exists"):
                    W.export(run, package, owner, root / "preview")
                observation.write_bytes(raw + b" ")
                with self.assertRaisesRegex(ValueError, "changed during intake"):
                    W.export(run, package, owner, root / "tampered")
                self.assertFalse((root / "tampered").exists())
            refused = types.SimpleNamespace(returncode=1, stdout="", stderr="native run incomplete")
            with patch.object(W.subprocess, "run", return_value=refused):
                with self.assertRaisesRegex(ValueError, "SAO rejected"):
                    W.export(run, package, owner, root / "refused")
                self.assertFalse((root / "refused").exists())


if __name__ == "__main__":
    unittest.main()
