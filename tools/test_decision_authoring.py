#!/usr/bin/env python3
"""Controlled evidence fixtures; none are a captured county or approved choice."""

from __future__ import annotations

import copy
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import cross_module_rows as Join
import decision_authoring as Author
from test_cross_module_rows import sao_row


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def claim_from_line(fragment, identity, knowable="1991-04-01T00:00:00",
                    confidence="HIGH", carrier="everyone"):
    relative = "world/us-1993/timeline.md"
    path = Join.ROOT / relative
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if fragment in line:
            return {"id": identity, "text": line.split("|")[1].strip(),
                    "confidence": confidence, "knowableAt": knowable,
                    "carrier": carrier, "acquisitionRules": ["read", "heard", "lived", "told"],
                    "source": {"path": relative, "sha256": Join.sha256(path), "line": number,
                               "excerptSha256": hashlib.sha256(line.encode("utf-8")).hexdigest()}}
    raise AssertionError("protected fixture source absent")


def native_event(ns, operation="consume"):
    """Production descriptor fields, with controlled item/source values."""
    parameters = {"action": "attempt-source-use" if operation == "consume"
                  else "attempt-inventory-transfer", "actorId": ns["personId"],
                  "placeId": "place-1", "category": "food", "admission": "standing",
                  "quantity": 1, "sourceId": "source-1", "sourceKind": "container",
                  "sourceX": 10, "sourceY": 20, "sourceZ": 0, "chunkX": 1, "chunkY": 2,
                  "fingerprint": "source-fingerprint", "revision": "revision-1",
                  "itemId": 12, "itemType": "Base.Apple", "itemAmount": 0, "itemUses": 1}
    private = {"kind": "private-source-revision", "actorId": ns["personId"],
               "sourceId": "source-1", "revision": "revision-1", "beliefAtTick": 230,
               "provenance": "seen"}
    admission = {"kind": "attempt-admission", "admission": "standing",
                 "atHours": ns["hour"], "physicalAccess": "revalidate-on-arrival"}
    if operation != "consume":
        parameters.update({"operation": operation, "quantityUnit": "item", "itemFluid": 0,
                           "itemPoison": 0, "itemRotten": False, "itemCategories": "food",
                           "itemCondition": 10, "itemCurrentUses": 1, "itemSignature": "signature-1"})
        if operation == "store":
            parameters["preItemSignature"] = "signature-1"
        private = {"kind": "private-source-inspection", "actorId": ns["personId"],
                   "sourceId": "source-1", "revision": "revision-1",
                   "provenance": "native-transfer-inspection", "atHours": ns["hour"]}
        admission = {"kind": "current-transfer-admission", "admission": "standing",
                     "physicalAccess": "native-reachable-inspection"}
    option = {"id": "source-1", "owner": "SAO.SourceUse", "parameters": parameters,
              "eligibility": {"status": "eligible", "evidence": [private, admission]}}
    offer = {"schemaVersion": 1, "actorId": ns["personId"], "category": "food",
             "quantity": 1, "admission": "standing", "atHours": ns["hour"],
             "place": {"id": "place-1", "cx": 10, "cy": 20},
             "scope": "selected-place-and-need" if operation == "consume" else "inspected-item-and-holder",
             "candidateCount": 1, "limit": 128, "truncated": False, "options": [option]}
    if operation != "consume":
        offer.update({"operation": operation, "quantityUnit": "item"})
    return {"schema": "sao-source-decision-event", "schemaVersion": 1,
            "runId": ns["runId"], "county": ns["county"], "eventId": ns["eventId"],
            "decision": {"eventType": "source-use", "runId": ns["runId"], "county": ns["county"],
                         "eventId": ns["eventId"], "hours": ns["hour"], "person": {"id": ns["personId"]},
                         "situation": {"county": ns["county"], "hour": ns["hour"], "sourceOffer": offer}},
            "choice": {"optionId": "source-1", "status": "selected", "ratified": False,
                       "authorship": "runtime-policy", "owner": "SAO.SourceUse.chooseOption"},
            "result": {"status": "pending"},
            "observation": {"atHours": ns["hour"] + 1, "decisionHours": ns["hour"],
                            "horizon": "source-action-terminal-or-capture-end", "laterConsequences": "not-observed"},
            "conditioning": {"status": "ineligible", "reasons": ["runtime-choice-not-ratified"]}}


class AuthoringTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="speakeasy-authoring-")
        self.root = Path(self.temporary.name)
        self.capture = self.root / "capture.json"
        self.knowledge = self.root / "knowledge.json"
        self.view = self.root / "view.json"
        self.request = self.root / "request.json"
        self.out = self.root / "out.json"
        self.event = sao_row()
        self.event["conditioning"]["status"] = "ineligible"
        self.event["conditioning"]["exclusions"] = ["runtime-choice-not-ratified"]
        self.reference = {"owner": "controlled-fixture", "recordId": "acquisition-1",
                          "sha256": "a" * 64}
        self.claim = claim_from_line("The federal minimum wage rose", "minimum-wage")
        self.bundle = {"schema": "speakeasy-knowledge-input", "schemaVersion": 1,
                       "namespace": copy.deepcopy(self.event["namespace"]),
                       "eventSha256": Author.digest(self.event),
                       "calendar": {"anchorHour": 0, "anchorAt": "1993-07-01T00:00:00",
                                    "horizonHour": 24, "evidence": self.reference},
                       "claims": [self.claim], "acquisitions": []}
        self.bundle["acquisitions"] = [self.acquisition(self.claim)]
        self.save()

    def tearDown(self):
        self.temporary.cleanup()

    def acquisition(self, claim):
        return {"claimId": claim["id"], "claimSha256": Author.digest(claim),
                "namespace": copy.deepcopy(self.event["namespace"]),
                "acquiredHour": 1, "asOfHour": 24, "path": "heard", "retained": True,
                "checks": {name: {"status": "supported", "evidence": [self.reference]}
                           for name in Author.CHECKS}, "evidence": [self.reference]}

    def save(self):
        write(self.capture, self.event)
        write(self.knowledge, self.bundle)

    def compile(self):
        self.save()
        return Author.compile_view(self.capture, self.knowledge)

    def request_for(self, view):
        option = view["options"][0]
        return {"schema": "speakeasy-choice-request", "schemaVersion": 1,
                "namespace": copy.deepcopy(view["namespace"]),
                "eventSha256": view["eventSha256"], "knowledgeViewSha256": view["contentSha256"],
                "optionId": option["id"], "optionSha256": Author.digest(option),
                "author": {"kind": "model", "id": "controlled-generator", "version": "1",
                           "promptSha256": "b" * 64},
                "rationale": "Controlled test rationale; not a real approved choice."}

    def prepare_proposal(self):
        view = self.compile()
        request = self.request_for(view)
        write(self.view, view)
        write(self.request, request)
        return view, request

    def propose(self):
        return Author.proposal(self.capture, self.knowledge, self.view, self.request)

    def test_deterministic_detached_view_retains_ineligible_standing(self):
        first = self.compile()
        second = self.compile()
        self.assertEqual(Author.encoded(first), Author.encoded(second))
        self.assertEqual(first["availableClaims"][0]["claim"]["id"], "minimum-wage")
        self.assertEqual(first["conditioning"]["status"], "ineligible")
        self.assertIn("runtime-choice-not-ratified", first["conditioning"]["exclusions"])
        first["availableClaims"][0]["claim"]["text"] = "mutated"
        self.assertNotEqual(first, self.compile())
        self.assertEqual(Join.protected_artifacts().__len__(), 15)

    def test_native_c65_capture_and_explicit_acquire_store_options(self):
        ns = self.event["namespace"]
        for operation in ("consume", "acquire", "store"):
            with self.subTest(operation=operation):
                self.event = native_event(ns, operation)
                self.bundle["eventSha256"] = Author.digest(self.event)
                self.save()
                capture = {"schema": "sao-source-decision-capture", "schemaVersion": 1,
                           "status": "observed", "eventCount": 1, "attemptedEvents": 1,
                           "captureFailureCount": 0, "failures": {}, "events": [self.event]}
                write(self.capture, capture)
                view = Author.compile_view(self.capture, self.knowledge)
                self.assertEqual(view["options"], self.event["decision"]["situation"]["sourceOffer"]["options"])
                self.assertNotIn("choice", view)
                self.assertNotIn("result", view)
                self.assertEqual(view["namespace"], ns)
        self.event["choice"]["ratified"] = True
        write(self.capture, self.event)
        with self.assertRaisesRegex(Join.ContractError, "unratified standing"):
            Author.compile_view(self.capture, self.knowledge)

    def test_v3_authoring_shares_complete_original_row_admission(self):
        original = copy.deepcopy(self.event)
        variants = [("person", "pathogen", {"asOfHour": 100}, "cross-module enriched"),
                    ("situation", "visibleForms", [{"personId": "hidden"}], "cross-module enriched"),
                    ("citation", "person", "other-person", "citation differs"),
                    ("citation", "hour", 100, "citation differs")]
        for section, field, value, error in variants:
            with self.subTest(section=section, field=field):
                self.event = copy.deepcopy(original)
                self.event[section][field] = value
                self.bundle["eventSha256"] = Author.digest(self.event)
                self.save()
                with self.assertRaisesRegex(Join.ContractError, error):
                    Join.validate_sao(self.capture)
                with self.assertRaisesRegex(Join.ContractError, error):
                    Author.compile_view(self.capture, self.knowledge)

    def test_native_option_actor_and_evidence_time_are_bound(self):
        ns = self.event["namespace"]
        for operation in ("consume", "acquire", "store"):
            mutations = [("parameters", "actorId", "other-person", "option actor"),
                         ("private", "actorId", "other-person", "private evidence actor"),
                         ("private", "sourceId", "other-source", "source/revision"),
                         ("private", "revision", "other-revision", "source/revision"),
                         ("admission", "atHours", 48, "evidence time"),
                         ("admission", "admission", "other-permission", "admission evidence")]
            if operation != "consume":
                mutations.append(("private", "atHours", 48, "evidence time"))
            for target, field, value, error in mutations:
                with self.subTest(operation=operation, target=target, field=field):
                    self.event = native_event(ns, operation)
                    option = self.event["decision"]["situation"]["sourceOffer"]["options"][0]
                    selected = option["parameters"] if target == "parameters" else option["eligibility"]["evidence"][0 if target == "private" else 1]
                    selected[field] = value
                    self.bundle["eventSha256"] = Author.digest(self.event)
                    self.save()
                    with self.assertRaisesRegex(Join.ContractError, error):
                        Author.compile_view(self.capture, self.knowledge)

    def test_native_c65_rejects_enriched_context_for_every_operation(self):
        ns = self.event["namespace"]
        for operation in ("consume", "acquire", "store"):
            variants = [("person", "pathogen", {"asOfHour": 100, "terminalState": "crossed"},
                         "person is already cross-module enriched"),
                        ("situation", "visibleForms", [{"personId": "unseen-person", "asOfHour": 100}],
                         "situation is already cross-module enriched"),
                        ("decision", "crossModule", {"asOfHour": 100}, "already carries join provenance"),
                        ("envelope", "crossModule", {"asOfHour": 100}, "already carries join provenance")]
            for section, field, value, error in variants:
                with self.subTest(operation=operation, section=section):
                    self.event = native_event(ns, operation)
                    target = self.event if section == "envelope" else self.event["decision"]
                    if section in ("person", "situation"):
                        target = target[section]
                    target[field] = value
                    self.bundle["eventSha256"] = Author.digest(self.event)
                    self.save()
                    self.out.write_bytes(b"prior-output\n")
                    with self.assertRaisesRegex(Join.ContractError, error):
                        Author.compile_view(self.capture, self.knowledge)
                    with redirect_stdout(io.StringIO()):
                        self.assertEqual(Author.main(["view", "--capture", str(self.capture),
                                                      "--knowledge", str(self.knowledge),
                                                      "--out", str(self.out)]), 2)
                    self.assertEqual(self.out.read_bytes(), b"prior-output\n")

    def test_semantically_equal_hour_namespaces_cannot_duplicate(self):
        first = copy.deepcopy(self.event)
        second = copy.deepcopy(first)
        second["namespace"]["hour"] = 24.0
        self.assertNotEqual(Author.digest(first), Author.digest(second))
        self.capture.write_text(json.dumps(first) + "\n" + json.dumps(second) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(Join.ContractError, "duplicate full event namespace"):
            Author.events(self.capture)
        ns = first["namespace"]
        native_first = native_event(ns)
        native_second = native_event({**ns, "hour": 24.0})
        self.capture.write_text(json.dumps(native_first) + "\n" + json.dumps(native_second) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(Join.ContractError, "duplicate full event namespace"):
            Author.events(self.capture)
        self.bundle["namespace"]["hour"] = 24.0
        self.save()
        self.assertEqual(Author.compile_view(self.capture, self.knowledge)["namespace"], first["namespace"])

    def test_future_low_and_missing_acquisition_exclude_text(self):
        future = claim_from_line("Michael Jordan, 30", "future-retirement",
                                 knowable="1993-10-06T00:00:00")
        low = claim_from_line("Still without a primary source", "low-chart",
                              confidence="LOW", carrier="-")
        self.bundle["claims"] += [future, low]
        self.bundle["acquisitions"] += [self.acquisition(future), self.acquisition(low)]
        self.bundle["acquisitions"][0]["namespace"]["personId"] = "other-person"
        view = self.compile()
        self.assertEqual(view["availableClaims"], [])
        reasons = {row["claimId"]: row["reason"] for row in view["excludedClaims"]}
        self.assertEqual(reasons, {"future-retirement": "future-to-person-horizon",
                                  "low-chart": "low-confidence",
                                  "minimum-wage": "other-person-or-event"})
        self.assertNotIn(future["text"], json.dumps(view))
        self.bundle["acquisitions"] = []
        view = self.compile()
        self.assertEqual(next(x for x in view["excludedClaims"] if x["claimId"] == "minimum-wage")["reason"],
                         "missing-acquisition")

    def test_other_namespace_late_acquisition_and_unverified_access_are_excluded(self):
        controls = [({"county": "County099"}, None, "other-person-or-event"),
                    (None, ("acquiredHour", 25), "outside-decision-time"),
                    (None, ("asOfHour", 23), "outside-decision-time"),
                    (None, ("retained", False), "not-retained")]
        for namespace_delta, delta, expected in controls:
            with self.subTest(expected=expected, delta=delta):
                record = self.acquisition(self.claim)
                if namespace_delta:
                    record["namespace"].update(namespace_delta)
                if delta:
                    record[delta[0]] = delta[1]
                self.bundle["acquisitions"] = [record]
                self.assertEqual(self.compile()["excludedClaims"][0]["reason"], expected)
        self.bundle["acquisitions"] = [self.acquisition(self.claim)]
        self.bundle["acquisitions"][0]["checks"]["access"] = {"status": "unknown", "evidence": []}
        self.assertEqual(self.compile()["excludedClaims"][0]["reason"], "person-checks-incomplete")

    def test_explicit_calendar_mapping_and_horizon_are_required(self):
        self.bundle["calendar"]["horizonHour"] = 25
        with self.assertRaisesRegex(Join.ContractError, "horizon exceeds"):
            self.compile()
        self.bundle["calendar"]["horizonHour"] = 24
        self.bundle["calendar"]["anchorAt"] = "1993"
        with self.assertRaisesRegex(Join.ContractError, "calendar instants"):
            self.compile()

    def test_claim_and_source_tamper_refuse(self):
        for field, changed in (("text", "invented fact"), ("confidence", "MEDIUM")):
            with self.subTest(field=field):
                original = self.claim[field]
                self.claim[field] = changed
                with self.assertRaises(Join.ContractError):
                    self.compile()
                self.claim[field] = original
        self.claim["source"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(Join.ContractError, "hash-matched"):
            self.compile()

    def test_review_and_adjudication_standing_comes_only_from_exact_receipts(self):
        review_path = self.root / "claim-review.json"
        adjudication_path = self.root / "acquisition-adjudication.json"
        review = Author.seal({
            "schema": Author.CLAIM_REVIEW_SCHEMA, "schemaVersion": 1,
            "claimId": self.claim["id"], "claimSha256": Author.digest(self.claim),
            "source": copy.deepcopy(self.claim["source"]),
            "ruleSources": [{
                "role": "claim-source",
                "path": self.claim["source"]["path"],
                "sha256": self.claim["source"]["sha256"],
                "startLine": self.claim["source"]["line"],
                "endLine": self.claim["source"]["line"],
                "excerptSha256": self.claim["source"]["excerptSha256"],
            }],
            "review": {"status": "reviewed", "textBoundary": "literal-substring",
                       "knowableAt": self.claim["knowableAt"],
                       "carrier": self.claim["carrier"],
                       "acquisitionRules": self.claim["acquisitionRules"],
                       "confidence": {"value": "HIGH", "basis": "literal-source-field",
                                      "sourceLineHasLiteralConfidence": True}},
            "reviewer": {"kind": "repository-review", "id": "controlled-review",
                         "procedureSha256": "c" * 64},
            "findings": ["The literal boundary and declared time match the cited line."],
        })
        record = self.bundle["acquisitions"][0]
        adjudication = Author.seal({
            "schema": Author.ACQUISITION_REVIEW_SCHEMA, "schemaVersion": 1,
            "claimId": self.claim["id"], "claimSha256": Author.digest(self.claim),
            "acquisitionSha256": Author.digest(record),
            "namespace": copy.deepcopy(self.event["namespace"]),
            "eventSha256": Author.digest(self.event),
            "importEvidence": self.reference,
            "checks": copy.deepcopy(record["checks"]), "status": "adjudicated",
            "reviewer": {"kind": "repository-review", "id": "controlled-review",
                         "procedureSha256": "d" * 64},
            "limitations": ["Controlled fixture; not a natural county sample."],
        })
        write(review_path, review)
        write(adjudication_path, adjudication)
        view = Author.compile_view(self.capture, self.knowledge,
                                   [review_path, adjudication_path])
        row = view["availableClaims"][0]
        self.assertEqual(row["extractionStanding"], "reviewed")
        self.assertEqual(row["acquisitionStanding"], "adjudicated")
        self.assertNotIn("claim-extraction-not-reviewed",
                         view["conditioning"]["exclusions"])
        self.assertNotIn("acquisition-evidence-not-adjudicated",
                         view["conditioning"]["exclusions"])
        self.assertNotIn("claim-extraction-not-ratified",
                         view["conditioning"]["exclusions"])
        review["findings"][0] = "changed without a new receipt"
        write(review_path, review)
        with self.assertRaisesRegex(Join.ContractError, "content hash differs"):
            Author.compile_view(self.capture, self.knowledge,
                                [review_path, adjudication_path])

    def test_nonliteral_confidence_requires_an_explicit_exact_review(self):
        relative = "world/us-1993/knox-event.md"
        path = Join.ROOT / relative
        line = path.read_text(encoding="utf-8").splitlines()[70]
        claim = {
            "id": "knox-telecommunications-outage-1993-07-02",
            "text": "Knox Telecommunications' telephone and Internet networks failed across the Knox area for hours",
            "confidence": "HIGH", "knowableAt": "1993-07-02T00:00:00",
            "carrier": "county", "acquisitionRules": ["lived"],
            "source": {"path": relative, "sha256": Join.sha256(path), "line": 71,
                       "excerptSha256": hashlib.sha256(line.encode("utf-8")).hexdigest()},
        }
        with self.assertRaisesRegex(Join.ContractError, "has no review"):
            Author.source_claim(claim, Join.protected_artifacts())
        review = Author.seal({
            "schema": Author.CLAIM_REVIEW_SCHEMA, "schemaVersion": 1,
            "claimId": claim["id"], "claimSha256": Author.digest(claim),
            "source": copy.deepcopy(claim["source"]),
            "ruleSources": [{
                "role": "claim-source", "path": relative,
                "sha256": claim["source"]["sha256"], "startLine": 71,
                "endLine": 71,
                "excerptSha256": claim["source"]["excerptSha256"],
            }],
            "review": {"status": "reviewed", "textBoundary": "literal-substring",
                       "knowableAt": claim["knowableAt"], "carrier": "county",
                       "acquisitionRules": ["lived"],
                       "confidence": {"value": "HIGH",
                                      "basis": "approved-direct-game-record",
                                      "sourceLineHasLiteralConfidence": False}},
            "reviewer": {"kind": "repository-review", "id": "record-52",
                         "procedureSha256": "e" * 64},
            "findings": ["The line predates claim-level confidence fields; the approved direct game record supports HIGH."],
        })
        Author.source_claim(claim, Join.protected_artifacts(), review)
        bad = copy.deepcopy(review)
        bad["review"]["confidence"]["sourceLineHasLiteralConfidence"] = True
        bad.pop("contentSha256")
        bad = Author.seal(bad)
        with self.assertRaisesRegex(Join.ContractError, "misstates"):
            Author.source_claim(claim, Join.protected_artifacts(), bad)

    def test_namespace_event_and_option_tamper_refuse(self):
        self.bundle["namespace"]["county"] = "elsewhere"
        with self.assertRaisesRegex(Join.ContractError, "namespace/event hash"):
            self.compile()
        self.bundle["namespace"] = copy.deepcopy(self.event["namespace"])
        self.event["options"][0]["parameters"]["role"] = "scout"
        with self.assertRaisesRegex(Join.ContractError, "namespace/event hash"):
            self.compile()

    def test_proposal_is_separate_and_cannot_self_approve(self):
        view, request = self.prepare_proposal()
        protected_before = {p: a["sha256"] for p, a in Join.protected_artifacts().items()}
        proposal = self.propose()
        self.assertEqual(proposal["approval"], {"status": "unratified"})
        self.assertEqual(proposal["conditioning"]["status"], "ineligible")
        self.assertEqual(proposal["namespace"], self.event["namespace"])
        self.assertEqual(view, Author.read(self.view))
        request["approval"] = {"status": "approved"}
        write(self.request, request)
        with self.assertRaisesRegex(Join.ContractError, "approval is not"):
            self.propose()
        self.assertEqual(protected_before, {p: a["sha256"] for p, a in Join.protected_artifacts().items()})

    def test_proposal_recomputes_view_and_binds_exact_option(self):
        view, request = self.prepare_proposal()
        request["optionSha256"] = "c" * 64
        write(self.request, request)
        with self.assertRaisesRegex(Join.ContractError, "option identity/content"):
            self.propose()
        write(self.request, self.request_for(view))
        view["availableClaims"][0]["claim"]["text"] = "hidden future information"
        view.pop("contentSha256")
        write(self.view, Author.seal(view))
        with self.assertRaisesRegex(Join.ContractError, "differs from reproducible"):
            self.propose()

    def test_protected_paths_inputs_and_manifest_are_not_outputs(self):
        view = self.compile()
        for output in (self.capture, self.knowledge, Join.PROTECTED_MANIFEST, Author.ACQUISITION_CORRECTIONS,
                       Join.ROOT / "world/us-1993/timeline.md"):
            with self.subTest(output=output):
                before = output.read_bytes()
                with self.assertRaisesRegex(Join.ContractError, "cannot replace"):
                    Author.publish(output, view, [self.capture, self.knowledge])
                self.assertEqual(output.read_bytes(), before)

    def test_atomic_failure_and_invalid_input_leave_existing_output(self):
        self.out.write_bytes(b"prior-output\n")
        view = self.compile()
        original = Join.os.replace
        Join.os.replace = lambda *args: (_ for _ in ()).throw(OSError("controlled failure"))
        try:
            with self.assertRaises(OSError):
                Author.publish(self.out, view, [self.capture, self.knowledge])
        finally:
            Join.os.replace = original
        self.assertEqual(self.out.read_bytes(), b"prior-output\n")
        self.assertEqual(list(self.root.glob(".out.json.*.tmp")), [])
        self.bundle["claims"][0]["text"] = "forged"
        self.save()
        self.assertEqual(Author.main(["view", "--capture", str(self.capture),
                                     "--knowledge", str(self.knowledge), "--out", str(self.out)]), 2)
        self.assertEqual(self.out.read_bytes(), b"prior-output\n")

    def test_duplicate_json_keys_and_unknown_capture_refuse(self):
        with self.assertRaisesRegex(Join.ContractError, "duplicate JSON key"):
            Author.loads('{"namespace":{},"namespace":{}}')
        write(self.capture, {"schema": "sao-source-decision-capture", "schemaVersion": 1,
                             "status": "unavailable", "captureFailureCount": 0, "failures": [],
                             "eventCount": 0, "attemptedEvents": 0, "events": []})
        with self.assertRaisesRegex(Join.ContractError, "unavailable or failed"):
            Author.compile_view(self.capture, self.knowledge)

    def test_real_excerpt_example_has_unknown_acquisition(self):
        example = Author.read(Join.ROOT / "world/claim-examples/minimum-wage.json")
        self.assertEqual(example["acquisition"], "unknown")
        self.assertEqual(example["conditioning"]["status"], "ineligible")
        self.bundle["claims"] = [example["claim"]]
        self.bundle["acquisitions"] = []
        result = self.compile()
        self.assertEqual(result["availableClaims"], [])
        self.assertEqual(result["excludedClaims"][0]["reason"], "missing-acquisition")

    def test_inspect_to_view_to_proposal_cli(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            self.assertEqual(Author.main(["inspect", "--capture", str(self.capture)]), 0)
        inspected = json.loads(stream.getvalue())
        self.assertEqual(inspected["eventSha256"], self.bundle["eventSha256"])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(Author.main(["view", "--capture", str(self.capture),
                                         "--knowledge", str(self.knowledge), "--out", str(self.view)]), 0)
        view = Author.read(self.view)
        request = self.request_for(view)
        self.assertEqual(inspected["options"][0]["optionSha256"], request["optionSha256"])
        write(self.request, request)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(Author.main(["propose", "--capture", str(self.capture),
                                         "--knowledge", str(self.knowledge), "--view", str(self.view),
                                         "--request", str(self.request), "--out", str(self.out)]), 0)
        self.assertEqual(Author.read(self.out)["approval"]["status"], "unratified")


if __name__ == "__main__":
    unittest.main(verbosity=2)
