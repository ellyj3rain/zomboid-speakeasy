"""Field Test of the actual SAO scalar fence and Speakeasy summary renderer.

Run against an explicit SAO checkout and JDK. Outputs characterize coverage,
not training admission. Java compiles the external production source in a
temporary directory; no SAO implementation is copied into this repository.
"""
import argparse
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import conversation_tasks as C
import decision_authoring as A
import speaker_tasks as S
import training_evidence as E
import cross_module_rows as J


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv):
    value = subprocess.run([str(x) for x in argv], capture_output=True, text=True,
                           encoding="utf-8", errors="strict", timeout=90)
    if value.returncode:
        raise RuntimeError(f"command failed ({value.returncode}): {value.stderr}")
    return value.stdout


def observe(java, classpath, fixtures, mode="actual"):
    out = run([java, "-cp", classpath, "SpeechConstraintProbe", fixtures, mode])
    result = {}
    for line in out.splitlines():
        name, value = line.split("\t")
        if name in result or value not in ("true", "false"):
            raise ValueError("invalid or repeated probe output")
        result[name] = value == "true"
    return result


def characterizes(cases, results):
    return set(results) == {c["id"] for c in cases} and all(
        results[c["id"]] == c["expectedCurrentResult"] for c in cases)


def reseal(row):
    row.pop("contentSha256", None)
    return A.seal(row)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sao-root", type=Path, required=True)
    parser.add_argument("--jdk-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sao = args.sao_root.resolve()
    source = sao / "java/src/com/sao/engine/SAOFence.java"
    projection = sao / "mod/42.20/media/lua/shared/SAO_Knowledge.lua"
    jar = sao / "java/dist/SAOAgent.jar"
    java = args.jdk_dir / ("java.exe" if os.name == "nt" else "java")
    javac = args.jdk_dir / ("javac.exe" if os.name == "nt" else "javac")
    harness = Path(__file__).with_name("SpeechConstraintProbe.java")
    for path in (source, projection, jar, java, javac, harness):
        if not path.is_file():
            raise FileNotFoundError(path)
    source_relative = source.relative_to(sao).as_posix()
    if run(["git", "-C", sao, "status", "--porcelain", "--", source_relative]).strip():
        raise ValueError("production fence source differs from its recorded commit")
    index = A.read(TOOLS.parent / "training/speaker/c77-example.json")
    store = E.Store()
    row = store.read(index["taskSha256"])
    S.validate_task(row, store)
    wording = store.read(index["wordingProposalSha256"])
    fact = row["input"]["modelInput"]["selectedClaims"][0]["fact"]
    # Hand-projected wire fixture using the documented string/number field rule.
    # This experiment does not execute or validate the Lua projector.
    wire = "\n".join(sorted(f"{k}={v}" for k, v in fact.items()
                              if type(v) in (str, int, float)))
    report_id = fact["claimId"]
    cases = []

    def case(name, kind, claims, filling, expected, meaning):
        cases.append({"id": name, "kind": kind, "claims": claims, "filling": filling,
                      "expectedCurrentResult": expected, "interpretation": meaning})

    prefix = f"claimId={report_id}\nreportHour=-168\nknowledgeKind=reported"
    case("exact-owned-fields", "membership-control", wire, prefix, True,
         "Owned report identifier, publication hour and reported status are accepted.")
    case("unknown-claim-id", "membership-control", wire, prefix.replace(report_id, "invented-report"), False,
         "An absent report identifier is refused.")
    case("publication-changed-to-question-hour", "membership-control", wire, prefix.replace("-168", "48"), False,
         "An absent value in the explicit reportHour slot is refused.")
    case("reported-changed-to-observed", "membership-control", wire, prefix.replace("reported", "observed"), False,
         "A changed explicit knowledgeKind value is refused.")
    case("unknown-field", "membership-control", wire, "currentService=restored", False,
         "An unknown explicit field is refused.")
    case("empty-claims-known-filling", "membership-control", "", prefix, False,
         "A filled field with no owned values is refused.")

    # Synthetic two-person observations, not C77 claims or project approvals.
    pair_a = "name=Jon\nwhereWord=east\nname=Eve\nwhereWord=west"
    pair_b = "name=Jon\nwhereWord=west\nname=Eve\nwhereWord=east"
    case("original-person-location", "association-probe", pair_a, "name=Jon\nwhereWord=east", True,
         "Both values belong to Jon's synthetic observation.")
    case("cross-person-location", "association-probe", pair_a, "name=Jon\nwhereWord=west", True,
         "Accepted even though west belongs to Eve in the synthetic records; tuple identity is absent from the wire contract.")
    case("changed-association-same-filling", "association-probe", pair_b, "name=Jon\nwhereWord=west", True,
         "The same filling is correct after swapping the synthetic person/location associations. Membership cannot distinguish the two sources.")

    good = wording["output"]["text"]
    bad = {
        "negation": "The July second paper said the phones were not out across Knox.",
        "current-time": "The phones are still down today.",
        "direct-experience": "I checked the phone lines myself.",
        "confirmed-cause": "Sabotage caused the outage.",
        "unsupported-recovery": "Service returned after a few hours.",
        "unsupported-household-access": "Everyone in Knox had Internet access."
    }
    case("raw-approved-personified-text", "out-of-contract-text-probe", wire, good, True,
         "Raw prose contains no field assignment and is skipped by the wire parser; this is not semantic acceptance.")
    for name, text in bad.items():
        case("raw-" + name, "out-of-contract-text-probe", wire, text, True,
             "Raw prose is outside the declared field/value input contract and receives no semantic evaluation.")
    case("owned-fields-with-appended-false-prose", "mixed-format-probe", wire,
         prefix + "\n" + bad["current-time"], True,
         "Owned assignments are checked and the appended non-assignment is skipped. An outer parser/decoder would need to enforce its own output contract.")
    case("unknown-field-with-known-id", "membership-control", wire,
         prefix + "\ncurrentService=restored", False,
         "A false extra claim represented as an unknown field is refused.")

    before_source = sha(source)
    before_jar = sha(jar)
    with tempfile.TemporaryDirectory(prefix="speakeasy-field-test-") as temp:
        temp = Path(temp)
        fixtures = temp / "cases.tsv"
        encoded = lambda text: base64.b64encode(text.encode("utf-8")).decode("ascii")
        fixtures.write_text("".join(f'{c["id"]}\t{encoded(c["claims"])}\t{encoded(c["filling"])}\n'
                                    for c in cases), encoding="utf-8", newline="\n")
        compiled = temp / "source-classes"
        compiled.mkdir()
        run([javac, "-encoding", "UTF-8", "-d", compiled, source, harness])
        current = observe(java, str(compiled), fixtures)
        if not characterizes(cases, current):
            raise AssertionError("production source differs from experiment predictions")
        controls = {}
        for mode in ("all-accept", "all-refuse"):
            corrupted = observe(java, str(compiled), fixtures, mode)
            if corrupted == current or characterizes(cases, corrupted):
                raise AssertionError("instrument failed to detect its corrupted observation")
            controls[mode] = {"detected": True, "changedObservations": sum(
                corrupted[k] != current[k] for k in current)}
        packaged = observe(java, os.pathsep.join((str(jar), str(compiled))), fixtures)
        if not characterizes(cases, packaged) or packaged != current:
            raise AssertionError("packaged fence differs from compiled production source")
    if before_source != sha(source) or before_jar != sha(jar):
        raise AssertionError("production files changed during experiment")

    speaker_results = []
    samples = [("exact-source-summary", row["output"]["text"], True),
               ("approved-personified-wording", good, False)]
    samples += [(name, text, False) for name, text in bad.items()]
    for name, text, expected in samples:
        candidate = copy.deepcopy(row)
        candidate["output"]["text"] = text
        candidate = reseal(candidate)
        try:
            S.validate_task(candidate, store)
            accepted, reason = True, None
        except J.ContractError as error:
            accepted, reason = False, str(error)
        if accepted != expected:
            raise AssertionError("speaker renderer observation differs: " + name)
        speaker_results.append({"id": name, "text": text, "accepted": accepted,
                                "reason": reason, "resealedBeforeValidation": True})

    for item in cases:
        item["sourceAccepted"] = current[item["id"]]
        item["packagedAccepted"] = packaged[item["id"]]
    result = A.seal({
        "schema": "speakeasy-speech-constraint-field-test", "schemaVersion": 1,
        "experimentId": "speech-constraint-coverage-001",
        "source": {"saoCommit": run(["git", "-C", sao, "rev-parse", "HEAD"]).strip(),
                   "javaFencePath": source_relative, "javaFenceSha256": before_source,
                   "packagedJarSha256": before_jar, "projectionSourceSha256": sha(projection),
                   "luaProjectionExecuted": False,
                   "speakerToolSha256": sha(TOOLS / "speaker_tasks.py"),
                   "experimentToolSha256": sha(Path(__file__)),
                   "javaProbeSha256": sha(harness), "javac": run([javac, "-version"]).strip()},
        "subjects": {"sourceTaskSha256": row["contentSha256"],
                     "wordingProposalSha256": wording["contentSha256"]},
        "cases": cases, "speakerCases": speaker_results,
        "instrumentControls": controls,
        "verdict": {
            "fieldMembershipControlsHold": True,
            "syntheticAssociationLossObserved": True,
            "rawProseReceivesSemanticEvaluation": False,
            "exactSummaryRendererAcceptsApprovedPersonifiedText": False,
            "generalSemanticGuaranteeEstablished": False,
            "trainedModelExercised": False, "gameplayExercised": False},
        "limits": [
            "The Java inputs are explicit wire fixtures; the Lua selected-claim producer was read but not executed.",
            "Person/location cases are synthetic; they are not additions to Mara's knowledge.",
            "Raw prose probes are outside SAOFence's declared wire contract and do not establish an exploitable live speaker path.",
            "The source and packaged jar run off-game; no saves, installed files or live game processes are changed.",
            "The speaker cases reseal the changed text, so rejection is from the renderer contract, not a stale content hash.",
            "Approval of the authored wording does not make it a version 3 task or an eligible training example."
        ]})
    data = A.encoded(result) + b"\n"
    if args.output.exists() and args.output.read_bytes() != data:
        raise FileExistsError("different evidence already exists; choose a new result path")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(json.dumps({"result": str(args.output), "contentSha256": result["contentSha256"],
                      "javaCases": len(cases), "speakerCases": len(speaker_results),
                      "instrumentControls": controls, "verdict": result["verdict"]}, indent=2))


if __name__ == "__main__":
    main()
