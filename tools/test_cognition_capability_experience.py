"""Data contract tests for native personal-use evidence; no model implementation."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cognition_contract as C
import cognition_episodes as E
from test_cognition_episodes import sample, native


def experiences():
    base = dict(actorId="person-1", observerId="person-1", worldHours=24002,
                perspective="performed", status="completed", occurredAtHours=24002)
    return [
        dict(base, id="medication/1", kind="medication-use", category="medicine",
             itemId=-12, itemType="Base.Pills"),
        dict(base, id="physical/60", kind="physical-change", category="body", occurredAtHours=1,
             stats=dict(PAIN=dict(before=50, after=20), THIRST=dict(before=.6, after=.4))),
        dict(base, id="cooking/person-1/1", kind="preparation", category="food",
             itemId=123, itemType="Base.Chicken", sourceId="C:fixture:0", heatObserved=True,
             beforeCookingTime=0, afterCookingTime=45),
    ]


def projection():
    value = sample()
    for ep in value["episodes"]:
        ep["worldHours"] += 24000; ep["frame"]["worldHours"] += 24000
        for p in ep["proposals"]:
            p["version"] = "sao-" + p["modelId"] + "/1"
    for model in value["models"]:
        model["version"] = "sao-" + model["id"] + "/2"
    value["experiences"] = experiences()
    return value


class CapabilityExperience(unittest.TestCase):
    def reject(self, value):
        with self.assertRaises(ValueError):
            C.projection(value, "person-1", full=True, max_hours=24002)

    def test_new_facts_preserve_old_predictions_and_current_versions(self):
        value = projection(); before = copy.deepcopy(value)
        accepted = C.projection(value, "person-1", full=True, max_hours=24002)
        self.assertEqual(accepted["experiences"], experiences())
        self.assertTrue(all(p["version"].endswith("/1") for p in accepted["episodes"][0]["proposals"]))
        self.assertTrue(all(m["version"].endswith("/2") for m in accepted["models"]))
        accepted["experiences"][1]["stats"]["PAIN"]["after"] = 0
        self.assertEqual(value, before)
        value.pop("experiences")
        C.projection(value, "person-1", max_hours=24002)

    def test_county_acquisition_clock_is_independent_of_old_occurrence(self):
        value = projection(); frame = native(value, hours=2); frame["countyHours"] = 24002
        joined = E.Trajectories(); joined.add(frame, "a" * 64)
        self.assertEqual(joined.snapshots[0]["projection"]["experiences"][1]["worldHours"], 24002)
        for index in range(3):
            changed = copy.deepcopy(value); changed["experiences"][index]["worldHours"] += .001
            with self.subTest(index=index): self.reject(changed)
            changed = copy.deepcopy(value); changed["experiences"][index]["occurredAtHours"] = 24002.001
            with self.subTest(occurrence=index): self.reject(changed)
        for field in ("worldHours", "occurredAtHours"):
            for invalid in (None, True, float("nan"), float("inf"), -1):
                changed = copy.deepcopy(value); changed["experiences"][1][field] = invalid
                with self.subTest(field=field, invalid=invalid): self.reject(changed)
        frame.pop("countyHours")
        with self.assertRaisesRegex(ValueError, "future"):
            E.Trajectories().add(frame, "b" * 64)

    def test_raw_native_attribution_and_labels_are_rejected(self):
        for index in range(3):
            for key in ("family", "profile", "exposures", "doseSequence", "efficacy", "nativeCredit", "preferredModel", "trainingTarget"):
                value = projection(); value["experiences"][index][key] = "hidden native attribution"
                with self.subTest(index=index, key=key): self.reject(value)
        value = projection(); value["experiences"][1]["stats"]["PAIN"]["family"] = "hidden"
        self.reject(value)

    def test_private_changes_cannot_be_witnessed_or_bound_to_an_episode(self):
        for index in range(3):
            for patch_data in (dict(actorId="someone-else", perspective="observed"),
                               dict(observerId="someone-else"), dict(episodeId="cognition-1")):
                value = projection(); value["experiences"][index].update(patch_data)
                with self.subTest(index=index, patch=patch_data): self.reject(value)
            for key in ("hungerDelta", "thirstDelta", "foodPresent", "waterPresent"):
                value = projection(); value["experiences"][index][key] = .1 if key.endswith("Delta") else True
                with self.subTest(index=index, key=key): self.reject(value)

    def test_measured_stats_are_named_finite_changed_and_bounded(self):
        invalid = [{}, [], {"UNKNOWN": dict(before=1, after=2)}, {"PAIN": dict(before=1, after=1)},
                   {"PAIN": dict(before=True, after=0)}, {"PAIN": dict(before=1)},
                   {"PAIN": dict(before=0, after=1e6+1)}, {"PAIN": dict(before=0, after=float("nan"))},
                   {"PAIN": dict(before=0, after=1, effect=1)}]
        for stats in invalid:
            value = projection(); value["experiences"][1]["stats"] = stats
            with self.subTest(stats=stats): self.reject(value)
        value = projection(); value["experiences"][1]["stats"] = {
            name: dict(before=-1e6, after=1e6) for name in C.FELT_STATS}
        C.projection(value, "person-1", full=True, max_hours=24002)
        for extra in (dict(itemId=7), dict(itemType="Base.Pills"), dict(sourceId="medicine:1"), dict(heatObserved=True)):
            value = projection(); value["experiences"][1].update(extra)
            with self.subTest(extra=extra): self.reject(value)

    def test_native_item_ids_include_signed_int_boundaries(self):
        for index in (0, 2):
            for item_id in (-(2**31), 2**31-1):
                value = projection(); value["experiences"][index]["itemId"] = item_id
                C.projection(value, "person-1", full=True, max_hours=24002)
            for item_id in (True, 1.5, -(2**31)-1, 2**31, "1", None):
                value = projection(); value["experiences"][index]["itemId"] = item_id
                with self.subTest(index=index, item_id=item_id): self.reject(value)
            for key in ("itemId", "itemType"):
                value = projection(); value["experiences"][index].pop(key)
                with self.subTest(index=index, key=key): self.reject(value)
        value = projection(); value["experiences"][0]["sourceId"] = "unmeasured-source"
        self.reject(value)

    def test_preparation_requires_exact_identity_and_measured_heat(self):
        for patch_data in (dict(heatObserved=False), dict(heatObserved=1),
                           dict(afterCookingTime=0), dict(beforeCookingTime=46),
                           dict(afterCookingTime=1e9+1), dict(beforeCookingTime=-1),
                           dict(sourceId=""), dict(itemType="")):
            value = projection(); value["experiences"][2].update(patch_data)
            with self.subTest(patch=patch_data): self.reject(value)
        for key in ("sourceId", "heatObserved", "beforeCookingTime", "afterCookingTime"):
            value = projection(); value["experiences"][2].pop(key)
            with self.subTest(missing=key): self.reject(value)

    def test_category_and_legacy_field_boundaries(self):
        for index in range(3):
            value = projection(); value["experiences"][index]["category"] = "water"
            with self.subTest(index=index): self.reject(value)
        for kind in (None, [], {}, True, "unknown"):
            value = projection(); value["experiences"][0]["kind"] = kind
            with self.subTest(kind=kind): self.reject(value)
        for key, extra in (("itemId", 1), ("occurredAtHours", 2), ("stats", {}),
                           ("heatObserved", True), ("beforeCookingTime", 0), ("afterCookingTime", 1)):
            value = sample(); value["experiences"] = [dict(id="native/1", actorId="person-1", observerId="person-1",
                worldHours=2, kind="consume", category="food", perspective="performed", status="completed", hungerDelta=.1)]
            value["experiences"][0][key] = extra
            with self.subTest(key=key), self.assertRaises(ValueError):
                C.projection(value, "person-1", full=True, max_hours=2)

    def test_new_facts_cannot_supply_goal_outcomes_or_new_actions(self):
        for event in experiences():
            value = projection(); ep = value["episodes"][0]
            ep.update(status="observed", executionStatus="observed", outcome=dict(eventId=event["id"], worldHours=24002,
                      actionId="inspect", status="completed", success=True))
            with self.subTest(kind=event["kind"]), self.assertRaisesRegex(ValueError, "cannot settle"):
                C.projection(value, "person-1", full=True, max_hours=24002)
        for action in ("medication", "prepare", "treat", "technology"):
            value = projection(); value["episodes"][0]["proposals"][0]["actionId"] = action
            with self.subTest(action=action): self.reject(value)

    def test_same_time_batch_and_local_actor_ids_remain_bounded(self):
        value = projection(); base = value["experiences"][1]
        value["experiences"] = [dict(base, id="physical/"+str(i)) for i in range(256)]
        C.projection(value, "person-1", full=True, max_hours=24002)
        value["experiences"].append(dict(base, id="physical/256")); self.reject(value)
        value["experiences"].pop(); value["experiences"][-1]["id"] = value["experiences"][0]["id"]
        self.reject(value)

    def test_personal_capability_context_is_preserved_and_typed(self):
        value = projection()
        for event in value["experiences"]:
            event["capabilities"] = dict(cook=True, forage=False, treat=True)
        accepted = C.projection(value, "person-1", full=True, max_hours=24002)
        self.assertEqual(accepted["experiences"], value["experiences"])
        accepted["experiences"][0]["capabilities"]["cook"] = False
        self.assertTrue(value["experiences"][0]["capabilities"]["cook"])
        for index in range(3):
            for context in (None, {}, dict(cook=True, forage=False),
                            dict(cook=1, forage=False, treat=True),
                            dict(cook=True, forage=False, treat=True, family="hidden")):
                changed = copy.deepcopy(value)
                changed["experiences"][index]["capabilities"] = context
                with self.subTest(index=index, context=context): self.reject(changed)

    def test_export_is_unreviewed_and_creates_no_training_rows(self):
        with tempfile.TemporaryDirectory(prefix="r74-contract-") as raw:
            root=Path(raw); run=root/"run"; package=root/"package"; package.mkdir()
            frame=native(projection(),2);frame["countyHours"]=24002
            frame["coverage"]=dict(peopleComplete=True,processesComplete=True,omittedFieldCount=0)
            frame["population"]=dict(total=1,captured=1)
            target=run/"cache/Lua/StudyWorld/frame.json";target.parent.mkdir(parents=True)
            target.write_bytes(E.encoded(frame))
            receipt=dict(status="completed",datasetAdmission="unreviewed",packageSha256="a"*64,
                         observations={"Lua/StudyWorld/frame.json":E.digest(target.read_bytes())})
            (run/"run.json").write_bytes(E.encoded(receipt))
            validator=root/"world_lab_run.py";validator.write_text("# controlled completed-run receipt\n")
            with patch.object(E.subprocess,"run",return_value=SimpleNamespace(returncode=0,stdout=json.dumps(receipt),stderr="")):
                manifest=E.export(run,package,validator,root/"intake")
            self.assertEqual((manifest["trainingRows"],manifest["teachingTargets"],manifest["observedTargets"]),(0,0,0))
            self.assertEqual(manifest["datasetAdmission"],"unreviewed")
            snapshot=json.loads((root/"intake/snapshots.jsonl").read_text())
            self.assertEqual(snapshot["projection"]["experiences"],experiences())
            row=json.loads((root/"intake/episodes.jsonl").read_text())
            self.assertTrue(all(p["targetStatus"]=="unobserved" and "target" not in p for p in row["selectedActionComparison"]))

    @unittest.skipUnless(os.environ.get("SAO_COGNITION_CANDIDATE"), "explicit installed native candidate is not configured")
    def test_installed_kahlua_source_bound_projection(self):
        candidate=Path(os.environ["SAO_COGNITION_CANDIDATE"]).resolve()
        sao=Path(os.environ["SAO_SOURCE_ROOT"]).resolve()
        game=Path(os.environ["PZ_DIR"]);jdk=Path(os.environ["JDK_BIN"])
        modules=[candidate/"mod/42.20/media/lua/shared"/name for name in ("SAO_CognitiveModels.lua","SAO_Cognition.lua")]
        labor=sao/"mod/42.20/media/lua/shared/SAO_Labor.lua"
        runner=sao/"tools/luacheck/LuaRun.java"
        inputs=modules+[labor,runner,game/"projectzomboid.jar"]
        fingerprints={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
        # This is a client of the source-owned data API. No producer/model code
        # is copied across the GPL/MIT repository boundary.
        fixture=r'''
SAO={History={countyHours=function()return 24002 end},Identity={get=function(id)return records[id]end}}
records={["person-1"]={id="person-1"}}
SAO.Census={skillOf=function(id,perk)
 assert(id=="person-1")
 local own={Cooking=2,Foraging=0,["First Aid"]=1}
 return own[perk]
end}
local data={}
ModData={get=function(k)return data[k]end,getOrCreate=function(k)data[k]=data[k] or {};return data[k]end}
'''
        invoke=r'''
local C=SAO.Cognition
assert(C.configure(.5,12,3))
assert(C.choose("person-1",{id="native-frame",actorId="person-1",worldHours=24002,hunger=.3,thirst=.2,fatigue=.1,
 eatAt=.4,drinkAt=.4,foodAllowed=true,waterAllowed=true,inspectionAllowed=true,knownFood=0,knownWater=1,knownPlaces=1,
 capabilities={cook=false,forage=true,treat=false}}))
assert(C.medicationUse("person-1",{actorId="person-1",sequence=1,itemId=-12,itemType="Base.Pills",atHours=24002,
 status="completed",consumed=1,family="not-private",capabilities={cook=false,forage=true,treat=false}}))
assert(C.physicalChange("person-1",{kind="physical-change",minute=60,atHours=1,observedAtHours=24002,
 stats={PAIN={before=50,after=20},THIRST={before=.6,after=.4}},exposures={hiddenFamily=1}}))
assert(C.preparationOutcome("person-1",{id="cooking/person-1/1",actorId="person-1",sequence=1,itemId=123,itemType="Base.Chicken",
 sourceId="C:fixture:0",startedAt=24001.8,atHours=24002,status="completed",detail="native-food-cooked-and-retrieved",
 beforeCookingTime=0,afterCookingTime=45,heatObserved=true,nativeCredit="cooking/person-1/1",retrieved=true,shutdown="off"}))
local function quoted(s)return '"'..string.gsub(string.gsub(s,'\\','\\\\'),'"','\\"')..'"'end
local function encoded(v)
 if type(v)=="string" then return quoted(v) end
 if type(v)~="table" then return tostring(v) end
 local values={}
 if #v>0 then for _,x in ipairs(v)do values[#values+1]=encoded(x)end return "["..table.concat(values,",").."]" end
 local keys={} for k in pairs(v)do keys[#keys+1]=k end table.sort(keys)
 for _,k in ipairs(keys)do values[#values+1]=quoted(k)..":"..encoded(v[k])end
 return "{"..table.concat(values,",").."}"
end
RESULT=encoded(C.snapshot("person-1",true))
'''
        with tempfile.TemporaryDirectory(prefix="r74-kahlua-") as raw:
            work=Path(raw);shutil.copyfile(game/"stdlib.lua",work/"stdlib.lua")
            (work/"fixture.lua").write_text(fixture,encoding="utf-8")
            (work/"invoke.lua").write_text(invoke,encoding="utf-8")
            built=subprocess.run([str(jdk/"javac.exe"),"-cp",str(game/"projectzomboid.jar"),"-d",str(work),str(runner)],
                                 capture_output=True,text=True,timeout=90)
            self.assertEqual(built.returncode,0,built.stderr)
            result=subprocess.run([str(jdk/"java.exe"),"-cp",str(game/"projectzomboid.jar")+os.pathsep+str(work),"LuaRun",
                str(work/"fixture.lua"),str(labor),*map(str,modules),str(work/"invoke.lua"),"--","RESULT"],
                cwd=work,capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        raw=next(line[6:]for line in result.stdout.splitlines()if line.startswith("VALUE "))
        view=json.loads(raw);accepted=C.projection(view,"person-1",full=True,max_hours=24002)
        expected=[dict(event,capabilities=dict(cook=True,forage=False,treat=True)) for event in experiences()]
        self.assertEqual(accepted["experiences"],expected)
        self.assertTrue(all(m["version"]=="sao-"+m["id"]+"/2" for m in accepted["models"]))
        self.assertTrue(all("outcome" not in ep for ep in accepted["episodes"]))
        self.assertTrue(all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in fingerprints.items()))
        if os.environ.get("R74_NATIVE_PROOF"):
            target=Path(os.environ["R74_NATIVE_PROOF"]);target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(dict(schema="speakeasy-native-capability-contract-proof/1",inputs=fingerprints,
                contractSha256=hashlib.sha256(Path(C.__file__).read_bytes()).hexdigest(),projection=view,verdict="PASS",
                boundary="Installed Kahlua source adapters with controlled completion receipts; native action authenticity belongs to their producer tests; no training admission."),indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":unittest.main()
