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


def process_observation():
    process = {
        "processId": "matter-1", "kind": "food-delivery",
        "originatorId": "person-origin", "originatorBodyOwner": "SAO",
        "status": "open", "revision": 1, "revisionCount": 1,
        "createdAt": 24, "addressedCount": 1,
        "currentReceivedCount": 0, "currentRespondedCount": 0,
        "currentUnheardCount": 1, "currentUnansweredCount": 0,
        "receptionCount": 0, "responseCount": 0,
        "returnedResponseCount": 0, "responses": {}, "commitments": {},
        "workOutcomes": {}, "contactAttemptCount": 1,
        "contactArrivalCount": 1, "activeContactAttemptCount": 1,
        "contactOutcomes": {"waiting": 1},
        "contactOwners": {"SAO.Controller": 1}, "eventCount": 3,
    }
    return {
        "schema": "sao-shared-process-observation", "schemaVersion": 1,
        "processCount": 1, "kindCounts": {"food-delivery": 1},
        "statusCounts": {"open": 1}, "addressedCount": 1,
        "receptionCount": 0, "responseCount": 0,
        "returnedResponseCount": 0, "currentUnheardCount": 1,
        "currentUnansweredCount": 0, "contactAttemptCount": 1,
        "contactArrivalCount": 1, "activeContactAttemptCount": 1,
        "contactOutcomeCounts": {"waiting": 1},
        "contactOwnerCounts": {"SAO.Controller": 1},
        "responseCounts": {}, "processes": [process],
    }


def reconcile_observation(observed):
    """Rebuild fixture aggregates after an intentional per-process change."""
    rows = observed["processes"] or []
    observed["processCount"] = len(rows)
    for field in ("addressedCount", "receptionCount", "responseCount",
                  "returnedResponseCount", "currentUnheardCount",
                  "currentUnansweredCount", "contactAttemptCount",
                  "contactArrivalCount", "activeContactAttemptCount"):
        observed[field] = sum(row[field] for row in rows)
    for top, child in (("responseCounts", "responses"),
                       ("contactOutcomeCounts", "contactOutcomes"),
                       ("contactOwnerCounts", "contactOwners")):
        counts = {}
        for row in rows:
            for key, value in row[child].items():
                counts[key] = counts.get(key, 0) + value
        observed[top] = counts
    for top, child in (("kindCounts", "kind"), ("statusCounts", "status")):
        counts = {}
        for row in rows:
            counts[row[child]] = counts.get(row[child], 0) + 1
        observed[top] = counts
    return observed


def answered_observation(row):
    observed = process_observation()
    process = observed["processes"][0]
    process.update({
        "processId": row["enactedProcess"]["processId"],
        "currentReceivedCount": 1, "currentRespondedCount": 1,
        "currentUnheardCount": 0, "receptionCount": 1, "responseCount": 1,
        "returnedResponseCount": 1, "responses": {"accept": 1},
        "commitments": {"completed": 1}, "workOutcomes": {"completed": 1},
        # A spoken exchange can happen without a separate contact journey.
        "contactAttemptCount": 0, "contactArrivalCount": 0,
        "activeContactAttemptCount": 0, "contactOutcomes": {},
        "contactOwners": {},
    })
    return reconcile_observation(observed)


