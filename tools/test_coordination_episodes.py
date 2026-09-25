#!/usr/bin/env python3
"""Defect controls for repeatable causal-episode coordination intake."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

import coordination_episodes as Episodes
import cross_module_rows as Join
from test_coordination_tasks import coordination_row


def episode(events=None, *, episode_id="Episode000", joint=True):
    events = copy.deepcopy(events or [])
    final = {"completedDay": 30, "observedHour": 720, "alive": 4,
             "dead": 1, "groups": {}, "groupSizes": {},
             "deathCauses": {"county": 1}, "pathogenStates": {"dead": 1}}
    start = {"completedDay": 0, "observedHour": 1.6, "alive": 5,
             "dead": 0, "groups": {}, "groupSizes": {},
             "deathCauses": {}, "pathogenStates": {}}
    for row in events:
        row["namespace"]["runId"] = episode_id
        row["namespace"]["county"] = episode_id
        row["situation"]["county"] = episode_id
        if isinstance(row.get("citation"), dict):
            row["citation"]["county"] = episode_id
    value = {
        "schema": "sao-causal-episode", "schemaVersion": 1,
        "episodeId": episode_id, "horizonDays": 30,
        "seed": episode_id + ":1993-08-08", "drawCount": 77,
        "checkpoints": [{"day": 0, "snapshot": start},
                        {"day": 30, "snapshot": final}],
        "trajectory": {
            "dailySnapshots": {"0": start, "30": final},
            "socialEvents": {}, "companies": {},
            "deathCauses": {"county": 1},
            "decisionCapture": {
                "schema": "sao-coordination-decision-capture",
                "schemaVersion": 1, "status": "observed",
                "attemptedEvents": len(events), "eventCount": len(events),
                "captureFailureCount": 0, "failures": [], "events": events,
            },
        },
        "terminal": {"alive": 4, "dead": 1},
        "source": {"saveName": episode_id, "requestedDays": 30,
                   "jointPathogen": joint},
        "standing": "candidate-observation",
        "exclusions": ["loaded-gameplay-unobserved"],
        "replay": {"runs": 2, "exact": True,
                   "reset": "fresh Kahlua process",
                   "comparison": "complete canonical simulation result",
                   "simulationSha256": "a" * 64},
    }
    value["episodeSha256"] = Episodes.digest(value)
    return value


def reseal(value):
    value = copy.deepcopy(value)
    value.pop("episodeSha256", None)
    value["episodeSha256"] = Episodes.digest(value)
    return value


class CoordinationEpisodesTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix="speakeasy-causal-episodes-")
        self.root = Path(self.temporary.name)
        self.input = self.root / "episodes.jsonl"
        self.projector = self.root / "projector.py"
        self.output = self.root / "compiled"
        self.projector.write_text('''\
def states_for(rows):
    return [{"schema":"zao-decision-state","schemaVersion":3,
      "namespace":dict(row["namespace"]),
      "asOfHour":row["namespace"]["hour"],
      "pathogen":{"terminalState":"crossed"},"visibleForms":[]}
      for row in rows]
''', encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, values):
        self.input.write_text("".join(
            json.dumps(value, sort_keys=True) + "\n" for value in values),
            encoding="utf-8")

    def test_decision_episode_preserves_horizons_and_compiles_candidate(self):
        row = coordination_row()
        self.write([episode([row])])
        bundle = Episodes.compile_bundle(self.input, self.projector)
        episodes, decisions, states, tasks, manifest = bundle
        self.assertEqual((len(episodes), len(decisions), len(states), len(tasks)),
                         (1, 1, 1, 1))
        self.assertTrue(manifest["horizons"]["separate"])
        self.assertEqual(tasks[0]["decisionTime"]["asOfHour"],
                         row["namespace"]["hour"])
        self.assertGreater(tasks[0]["laterOutcome"]["asOfHour"],
                           tasks[0]["decisionTime"]["asOfHour"])
        self.assertEqual(tasks[0]["admission"]["status"],
                         "candidate-observation")
        self.assertNotIn("crossed",
                         json.dumps(tasks[0]["decisionTime"], sort_keys=True))
        Episodes.publish(self.output, *bundle)
        self.assertEqual(len(self.output.joinpath("tasks.jsonl")
                             .read_text(encoding="utf-8").splitlines()), 1)

    def test_empty_episode_is_retained_without_manufacturing_a_task(self):
        self.write([episode()])
        bundle = Episodes.compile_bundle(self.input, None)
        self.assertEqual(bundle[-1]["emptyEpisodeCount"], 1)
        self.assertEqual(bundle[-1]["taskCount"], 0)
        Episodes.publish(self.output, *bundle)
        self.assertEqual(self.output.joinpath("tasks.jsonl").read_bytes(), b"")
        self.assertEqual(len(self.output.joinpath("episodes.jsonl")
                             .read_text(encoding="utf-8").splitlines()), 1)

    def test_seal_replay_namespace_projector_and_output_controls(self):
        row = coordination_row()
        good = episode([row])

        changed = copy.deepcopy(good)
        changed["drawCount"] += 1
        self.write([changed])
        with self.assertRaisesRegex(Join.ContractError, "content seal differs"):
            Episodes.compile_bundle(self.input, self.projector)

        replay = copy.deepcopy(good)
        replay["replay"]["exact"] = False
        self.write([reseal(replay)])
        with self.assertRaisesRegex(Join.ContractError, "replay evidence"):
            Episodes.compile_bundle(self.input, self.projector)

        future = copy.deepcopy(good)
        event = future["trajectory"]["decisionCapture"]["events"][0]
        event["namespace"]["hour"] = 800
        event["situation"]["hour"] = 800
        event["conditioning"]["decisionHour"] = 800
        if isinstance(event.get("citation"), dict):
            event["citation"]["hour"] = 800
        self.write([reseal(future)])
        with self.assertRaisesRegex(Join.ContractError, "outside the episode horizon"):
            Episodes.compile_bundle(self.input, self.projector)

        self.write([good])
        with self.assertRaisesRegex(Join.ContractError, "require.*ZAO|require the current ZAO"):
            Episodes.compile_bundle(self.input, None)

        wrong = self.root / "wrong_projector.py"
        wrong.write_text(self.projector.read_text(encoding="utf-8").replace(
            'dict(row["namespace"])',
            '{**row["namespace"], "eventId":"wrong"}'), encoding="utf-8")
        with self.assertRaisesRegex(Join.ContractError, "missing ZAO state"):
            Episodes.compile_bundle(self.input, wrong)

        bundle = Episodes.compile_bundle(self.input, self.projector)
        Episodes.publish(self.output, *bundle)
        before = self.output.joinpath("manifest.json").read_bytes()
        with self.assertRaisesRegex(Join.ContractError, "output already exists"):
            Episodes.publish(self.output, *bundle)
        self.assertEqual(self.output.joinpath("manifest.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
