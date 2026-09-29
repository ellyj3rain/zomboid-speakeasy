#!/usr/bin/env python3
"""Compact observed competing-cognition trajectories for human disposition.

The review describes exact completed outcomes and a repetition heuristic. It
creates no target, model winner, teaching row or dataset admission. Mousecat
holds the resulting operator decision before any later admission work.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import tempfile

import decision_authoring as A
import mousecat_client as Mousecat


SCHEMA = "speakeasy-cognition-review-packet/1"
QUEUE_SCHEMA = "speakeasy-cognition-review-outbox/1"
MAX_EPISODE_BYTES = 64 * 1024 * 1024
MAX_ACTORS = 32


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def atomic(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix="." + path.name, suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded(value)); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try: os.close(descriptor)
        except OSError: pass
        temporary.unlink(missing_ok=True)
        raise


def evidence(root: Path):
    root = root.resolve()
    manifest_raw = (root / "manifest.json").read_bytes()
    manifest = A.loads(manifest_raw.decode("utf-8"))
    A.require(manifest.get("schema") == "speakeasy-cognition-trajectories/1"
              and manifest.get("datasetAdmission") == "unreviewed"
              and manifest.get("trainingRows") == 0 and manifest.get("teachingTargets") == 0,
              "cognition evidence standing differs")
    episodes_path = root / "episodes.jsonl"
    A.require(0 <= episodes_path.stat().st_size <= MAX_EPISODE_BYTES,
              "cognition episode file size differs")
    raw = episodes_path.read_bytes()
    A.require(digest(raw) == manifest.get("files", {}).get("episodes.jsonl"),
              "cognition episode file changed")
    rows = [A.loads(line.decode("utf-8")) for line in raw.splitlines() if line]
    A.require(len(rows) == manifest.get("episodes") and len(rows) <= 100000,
              "cognition episode count differs")
    for row in rows:
        episode = row.get("episode", {})
        A.require(row.get("schema") == "speakeasy-cognition-episode/1"
                  and row.get("datasetAdmission") == "unreviewed"
                  and isinstance(row.get("actorId"), str)
                  and isinstance(episode.get("proposals"), list)
                  and type(episode.get("disagreement")) is bool,
                  "cognition episode row differs")
    return manifest, rows, digest(manifest_raw)


def longest_repeat(actions):
    longest = current = 0; prior = None
    for action in actions:
        current = current + 1 if action == prior else 1
        longest = max(longest, current); prior = action
    return longest


def actor_summary(actor_id, rows):
    rows = sorted(rows, key=lambda row: (row["episode"]["worldHours"], row["episode"]["id"]))
    actions = [row["episode"]["selectedActionId"] for row in rows]
    action_counts, model_counts = Counter(actions), Counter(row["episode"]["selectedModelId"] for row in rows)
    proposal_counts = Counter()
    calibration = {}
    for row in rows:
        episode = row["episode"]
        for proposal in episode["proposals"]:
            proposal_counts[(proposal["modelId"], proposal["actionId"])] += 1
        for comparison in row.get("selectedActionComparison", []):
            model = comparison["modelId"]
            item = calibration.setdefault(model, {"probability": 0.0, "squaredError": 0.0, "count": 0})
            item["probability"] += comparison["probability"]
            item["squaredError"] += comparison.get("squaredError", 0)
            item["count"] += 1
    for item in calibration.values():
        item["meanProbability"] = round(item.pop("probability") / item["count"], 4)
        item["meanSquaredError"] = round(item.pop("squaredError") / item["count"], 4)
    repeat = longest_repeat(actions)
    successes = sum(row["episode"]["outcome"]["success"] is True for row in rows)
    heuristic = repeat >= 3
    model_evidence = {}
    for model in ("ordinary", "associative"):
        model_evidence[model] = {
            "proposals": {action: count for (owner, action), count in sorted(proposal_counts.items())
                          if owner == model},
            "selected": model_counts.get(model, 0),
            "calibration": calibration.get(model, {"count": 0})}
    return {"actorId": actor_id, "episodes": len(rows),
        "firstWorldHour": rows[0]["episode"]["worldHours"],
        "lastWorldHour": rows[-1]["episode"]["outcome"]["worldHours"],
        "actions": dict(sorted(action_counts.items())), "sequence": actions,
        "selectedModels": dict(sorted(model_counts.items())),
        "proposals": {f"{model}:{action}": count
                      for (model, action), count in sorted(proposal_counts.items())},
        "modelEvidence": model_evidence,
        "successfulOutcomes": successes, "failedOutcomes": len(rows) - successes,
        "longestSameActionRun": repeat, "repetitionHeuristic": heuristic,
        "calibration": calibration,
        "eventIds": [row["episode"]["outcome"]["eventId"] for row in rows]}


def seam(summary, manifest_hash, order):
    recommended = "loop-diagnostic" if summary["repetitionHeuristic"] else "retain-analysis"
    action_text = ", ".join(f"{key} x{value}" for key, value in summary["actions"].items())
    scenario = (f"{summary['actorId']} completed {summary['episodes']} competing-model experiments from "
                f"world hour {summary['firstWorldHour']:.3f} to {summary['lastWorldHour']:.3f}: "
                f"{action_text}. {summary['successfulOutcomes']} succeeded and "
                f"{summary['failedOutcomes']} failed. The longest repeated action run was "
                f"{summary['longestSameActionRun']}.")
    options = [
        {"label": "Inspect as a behavioral loop", "value": "loop-diagnostic",
         "recommended": recommended == "loop-diagnostic",
         "description": "Keep the evidence quarantined for loop and affordance diagnosis before considering any learning use."},
        {"label": "Retain for later analysis", "value": "retain-analysis",
         "recommended": recommended == "retain-analysis",
         "description": "Preserve this exact trajectory as evidence for later candidate construction without approving a target."},
        {"label": "Collect more context", "value": "insufficient-context",
         "description": "Sequester the trajectory until a richer situation and outcome history exists."},
        {"label": "Exclude this trajectory", "value": "exclude",
         "description": "Mark this exact trajectory unsuitable for downstream learning work."},
    ]
    return {"id": "cognition-trajectory-" + summary["actorId"], "order": order,
        "shape": "decision", "title": f"{summary['actorId']} competing-cognition trajectory",
        "prompt": "How should this observed trajectory be handled before any dataset use?",
        "description": "The recommendation is a repetition heuristic, not a behavioral verdict.",
        "evidenceRef": "speakeasy:sha256:" + manifest_hash,
        "selectionMode": "single", "allowFreeform": True, "options": options,
        "mlReview": {"schema": "mousecat.ml-review/1",
            "subject": f"Observed cognition trajectory for {summary['actorId']}",
            "scenario": scenario,
            "systemRole": "The ordinary cognition model and opposing associative discovery model remain independently attributable while proposing actions from the same private decision frame. The selected action is attempted in the native world; only its later observed outcome is a target-bearing fact.",
            "causalPath": [
                {"label": "Competing proposals", "value": "Both models interpret the same bounded needs, affordances and capability frame."},
                {"label": "Native intervention", "value": "One proposal is selected and the game performs or refuses the corresponding action."},
                {"label": "Observed consequence", "value": "A later native event closes only the selected action; unexecuted alternatives remain unobserved."}],
            "playerImpact": "This evidence can reveal useful discovery, repeated appliance inspection, resource acquisition, or a stuck loop before such patterns influence later models.",
            "decisionPrecedent": "Your answer records the disposition of this exact actor trajectory. It does not ratify a rule, choose a winning cognition model or admit a training row.",
            "actualInput": [
                {"label": "Observed action sequence", "value": json.dumps(summary["sequence"])},
                {"label": "Ordinary cognition model", "value": json.dumps(summary["modelEvidence"]["ordinary"], sort_keys=True)},
                {"label": "Associative discovery model", "value": json.dumps(summary["modelEvidence"]["associative"], sort_keys=True)},
                {"label": "Observed outcomes", "value": json.dumps({
                    "successful": summary["successfulOutcomes"], "failed": summary["failedOutcomes"]}, sort_keys=True)}],
            "proposedLearning": [
                {"label": "Disposition under review", "value": "Retain, diagnose, sequester or exclude this exact trajectory before any candidate dataset work."},
                {"label": "Repetition signal", "value": f"Longest same-action run: {summary['longestSameActionRun']}; heuristic flag: {str(summary['repetitionHeuristic']).lower()}."}],
            "approvalEffects": [
                "Record a human disposition for this exact observed trajectory.",
                "Keep the evidence and its source hashes available for later diagnosis or candidate construction."],
            "remainingExclusions": [
                "No option creates a teaching target or admits data to a dataset.",
                "Unexecuted alternatives receive no counterfactual outcome.",
                "A successful native action does not establish desirable strategy or a generally correct model.",
                "The repetition heuristic is not a diagnosis and can be overridden with context."],
            "evidence": [
                {"label": "Trajectory manifest", "value": manifest_hash},
                {"label": "Native outcome events", "value": ", ".join(summary["eventIds"])}]}}


def review_invocation(root: Path, session_id: str, invocation_id: str):
    manifest, rows, manifest_hash = evidence(root)
    observed = [row for row in rows if row["episode"].get("status") == "observed"
                and type(row["episode"].get("outcome", {}).get("success")) is bool
                and row["episode"].get("disagreement") is True]
    groups = {}
    for row in observed:
        groups.setdefault(row["actorId"], []).append(row)
    A.require(len(groups) <= MAX_ACTORS, "too many actor trajectories for one review")
    summaries = [actor_summary(actor_id, groups[actor_id]) for actor_id in sorted(groups)]
    packet = None
    if summaries:
        packet = {"action": "invoke", "skillRef": "mass-assault",
            "frameworkRef": "recursive-deliberation", "projectRef": "project:zomboid-speakeasy",
            "source": {"host": "speakeasy", "sessionId": session_id,
                       "invocationId": invocation_id},
            "title": f"Review {len(observed)} observed competing-cognition outcomes",
            "intake": {"seams": [seam(summary, manifest_hash, index + 1)
                                  for index, summary in enumerate(summaries)]}}
    return {"schema": SCHEMA, "datasetAdmission": "unreviewed",
        "manifestSha256": manifest_hash, "totalEpisodes": manifest["episodes"],
        "observedDisagreements": len(observed), "sequesteredWithoutObservedOutcome": len(rows) - len(observed),
        "actorTrajectories": len(summaries), "trainingRows": 0, "teachingTargets": 0,
        "invocation": packet}


def queue(root: Path, outbox: Path, endpoint: str, session_id: str):
    outbox = outbox.resolve(); outbox.mkdir(parents=True, exist_ok=True)
    manifest_hash = digest((root / "manifest.json").read_bytes())
    queued = outbox / "queued.json"
    if queued.exists():
        value = A.read(queued)
        A.require(value.get("schema") == QUEUE_SCHEMA and value.get("status") in ("queued", "already-queued"),
                  "review queue receipt differs")
        A.require(value.get("manifestSha256") == manifest_hash
                  and value.get("trainingRows") == value.get("teachingTargets") == 0,
                  "review queue receipt belongs to different evidence")
        return value
    no_review = outbox / "no-review.json"
    if no_review.exists():
        value = A.read(no_review)
        A.require(value.get("schema") == QUEUE_SCHEMA
                  and value.get("status") == "no-reviewable-outcomes",
                  "empty review receipt differs")
        A.require(value.get("manifestSha256") == manifest_hash
                  and value.get("trainingRows") == value.get("teachingTargets") == 0,
                  "empty review receipt belongs to different evidence")
        return value
    invocation_id = "cognition-review-" + manifest_hash[:24]
    compiled = review_invocation(root, session_id, invocation_id)
    atomic(outbox / "review.json", compiled)
    if compiled["invocation"] is None:
        receipt = {"schema": QUEUE_SCHEMA, "status": "no-reviewable-outcomes",
            "trainingRows": 0, "teachingTargets": 0,
            **{key: compiled[key] for key in ("manifestSha256", "totalEpisodes",
                "observedDisagreements", "sequesteredWithoutObservedOutcome", "actorTrajectories")}}
        atomic(no_review, receipt)
        return receipt
    result = Mousecat.invoke_skill(endpoint, compiled["invocation"])
    receipt = {"schema": QUEUE_SCHEMA, "status": result["status"],
        "interactionId": result["interactionId"], "trainingRows": 0, "teachingTargets": 0,
        **{key: compiled[key] for key in ("manifestSha256", "totalEpisodes",
            "observedDisagreements", "sequesteredWithoutObservedOutcome", "actorTrajectories")}}
    atomic(queued, receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--outbox", required=True, type=Path)
    parser.add_argument("--endpoint", default="http://127.0.0.1:4317/mcp")
    parser.add_argument("--session-id", required=True)
    args = parser.parse_args()
    print(json.dumps(queue(args.evidence.resolve(), args.outbox.resolve(), args.endpoint,
                           args.session_id), indent=2))


if __name__ == "__main__":
    main()
