"""Focused controls for receipt attribution, clock provenance and graph bounds."""
from __future__ import annotations

import copy
import pathlib
import types
import unittest

import observation_graph as G


def people():
    return [dict(id="person-1", x=1000.5, y=2000.25, z=-1.25, positionSource="native-body",
                 record=dict(forename="Mara", surname="Hayes", occupation="Nurse", dead=False),
                 context=dict(controller=dict(state="Inspect"), perceptionAvailable=True,
                              beliefCounts=dict(people=0, zombies=2, sounds=1)))]


def cognition(outcome=False):
    frame = dict(id="decision/1", actorId="person-1", worldHours=2, hunger=.3, thirst=.2, fatigue=.1,
                 eatAt=.4, drinkAt=.4, foodAllowed=True, waterAllowed=True, inspectionAllowed=True,
                 knownFood=0, knownWater=1, knownPlaces=1, capabilities=dict(cook=False, forage=True, treat=False))
    proposals = [dict(modelId=model, version="model/1", actionId=action,
                      interpretation="Private interpretation " + model, confidence=.6,
                      predictions={a: dict(probability=probability, claim="Predicted result for " + a)
                                   for a in ("food", "water", "inspect", "continue")})
                 for model, action, probability in (("ordinary", "continue", .25), ("associative", "inspect", .75))]
    episode = dict(id="decision/1", worldHours=2, status="attempted", executionStatus="queued", frame=frame,
                   proposals=proposals, selectedModelId="associative", selectedActionId="inspect",
                   selectionWeight=.5, selectionPolicy="deterministic-balanced", disagreement=True)
    if outcome:
        episode.update(status="observed", executionStatus="observed", outcome=dict(
            eventId="native/inspection/1", worldHours=2.1, actionId="inspect", status="completed", success=True))
    return dict(schema="simulation.cognition/1", actorId="person-1", sequence=1,
                settings=dict(enabled=True, opponentShare=.5, opportunitiesPerHour=12, maxDepth=3),
                omittedEpisodes=0, omittedExperiences=0, episodes=[episode],
                models=[dict(id=model, version="model/1", beliefs=[], hypotheses=[])
                        for model in ("ordinary", "associative")])


def section(identifier="needs", status="available"):
    return dict(id=identifier, label="Current needs", source="Native body", perspective="Current physical state",
                status=status, message="" if status == "available" else "No native body was sampled",
                rows=[dict(label="Hunger", value="0.3000"), dict(label="Health (%)", value="98.50")])


def event(identifier, hours=2.2, **fields):
    return dict(id=identifier, capturedAtUnixMs=800, worldHours=hours, source="Communication",
                stage="emitted", summary="Contact was emitted", **fields)


def detail(view=None, **fields):
    result = dict(sections=[section()], events=[], capturedAtUnixMs=900, worldHours=2.5, **fields)
    if view is not None:
        result["cognition"] = view
    return result


def build(view=None, persons=None, details=None, hours=3):
    return G.build_observation_graph(people() if persons is None else persons,
                                    {"person-1": detail(view)} if details is None else details,
                                    captured_at_unix_ms=1000, world_hours=hours)


def metric(node, key):
    return next((m["value"] for m in node.get("metrics", []) if m["key"] == key), None)


def receipt_semantics(graph):
    """Independent test oracle for selected actions and actual outcome ownership."""
    nodes = {node["id"]: node for node in graph["nodes"]}
    selections = [edge for edge in graph["edges"] if edge["relation"] == "selects"]
    if len(selections) != 1:
        return False
    action = nodes[selections[0]["to"]]
    if metric(action, "actionId") != "inspect" or metric(action, "selected") is not True:
        return False
    results = [edge for edge in graph["edges"] if edge["relation"] == "result"]
    if len(results) != 1 or results[0]["from"] != action["id"]:
        return False
    outcome = nodes[results[0]["to"]]
    return (outcome["source"]["recordId"] == "native/inspection/1"
            and metric(outcome, "actionId") == "inspect" and outcome["perspective"] == "observed")


