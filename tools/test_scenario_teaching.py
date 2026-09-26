"""Teaching stays unratified until a human evaluates the exact scene and target."""
import copy
import tempfile
from pathlib import Path
import unittest

import decision_authoring as A
import scenario_teaching as Teaching
import training_evidence as Evidence


def authored_scenario():
    """An explicitly hypothetical situation, authored without a captured base row."""
    actors = [{"id": "rhea", "label": "Rhea"}, {"id": "jon", "label": "Jon"}]
    def states(jon_location, heard=False):
        return [
            {"actorId": "rhea", "locationId": "collector", "activity": "repairing-water-collector",
             "knowledge": ["The collector is leaking; Rhea is working on its seal."]
             + (["Jon has asked her to carry one can of food to the kitchen."] if heard else [])},
            {"actorId": "jon", "locationId": jon_location, "activity": "asking-for-help" if heard else "walking",
             "knowledge": ["There is a can of food in the pantry.", "The food is wanted at the kitchen."]},
        ]
    constraints = {"represented": True, "currentActivity": "repairing-water-collector",
                   "executionOwnerAvailable": True, "ownNeedAvailable": True, "contest": False}
    value = {
        "schema": Teaching.SCENARIO, "schemaVersion": 1, "id": "water-repair-and-food-request",
        "lineageId": "authored-water-repair-001", "revision": 1,
        "title": "A request during a water-collector repair",
        "summary": "Rhea is repairing a leaking water collector. Jon comes over and asks her to carry a can of food from the pantry to the kitchen. She can carry it, trusts Jon, and has little immediate personal pressure. Her current work still matters to her.",
        "authorship": "Assistant-authored hypothetical for operator evaluation; no sampled gameplay or recorded movement.",
        "scene": {"coordinateSystem": "schematic", "actors": actors,
                  "locations": [{"id": "collector", "label": "Water collector", "x": 65, "y": 30},
                                {"id": "pantry", "label": "Pantry", "x": 20, "y": 70},
                                {"id": "kitchen", "label": "Kitchen", "x": 80, "y": 75}],
                  "frames": [
                      {"id": "before-contact", "label": "Before contact", "elapsedSeconds": 0,
                       "states": states("pantry"), "communications": []},
                      {"id": "request-heard", "label": "The request reaches Rhea", "elapsedSeconds": 20,
                       "states": states("collector", True), "communications": [
                           {"id": "food-request", "fromId": "jon", "toId": "rhea", "status": "heard",
                            "summary": "Carry one can of food from the pantry to the kitchen."}]}]},
        "decision": {"frameId": "request-heard", "actorId": "rhea", "communicationId": "food-request",
                     "input": {"schema": "speakeasy-coordination-response-input", "schemaVersion": 1,
                               "route": "coordination-response", "process": {"kind": "food-delivery"},
                               "actor": {"executor": "SAO.Controller", "bodyOwner": "SAO"},
                               "decisionTime": {
                                   "proposal": {"purpose": "carry-food-to-kitchen", "scope": {"category": "food", "quantity": 1},
                                                "requiredCapabilities": {"acquire": True, "carry": True, "deliver": True},
                                                "destination": {"minX": 8, "maxX": 12, "minY": 8, "maxY": 12, "z": 0}},
                                   "reception": {"channel": "spoken", "evidence": {"kind": "authored-hypothesis"}},
                                   "currentWork": {"activity": "repairing-water-collector", "owner": "SAO.Controller"},
                                   "competingPriorities": {
                                       "competingPressure": {"value": 0.2, "available": True, "owner": "SAO.Needs"},
                                       "relationship": 0.7, "interests": {"currentWork": "keep-the-collector-usable"},
                                       "constraints": constraints,
                                       "owners": {"ownNeed": "SAO.Needs", "relationship": "SAO.Standing",
                                                  "interests": "SAO.Identity+SAO.Standing", "constraints": "SAO.Controller"}},
                                   "capabilities": {"values": {"acquire": True, "carry": True, "deliver": True, "execute": True},
                                                    "owner": "SAO.Controller", "availability": "available"},
                                   "feasibleOptions": ["accept", "qualify", "counter-propose", "decline", "defer", "contest"]}}},
        "teaching": {"response": "defer", "rationale": "Rhea can acknowledge the request while giving her ongoing repair priority. This proposes deferral in this particular situation; it does not establish that busy people always defer or that she later completes either task."},
    }
    return A.seal(value)


def reseal(value):
    value = copy.deepcopy(value)
    value.pop("contentSha256", None)
    return A.seal(value)


def test_receipt(subject_hash, status="approved", notes=None):
    """Test-only evidence; never written into the repository's evidence store."""
    lineage = {"evidenceRef": "speakeasy:content-sha256:" + subject_hash,
               "threadId": "test-only-scenario"}
    return {"schema": "mousecat.skill-invocation/2", "action": "await", "skillRef": "crucible",
            "interactionId": "test-only-human-result", "status": "answered",
            "items": [{"id": "test-only-item", "shape": "decision", "lineage": lineage}],
            "responses": [{"itemId": "test-only-item", "shape": "decision", "status": "answered",
                           "value": status, "selectedOption": status, "selectedOptions": [status],
                           "notes": notes, "lineage": lineage}]}


