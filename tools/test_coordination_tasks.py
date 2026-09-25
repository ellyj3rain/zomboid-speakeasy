#!/usr/bin/env python3
"""Defect controls for actor-private enacted coordination task views."""

from __future__ import annotations

import copy
import json
import pathlib
import tempfile
import unittest

import coordination_tasks as Tasks
import cross_module_rows as Join
from test_cross_module_rows import namespace, sao_row, zao_row, write_jsonl


OPTIONS = ["accept", "qualify", "counter-propose", "decline", "defer", "contest"]


def enacted(ns=None, *, choice="accept", body_owner="SAO",
            executor="SAO.Controller", activity="forage", available=True,
            need_available=True, need_owner="SAO.Needs", own_need=0.2):
    ns = ns or namespace()
    process_id, originator = "matter:7:requester", "requester"
    proposed = ns["hour"] - 1
    private = {
        "owner": "Controller.coordination",
        "executor": executor,
        "bodyOwner": body_owner,
        "currentActivity": activity,
        "capabilities": {name: available for name in Tasks.CAPABILITIES},
        "constraints": {"represented": True, "currentActivity": activity,
                        "executionOwnerAvailable": available,
                        "ownNeedAvailable": need_available},
        "interests": {"designation": "forager", "ownGroup": "group-1"},
        "inputOwners": {
            "currentActivity": executor, "capabilities": executor,
            "ownNeed": need_owner, "relationship": "SAO.Standing",
            "interests": "SAO.Identity+SAO.Standing",
            "constraints": "SAO.Controller",
        },
        "relationship": 0.55,
        "ownNeed": own_need,
        "destinationKnown": True,
        "feasibleOptions": OPTIONS if available else ["decline", "defer", "contest"],
        "choice": choice,
        "reconsider": False,
    }
    proposal = {
        "purpose": "carry food to the requesting household",
        "destination": {"minX": 10, "minY": 11, "maxX": 12, "maxY": 13},
        "scope": {"quantity": 1, "category": "food"},
        "requiredCapabilities": {name: True for name in Tasks.CAPABILITIES},
    }
    decision = {
        "id": process_id, "kind": "food-delivery", "organizationId": "group-1",
        "originatorId": originator, "createdAt": proposed, "revisedAt": proposed,
        "revision": 1, "currentRevision": 1, "status": "open",
        "proposal": {"revision": 1, "proposedAt": proposed,
                     "proposedBy": originator, "proposal": proposal},
        "reception": {"at": proposed + 0.25, "channel": "spoken",
                      "fromId": originator, "evidence": {"distance": 2}},
        "response": {"personId": ns["personId"], "revision": 1,
                     "response": choice, "terms": {}, "responseRevision": 1,
                     "formedAt": ns["hour"], "delivered": False},
        "responseHistory": [], "privateInputs": private,
        "responses": {}, "commitments": {}, "asOfHour": ns["hour"],
    }
    later_response = copy.deepcopy(decision["response"])
    later_response.update({"delivered": True, "deliveredAt": ns["hour"] + 0.25,
                           "channel": "spoken", "deliveryEvidence": {"distance": 2}})
    commitments = {}
    if choice in {"accept", "withdraw"}:
        commitment_id = process_id + ":commitment:1"
        commitments[commitment_id] = {
            "id": commitment_id, "processId": process_id, "revision": 1,
            "actorId": ns["personId"], "beneficiaryId": originator,
            "organizationId": "group-1", "matter": "food-delivery",
            "scope": {"quantity": 1, "category": "food"},
            "acceptedAt": ns["hour"] + 0.25, "status": "completed",
            "work": {
                "phase": "completed", "owner": body_owner,
                "nativeOwner": "Handover",
                "currentActivity": "carrying", "acceptedAt": ns["hour"] + 0.25,
                "acquiredAt": ns["hour"] + 1, "completedAt": ns["hour"] + 2,
                "endedAt": ns["hour"] + 2,
                "sourceReceipts": {"source-1": {"owner": "SourceUse",
                                                 "status": "completed",
                                                 "at": ns["hour"] + 1}},
                "handoverReceipts": {"handover-1": {"owner": "Handover",
                                                       "status": "completed",
                                                       "completedAt": ns["hour"] + 2}},
                "routeAttempts": [{"owner": "Locomotion",
                                   "status": "completed", "beganAt": ns["hour"] + 1,
                                   "endedAt": ns["hour"] + 2}],
                "outcomes": [{"phase": "completed", "at": ns["hour"] + 2,
                              "detail": {"receiptId": "handover-1"}}],
            },
        }
    outcome = {
        "id": process_id, "kind": "food-delivery", "organizationId": "group-1",
        "originatorId": originator, "createdAt": proposed, "revisedAt": proposed,
        "revision": 1, "currentRevision": 1,
        "status": "closed" if commitments else "open",
        "response": later_response, "commitments": commitments,
        "asOfHour": ns["hour"] + 2,
    }
    return {"schema": 1, "processId": process_id, "processRevision": 1,
            "actorId": ns["personId"], "decisionTime": decision,
            "laterOutcome": outcome}


