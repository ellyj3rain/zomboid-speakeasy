import copy
import unittest

import cognition_contract as C
import cognition_episodes as E
import world_watch as W


def sample():
    frame = dict(id="cognition-1", actorId="person-1", worldHours=2, hunger=.3, thirst=.2, fatigue=.1,
                 eatAt=.4, drinkAt=.4, foodAllowed=True, waterAllowed=True, inspectionAllowed=True,
                 knownFood=0, knownWater=1, knownPlaces=1, capabilities=dict(cook=False, forage=True, treat=False))
    proposals = [dict(modelId=model, version="model/1", actionId=action,
                      interpretation="Prediction from this model's private prior", confidence=.6,
                      predictions={a: dict(probability=probability, claim="A qualified native outcome for " + a)
                                   for a in C.ACTIONS})
                 for model, action, probability in (("ordinary", "continue", .25), ("associative", "inspect", .75))]
    ep = dict(id="cognition-1", worldHours=2, status="attempted", executionStatus="queued", frame=frame,
              proposals=proposals, selectedModelId="associative", selectedActionId="inspect",
              selectionWeight=.5, selectionPolicy="deterministic-balanced", disagreement=True)
    return dict(schema="simulation.cognition/1", actorId="person-1", sequence=1,
                settings=dict(enabled=True, opponentShare=.5, opportunitiesPerHour=12, maxDepth=3),
                omittedEpisodes=0, omittedExperiences=0, episodes=[ep],
                models=[dict(id=m, version="model/1", beliefs={}, hypotheses={}) for m in sorted(C.MODELS)])


def native(view, hours=2):
    return dict(schema="sao-study-observation/1", datasetAdmission="unreviewed", hours=hours, save="Study",
                people=[dict(id="person-1", context=dict(cognition=view))])