class ScenarioTeachingTest(unittest.TestCase):
    def setUp(self):
        self.scenario = authored_scenario()
        self.subject = Teaching.review_subject(self.scenario)
        self.temp = tempfile.TemporaryDirectory(prefix="speakeasy-teaching-test-")
        self.root = Path(self.temp.name)
        self.store = Evidence.Store(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def save_receipt(self, value):
        digest = A.digest(value)
        Teaching.write_new(self.root / (digest + ".json"), value)
        return digest

    def test_authored_scene_needs_no_base_capture(self):
        self.assertEqual(Teaching.validate_review(self.subject), self.subject)
        self.assertEqual(self.subject["targetScope"], Teaching.SCOPE)
        self.assertNotIn("admission", self.scenario)

    def test_mousecat_packet_carries_exact_scene_input_and_teaching_proposal(self):
        packet = Teaching.review_invocation(self.subject, "test-session", "test-invocation", "2026-09-26T01:00:00Z")
        seam = packet["intake"]["seams"][0]
        self.assertEqual(seam["evidenceRef"], "speakeasy:content-sha256:" + self.subject["contentSha256"])
        preview = seam["mlReview"]["scenePreview"]
        self.assertEqual(preview["frames"], self.scenario["scene"]["frames"])
        self.assertEqual(preview["decision"], {"frameId": "request-heard", "actorId": "rhea"})
        self.assertEqual(preview["provenance"]["kind"], "authored")
        actual = {row["label"]: A.loads(row["value"]) for row in seam["mlReview"]["actualInput"]}
        self.assertEqual(actual["competingPriorities"], self.scenario["decision"]["input"]["decisionTime"]["competingPriorities"])

    def test_admission_requires_saved_exact_unqualified_operator_result(self):
        with self.assertRaisesRegex(ValueError, "missing evidence"):
            Teaching.admit(self.subject, "0" * 64, self.store)
        for status, notes in (("rejected", None), ("revision-requested", None),
                              ("approved", "Only if the repair is safe to leave")):
            with self.subTest(status=status, notes=notes):
                receipt = self.save_receipt(test_receipt(self.subject["contentSha256"], status, notes))
                with self.assertRaises(ValueError):
                    Teaching.admit(self.subject, receipt, self.store)
        receipt = self.save_receipt(test_receipt(self.subject["contentSha256"]))
        row = Teaching.admit(self.subject, receipt, self.store)
        self.assertEqual(row["input"], self.scenario["decision"]["input"])
        self.assertEqual(row["target"], {"response": "defer"})
        self.assertNotIn("scene", row["input"])

    def test_every_scene_or_target_correction_invalidates_old_approval(self):
        receipt = self.save_receipt(test_receipt(self.subject["contentSha256"]))
        mutations = [lambda s: s["scene"]["locations"][0].update(x=64),
                     lambda s: s["scene"]["frames"][0]["states"][0]["knowledge"].append("The leak is small."),
                     lambda s: s["teaching"].update(response="qualify"),
                     lambda s: s["teaching"].update(rationale="Only the revised rationale."),
                     lambda s: s["decision"]["input"]["decisionTime"]["competingPriorities"].update(relationship=0.1)]
        for mutate in mutations:
            changed = copy.deepcopy(self.scenario)
            mutate(changed)
            with self.subTest(mutate=mutate):
                with self.assertRaisesRegex(ValueError, "exact subject"):
                    Teaching.admit(Teaching.review_subject(reseal(changed)), receipt, self.store)

    def test_scene_cannot_claim_reception_or_work_absent_from_input(self):
        for mutation in (lambda s: s["scene"]["frames"][-1]["communications"][0].update(status="unheard"),
                         lambda s: s["scene"]["frames"][-1]["states"][0].update(activity="idle"),
                         lambda s: s["scene"]["frames"][-1]["states"].pop(),
                         lambda s: s["decision"].update(frameId="before-contact")):
            changed = copy.deepcopy(self.scenario)
            mutation(changed)
            with self.assertRaises(ValueError):
                Teaching.validate_scenario(reseal(changed))

    def test_hidden_state_or_impossible_target_refuses(self):
        mutations = [lambda s: s["decision"]["input"]["decisionTime"]["competingPriorities"]["interests"].update(pathogen="crossed"),
                     lambda s: s["decision"]["input"]["decisionTime"]["capabilities"]["values"].update(carry=False),
                     lambda s: s["teaching"].update(response="withdraw"),
                     lambda s: s["scene"]["locations"][0].update(x=float("nan"))]
        for mutate in mutations:
            changed = copy.deepcopy(self.scenario)
            mutate(changed)
            with self.assertRaises(ValueError):
                Teaching.validate_scenario(reseal(changed))

    def test_authorship_is_not_fabricated_capture_provenance(self):
        changed = copy.deepcopy(self.scenario)
        changed["decision"]["input"]["decisionTime"]["reception"]["evidence"] = {"kind": "headless-native-distance", "distance": 1}
        with self.assertRaisesRegex(ValueError, "hypothetical"):
            Teaching.validate_scenario(reseal(changed))

    def test_existing_artifacts_are_not_overwritten(self):
        path = self.root / "review.json"
        Teaching.write_new(path, self.subject)
        with self.assertRaises(FileExistsError):
            Teaching.write_new(path, self.scenario)
        self.assertEqual(A.read(path), self.subject)


if __name__ == "__main__":
    unittest.main()