def coordination_row(ns=None, **kwargs):
    ns = ns or namespace()
    evidence = enacted(ns, **kwargs)
    row = sao_row(ns)
    options = evidence["decisionTime"]["privateInputs"]["feasibleOptions"]
    row["options"] = [{
        "id": "coordination:" + response,
        "owner": "SAO.Organization.respond",
        "parameters": {"actorId": ns["personId"],
                       "processId": evidence["processId"],
                       "processRevision": evidence["processRevision"],
                       "response": response},
        "eligibility": {"status": "eligible", "evidence": [{
            "kind": "actor-private-appraisal", "actorId": ns["personId"],
            "processRevision": evidence["processRevision"],
        }]},
    } for response in options]
    row["choice"] = {"optionId": "coordination:" + kwargs.get("choice", "accept")}
    row["enactedProcess"] = evidence
    return row


class CoordinationTasksTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="speakeasy-coordination-")
        self.root = pathlib.Path(self.temporary.name)
        self.sao = self.root / "sao.jsonl"
        self.zao = self.root / "zao.jsonl"
        self.out = self.root / "tasks.jsonl"

    def tearDown(self):
        self.temporary.cleanup()

    def joined(self, row=None, state=None):
        write_jsonl(self.sao, [row or coordination_row()])
        write_jsonl(self.zao, [state or zao_row()])
        return Join.joined_rows(self.sao, self.zao, self.out)[0]

    def test_private_scene_has_work_priorities_choice_and_later_result(self):
        task = Tasks.compile_task(self.joined())
        self.assertEqual(task["namespace"], namespace())
        self.assertEqual(task["actor"], {"id": "person-1",
                                         "executor": "SAO.Controller",
                                         "bodyOwner": "SAO"})
        self.assertEqual(task["decisionTime"]["currentWork"],
                         {"activity": "forage", "owner": "SAO.Controller"})
        self.assertEqual(task["schemaVersion"], 2)
        self.assertEqual(task["decisionTime"]["competingPriorities"]
                         ["competingPressure"],
                         {"value": 0.2, "available": True,
                          "owner": "SAO.Needs"})
        self.assertEqual(task["choice"]["response"], "accept")
        self.assertEqual(task["laterOutcome"]["commitments"][0]["status"], "completed")
        self.assertEqual(task["admission"]["status"], "candidate-observation")
        encoded = json.dumps(task, sort_keys=True)
        self.assertNotIn('"pathogen"', encoded)
        self.assertNotIn('"visibleForms"', encoded)

    def test_afflicted_and_crossed_share_zao_execution_without_shared_state(self):
        crossed = Tasks.compile_task(self.joined(
            coordination_row(body_owner="ZAO", executor="ZAO.Driver",
                             activity="coordination",
                             need_owner="SAO.Needs via ZAO.Mind"),
            zao_row(terminal="crossed")))
        self.assertEqual(crossed["actor"], {"id": "person-1",
                                            "executor": "ZAO.Driver",
                                            "bodyOwner": "ZAO"})
        self.assertEqual(crossed["decisionTime"]["capabilities"]["owner"],
                         "ZAO.Driver")
        self.assertEqual(crossed["decisionTime"]["competingPriorities"]
                         ["competingPressure"],
                         {"value": 0.2, "available": True,
                          "owner": "SAO.Needs via ZAO.Mind"})
        self.assertEqual(crossed["laterOutcome"]["commitments"][0]["work"]["owner"],
                         "ZAO")
        self.assertNotIn("crossed", json.dumps(crossed["decisionTime"], sort_keys=True))

        afflicted = Tasks.compile_task(self.joined(
            coordination_row(choice="defer", body_owner="ZAO",
                             executor="ZAO.Driver", activity="coordination",
                             need_available=False, need_owner="unavailable"),
            zao_row(terminal="afflicted")))
        self.assertEqual(afflicted["actor"]["executor"], "ZAO.Driver")
        self.assertEqual(afflicted["decisionTime"]["competingPriorities"]
                         ["competingPressure"],
                         {"value": None, "available": False,
                          "owner": "unavailable"})
        self.assertEqual(afflicted["choice"]["response"], "defer")
        self.assertEqual(afflicted["laterOutcome"]["commitments"], [])
        self.assertNotIn("afflicted",
                         json.dumps(afflicted["decisionTime"], sort_keys=True))

    def test_joined_hidden_truth_cannot_change_decision_input(self):
        private = {"choice": "defer", "body_owner": "ZAO",
                   "executor": "ZAO.Driver", "activity": "coordination",
                   "need_available": False, "need_owner": "unavailable"}
        first = Tasks.compile_task(self.joined(
            coordination_row(**private), zao_row(terminal="afflicted")))
        second = Tasks.compile_task(self.joined(
            coordination_row(**private), zao_row(terminal="crossed")))
        self.assertEqual(first["decisionTime"], second["decisionTime"])
        self.assertEqual(first["choice"], second["choice"])
        self.assertEqual(first["laterOutcome"], second["laterOutcome"])
        self.assertNotEqual(first["provenance"]["crossModule"]["zaoSha256"],
                            second["provenance"]["crossModule"]["zaoSha256"])

    def test_unavailable_execution_owner_is_explicit_and_non_executable(self):
        row = coordination_row(choice="decline", available=False, activity="hunt")
        task = Tasks.compile_task(self.joined(row))
        self.assertEqual(task["decisionTime"]["capabilities"]["availability"],
                         "unavailable")
        self.assertEqual(task["choice"]["response"], "decline")

        invalid = coordination_row(choice="decline", available=False)
        private = invalid["enactedProcess"]["decisionTime"]["privateInputs"]
        private["choice"] = "accept"
        invalid["enactedProcess"]["decisionTime"]["response"]["response"] = "accept"
        invalid["enactedProcess"]["laterOutcome"]["response"]["response"] = "accept"
        invalid["choice"]["optionId"] = "coordination:accept"
        with self.assertRaisesRegex(Join.ContractError,
                                    "choice optionId|not a feasible option"):
            Tasks.compile_task(self.joined(invalid))

    def test_wrong_person_stale_revision_impossible_option_and_leakage_refuse(self):
        mutations = []

        wrong_person = coordination_row()
        wrong_person["enactedProcess"]["actorId"] = "person-2"
        mutations.append((wrong_person, "actor differs"))

        stale = coordination_row()
        stale["enactedProcess"]["decisionTime"]["revision"] = 2
        mutations.append((stale, "stale process revision"))

        impossible = coordination_row()
        impossible["enactedProcess"]["decisionTime"]["proposal"]["proposal"][
            "requiredCapabilities"]["carry"] = True
        impossible["enactedProcess"]["decisionTime"]["privateInputs"][
            "capabilities"]["carry"] = False
        mutations.append((impossible, "required carry capability"))

        hidden = coordination_row()
        hidden["enactedProcess"]["decisionTime"]["privateInputs"][
            "pathogenDiagnosis"] = "afflicted"
        mutations.append((hidden, "privateInputs fields differ"))

        nested_hidden = coordination_row()
        nested_hidden["enactedProcess"]["decisionTime"]["privateInputs"][
            "constraints"]["terminalState"] = "crossed"
        mutations.append((nested_hidden, "private constraints contain hidden fields"))

        missing_need_availability = coordination_row()
        del missing_need_availability["enactedProcess"]["decisionTime"][
            "privateInputs"]["constraints"]["ownNeedAvailable"]
        mutations.append((missing_need_availability, "lack representation/activity/owner/need"))

        leaked_commitment = coordination_row()
        leaked_commitment["enactedProcess"]["decisionTime"]["commitments"] = {
            "future": {"status": "completed"}}
        mutations.append((leaked_commitment, "later commitments"))

        leaked_delivery = coordination_row()
        leaked_delivery["enactedProcess"]["decisionTime"]["response"][
            "delivered"] = True
        mutations.append((leaked_delivery, "later response-delivery fact"))

        missing_owner = coordination_row()
        del missing_owner["enactedProcess"]["decisionTime"]["privateInputs"][
            "inputOwners"]["currentActivity"]
        mutations.append((missing_owner, "inputOwners fields differ"))

        foreign_executor = coordination_row()
        commitment = next(iter(foreign_executor["enactedProcess"]["laterOutcome"]
                               ["commitments"].values()))
        commitment["work"]["owner"] = "ZAO"
        mutations.append((foreign_executor, "work owner differs"))

        foreign_native = coordination_row()
        commitment = next(iter(foreign_native["enactedProcess"]["laterOutcome"]
                               ["commitments"].values()))
        commitment["work"]["sourceReceipts"]["source-1"]["owner"] = "planner"
        mutations.append((foreign_native, "SourceUse ownership"))

        for row, message in mutations:
            with self.subTest(message=message):
                with self.assertRaisesRegex(Join.ContractError, message):
                    Tasks.compile_task(self.joined(row))

    def test_full_envelope_and_outcome_clocks_are_bound(self):
        wrong_option = coordination_row()
        wrong_option["options"][0]["parameters"]["actorId"] = "person-2"
        with self.assertRaisesRegex(Join.ContractError,
                                    "option differs from its actor/process/revision"):
            Tasks.compile_task(self.joined(wrong_option))

        future = coordination_row()
        future["enactedProcess"]["laterOutcome"]["asOfHour"] = 25
        with self.assertRaisesRegex(Join.ContractError, "exceeds the later-outcome horizon"):
            Tasks.compile_task(self.joined(future))

        old_revision = coordination_row()
        old_revision["enactedProcess"]["laterOutcome"]["currentRevision"] = 2
        task = Tasks.compile_task(self.joined(old_revision))
        self.assertEqual(task["process"]["revision"], 1)
        self.assertEqual(task["laterOutcome"]["currentRevision"], 2)

    def test_export_is_atomic_and_revalidates_every_row(self):
        write_jsonl(self.sao, [coordination_row()])
        write_jsonl(self.zao, [zao_row()])
        self.assertEqual(Tasks.export_tasks(self.sao, self.zao, self.out), 1)
        saved = self.out.read_bytes()
        invalid = coordination_row(namespace(event="event-2", person="person-2"))
        invalid["enactedProcess"]["actorId"] = "wrong"
        write_jsonl(self.sao, [coordination_row(), invalid])
        write_jsonl(self.zao, [zao_row(), zao_row(invalid["namespace"])])
        with self.assertRaises(Join.ContractError):
            Tasks.export_tasks(self.sao, self.zao, self.out)
        self.assertEqual(self.out.read_bytes(), saved)


if __name__ == "__main__":
    unittest.main(verbosity=2)
