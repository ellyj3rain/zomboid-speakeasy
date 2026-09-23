"""Source binding and hostile meaning changes for the bounded expression proof."""
import copy
import itertools
import unittest
from unittest.mock import patch

import decision_authoring as A
import cross_module_rows as J
import conversation_tasks as C
import expression_proof as P
import experimental_admission as X
import training_evidence as E

FIXTURES = C.ROOT / "training/experiments/expression-proof/fixtures.json"


def fixture_sources():
    for scene in A.read(FIXTURES)["scenes"]:
        yield {key: copy.deepcopy(value) for key, value in scene.items()
               if key not in {"id", "expected"}}, scene["expected"]


class ExpressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = E.Store()
        cls.index = A.read(C.ROOT / "training/speaker/c77-example.json")
        cls.source = P.from_target(cls.index["retrieverTargetSha256"], cls.store)
        cls.model = P.compile_source(cls.source)
        cls.plan = P.report_plan(cls.model, next(iter(cls.model["reports"])),
                                 {kind: 1 for kind in P.KINDS}, vocative=True)

    def test_actual_approved_sentence_and_all_combinations(self):
        output = P.produce(self.source, self.plan)
        approved = self.store.read(self.index["wordingProposalSha256"])
        self.assertEqual(output["text"], approved["output"]["text"])
        outputs = set()
        for choices in itertools.product((0, 1), repeat=len(P.KINDS)):
            plan = copy.deepcopy(self.plan)
            plan["variants"] = dict(zip(P.KINDS, choices))
            value = P.produce(self.source, plan)
            P.validate_output(value, self.source)
            outputs.add(value["text"])
        self.assertEqual(len(outputs), 64)
        self.assertEqual(self.model["participants"]["sao-2"]["givenName"], "Jon")

    def test_independently_written_source_and_expected_text(self):
        for source, expected in fixture_sources():
            model = P.compile_source(source)
            if source["locations"]:
                plans = [{"kind": "location", "proposition": p, "variant": 0}
                         for p in model["propositions"].values()]
            else:
                plans = [P.report_plan(model, next(iter(model["reports"])))]
            self.assertEqual([P.produce(source, p)["text"] for p in plans], expected)

    def test_same_valid_claim_id_cannot_hide_a_changed_proposition(self):
        for key, value in [("ownerRef", "sao-2"), ("knowledgeKind", "observed"),
                           ("at", "1993-07-11"), ("source", {"label": "invented"}),
                           ("value", "working"), ("certainty", "confirmed"),
                           ("relation", "recovery")]:
            plan = copy.deepcopy(self.plan)
            plan["propositions"][0][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(J.ContractError, "binding"):
                P.produce(self.source, plan)
        plan = copy.deepcopy(self.plan)
        plan["propositions"][0]["subject"]["region"] = "Valley"
        with self.assertRaisesRegex(J.ContractError, "binding"):
            P.produce(self.source, plan)

    def test_crossed_people_times_and_reported_observed_are_refused(self):
        source, _ = next(fixture_sources())
        model = P.compile_source(source)
        original = model["propositions"]["jon-location"]
        for key, value in [("subject", "eve"), ("value", "west"),
                           ("at", "09:05"), ("knowledgeKind", "reported"),
                           ("source", "Leah")]:
            p = copy.deepcopy(original)
            p[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(J.ContractError, "binding"):
                P.produce(source, {"kind": "location", "proposition": p, "variant": 0})

    def test_negation_invention_and_extra_prose_refuse(self):
        original = P.produce(self.source, self.plan)
        for text in [original["text"].replace("were out", "were not out"),
                     original["text"].replace("when it went to press", "today"),
                     original["text"].replace("there was talk of", "the cause was"),
                     original["text"] + " I checked the wires myself."]:
            value = copy.deepcopy(original)
            value["text"] = text
            with self.subTest(text=text), self.assertRaisesRegex(J.ContractError, "text"):
                P.validate_output(value, self.source)
        plan = copy.deepcopy(self.plan)
        plan["freeText"] = "Everyone uses the Internet."
        with self.assertRaises(J.ContractError):
            P.produce(self.source, plan)

    def test_missing_name_and_unsupported_source_language_remain_missing(self):
        source = copy.deepcopy(self.source)
        source["participants"]["sao-2"]["givenName"] = None
        with self.assertRaisesRegex(J.ContractError, "name-unavailable"):
            P.produce(source, self.plan)
        source = copy.deepcopy(self.source)
        source["reports"][0]["summary"] += " The service recovered."
        with self.assertRaisesRegex(J.ContractError, "outside-proof-grammar"):
            P.compile_source(source)

    def test_personality_changes_do_not_change_factual_entitlement(self):
        source = copy.deepcopy(self.source)
        source["voiceConditioning"]["conditions"] = ["calm"]
        changed = P.compile_source(source)
        self.assertEqual(changed["propositions"], self.model["propositions"])
        self.assertNotEqual(changed["sourceSha256"], self.model["sourceSha256"])
        self.assertEqual(P.produce(source, self.plan)["text"], P.produce(self.source, self.plan)["text"])

    def test_source_time_and_attribution_cannot_smuggle_prose(self):
        source, _ = next(fixture_sources())
        for at in ["09:00. The phones are working now", "25:00", "09:99", "today"]:
            bad = copy.deepcopy(source)
            bad["locations"][0]["at"] = at
            with self.subTest(at=at), self.assertRaisesRegex(J.ContractError, "HH-MM"):
                P.compile_source(bad)
        for origin in ["Leah never", {"kind": "testimony", "personRef": "unknown"},
                       {"kind": "testimony", "personRef": "leah", "text": "The phones work"}]:
            bad = copy.deepcopy(source)
            bad["locations"][1]["source"] = origin
            with self.subTest(origin=origin), self.assertRaises(J.ContractError):
                P.compile_source(bad)
        model = P.compile_source(source)
        value = P.produce(source, {"kind": "location",
            "proposition": model["propositions"]["eve-location"], "variant": 1})
        self.assertEqual(value["text"], "At 09:05, Leah reported Eve to the west.")

    def test_instrument_detects_a_broken_validator(self):
        value = P.produce(self.source, self.plan)
        value["text"] = "The phones work now."
        with patch.object(P, "validate_output", lambda output, source: output):
            # The test oracle must fail if the shipped admission check is bypassed.
            with self.assertRaises(AssertionError):
                with self.assertRaises(J.ContractError):
                    P.validate_output(value, self.source)

    def test_report_entities_cannot_smuggle_prose(self):
        source = list(fixture_sources())[1][0]
        for before, after in [
            ("the Valley area", "the Valley but the phones are working now throughout Knox area"),
            ("Valley Telecommunications'", "Valley and all phones are working Telecommunications'"),
            ("the Valley area", "the Unknown area")]:
            bad = copy.deepcopy(source)
            bad["reports"][0]["summary"] = bad["reports"][0]["summary"].replace(before, after)
            with self.subTest(after=after), self.assertRaisesRegex(J.ContractError, "entities-outside"):
                P.compile_source(bad)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.store = E.Store()
        self.index = A.read(C.ROOT / "training/understander/c77-example.json")
        self.row = self.store.read(self.index["taskSha256"])

    def test_exact_understander_and_independent_retrieval_are_admitted_to_declared_scope(self):
        result = C.task_conditioning(self.row, self.store, scope=X.SCOPE,
                                    approval=self.index["approvalReceiptSha256"])
        self.assertEqual(result["status"], "admitted-to-offline-evaluation")
        self.assertFalse(result["runtime"]["ready"])
        self.assertEqual(len(result["unavailableNativeInputs"]), 3)
        self.assertEqual(C.task_conditioning(self.row, self.store)["status"], "ineligible")
        target = self.store.read(self.index["retrieverTargetSha256"])
        self.assertEqual(X.inspect(target, scope=X.SCOPE)["status"], "admitted-to-offline-evaluation")
        self.assertEqual(len(target["labels"]["unjudgedClaimRefs"]), 7)

    def test_missing_approval_changed_subject_and_missing_input_refuse(self):
        result = X.inspect(self.row, scope=X.SCOPE)
        self.assertEqual(result["status"], "excluded")
        for mutate in [lambda row: row["output"].update(listenerRef="sao-2"),
                       lambda row: row["input"]["context"].pop("utterance")]:
            row = copy.deepcopy(self.row)
            mutate(row)
            row.pop("contentSha256")
            result = X.inspect(A.seal(row), scope=X.SCOPE,
                               approval=self.index["approvalReceiptSha256"])
            self.assertEqual(result["status"], "excluded")
            self.assertTrue(result["exclusions"])
        with self.assertRaisesRegex(J.ContractError, "unknown experimental"):
            X.inspect(self.row, scope="anything-goes")

    def test_speaker_wording_approval_does_not_approve_formal_task(self):
        index = A.read(C.ROOT / "training/speaker/c77-example.json")
        for key in ["taskSha256", "wordingProposalSha256"]:
            result = X.inspect(self.store.read(index[key]), scope=X.SCOPE,
                               approval=index["wordingReviewReceiptSha256"])
            self.assertEqual(result["status"], "excluded")

    def test_dataset_keeps_shared_sources_together_and_reports_missing_evaluation(self):
        rows = [{"rowSha256": self.index["taskSha256"],
                 "approvalReceiptSha256": self.index["approvalReceiptSha256"]},
                {"rowSha256": self.index["retrieverTargetSha256"]}]
        report = X.compile_dataset(rows, {"train": [rows[0]["rowSha256"]],
            "validation": [], "test": [rows[1]["rowSha256"]]}, scope=X.SCOPE)
        self.assertIn("shared-source-split-leakage", report["dataset"]["exclusions"])
        joined = X.compile_dataset(rows, {"train": [r["rowSha256"] for r in rows],
                                         "validation": [], "test": []}, scope=X.SCOPE)
        self.assertFalse(joined["leakage"])
        self.assertEqual(joined["dataset"]["exclusions"], ["independent-evaluation-partitions-missing"])
        self.assertEqual(joined["evaluation"]["status"], "not-run")
        for invalid in [{rows[0]["rowSha256"]: "ignored"}, rows[0]["rowSha256"], [42]]:
            with self.subTest(invalid=invalid), self.assertRaises(J.ContractError):
                X.compile_dataset(rows, {"train": invalid, "validation": [], "test": []}, scope=X.SCOPE)


if __name__ == "__main__":
    unittest.main()
