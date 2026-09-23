"""Deterministic task-data preparation over exact independently approved evidence.

Preview rows are inspectable while admission is incomplete. Dataset release also
requires independent partitions for every requested task; it trains no model.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path

import conversation_tasks as C
import cross_module_rows as J
import decision_authoring as A
import experimental_admission as X
import training_evidence as E

PARTITIONS = ("train", "validation", "test")


def example(row, admission):
    task = admission["task"]
    if task == "speaker":
        inputs = row["input"]["modelInput"]
        # The construction witness remains audit evidence, never a target
        # telling the learned speaker to choose among a fixed sentence menu.
        target = {"text": row["output"]["text"]}
        objective = "source-bound-text"
    else:
        inputs = {key: row["input"][key] for key in ("catalogue", "context")}
        if task == "understander":
            inputs["utteranceRoles"] = row["input"]["utteranceRoles"]
            target = row["output"]
            objective = "typed-semantic-frame"
        else:
            A.require(task == "retriever", "unsupported preparation task")
            required = set(row["labels"]["requiredClaimRefs"])
            negatives = {entry["claimRef"] for entry in row["labels"]["hardNegatives"]}
            target = {"claims": [{"claimRef": claim["ref"],
                "label": 1 if claim["ref"] in required else 0 if claim["ref"] in negatives else None,
                "lossMask": claim["ref"] in required or claim["ref"] in negatives}
                for claim in row["input"]["catalogue"]["claims"]]}
            objective = "reviewed-claim-selection"
    return {
        "rowSha256": row["contentSha256"], "task": task,
        "input": copy.deepcopy(inputs), "target": copy.deepcopy(target),
        "objective": objective, "sourceGroups": list(admission["sourceGroups"]),
        "unavailableNativeInputs": list(admission["unavailableNativeInputs"])}


def prepare(request, evidence=None):
    evidence = evidence or E.Store()
    A.fields(request, {"schema", "schemaVersion", "scope", "requests", "splits"}, "data request")
    A.schema(request, "speakeasy-task-data-request")
    A.require(isinstance(request["requests"], list) and request["requests"], "requests required")
    for entry in request["requests"]:
        A.require(isinstance(entry, dict) and set(entry) in (
            {"rowSha256"}, {"rowSha256", "approvalReceiptSha256"}), "invalid task request")
        for value in entry.values():
            A.hash_value(value, "task request hash")
    A.fields(request["splits"], set(PARTITIONS), "data splits")
    for values in request["splits"].values():
        A.require(isinstance(values, list), "split must be a list")
        for value in values:
            A.hash_value(value, "split row hash")
    # Order of supplied requests/partitions cannot change the prepared bytes.
    requests = sorted(copy.deepcopy(request["requests"]), key=lambda item: item["rowSha256"])
    splits = {name: sorted(request["splits"][name]) for name in PARTITIONS}
    admission = X.compile_dataset(requests, splits, scope=request["scope"], evidence=evidence)
    tasks = sorted({row["task"] for row in admission["rows"]})
    datasets = {task: {name: [] for name in PARTITIONS} for task in tasks}
    by_hash = {row["rowSha256"]: row for row in admission["rows"]}
    for partition, hashes in splits.items():
        for digest in hashes:
            status = by_hash[digest]
            if status["status"] == "admitted-to-offline-evaluation":
                datasets[status["task"]][partition].append(example(evidence.read(digest), status))
    missing = [{"task": task, "partition": partition} for task in tasks
               for partition in PARTITIONS if not datasets[task][partition]]
    reasons = list(admission["dataset"]["exclusions"])
    if missing:
        reasons.append("per-task-evaluation-partitions-missing")
    normalized = {**request, "requests": requests, "splits": splits}
    return A.seal({
        "schema": "speakeasy-task-data-preview", "schemaVersion": 1,
        "request": normalized, "admission": admission, "datasets": datasets,
        "release": {"status": "excluded" if reasons else "ready-for-tokenization",
                    "exclusions": reasons, "missingPartitions": missing},
        "limits": ["authored-offline-evaluation-scope", "no-tokenizer-or-trained-model",
                   "no-runtime-admission", "speaker-witness-is-not-a-learned-decoder",
                   "unjudged-retrieval-labels-must-remain-masked"]})


def validate(preview, evidence=None):
    A.unseal(preview, "speakeasy-task-data-preview")
    expected = prepare(preview["request"], evidence)
    A.require(A.digest(preview) == A.digest(expected), "prepared data differs from source evidence")
    return preview


def release(preview, evidence=None):
    """Consumers must revalidate standing and full content before dataset use."""
    validate(preview, evidence)
    A.require(preview["release"]["status"] == "ready-for-tokenization",
              "dataset release refused: " + "; ".join(preview["release"]["exclusions"]))
    return copy.deepcopy(preview["datasets"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    try:
        preview = prepare(A.read(args.request))
        if args.require_ready:
            release(preview)
        data = A.encoded(preview) + b"\n"
        if args.check:
            A.require(args.output.read_bytes() == data, "saved task data differs")
        else:
            A.require(not args.output.exists() or args.output.read_bytes() == data,
                      "different data already exists; choose a new output path")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(data)
        print(preview["contentSha256"], preview["release"]["status"])
        for task, partitions in preview["datasets"].items():
            print(task, {key: len(value) for key, value in partitions.items()})
    except (J.ContractError, OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, "REFUSED: " + str(error) + "\n")


if __name__ == "__main__":
    main()
