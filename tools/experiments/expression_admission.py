"""Reproduce the offline expression and admission proof; no model is trained."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import itertools
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import decision_authoring as A
import cross_module_rows as J
import conversation_tasks as C
import experimental_admission as X
import expression_proof as P
import training_evidence as E

OUT = C.ROOT / "training/experiments/expression-proof"


def refused(action):
    try:
        action()
    except (J.ContractError, KeyError, TypeError, ValueError):
        return True
    return False


def defect_controls(source, good):
    original = Path(P.__file__).read_text(encoding="utf-8")
    controls = []
    for name, before, after in [
        ("text-binding", 'value["text"] == render(model, value["plan"])',
         'True or value["text"] == render(model, value["plan"])'),
        ("proposition-binding", 'plan["propositions"] == expected',
         'True or plan["propositions"] == expected')
    ]:
        A.require(original.count(before) == 1, "defect control did not target one production expression")
        mutated = original.replace(before, after)
        A.require(mutated != original, "defect control did not land")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "expression_control.py"
            path.write_text(mutated, encoding="utf-8")
            spec = importlib.util.spec_from_file_location("expression_control", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            bad = copy.deepcopy(good)
            if name == "text-binding":
                bad["text"] += " The phones work today."
            else:
                bad["plan"]["propositions"][0]["ownerRef"] = "foreign-person"
            production_rejects = refused(lambda: P.validate_output(bad, source))
            mutated_rejects = refused(lambda: module.validate_output(bad, source))
            A.require(production_rejects and not mutated_rejects,
                      "known-bad production mutation was not discriminated: " + name)
            controls.append({"control": name, "mutationLanded": True,
                             "productionRefused": production_rejects,
                             "mutatedRefused": mutated_rejects, "detected": True})
    return controls


def run():
    evidence = E.Store()
    index = A.read(C.ROOT / "training/speaker/c77-example.json")
    task_index = A.read(C.ROOT / "training/understander/c77-example.json")
    source = P.from_target(index["retrieverTargetSha256"], evidence)
    model = P.compile_source(source)
    report_ref = next(iter(model["reports"]))
    outputs = []
    for name, variants, vocative in [
        ("plain", {k: 0 for k in P.KINDS}, False),
        ("mixed", {k: i % 2 for i, k in enumerate(P.KINDS)}, True),
        ("approved-personified", {k: 1 for k in P.KINDS}, True)]:
        plan = P.report_plan(model, report_ref, variants, vocative=vocative)
        output = P.produce(source, plan)
        P.validate_output(output, source)
        outputs.append({"name": name, "output": output})
    good = outputs[-1]["output"]
    proposal = evidence.read(index["wordingProposalSha256"])
    A.require(good["text"] == proposal["output"]["text"], "approved wording not reproduced")
    variants = set()
    for choice in itertools.product((0, 1), repeat=len(P.KINDS)):
        value = P.produce(source, P.report_plan(model, report_ref, dict(zip(P.KINDS, choice))))
        P.validate_output(value, source)
        variants.add(value["text"])
    controls = []
    for name, replacement in [
        ("negation", good["text"].replace("were out", "were not out")),
        ("present-time-invention", good["text"].replace("when it went to press", "today")),
        ("unsupported-certainty", good["text"].replace("there was talk of", "the cause was")),
        ("added-factual-prose", good["text"] + " I checked it myself.")]:
        bad = copy.deepcopy(good)
        bad["text"] = replacement
        A.require(bad["text"] != good["text"], "negative control unchanged")
        observed = refused(lambda: P.validate_output(bad, source))
        A.require(observed, "false meaning accepted: " + name)
        controls.append({"case": name, "text": replacement, "refused": observed})
    for field, replacement in [("ownerRef", "sao-2"), ("at", "1993-07-11"),
                               ("knowledgeKind", "observed"), ("certainty", "confirmed"),
                               ("source", {"label": "invented-source"})]:
        bad = copy.deepcopy(good)
        bad["plan"]["propositions"][0][field] = replacement
        observed = refused(lambda: P.validate_output(bad, source))
        A.require(observed, "changed proposition accepted: " + field)
        controls.append({"case": "changed-" + field, "refused": observed})
    fixture = A.read(OUT / "fixtures.json")
    scenes = []
    for raw in fixture["scenes"]:
        scene = {k: copy.deepcopy(v) for k, v in raw.items() if k not in {"id", "expected"}}
        compiled = P.compile_source(scene)
        if scene["locations"]:
            plans = [{"kind": "location", "proposition": p, "variant": 0}
                     for p in compiled["propositions"].values()]
        else:
            plans = [P.report_plan(compiled, next(iter(compiled["reports"])))]
        actual = [P.produce(scene, plan)["text"] for plan in plans]
        A.require(actual == raw["expected"], "independent fixture differs: " + raw["id"])
        scenes.append({"id": raw["id"], "standing": fixture["standing"],
                       "sourceSha256": A.digest(scene), "actual": actual})
    requests = [
        {"rowSha256": task_index["taskSha256"],
         "approvalReceiptSha256": task_index["approvalReceiptSha256"]},
        {"rowSha256": index["retrieverTargetSha256"]},
        {"rowSha256": index["taskSha256"],
         "approvalReceiptSha256": index["wordingReviewReceiptSha256"]},
        {"rowSha256": index["wordingProposalSha256"],
         "approvalReceiptSha256": index["wordingReviewReceiptSha256"]}]
    dataset = X.compile_dataset(requests, {"train": [r["rowSha256"] for r in requests],
                                          "validation": [], "test": []}, scope=X.SCOPE)
    approval = A.read(C.ROOT / "training/direction/admission-work-plan-result.json")
    work_plan = A.read(C.ROOT / "training/direction/admission-work-plan.json")
    expected_ref = "field-test:plan-sha256:" + A.digest(work_plan)
    A.require(approval["status"] == "answered" and len(approval["responses"]) == 1,
              "plan ruling incomplete")
    ruling = approval["responses"][0]
    A.require(ruling["selectedOption"] == ruling["value"] == "approved"
              and ruling["notes"] is None
              and ruling["lineage"]["evidenceRef"] == expected_ref,
              "plan ruling subject or qualifications differ")
    return A.seal({
        "schema": "speakeasy-expression-admission-proof", "schemaVersion": 1,
        "planSha256": A.digest(work_plan), "planRulingSha256": A.digest(approval),
        "source": source, "expressionInput": model, "outputs": outputs,
        "supportedCombinationCount": len(variants), "negativeCases": controls,
        "defectControls": defect_controls(source, good), "independentScenes": scenes,
        "admission": dataset,
        "voiceEvaluation": {"status": "not-evaluated",
            "exactApprovedWordingReproduced": True,
            "newVariantsStanding": "unreviewed",
            "conditioningChangesTestedForFactualEntitlementOnly": True},
        "limits": [
            "The source parser recognizes one bounded report grammar and explicitly authored location facts.",
            "The composer assembles a finite lexical grammar. It is not a free-text semantic verifier or a learned decoder.",
            "The exact personified wording is supported; broader natural expression is untested.",
            "Personality-to-expression learning and runtime register floors are not implemented.",
            "Independent synthetic fixtures are unreviewed and do not create approved training scenes.",
            "Dataset evaluation and live runtime readiness remain incomplete."],
        "implementation": {name: hashlib.sha256((C.ROOT / name).read_bytes()).hexdigest()
            for name in ["tools/expression_proof.py", "tools/experimental_admission.py",
                         "tools/experiments/expression_admission.py",
                         "training/experiments/expression-proof/fixtures.json"]}})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = run()
    path = OUT / "result.json"
    if args.check:
        A.require(A.read(path) == result, "saved proof result differs")
    if args.write:
        path.write_bytes(A.encoded(result) + b"\n")
    print("Exact approved wording reproduced; supported combinations:", result["supportedCombinationCount"])
    print("Meaning controls refused:", len(result["negativeCases"]))
    print("Production defect controls detected:", len(result["defectControls"]))
    for row in result["admission"]["rows"]:
        print(row["task"], row["status"], "; ".join(row["exclusions"]))
    print("Dataset:", result["admission"]["dataset"]["status"])
    print("Result:", result["contentSha256"])


if __name__ == "__main__":
    main()
