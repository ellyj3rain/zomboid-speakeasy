#!/usr/bin/env python3
"""Train and evaluate the bounded coordination-response reference adapter.

The implementation is dependency-free and deterministic.  It uses the shared
frozen byte-BPE tokenizer, a learned mean byte-token embedding base and a typed
coordination softmax head over decision-time numeric channels.  Output logits
are restricted to both current feasible options and labels observed in the
approved training family; decline and withdrawal therefore remain unsupported
rather than acquiring random behavior from absent targets.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
import math
import os
from pathlib import Path
import random
import shutil
import sys
import tempfile
from typing import Any

import byte_tokenizer as Byte
import coordination_data as Data
import cross_module_rows as Join
import decision_authoring as Author


VERSION = 1
ROOT = Join.ROOT
TOKENIZER_PATH = ROOT / "training/datasets/c77-tokenization/tokenizer.json"
FEATURES = (
    "relationship", "absoluteRelationship", "competingPressure",
    "pressureAvailable", "activityIdle", "constraintContest",
    "constraintRepresented", "executionOwnerAvailable", "ownNeedAvailable",
    "destinationKnown", "executorIsZAODriver", "bodyOwnerIsZAO",
    "capabilityAcquire", "capabilityCarry", "capabilityDeliver",
    "capabilityExecute",
)
DEFAULT_CONFIG = {
    "seed": 66081,
    "embeddingDimension": 8,
    "epochs": 1200,
    "learningRate": 0.18,
    "learningRateDecay": 0.0008,
    "l2": 0.0002,
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Join.ContractError(message)


def rounded(value: float) -> float:
    return round(float(value), 12)


def load_tokenizer(path: Path = TOKENIZER_PATH) -> tuple[dict[str, Any], Byte.Tokenizer]:
    artifact = Author.read(path)
    tokenizer = Byte.Tokenizer(artifact)
    return artifact, tokenizer


def input_tokens(value: dict[str, Any], tokenizer: Byte.Tokenizer) -> list[int]:
    payload = Author.encoded(value)
    return [Byte.SPECIAL_IDS["bos"], Byte.SPECIAL_IDS["schema"],
            Byte.SPECIAL_IDS["input"], *tokenizer.encode_bytes(payload),
            Byte.SPECIAL_IDS["eos"]]


def typed_features(value: dict[str, Any]) -> list[float]:
    actor = value["actor"]
    decision = value["decisionTime"]
    priorities = decision["competingPriorities"]
    pressure = priorities["competingPressure"]
    constraints = priorities["constraints"]
    capabilities = decision["capabilities"]["values"]
    relationship = float(priorities["relationship"])
    pressure_value = pressure["value"] if pressure["available"] else 0.0
    destination_known = "destination" in decision["proposal"]
    result = [
        relationship,
        abs(relationship),
        float(pressure_value or 0.0),
        float(pressure["available"]),
        float(decision["currentWork"]["activity"] == "idle"),
        float(bool(constraints.get("contest", False))),
        float(bool(constraints["represented"])),
        float(bool(constraints["executionOwnerAvailable"])),
        float(bool(constraints["ownNeedAvailable"])),
        float(destination_known),
        float(actor["executor"] == "ZAO.Driver"),
        float(actor["bodyOwner"] == "ZAO"),
        *[float(bool(capabilities[name]))
          for name in ("acquire", "carry", "deliver", "execute")],
    ]
    require(len(result) == len(FEATURES)
            and all(math.isfinite(item) for item in result),
            "coordination typed features are invalid")
    return result


def examples(dataset: dict[str, Any], tokenizer: Byte.Tokenizer,
             target_override: dict[str, str] | None = None) -> list[dict[str, Any]]:
    Data.validate_dataset(dataset)
    output = []
    for row in dataset["rows"]:
        target = (target_override or {}).get(row["rowId"],
                                             row["target"]["response"])
        feasible = [label for label in row["input"]["decisionTime"]["feasibleOptions"]
                    if label in dataset["observedLabels"]]
        require(target in feasible, "coordination target is outside the learned mask")
        tokens = input_tokens(row["input"], tokenizer)
        output.append({"row": row, "tokens": tokens,
                       "tokenCounts": Counter(tokens),
                       "features": typed_features(row["input"]),
                       "target": target, "allowed": feasible})
    return output


def initialize(tokenizer: Byte.Tokenizer, labels: list[str], config: dict[str, Any]):
    rng = random.Random(config["seed"])
    dimension = config["embeddingDimension"]
    vocabulary_size = max(max(tokenizer.vocabulary), max(Byte.SPECIAL_IDS.values())) + 1
    embeddings = [[rng.uniform(-0.025, 0.025) for _ in range(dimension)]
                  for _ in range(vocabulary_size)]
    width = dimension + len(FEATURES)
    weights = [[rng.uniform(-0.025, 0.025) for _ in range(width)] for _ in labels]
    biases = [0.0 for _ in labels]
    return embeddings, weights, biases


def pooled(tokens: list[int], embeddings: list[list[float]]) -> list[float]:
    dimension = len(embeddings[0])
    result = [0.0] * dimension
    for token in tokens:
        for index in range(dimension):
            result[index] += embeddings[token][index]
    inverse = 1.0 / len(tokens)
    return [value * inverse for value in result]


def probabilities(logits: dict[str, float]) -> dict[str, float]:
    maximum = max(logits.values())
    shifted = {key: math.exp(value - maximum) for key, value in logits.items()}
    total = sum(shifted.values())
    return {key: value / total for key, value in shifted.items()}


def infer_components(example: dict[str, Any], labels: list[str],
                     embeddings: list[list[float]], weights: list[list[float]],
                     biases: list[float]) -> tuple[list[float], dict[str, float]]:
    vector = pooled(example["tokens"], embeddings) + example["features"]
    allowed = set(example["allowed"])
    logits = {label: sum(weight * value for weight, value in
                         zip(weights[index], vector, strict=True)) + biases[index]
              for index, label in enumerate(labels) if label in allowed}
    require(logits, "coordination inference has no supported feasible response")
    return vector, probabilities(logits)


def fit(dataset: dict[str, Any], tokenizer_artifact: dict[str, Any],
        tokenizer: Byte.Tokenizer, *, config: dict[str, Any] | None = None,
        target_override: dict[str, str] | None = None,
        epochs_override: int | None = None) -> dict[str, Any]:
    config = {**DEFAULT_CONFIG, **(config or {})}
    if epochs_override is not None:
        config["epochs"] = epochs_override
    labels = list(dataset["labels"])
    support = list(dataset["observedLabels"])
    prepared = examples(dataset, tokenizer, target_override)
    train = [item for item in prepared if item["row"]["split"] == "train"]
    require(train, "coordination training split is empty")
    embeddings, weights, biases = initialize(tokenizer, labels, config)
    dimension = config["embeddingDimension"]
    label_index = {label: index for index, label in enumerate(labels)}

    for epoch in range(config["epochs"]):
        embedding_gradient: dict[int, list[float]] = {}
        weight_gradient = [[0.0] * len(weights[0]) for _ in labels]
        bias_gradient = [0.0] * len(labels)
        for example in train:
            vector, probs = infer_components(example, labels, embeddings,
                                              weights, biases)
            vector_gradient = [0.0] * len(vector)
            for label, probability in probs.items():
                index = label_index[label]
                delta = probability - float(label == example["target"])
                bias_gradient[index] += delta
                for column, value in enumerate(vector):
                    weight_gradient[index][column] += delta * value
                    vector_gradient[column] += delta * weights[index][column]
            token_scale = 1.0 / len(example["tokens"])
            for token, count in example["tokenCounts"].items():
                gradient = embedding_gradient.setdefault(token, [0.0] * dimension)
                for column in range(dimension):
                    gradient[column] += vector_gradient[column] * token_scale * count
        scale = 1.0 / len(train)
        learning_rate = config["learningRate"] / (
            1.0 + epoch * config["learningRateDecay"])
        for index in range(len(labels)):
            biases[index] -= learning_rate * bias_gradient[index] * scale
            for column in range(len(weights[index])):
                gradient = weight_gradient[index][column] * scale
                gradient += config["l2"] * weights[index][column]
                weights[index][column] -= learning_rate * gradient
        for token, gradient in embedding_gradient.items():
            for column in range(dimension):
                update = gradient[column] * scale
                update += config["l2"] * embeddings[token][column]
                embeddings[token][column] -= learning_rate * update

    model = Author.seal({
        "schema": "speakeasy-coordination-reference-model",
        "schemaVersion": VERSION,
        "task": "coordination-response",
        "datasetSha256": dataset["contentSha256"],
        "tokenizerSha256": tokenizer_artifact["contentSha256"],
        "config": config,
        "labels": labels,
        "observedLabelSupport": support,
        "unsupportedLabels": [label for label in labels if label not in support],
        "base": {"kind": "learned-mean-byte-bpe-embedding",
                 "weights": [[rounded(value) for value in row]
                             for row in embeddings]},
        "adapter": {"kind": "typed-linear-softmax",
                    "featureNames": list(FEATURES),
                    "weights": [[rounded(value) for value in row]
                                for row in weights],
                    "biases": [rounded(value) for value in biases]},
        "outputConstraint": "intersection-of-current-feasible-and-observed-support",
    })
    return model


def validate_model(dataset: dict[str, Any], tokenizer_artifact: dict[str, Any],
                   tokenizer: Byte.Tokenizer, model: Any) -> dict[str, Any]:
    Data.unseal(model, "speakeasy-coordination-reference-model")
    require(model["datasetSha256"] == dataset["contentSha256"]
            and model["tokenizerSha256"] == tokenizer_artifact["contentSha256"],
            "coordination model source identity differs")
    require(model["labels"] == dataset["labels"]
            and model["observedLabelSupport"] == dataset["observedLabels"]
            and model["unsupportedLabels"] == ["decline", "withdraw"],
            "coordination model label support differs")
    require(model["adapter"]["featureNames"] == list(FEATURES),
            "coordination model feature contract differs")
    reproduced = fit(dataset, tokenizer_artifact, tokenizer,
                     config=model["config"])
    require(Author.encoded(reproduced) == Author.encoded(model),
            "coordination model does not reproduce")
    return model


def model_components(model: dict[str, Any]):
    return (model["labels"], model["base"]["weights"],
            model["adapter"]["weights"], model["adapter"]["biases"])


def predict(example: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    labels, embeddings, weights, biases = model_components(model)
    _, probs = infer_components(example, labels, embeddings, weights, biases)
    choice = min(probs, key=lambda label: (-probs[label], labels.index(label)))
    return {"response": choice,
            "probabilities": {label: rounded(probs[label]) for label in labels
                              if label in probs}}


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    require(rows, "cannot evaluate an empty coordination partition")
    correct = sum(row["actual"] == row["predicted"] for row in rows)
    nll = -sum(math.log(max(row["probabilities"].get(row["actual"], 0.0),
                             1e-15)) for row in rows) / len(rows)
    confusion: dict[str, dict[str, int]] = {}
    support: dict[str, int] = {}
    for row in rows:
        support[row["actual"]] = support.get(row["actual"], 0) + 1
        confusion.setdefault(row["actual"], {})[row["predicted"]] = \
            confusion.setdefault(row["actual"], {}).get(row["predicted"], 0) + 1
    return {"count": len(rows), "accuracy": rounded(correct / len(rows)),
            "negativeLogLikelihood": rounded(nll), "support": support,
            "confusion": confusion}


def predictions(dataset: dict[str, Any], tokenizer: Byte.Tokenizer,
                model: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for example in examples(dataset, tokenizer):
        result = predict(example, model)
        row = example["row"]
        output.append({"rowId": row["rowId"], "split": row["split"],
                       "actual": example["target"],
                       "predicted": result["response"],
                       "probabilities": result["probabilities"],
                       "feasibleOptions": list(example["allowed"]),
                       "auditActorKind": row["auditOnly"]["actorKind"]})
    return output


def evaluate(dataset: dict[str, Any], tokenizer_artifact: dict[str, Any],
             tokenizer: Byte.Tokenizer, model: dict[str, Any]) -> tuple[
                 dict[str, Any], list[dict[str, Any]]]:
    rows = predictions(dataset, tokenizer, model)
    by_split = {split: metrics([row for row in rows if row["split"] == split])
                for split in Data.SPLITS}
    prepared = examples(dataset, tokenizer)
    config = model["config"]
    zero_model = fit(dataset, tokenizer_artifact, tokenizer, config=config,
                     epochs_override=0)
    zero_rows = []
    for example in prepared:
        if example["row"]["split"] == "test":
            result = predict(example, zero_model)
            zero_rows.append({"actual": example["target"],
                              "predicted": result["response"],
                              "probabilities": result["probabilities"]})
    rotation = dict(zip(dataset["observedLabels"],
                        dataset["observedLabels"][1:] + dataset["observedLabels"][:1]))
    override = {item["row"]["rowId"]: rotation[item["target"]]
                for item in prepared if item["row"]["split"] == "train"}
    permuted = fit(dataset, tokenizer_artifact, tokenizer, config=config,
                   target_override=override)
    permuted_rows = []
    for example in prepared:
        if example["row"]["split"] == "test":
            result = predict(example, permuted)
            permuted_rows.append({"actual": example["target"],
                                  "predicted": result["response"],
                                  "probabilities": result["probabilities"]})
    require(by_split["train"]["accuracy"] > metrics(zero_rows)["accuracy"],
            "trained coordination model does not improve on initialization")
    require(by_split["test"]["accuracy"] > metrics(permuted_rows)["accuracy"],
            "coordination evaluation does not discriminate permuted targets")
    evaluation = Author.seal({
        "schema": "speakeasy-coordination-reference-evaluation",
        "schemaVersion": VERSION,
        "datasetSha256": dataset["contentSha256"],
        "modelSha256": model["contentSha256"],
        "partitions": by_split,
        "auditBreakdown": {
            kind: metrics([row for row in rows if row["auditActorKind"] == kind])
            for kind in ("survivor", "afflicted", "crossed")},
        "controls": {
            "zeroEpochTest": metrics(zero_rows),
            "permutedTrainTargetsTest": metrics(permuted_rows),
            "laterOutcomeExcludedFromInput": True,
            "conditionAuditExcludedFromInput": True,
            "lineagePartitionsDisjoint": True,
            "unsupportedLabelsMasked": list(model["unsupportedLabels"]),
        },
        "standing": "bounded-headless-reference",
        "exclusions": list(dataset["exclusions"]) + [
            "This evaluation measures reproduction of one synthetic production-rule family, not general gameplay quality.",
            "The artifact is not a native runtime candidate.",
        ],
    })
    return evaluation, rows


def output_files(dataset: dict[str, Any], tokenizer_artifact: dict[str, Any],
                 tokenizer: Byte.Tokenizer) -> dict[str, bytes]:
    model = fit(dataset, tokenizer_artifact, tokenizer)
    validate_model(dataset, tokenizer_artifact, tokenizer, model)
    evaluation, rows = evaluate(dataset, tokenizer_artifact, tokenizer, model)
    model_bytes = json.dumps(model, ensure_ascii=False, indent=2,
                             sort_keys=True).encode("utf-8") + b"\n"
    evaluation_bytes = json.dumps(evaluation, ensure_ascii=False, indent=2,
                                  sort_keys=True).encode("utf-8") + b"\n"
    prediction_bytes = Data.jsonl_bytes(rows)
    manifest = Author.seal({
        "schema": "speakeasy-coordination-reference-run",
        "schemaVersion": VERSION,
        "runId": "r66-c81-coordination-reference-v1",
        "datasetSha256": dataset["contentSha256"],
        "tokenizerSha256": tokenizer_artifact["contentSha256"],
        "files": {"model.json": Data.sha256_bytes(model_bytes),
                  "evaluation.json": Data.sha256_bytes(evaluation_bytes),
                  "predictions.jsonl": Data.sha256_bytes(prediction_bytes)},
        "standing": "offline-reference-only",
    })
    return {"model.json": model_bytes, "evaluation.json": evaluation_bytes,
            "predictions.jsonl": prediction_bytes,
            "manifest.json": json.dumps(manifest, ensure_ascii=False, indent=2,
                                        sort_keys=True).encode("utf-8") + b"\n"}


def train_to(dataset_path: Path, output: Path) -> dict[str, bytes]:
    dataset = Data.validate_dataset(Author.read(dataset_path))
    tokenizer_artifact, tokenizer = load_tokenizer()
    files = output_files(dataset, tokenizer_artifact, tokenizer)
    require(not output.exists(), "coordination reference output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="." + output.name + ".",
                                    dir=output.parent))
    try:
        for name, value in files.items():
            (staging / name).write_bytes(value)
        os.replace(staging, output)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    validate_run(dataset_path, output)
    return files


def validate_run(dataset_path: Path, output: Path) -> dict[str, bytes]:
    dataset = Data.validate_dataset(Author.read(dataset_path))
    tokenizer_artifact, tokenizer = load_tokenizer()
    expected = output_files(dataset, tokenizer_artifact, tokenizer)
    actual = {}
    for name, value in expected.items():
        path = output / name
        require(path.is_file(), "coordination reference file is missing: " + name)
        actual[name] = path.read_bytes()
        require(actual[name] == value,
                "coordination reference file does not reproduce: " + name)
    return actual


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_subparsers(dest="command", required=True)
    train = command.add_parser("train")
    train.add_argument("--dataset", type=Path, required=True)
    train.add_argument("--out", type=Path, required=True)
    validate = command.add_parser("validate")
    validate.add_argument("--dataset", type=Path, required=True)
    validate.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "train":
            files = train_to(args.dataset, args.out)
            print("trained bounded coordination reference " +
                  Author.read(args.out / "manifest.json")["contentSha256"])
        else:
            files = validate_run(args.dataset, args.run_dir)
            print("validated bounded coordination reference " +
                  Author.read(args.run_dir / "manifest.json")["contentSha256"])
        require(bool(files), "coordination reference produced no files")
    except (Join.ContractError, OSError, UnicodeError, ValueError,
            OverflowError) as error:
        print("REFUSED: " + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
