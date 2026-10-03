"""C120 private entry/recovery projections through contract and archive export."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cognition_contract as C
import cognition_episodes as E
from test_cognition_episodes import sample, native


def experiences():
    base = dict(actorId="person-1", observerId="person-1", worldHours=2,
                occurredAtHours=1.9, category="body", perspective="performed", status="completed")
    return [dict(base, id="entry/person-1/1", kind="entry-outcome", sourceId="42:99:10:0:door",
                 actionKind="door", apertureState="closed", succeeded=False),
            dict(base, id="recovery/person-1/1", kind="recovery-outcome", actionKind="sleep",
                 beforeValue=.95, afterValue=.3, durationHours=.5, succeeded=True)]


def projection():
    value = sample()
    value["experiences"] = experiences()
    return value


class BehaviorExperience(unittest.TestCase):
    def reject(self, value):
        with self.assertRaises(ValueError):
            C.projection(value, "person-1", full=True, max_hours=2)

    def test_personal_results_are_detached_and_retain_outcomes(self):
        value = projection(); before = copy.deepcopy(value)
        accepted = C.projection(value, "person-1", full=True, max_hours=2)
        self.assertEqual(accepted["experiences"], experiences())
        accepted["experiences"][0]["succeeded"] = True
        self.assertEqual(value, before)
        for succeeded in (True, False):
            value["experiences"][0].update(actionKind="window", apertureState="open", succeeded=succeeded)
            C.projection(value, "person-1", full=True, max_hours=2)

    def test_actor_qualified_event_ids_and_sequence_boundaries(self):
        for index, producer in enumerate(("entry", "recovery")):
            for suffix in ("1", "99999999999999", "1.0E14", "1.00000000000001E14", "9.007199254740991E15"):
                value = projection(); value["experiences"][index]["id"] = producer+"/person-1/"+suffix
                C.projection(value, "person-1", full=True, max_hours=2)
            for event_id in (producer+"/other/1", producer+"/person-1/0", producer+"/person-1/01",
                             producer+"/person-1/1.0", producer+"/person-1/1e2", producer+"/person-1/-1",
                             producer+"/person-1/100000000000000", producer+"/person-1/1.00E14",
                             producer+"/person-1/1.00000000000000001E14", producer+"/person-1/9.007199254740992E15",
                             producer+"/person-1/"+str(2**53), "unqualified/1"):
                value = projection(); value["experiences"][index]["id"] = event_id
                with self.subTest(event_id=event_id): self.reject(value)

    def test_private_attribution_and_occurrence_clocks(self):
        for index in range(2):
            for changed in (dict(actorId="other"), dict(observerId="other"), dict(perspective="observed"),
                            dict(status="interrupted"), dict(status="no-effect"), dict(category="food"),
                            dict(succeeded=1), dict(occurredAtHours=2.01), dict(worldHours=2.01)):
                value = projection(); value["experiences"][index].update(changed)
                with self.subTest(index=index, changed=changed): self.reject(value)
            for field in ("occurredAtHours", "worldHours"):
                for invalid in (-1, True, None, float("nan"), float("inf")):
                    value = projection(); value["experiences"][index][field] = invalid
                    with self.subTest(field=field, invalid=invalid): self.reject(value)

    def test_entry_fields_are_exact_and_observed_condition_is_bounded(self):
        for condition in ("open", "closed", "clear", "smashed", "barricaded", "unknown"):
            value = projection(); value["experiences"][0]["apertureState"] = condition
            C.projection(value, "person-1", full=True, max_hours=2)
        for changed in (dict(actionKind="sleep"), dict(actionKind=[]), dict(apertureState="locked"),
                        dict(apertureState={}), dict(sourceId=""), dict(beforeValue=.5),
                        dict(afterValue=.4), dict(durationHours=1)):
            value = projection(); value["experiences"][0].update(changed)
            with self.subTest(changed=changed): self.reject(value)
        for field in ("sourceId", "actionKind", "apertureState", "succeeded"):
            value = projection(); value["experiences"][0].pop(field); self.reject(value)

    def test_recovery_direction_is_measured_and_duration_is_bounded(self):
        for kind, before, after, succeeded in (("sleep", .9, .3, True), ("sleep", .3, .9, False),
                                              ("rest", .3, .9, True), ("rest", .9, .3, False),
                                              ("sleep", .5, .5, False), ("rest", .5, .5, False)):
            value = projection(); value["experiences"][1].update(
                actionKind=kind, beforeValue=before, afterValue=after, succeeded=succeeded)
            C.projection(value, "person-1", full=True, max_hours=2)
            value["experiences"][1]["succeeded"] = not succeeded
            self.reject(value)
        for field, invalids in (("durationHours", (0, -1, 12.01, True, None, float("nan"))),
                               ("beforeValue", (-.1, 1.1, True, float("inf"))),
                               ("afterValue", (-.1, 1.1, True, float("nan")))):
            for invalid in invalids:
                value = projection(); value["experiences"][1][field] = invalid
                with self.subTest(field=field, invalid=invalid): self.reject(value)
        for changed in (dict(sourceId="somewhere"), dict(apertureState="open"), dict(actionKind="door")):
            value = projection(); value["experiences"][1].update(changed); self.reject(value)

    def test_no_goal_or_training_credit_from_private_results(self):
        for index in range(2):
            for extra in (dict(episodeId="cognition-1"), dict(trainingTarget=True), dict(nativeCredit=1),
                          dict(itemId=1), dict(stats={}), dict(foodPresent=True), dict(hungerDelta=.1)):
                value = projection(); value["experiences"][index].update(extra)
                with self.subTest(index=index, extra=extra): self.reject(value)
            value = projection(); ep = value["episodes"][0]
            ep.update(status="observed", executionStatus="observed", outcome=dict(
                eventId=value["experiences"][index]["id"], worldHours=2,
                actionId="inspect", status="completed", success=True))
            self.reject(value)
        value = projection(); value["experiences"][0].update(kind="consume", category="food")
        self.reject(value)

    def test_archive_export_keeps_private_snapshots_without_policy_targets(self):
        with tempfile.TemporaryDirectory(prefix="r90-behavior-") as raw:
            root=Path(raw); run=root/"run"; package=root/"package"; package.mkdir()
            frame=native(projection(),2)
            frame["coverage"]=dict(peopleComplete=True,processesComplete=True,omittedFieldCount=0)
            frame["population"]=dict(total=1,captured=1)
            target=run/"cache/Lua/StudyWorld/frame.json";target.parent.mkdir(parents=True)
            target.write_bytes(E.encoded(frame))
            receipt=dict(status="completed",datasetAdmission="unreviewed",packageSha256="a"*64,
                         observations={"Lua/StudyWorld/frame.json":E.digest(target.read_bytes())})
            (run/"run.json").write_bytes(E.encoded(receipt))
            validator=root/"world_lab_run.py";validator.write_text("# controlled completed-run receipt\n")
            with patch.object(E.subprocess,"run",return_value=SimpleNamespace(
                    returncode=0,stdout=json.dumps(receipt),stderr="")):
                manifest=E.export(run,package,validator,root/"intake")
            self.assertEqual((manifest["trainingRows"],manifest["teachingTargets"],manifest["observedTargets"]),(0,0,0))
            self.assertEqual(manifest["datasetAdmission"],"unreviewed")
            snapshots=(root/"intake/snapshots.jsonl").read_bytes()
            self.assertEqual(manifest["files"]["snapshots.jsonl"],E.digest(snapshots))
            self.assertEqual(json.loads(snapshots)["projection"]["experiences"],experiences())
            row=json.loads((root/"intake/episodes.jsonl").read_text())
            self.assertTrue(all(p["targetStatus"]=="unobserved" and "target" not in p
                                for p in row["selectedActionComparison"]))

    def test_contract_defect_controls_change_the_rejection(self):
        source=Path(C.__file__).read_text(encoding="utf-8")
        controls=[
            ('value["id"].startswith(prefix)', 'True', lambda v: v["experiences"][0].update(id="entry/otherxxx/1")),
            ('value["succeeded"] == improved', 'True', lambda v: v["experiences"][1].update(succeeded=False)),
            ('value["perspective"] == "performed"', 'True', lambda v: v["experiences"][0].update(status="no-effect")),
        ]
        # The status mutation isolates admission of an unfinished observation;
        # perspective remains independently enforced by the common contract.
        controls[2]=('value["status"] == "completed" and type(value["succeeded"]) is bool',
                     'type(value["succeeded"]) is bool',controls[2][2])
        for before, after, tamper in controls:
            with self.subTest(before=before):
                self.assertEqual(source.count(before),1)
                value=projection();tamper(value);self.reject(value)
                namespace={"__name__":"cognition_contract_defect_control"}
                exec(compile(source.replace(before,after,1),C.__file__,"exec"),namespace)
                namespace["projection"](value,"person-1",full=True,max_hours=2)


if __name__=="__main__":unittest.main()