def episode(events=None, *, episode_id="Episode000", joint=True, processes=None):
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
    capture = {
        "schema": "sao-coordination-decision-capture",
        "schemaVersion": 1, "status": "observed",
        "attemptedEvents": len(events), "eventCount": len(events),
        "captureFailureCount": 0, "failures": [], "events": events,
    }
    trajectory = {
        "dailySnapshots": {"0": start, "30": final},
        "socialEvents": {}, "companies": {},
        "deathCauses": {"county": 1}, "decisionCapture": capture,
    }
    if processes is not None:
        capture["processObservation"] = copy.deepcopy(processes)
        trajectory["processObservation"] = copy.deepcopy(processes)
    value = {
        "schema": "sao-causal-episode", "schemaVersion": 1,
        "episodeId": episode_id, "horizonDays": 30,
        "seed": episode_id + ":1993-08-08", "drawCount": 77,
        "checkpoints": [{"day": 0, "snapshot": start},
                        {"day": 30, "snapshot": final}],
        "trajectory": trajectory,
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
        self.assertEqual(bundle[-1]["processObservation"]["legacyEpisodeCount"], 1)
        self.assertEqual(bundle[-1]["episodes"][0]["processObservation"],
                         {"available": False, "reason": "legacy-source-omitted"})
        Episodes.publish(self.output, *bundle)
        self.assertEqual(self.output.joinpath("tasks.jsonl").read_bytes(), b"")
        self.assertEqual(len(self.output.joinpath("episodes.jsonl")
                             .read_text(encoding="utf-8").splitlines()), 1)

    def test_process_observation_locates_zero_decision_break_without_private_state(self):
        observed = process_observation()
        self.write([episode(processes=observed)])
        bundle = Episodes.compile_bundle(self.input, None)
        manifest = bundle[-1]
        summary = manifest["episodes"][0]["processObservation"]
        self.assertTrue(summary["available"])
        self.assertEqual(summary["firstUnobservedStage"], "reception")
        self.assertEqual(summary["counts"]["processCount"], 1)
        self.assertEqual(summary["counts"]["contactArrivalCount"], 1)
        self.assertEqual(manifest["processObservation"]["totals"]
                         ["contactArrivalCount"], 1)
        self.assertEqual(manifest["processObservation"]
                         ["firstUnobservedStageCounts"], {"reception": 1})
        rendered = json.dumps(summary, sort_keys=True)
        self.assertNotIn("pathogen", rendered)
        self.assertNotIn("diet", rendered)
        Episodes.publish(self.output, *bundle)
        progression = json.loads(self.output.joinpath("progression.jsonl")
                                 .read_text(encoding="utf-8"))
        self.assertEqual(progression["processObservation"]
                         ["firstUnobservedStage"], "reception")

    def test_empty_lua_process_table_is_observed_absence_and_preserves_source(self):
        for empty in ({}, []):
            with self.subTest(encoded=empty):
                observed = process_observation()
                observed["processes"] = empty
                reconcile_observation(observed)
                source = episode(processes=observed)
                self.write([source])
                bundle = Episodes.compile_bundle(self.input, None)
                self.assertEqual(bundle[0], [source])
                summary = bundle[-1]["episodes"][0]["processObservation"]
                self.assertTrue(summary["available"])
                self.assertEqual(summary["firstUnobservedStage"], "matter")
                self.assertEqual(bundle[-1]["taskCount"], 0)

    def test_progression_skips_unused_channels_and_never_enters_model_input(self):
        row = coordination_row()
        observed = answered_observation(row)
        self.write([episode([row], processes=observed)])
        baseline = Episodes.compile_bundle(self.input, self.projector)
        self.assertIsNone(baseline[-1]["episodes"][0]["processObservation"]
                          ["firstUnobservedStage"])
        self.assertEqual(baseline[-1]["processObservation"]["use"],
                         "episode-audit-only")
        # Terminal process totals can change without changing the exact frozen
        # decision and its separately captured outcome horizon.
        observed["processes"][0]["workOutcomes"] = {"failed": 2}
        self.write([episode([row], processes=observed)])
        changed = Episodes.compile_bundle(self.input, self.projector)
        self.assertEqual(baseline[3], changed[3])
        self.assertNotEqual(baseline[-1]["episodes"], changed[-1]["episodes"])
        self.assertNotIn("processObservation", json.dumps(changed[3]))
        self.assertNotIn("crossed", json.dumps(changed[3][0]["decisionTime"]))

    def test_mixed_legacy_and_observed_episodes_keep_absence_distinct(self):
        self.write([episode(episode_id="Legacy"),
                    episode(episode_id="Current", processes=process_observation())])
        manifest = Episodes.compile_bundle(self.input, None)[-1]
        self.assertEqual(manifest["episodeCount"], 2)
        summary = manifest["processObservation"]
        self.assertEqual(summary["availableEpisodeCount"], 1)
        self.assertEqual(summary["legacyEpisodeCount"], 1)
        self.assertEqual(summary["totals"]["processCount"], 1)
        self.assertEqual(summary["firstUnobservedStageCounts"], {"reception": 1})

    def test_process_decisions_require_exact_unique_observed_response(self):
        row = coordination_row()
        observed = answered_observation(row)
        other = copy.deepcopy(observed["processes"][0])
        other["processId"] = "other-process"
        observed["processes"].append(other)
        observed["processes"][0].update({
            "currentRespondedCount": 0, "currentUnansweredCount": 1,
            "responseCount": 0, "returnedResponseCount": 0, "responses": {},
            "commitments": {}, "workOutcomes": {},
        })
        reconcile_observation(observed)
        self.write([episode([row], processes=observed)])
        with self.assertRaisesRegex(Join.ContractError, "decisions exceed responses"):
            Episodes.compile_bundle(self.input, self.projector)

        observed["processes"] = [other]
        reconcile_observation(observed)
        self.write([episode([row], processes=observed)])
        with self.assertRaisesRegex(Join.ContractError, "process is not observed"):
            Episodes.compile_bundle(self.input, self.projector)

        duplicate = copy.deepcopy(row)
        duplicate["namespace"]["eventId"] += "-duplicate"
        self.write([episode([row, duplicate], processes=answered_observation(row))])
        with self.assertRaisesRegex(Join.ContractError,
                                    "duplicate captured process/actor/revision"):
            Episodes.compile_bundle(self.input, self.projector)

    def test_process_observation_rejects_malformed_counts_and_shapes(self):
        cases = [
            ("boolean", lambda p: p.update(addressedCount=True), "nonnegative integer"),
            ("negative", lambda p: p.update(eventCount=-1), "nonnegative integer"),
            ("active", lambda p: p.update(activeContactAttemptCount=0), "active contact"),
            ("heard", lambda p: p.update(currentReceivedCount=1,
                                         currentUnheardCount=0,
                                         currentUnansweredCount=1), "retained response"),
            ("nested-private", lambda p: p["workOutcomes"].update(
                pathogen={"terminalState": "crossed"}), "private field"),
            ("scalar-private", lambda p: p["workOutcomes"].update(
                diet=1), "private field"),
        ]
        for name, mutate, reason in cases:
            with self.subTest(case=name):
                observed = process_observation()
                mutate(observed["processes"][0])
                self.write([episode(processes=observed)])
                with self.assertRaisesRegex(Join.ContractError, reason):
                    Episodes.compile_bundle(self.input, None)
        for processes, reason in (({"unexpected": {}}, "processes must be a list"),
                                  ([process_observation()["processes"][0]] * 2,
                                   "duplicate processId")):
            observed = process_observation()
            observed["processes"] = processes
            observed["processCount"] = len(processes)
            self.write([episode(processes=observed)])
            with self.assertRaisesRegex(Join.ContractError, reason):
                Episodes.compile_bundle(self.input, None)

    def test_compiler_identity_normalizes_newlines_but_evidence_identity_does_not(self):
        lf, crlf = self.root / "lf.py", self.root / "crlf.py"
        lf.write_bytes(b"value = 1\n")
        crlf.write_bytes(b"value = 1\r\n")
        self.assertEqual(Episodes.compiler_sha256(lf), Episodes.compiler_sha256(crlf))
        self.assertNotEqual(Episodes.file_sha256(lf), Episodes.file_sha256(crlf))
        crlf.write_bytes(b"value = 2\r\n")
        self.assertNotEqual(Episodes.compiler_sha256(lf), Episodes.compiler_sha256(crlf))

    def test_process_observation_refuses_aggregate_drift_copy_drift_and_private_fields(self):
        observed = process_observation()
        drift = episode(processes=observed)
        drift["trajectory"]["processObservation"]["contactArrivalCount"] = 0
        drift["trajectory"]["decisionCapture"]["processObservation"] = copy.deepcopy(
            drift["trajectory"]["processObservation"])
        self.write([reseal(drift)])
        with self.assertRaisesRegex(Join.ContractError,
                                    "contactArrivalCount aggregate differs"):
            Episodes.compile_bundle(self.input, None)

        copies = episode(processes=observed)
        copies["trajectory"]["decisionCapture"]["processObservation"] \
            ["processes"][0]["status"] = "closed"
        self.write([reseal(copies)])
        with self.assertRaisesRegex(Join.ContractError,
                                    "process observation copies differ"):
            Episodes.compile_bundle(self.input, None)

        private = episode(processes=observed)
        private["trajectory"]["processObservation"]["processes"][0] \
            ["pathogen"] = {"terminalState": "crossed"}
        private["trajectory"]["decisionCapture"]["processObservation"] = copy.deepcopy(
            private["trajectory"]["processObservation"])
        self.write([reseal(private)])
        with self.assertRaisesRegex(Join.ContractError, "process fields differ"):
            Episodes.compile_bundle(self.input, None)

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