class CognitionEvidence(unittest.TestCase):
    def test_compact_native_projection_at_byte_boundary(self):
        value=sample(); template=value["episodes"][0]
        value["episodes"]=[]
        for i in range(8):
            episode=copy.deepcopy(template);episode["id"]="ep-"+str(i)
            for proposal in episode["proposals"]:
                proposal["interpretation"]="i"*512
                for prediction in proposal["predictions"].values(): prediction["claim"]="p"*512
            value["episodes"].append(episode)
        for model in value["models"]:
            model["hypotheses"]=[]
            model["beliefs"]=[dict(id="belief-"+str(i),label="b",confidence=.5,status="supported") for i in range(64)]
        base=len(E.encoded(value))-1
        remaining=64*1024-base
        self.assertGreater(remaining,0)
        for model in value["models"]:
            for belief in model["beliefs"]:
                added=min(511,remaining);belief["label"]+="b"*added;remaining-=added
        self.assertEqual(remaining,0)
        self.assertEqual(len(E.encoded(value))-1,64*1024)
        C.projection(value,"person-1",max_hours=2)
        value["models"][-1]["beliefs"][-1]["label"]+="b"
        with self.assertRaises(ValueError): C.projection(value,"person-1",max_hours=2)

    def test_county_time_bounds_every_retained_experience(self):
        view = sample()
        for ep in view["episodes"]:
            ep["worldHours"] += 24000; ep["frame"]["worldHours"] += 24000
        view["experiences"] = [dict(id="native/1", actorId="person-1", observerId="person-1",
            worldHours=24002,kind="inspection",category="container",perspective="performed",status="completed")]
        frame = native(view);frame["countyHours"] = 24002
        E.Trajectories().add(frame, "a"*64)
        view["experiences"][0]["worldHours"] += .01
        with self.assertRaises(ValueError): E.Trajectories().add(frame, "b"*64)
        view.pop("experiences")
        with self.assertRaises(ValueError): C.projection(view, "person-1", max_hours=24001.99)
        C.projection(view, "person-1", max_hours=24002)

    def test_streamed_snapshots_do_not_accumulate_in_memory(self):
        output=[]
        joined=E.Trajectories(output.append)
        for _ in range(3): joined.add(native(sample()), "a"*64)
        self.assertEqual(joined.snapshots, [])
        self.assertEqual(joined.snapshot_count, 3)
        self.assertEqual(len(output), 3)
        self.assertGreater(joined.snapshot_bytes, 0)
        joined.episode_bytes=64*1024*1024
        view=sample();view["episodes"][0]["id"]="new-episode"
        with self.assertRaisesRegex(ValueError, "episode memory byte limit"):
            joined.add(native(view), "b"*64)

    def test_detached_lua_arrays_and_actor_private_frame(self):
        value = sample()
        validated = C.projection(value, "person-1")
        self.assertEqual(validated["models"][0]["beliefs"], [])
        validated["episodes"][0]["frame"]["hunger"] = .9
        self.assertEqual(value["episodes"][0]["frame"]["hunger"], .3)
        for patch in (dict(actorId="someone-else"), dict(objectiveStock={"food": True}), dict(hunger=float("nan"))):
            changed = copy.deepcopy(value)
            changed["episodes"][0]["frame"].update(patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                C.projection(changed, "person-1")

    def test_selected_action_is_only_observed_target_for_both_contestants(self):
        value = sample()
        joined = E.Trajectories()
        joined.add(native(value), "a" * 64)
        ep = value["episodes"][0]
        ep.update(status="observed", executionStatus="observed",
                  outcome=dict(eventId="inspection-1", worldHours=2.1, actionId="inspect", status="completed", success=True))
        joined.add(native(value, 2.1), "b" * 64)
        row = joined.rows()[0]
        self.assertEqual(row["unobservedAlternatives"], ["continue"])
        scores = {p["modelId"]: p for p in row["selectedActionComparison"]}
        self.assertEqual(scores["ordinary"]["actionId"], "inspect")
        self.assertEqual(scores["ordinary"]["squaredError"], .5625)
        self.assertEqual(scores["associative"]["squaredError"], .0625)
        self.assertEqual(row["firstObservedStatus"], "attempted")
        self.assertEqual(row["datasetAdmission"], "unreviewed")
        self.assertNotIn("preferredModel", row)

    def test_absent_and_censored_outcomes_never_become_negative_examples(self):
        for status, outcome in (("attempted", None), ("censored", None),
                                ("censored", dict(eventId="route-1", worldHours=2,
                                                  actionId="inspect", status="unavailable"))):
            view = sample(); view["episodes"][0]["status"] = status
            if outcome:
                view["episodes"][0]["outcome"] = outcome
            joined = E.Trajectories(); joined.add(native(view), "a" * 64)
            for predicted in joined.rows()[0]["selectedActionComparison"]:
                self.assertEqual(predicted["targetStatus"], "unobserved")
                self.assertNotIn("target", predicted)
                self.assertNotIn("squaredError", predicted)

    def test_mutated_prediction_and_terminal_rewrite_are_refused(self):
        view = sample(); joined = E.Trajectories(); joined.add(native(view), "a" * 64)
        changed = copy.deepcopy(view)
        changed["episodes"][0]["proposals"][0]["predictions"]["inspect"]["probability"] = .9
        with self.assertRaisesRegex(ValueError, "pre-outcome"):
            joined.add(native(changed, 2.2), "b" * 64)
        view["episodes"][0]["status"] = "censored"
        joined.add(native(view, 2.3), "c" * 64)
        view["episodes"][0]["status"] = "attempted"
        with self.assertRaisesRegex(ValueError, "terminal"):
            joined.add(native(view, 2.4), "d" * 64)

    def test_wrong_selection_false_score_and_future_outcome_refused(self):
        value = sample()
        ep = value["episodes"][0]
        ep.update(status="observed", outcome=dict(eventId="inspection-1", worldHours=2.1,
                                                actionId="inspect", status="completed", success=True))
        changed = copy.deepcopy(value); changed["episodes"][0]["outcome"]["actionId"] = "food"
        with self.assertRaises(ValueError): C.projection(changed, "person-1")
        changed = copy.deepcopy(value); changed["episodes"][0]["selectedModelId"] = "ordinary"
        with self.assertRaises(ValueError): C.projection(changed, "person-1")
        with self.assertRaisesRegex(ValueError, "future"):
            E.Trajectories().add(native(value, 2), "a" * 64)
        predictions = {p["modelId"]: dict(p["predictions"]["inspect"], squaredError=0) for p in ep["proposals"]}
        ep["outcome"]["predictions"] = predictions
        with self.assertRaisesRegex(ValueError, "score"):
            C.projection(value, "person-1")

    def test_bridge_preserves_source_cognition_without_learning(self):
        source = sample()
        inspection = dict(sequence=1, capturedAtUnixMs=1, worldHours=2, status="available", message="",
                          omittedPeople=0, omittedEvents=0,
                          people={"person-1": dict(sections=[], events=[], cognition=source)})
        before = copy.deepcopy(inspection)
        _, details = W.inspection_view(inspection, [{"id": "person-1"}])
        self.assertEqual(details["person-1"]["cognition"]["episodes"], source["episodes"])
        self.assertEqual(inspection, before)
        projected = W.people_view([dict(id="person-1")], details)
        self.assertEqual(projected[0]["cognition"]["actorId"], "person-1")

    def test_acceleration_translates_only_bounded_model_budget(self):
        command = dict(schema="mousecat.native-view-command/1", sessionId="study", sequence=1,
                       action="cognition", opponentShare=.75, opportunitiesPerHour=30, maxDepth=4)
        result = W.translate(command, "study", 1, {}, [], (0, 0, 512, 512)).decode()
        self.assertEqual(result, "maxDepth=4\nopponentShare=0.75\nopportunitiesPerHour=30\nsequence=1\n")
        for patch in (dict(opponentShare=True), dict(opportunitiesPerHour=61), dict(maxDepth=1.5),
                      dict(enabled=True), dict(speed=3)):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                W.translate(command | patch, "study", 1, {}, [], (0, 0, 512, 512))


if __name__ == "__main__":
    unittest.main()
