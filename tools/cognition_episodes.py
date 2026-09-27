#!/usr/bin/env python3
"""Preserve competing-model trajectories from a verified native study.

The result is unreviewed evidence for downstream aggregation. Only the selected
action can have an observed target. Model preference and prediction disagreement
are measurements, never teacher labels or automatic dataset admission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
import subprocess
import sys

import cognition_contract as C
import decision_authoring as A


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


FROZEN = ("id", "worldHours", "frame", "proposals", "selectedModelId",
          "selectedActionId", "selectionWeight", "selectionPolicy", "disagreement")


class Trajectories:
    def __init__(self, snapshot_sink=None):
        self.episodes = {}
        self.snapshots = []
        self.snapshot_sink = snapshot_sink
        self.snapshot_count = 0
        self.snapshot_bytes = 0
        self.episode_bytes = 0
        self.last_hours = -1

    def add(self, native, source_hash):
        C.require(native.get("schema") == "sao-study-observation/1"
                  and native.get("datasetAdmission") == "unreviewed", "native frame standing differs")
        hours = C.number(native.get("countyHours", native["hours"]), self.last_hours)
        self.last_hours = hours
        for person in native["people"]:
            raw = person.get("context", {}).get("cognition")
            if raw is None:
                continue
            view = C.projection(raw, person["id"], full=True, max_hours=hours)
            snapshot = {"nativeFrameSha256": source_hash, "nativeHours": hours, "projection": view}
            self.snapshot_count += 1
            self.snapshot_bytes += len(encoded(snapshot))
            C.require(self.snapshot_count <= 100000, "trajectory snapshot limit")
            C.require(self.snapshot_bytes <= (1024 if self.snapshot_sink else 64) * 1024 * 1024,
                      "trajectory snapshot byte limit")
            if self.snapshot_sink: self.snapshot_sink(snapshot)
            else: self.snapshots.append(snapshot)
            for ep in view["episodes"]:
                C.require(ep["worldHours"] <= hours and ep.get("outcome", {}).get("worldHours", 0) <= hours,
                          "future outcome or decision in native frame")
                key = (native["save"], person["id"], ep["id"])
                prior = self.episodes.get(key)
                if prior:
                    C.require(all(prior["episode"][field] == ep[field] for field in FROZEN),
                              "pre-outcome record was rewritten")
                    if prior["episode"]["status"] in ("observed", "censored"):
                        C.require(prior["episode"] == ep, "terminal episode was rewritten")
                    if prior["episode"]["status"] == "attempted":
                        C.require(ep["status"] != "proposed", "execution moved backward")
                row = {"schema": "speakeasy-cognition-episode/1", "datasetAdmission": "unreviewed",
                    "save": native["save"], "actorId": person["id"], "episode": ep,
                    "firstFrameSha256": prior["firstFrameSha256"] if prior else source_hash,
                    "lastFrameSha256": source_hash,
                    "firstObservedStatus": prior["firstObservedStatus"] if prior else ep["status"]}
                self.episode_bytes += len(encoded(row)) - (len(encoded(prior)) if prior else 0)
                C.require(self.episode_bytes <= 64 * 1024 * 1024, "episode memory byte limit")
                self.episodes[key] = row
                C.require(len(self.episodes) <= 100000, "episode limit")

    def rows(self):
        rows = []
        for key in sorted(self.episodes):
            row = dict(self.episodes[key])
            ep = row["episode"]
            out = ep.get("outcome", {})
            observed = ep["status"] == "observed" and type(out.get("success")) is bool
            selected = ep["selectedActionId"]
            # Each contestant is assessed on the same performed intervention.
            comparison = []
            for proposal in ep["proposals"]:
                prediction = proposal["predictions"][selected]
                item = {"modelId": proposal["modelId"], "actionId": selected, **prediction,
                        "targetStatus": "observed" if observed else "unobserved"}
                if observed:
                    item.update(target=out["success"], squaredError=(prediction["probability"] - int(out["success"]))**2)
                comparison.append(item)
            row["selectedActionComparison"] = comparison
            row["unobservedAlternatives"] = sorted({p["actionId"] for p in ep["proposals"]} - {selected})
            rows.append(row)
        return rows


def export(run, package, validator, destination):
    run, package, validator, destination = (Path(p).resolve() for p in (run, package, validator, destination))
    C.require(validator.is_file() and validator.name == "world_lab_run.py", "explicit native validator required")
    C.require(not destination.exists() and not destination.is_relative_to(run)
              and not destination.is_relative_to(package), "output exists or overlaps native inputs")
    checked = subprocess.run([sys.executable, str(validator), str(package), "--out", str(run), "--verify"],
                             capture_output=True, text=True, encoding="utf-8", timeout=180)
    C.require(checked.returncode == 0, "native validator refused: " + checked.stderr[-1600:])
    receipt = A.loads(checked.stdout)
    C.require(receipt.get("status") == "completed" and receipt.get("datasetAdmission") == "unreviewed",
              "native run is not completed unreviewed evidence")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="." + destination.name + ".", dir=destination.parent)).resolve()
    C.require(staging.parent == destination.parent and staging != destination, "invalid staging destination")
    try:
        sources, source_coverage, snapshot_hash = {}, [], hashlib.sha256()
        with (staging / "snapshots.jsonl").open("wb") as stream:
            def snapshot_sink(row):
                raw = encoded(row)
                stream.write(raw); snapshot_hash.update(raw)
            trajectories = Trajectories(snapshot_sink)
            observations = receipt.get("observations", {})
            C.require(0 < len(observations) <= 10000, "native frame limit")
            for relative, expected in sorted(observations.items()):
                path = (run / "cache" / relative).resolve()
                C.require(path.is_relative_to(run / "cache/Lua/StudyWorld"), "observation leaves native output")
                C.require(path.stat().st_size <= 64 * 1024 * 1024, "native observation byte limit")
                raw = path.read_bytes()
                C.require(digest(raw) == expected, "native observation changed")
                native = A.loads(raw.decode("utf-8"))
                trajectories.add(native, expected)
                coverage = native["coverage"]
                source_coverage.append({"nativeFrameSha256": expected,
                    "countyHours": native.get("countyHours", native["hours"]),
                    "peopleComplete": coverage["peopleComplete"],
                    "processesComplete": coverage["processesComplete"],
                    "omittedFieldCount": coverage["omittedFieldCount"],
                    "populationTotal": native["population"]["total"],
                    "populationCaptured": native["population"]["captured"]})
                sources[relative] = expected
        C.require(A.loads((run / "run.json").read_text(encoding="utf-8")) == receipt, "run changed during intake")
        rows = trajectories.rows()
        episode_hash = hashlib.sha256()
        with (staging / "episodes.jsonl").open("wb") as stream:
            for row in rows:
                raw = encoded(row); stream.write(raw); episode_hash.update(raw)
        manifest = {"schema": "speakeasy-cognition-trajectories/1", "datasetAdmission": "unreviewed",
                    "packageSha256": receipt["packageSha256"], "validatorSha256": digest(validator.read_bytes()),
                    "extractorSha256": digest(Path(__file__).read_bytes()),
                    "contractSha256": digest(Path(C.__file__).read_bytes()), "nativeSources": sources,
                    "sourceCoverage": source_coverage,
                    "episodes": len(rows), "snapshots": trajectories.snapshot_count,
                    "snapshotBytes": trajectories.snapshot_bytes,
                    "observedTargets": sum(r["episode"]["status"] == "observed" and
                                           type(r["episode"].get("outcome", {}).get("success")) is bool for r in rows),
                    "files": {"episodes.jsonl": episode_hash.hexdigest(), "snapshots.jsonl": snapshot_hash.hexdigest()},
                    "trainingRows": 0, "teachingTargets": 0,
                    "limits": ["Selection and causal outcomes are observational evidence, not desired behavior labels.",
                               "Alternatives were not executed in the same world and have no counterfactual target.",
                               "Retained source omissions and first-observed status remain explicit.",
                               "Deterministic allocation weights are not random policy propensities."]}
        (staging / "manifest.json").write_bytes(encoded(manifest))
        C.require(not destination.exists(), "output appeared during intake")
        os.rename(staging, destination)
        return manifest
    except BaseException:
        if staging.exists():
            C.require(staging.resolve().parent == destination.parent, "staging escaped parent")
            shutil.rmtree(staging)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run", "package", "sao-validator", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(export(args.run, args.package, args.sao_validator, args.out), indent=2))


if __name__ == "__main__":
    main()