class ObservationGraph(unittest.TestCase):
    def test_frozen_predictions_are_distinct_from_selected_and_observed_results(self):
        before, after = build(cognition()), build(cognition(True))
        self.assertEqual(before["status"], "available")
        self.assertFalse(any(n["kind"] == "outcome" for n in before["nodes"]))
        self.assertFalse(any(e["relation"] == "result" for e in before["edges"]))
        predictions = [n for n in after["nodes"] if n["status"] == "prediction"]
        self.assertEqual(len(predictions), 8)
        self.assertTrue(all(n["perspective"] == "predicted" for n in predictions))
        self.assertEqual({metric(n, "probability") for n in predictions}, {.25, .75})
        self.assertTrue(all(n["confidence"] == .6 for n in predictions))
        self.assertTrue(receipt_semantics(after))
        actions = [n for n in after["nodes"] if n["kind"] == "action"]
        self.assertEqual(len(actions), 4)
        self.assertTrue(all(n["perspective"] == "predicted" for n in actions if metric(n, "actionId") != "inspect"))
        G.validate_observation_graph(after)

    def test_clocks_are_source_clocks_and_native_position_remains_fractional(self):
        graph = build(cognition(True))
        person = next(n for n in graph["nodes"] if n["kind"] == "person")
        self.assertEqual(person["position"], dict(x=1000.5, y=2000.25, z=-1.25, source="native-body"))
        self.assertEqual(person["source"]["worldHours"], 3)
        self.assertEqual(person["source"]["capturedAtUnixMs"], 0)
        need = next(n for n in graph["nodes"] if n["kind"] == "need")
        self.assertEqual(need["source"]["worldHours"], 2.5)
        self.assertEqual(need["source"]["capturedAtUnixMs"], 900)
        decision = next(n for n in graph["nodes"] if n["kind"] == "decision")
        self.assertEqual(decision["source"]["worldHours"], 2)
        self.assertEqual(decision["source"]["capturedAtUnixMs"], 0)
        outcome = next(n for n in graph["nodes"] if n["kind"] == "outcome")
        self.assertEqual(outcome["source"]["worldHours"], 2.1)

    def test_independent_snapshot_clock_missing_is_unknown(self):
        source = detail(cognition())
        source.pop("capturedAtUnixMs"); source.pop("worldHours")
        graph = build(details={"person-1": source})
        need = next(n for n in graph["nodes"] if n["kind"] == "need")
        self.assertIsNone(need["source"]["worldHours"])
        self.assertEqual(need["source"]["capturedAtUnixMs"], 0)
        self.assertEqual(next(n for n in graph["nodes"] if n["kind"] == "decision")["source"]["worldHours"], 2)

    def test_durable_location_is_explicitly_recorded_and_never_current_body(self):
        persons = people(); persons[0]["positionSource"] = "durable-record"
        graph = build(persons=persons)
        person = next(n for n in graph["nodes"] if n["kind"] == "person")
        self.assertEqual(person["perspective"], "unknown")
        self.assertEqual(person["status"], "recorded")
        self.assertEqual(person["position"]["source"], "durable-record")
        self.assertIn("not sampled", person["summary"])
        changed = copy.deepcopy(graph); changed["nodes"][0]["perspective"] = "observed"
        with self.assertRaisesRegex(ValueError, "provenance"):
            G.validate_observation_graph(changed)

    def test_missing_native_references_stay_unknown_and_model_status_is_private(self):
        view = cognition()
        for model in view["models"]:
            model["beliefs"] = [dict(id="same-belief", label="Food is likely here", confidence=.7, status="supported")]
            model["hypotheses"] = [dict(id="same-hypothesis", label="Containment may preserve food", branch="preservation",
                depth=2, confidence=.6, status="supported", evidenceIds=["missing-native-receipt"],
                parentIds=["missing-parent"], missing=["Duration and losses are unmeasured"])]
        graph = build(view)
        beliefs = [n for n in graph["nodes"] if n["source"]["recordId"] == "same-belief"]
        self.assertEqual(len(beliefs), 2)
        self.assertEqual(len({n["id"] for n in beliefs}), 2)
        self.assertTrue(all(n["perspective"] == "private" for n in beliefs))
        unknowns = [n for n in graph["nodes"] if n["source"]["recordId"] == "missing-native-receipt"]
        self.assertEqual(len(unknowns), 1)
        self.assertEqual(unknowns[0]["perspective"], "unknown")
        self.assertIsNone(unknowns[0]["source"]["worldHours"])
        self.assertFalse(any(e["relation"] in {"supports", "refutes", "result"} for e in graph["edges"]))
        self.assertTrue(any(e["relation"] == "reports" and e["to"] == unknowns[0]["id"] for e in graph["edges"]))

    def test_explicit_evidence_resolves_exact_receipt_without_asserting_causality(self):
        view = cognition(True)
        view["models"][1]["hypotheses"] = [dict(id="h1", label="Inspecting locates water", branch="water", depth=1,
            confidence=.5, status="supported", evidenceIds=["native/inspection/1"], parentIds=[], missing=[])]
        graph = build(view)
        outcome = next(n for n in graph["nodes"] if n["kind"] == "outcome")
        self.assertTrue(any(e["to"] == outcome["id"] and e["relation"] == "reports" for e in graph["edges"]))
        self.assertFalse(any(n["kind"] == "externality" for n in graph["nodes"]))

    def test_limited_inspection_reports_unavailable_without_filling_default_needs(self):
        graph = build(details={"person-1": dict(sections=[section(status="unavailable")], events=[])})
        self.assertEqual(graph["status"], "available")
        self.assertFalse(any(n["kind"] == "need" for n in graph["nodes"]))
        unknown = next(n for n in graph["nodes"] if n["kind"] == "unknown")
        self.assertEqual(unknown["metrics"], [])
        self.assertIn("unavailable", graph["message"])
        graph = build(details={})
        self.assertTrue(any(n["label"] == "Inspection unavailable" for n in graph["nodes"]))

    def test_event_correlation_and_recipient_do_not_prove_reception_or_externality(self):
        source = detail()
        source["events"] = [event("e1", recipientId="person-2", correlationId="communication/1"),
                            event("e2", 2.3, correlationId="communication/1"), event("e3", 2.4)]
        persons = people() + [dict(id="person-2", x=1000.6, y=2000.3, z=-1.25, positionSource="native-body")]
        graph = build(persons=persons, details={"person-1": source})
        edges = [e for e in graph["edges"] if e["relation"] == "correlates"]
        self.assertEqual(len(edges), 1)
        self.assertFalse(any(e["relation"] in {"result", "precedes", "supports", "refutes"} for e in graph["edges"]))
        self.assertFalse(any(n["kind"] in {"outcome", "externality"} for n in graph["nodes"]))
        self.assertEqual(next(n for n in graph["nodes"] if n["source"]["recordId"] == "e1")["source"]["capturedAtUnixMs"], 800)

    def test_observed_other_actor_experience_has_no_private_effect_or_causal_arrow(self):
        view = cognition()
        view["experiences"] = [dict(id="seen-store", actorId="outsider", observerId="person-1", worldHours=2.3,
            kind="store", category="food", perspective="observed", status="completed", sourceId="container/2")]
        graph = build(view)
        node = next(n for n in graph["nodes"] if n["source"]["recordId"] == "seen-store")
        self.assertEqual(node["actorId"], "outsider")
        self.assertEqual(node["perspective"], "observed")
        self.assertFalse(any(n["kind"] == "externality" for n in graph["nodes"]))
        self.assertFalse(any(e["relation"] == "result" for e in graph["edges"]))

    def test_future_inspection_is_withheld_without_reclocking_people(self):
        source = detail(cognition(True)); source["worldHours"] = 3.1
        graph = build(details={"person-1": source})
        self.assertEqual(graph["worldHours"], 3)
        self.assertFalse(any(n["kind"] in {"decision", "need", "outcome"} for n in graph["nodes"]))
        self.assertIn("1 newer receipts withheld", graph["message"])
        source = detail(); source["capturedAtUnixMs"] = 1001
        self.assertIn("1 newer receipts withheld", build(details={"person-1": source})["message"])

    def test_future_outcome_is_withheld_but_earlier_prediction_is_preserved(self):
        view = cognition(True); view["episodes"][0]["outcome"]["worldHours"] = 3.1
        graph = build(view)
        self.assertTrue(any(n["kind"] == "decision" for n in graph["nodes"]))
        self.assertEqual(len([n for n in graph["nodes"] if n["status"] == "prediction"]), 8)
        self.assertFalse(any(n["kind"] == "outcome" for n in graph["nodes"]))
        self.assertFalse(any(e["relation"] == "result" for e in graph["edges"]))

    def test_censored_receipt_does_not_become_success_or_observed_effect(self):
        view = cognition(True); episode = view["episodes"][0]
        episode["status"] = "censored"; episode["executionStatus"] = "censored"
        episode["outcome"].pop("success"); episode["outcome"]["status"] = "interrupted"
        graph = build(view)
        outcome = next(n for n in graph["nodes"] if n["kind"] == "outcome")
        self.assertEqual(outcome["perspective"], "unknown")
        self.assertIsNone(metric(outcome, "success"))

    def test_malformed_or_unknown_data_never_manufactures_claims(self):
        for patch in (dict(selectedActionId="food"), dict(outcome=dict(eventId="bad", worldHours=2,
                       actionId="water", status="completed"))):
            view = cognition(); view["episodes"][0].update(patch)
            graph = build(view)
            self.assertFalse(any(n["kind"] in {"decision", "outcome"} for n in graph["nodes"]))
            self.assertIn("1 invalid records withheld", graph["message"])
        for position in (dict(x="1000"), dict(y=float("nan")), dict(z=32), dict(z=-32.1),
                         dict(positionSource="inferred-region"), dict(x=10**400)):
            persons = people(); persons[0].update(position)
            graph = build(persons=persons)
            self.assertNotIn("position", next(n for n in graph["nodes"] if n["kind"] == "person"))
        graph = build(details={"person-1": dict(sections=[dict(garbage=True)], events=[dict(garbage=True)])})
        self.assertEqual(graph["status"], "available")
        self.assertFalse(any(n["kind"] in {"need", "event", "outcome"} for n in graph["nodes"]))

    def test_unavailable_and_failed_are_empty_and_have_no_world_clock(self):
        for persons, hours, state in ((None, 3, "unavailable"), ({}, 3, "failed"), ([], float("nan"), "failed")):
            graph = G.build_observation_graph(persons, {}, captured_at_unix_ms=1000, world_hours=hours)
            self.assertEqual(graph["status"], state)
            self.assertIsNone(graph["worldHours"])
            self.assertEqual((graph["nodes"], graph["edges"]), ([], []))
            G.validate_observation_graph(graph)
        self.assertEqual(build(persons=[])["status"], "available")
        persons = people() * 2
        self.assertEqual(build(persons=persons)["status"], "failed")

    def test_all_source_rows_retained_in_chunks_with_exact_strings_and_units(self):
        source = section(); source["rows"] += [dict(label="Recorded " + str(i), value="value/" + str(i)) for i in range(40)]
        graph = build(details={"person-1": dict(sections=[source], events=[])})
        rows = [m for n in graph["nodes"] if n["kind"] == "need" for m in n["metrics"]]
        self.assertEqual(len(rows), 42)
        self.assertEqual([m["value"] for m in rows], [r["value"] for r in source["rows"]])
        self.assertEqual(rows[0]["unit"], "native ratio")
        self.assertEqual(rows[1]["unit"], "%")
        unverified = section(); unverified["source"] = "Unknown physical owner"
        graph = build(details={"person-1": dict(sections=[unverified], events=[])})
        self.assertFalse(any(n["kind"] == "need" for n in graph["nodes"]))

    def test_bounds_omit_facts_and_edges_without_dangling_endpoints(self):
        view = cognition(True); template = view["episodes"][0]
        view["episodes"] = []
        for i in range(64):
            episode = copy.deepcopy(template); episode["id"] = "decision/" + str(i)
            episode["outcome"]["eventId"] = "native/" + str(i)
            view["episodes"].append(episode)
        graph = build(view)
        self.assertEqual(len(graph["nodes"]), 128)
        self.assertGreater(graph["omittedNodes"], 0)
        self.assertGreater(graph["omittedEdges"], 0)
        self.assertLessEqual(len(graph["edges"]), 256)
        ids = {n["id"] for n in graph["nodes"]}
        self.assertTrue(all(e["from"] in ids and e["to"] in ids for e in graph["edges"]))
        G.validate_observation_graph(graph)
        persons = [dict(id="person/" + str(i), x=i * 100, y=-i, z=-32, positionSource="durable-record") for i in range(200)]
        graph = build(persons=persons, details={})
        self.assertEqual(len(graph["nodes"]), 128)
        self.assertGreaterEqual(graph["omittedNodes"], 72)

    def test_ids_are_stable_across_publication_and_input_order(self):
        source = cognition(True)
        graph1 = build(source)
        source["models"].reverse(); source["episodes"][0]["proposals"].reverse()
        graph2 = G.build_observation_graph(people(), {"person-1": detail(source)}, captured_at_unix_ms=2000, world_hours=4)
        self.assertEqual({n["id"] for n in graph1["nodes"]}, {n["id"] for n in graph2["nodes"]})
        self.assertEqual({e["id"] for e in graph1["edges"]}, {e["id"] for e in graph2["edges"]})

    def test_direct_normalized_cognition_and_raw_context_use_same_contract(self):
        source = cognition(True)
        source["capturedAtUnixMs"] = 900; source["worldHours"] = 2.5
        graph = build(details={"person-1": source})
        self.assertTrue(receipt_semantics(graph))
        persons = people(); persons[0]["context"]["cognition"] = cognition(True)
        graph = build(persons=persons, details={})
        self.assertTrue(receipt_semantics(graph))

    def test_validator_rejects_fabricated_edges_extra_fields_and_future_source(self):
        original = build(cognition(True))
        for mutation in ("selected", "outcome", "clock", "extra", "position"):
            graph = copy.deepcopy(original)
            alternative = next(n for n in graph["nodes"] if n["kind"] == "action" and metric(n, "actionId") == "food")
            if mutation == "selected":
                next(e for e in graph["edges"] if e["relation"] == "selects")["to"] = alternative["id"]
            elif mutation == "outcome":
                next(e for e in graph["edges"] if e["relation"] == "result")["from"] = alternative["id"]
            elif mutation == "clock":
                graph["nodes"][0]["source"]["worldHours"] = 4
            elif mutation == "extra":
                graph["nodes"][0]["omniscient"] = True
            else:
                graph["nodes"][0]["position"]["source"] = "inferred-region"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                G.validate_observation_graph(graph)

    def test_source_mutation_controls_detect_selected_outcome_clock_and_position_defects(self):
        source = pathlib.Path(G.__file__).read_text(encoding="utf-8")
        controls = [
            ("selected", 'builder.edge(decision, actions[episode["selectedActionId"]], "selects"',
             'builder.edge(decision, actions["food"], "selects"'),
            ("outcome", 'builder.edge(actions[episode["selectedActionId"]], node, "result"',
             'builder.edge(actions["food"], node, "result"'),
            ("body-clock", '_source("Native people observation", actor, world_hours)',
             '_source("Native people observation", actor, world_hours, captured)'),
            ("floor", 'optional["position"] = {k: person[k] for k in ("x", "y", "z")} | {"source": provenance}',
             'optional["position"] = {k: (0 if k == "z" else person[k]) for k in ("x", "y", "z")} | {"source": provenance}'),
        ]
        self.assertTrue(receipt_semantics(build(cognition(True))))
        for label, before, after in controls:
            self.assertEqual(source.count(before), 1, "Control target must be executable and unique: " + label)
            changed = source.replace(before, after)
            self.assertNotEqual(changed, source)
            namespace = types.ModuleType("observation_graph_control_" + label)
            exec(compile(changed, "<observation-graph-control>", "exec"), namespace.__dict__)
            with self.subTest(control=label):
                if label in {"selected", "outcome"}:
                    with self.assertRaises(ValueError):
                        namespace.build_observation_graph(people(), {"person-1": detail(cognition(True))},
                                                         captured_at_unix_ms=1000, world_hours=3)
                else:
                    graph = namespace.build_observation_graph(people(), {"person-1": detail(cognition(True))},
                                                              captured_at_unix_ms=1000, world_hours=3)
                    person = next(n for n in graph["nodes"] if n["kind"] == "person")
                    verdict = person["source"]["capturedAtUnixMs"] == 0 if label == "body-clock" else person["position"]["z"] == -1.25
                    self.assertFalse(verdict, "Mutation must flip the provenance verdict: " + label)
        self.assertTrue(receipt_semantics(build(cognition(True))), "Controls must not mutate production source")


if __name__ == "__main__":
    unittest.main()
