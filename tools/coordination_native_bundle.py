#!/usr/bin/env python3
"""Export and validate the bounded coordination model's pure-Java bundle.

The bundle is deliberately small and dependency-free: a frozen byte-BPE merge
program, reserved token IDs, FP32 parameters, typed feature names and the
observed-response mask.  Parity vectors retain the exact canonical input bytes,
token sequence and FP32 result for every admitted R66 row.  Runtime authority is
not conveyed by this export; SAO consumes it in shadow mode until a later review.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import math
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
from typing import Any

import byte_tokenizer as Byte
import coordination_data as Data
import coordination_reference as Reference
import cross_module_rows as Join
import decision_authoring as Author


ROOT = Join.ROOT
DATASET = ROOT / "training/coordination/r66-source/dataset.json"
REFERENCE_RUN = ROOT / "training/coordination/r66-reference"
TOKENIZER_VECTORS = ROOT / "training/datasets/c77-tokenization/vectors.json"
MAGIC = b"SAOCRD01"
FORMAT_VERSION = 1
BUNDLE_ID = "r67-r66-coordination-fp32-v1"
COMPATIBILITY = "sao-coordination-consumer-v1"
MAX_STRING_BYTES = 1_048_576
MAX_COUNT = 16_384


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Join.ContractError(message)


def sha256_bytes(value: bytes) -> str:
    return Data.sha256_bytes(value)


def f32(value: float) -> float:
    """Round once to the IEEE-754 binary32 value used by the Java consumer."""
    return struct.unpack(">f", struct.pack(">f", float(value)))[0]


def f32_text(value: float) -> str:
    # Nine significant digits round-trip every finite binary32 value.
    return format(f32(value), ".9g")


class Writer:
    def __init__(self) -> None:
        self.value = io.BytesIO()

    def raw(self, value: bytes) -> None:
        self.value.write(value)

    def integer(self, value: int) -> None:
        require(type(value) is int and 0 <= value <= 0x7fffffff,
                "native bundle integer is outside the supported range")
        self.value.write(struct.pack(">i", value))

    def string(self, value: str) -> None:
        require(isinstance(value, str), "native bundle string is not text")
        encoded = value.encode("utf-8", errors="strict")
        require(len(encoded) <= MAX_STRING_BYTES,
                "native bundle string exceeds its bound")
        self.integer(len(encoded))
        self.raw(encoded)

    def floating(self, value: float) -> None:
        rounded = f32(value)
        require(math.isfinite(rounded), "native bundle contains non-finite FP32")
        self.raw(struct.pack(">f", rounded))

    def finish(self) -> bytes:
        return self.value.getvalue()


class Reader:
    """Strict mirror used to reject malformed or trailing bundle content."""

    def __init__(self, value: bytes) -> None:
        self.value = io.BytesIO(value)

    def raw(self, count: int) -> bytes:
        value = self.value.read(count)
        require(len(value) == count, "native bundle ended early")
        return value

    def integer(self, maximum: int = MAX_COUNT) -> int:
        value = struct.unpack(">i", self.raw(4))[0]
        require(0 <= value <= maximum, "native bundle count is invalid")
        return value

    def string(self) -> str:
        size = self.integer(MAX_STRING_BYTES)
        try:
            return self.raw(size).decode("utf-8", errors="strict")
        except UnicodeError as error:
            raise Join.ContractError("native bundle string is not UTF-8") from error

    def floating(self) -> float:
        value = struct.unpack(">f", self.raw(4))[0]
        require(math.isfinite(value), "native bundle float is not finite")
        return value

    def exhausted(self) -> None:
        require(self.value.read(1) == b"", "native bundle has trailing bytes")


def fp32_predict(example: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    """Execute the specified FP32 accumulation/softmax contract."""
    labels = list(model["labels"])
    support = set(model["observedLabelSupport"])
    embeddings = [[f32(value) for value in row]
                  for row in model["base"]["weights"]]
    weights = [[f32(value) for value in row]
               for row in model["adapter"]["weights"]]
    biases = [f32(value) for value in model["adapter"]["biases"]]
    dimension = len(embeddings[0])
    pooled = [f32(0.0)] * dimension
    for token in example["tokens"]:
        for index in range(dimension):
            pooled[index] = f32(pooled[index] + embeddings[token][index])
    inverse = f32(1.0 / len(example["tokens"]))
    pooled = [f32(value * inverse) for value in pooled]
    vector = pooled + [f32(value) for value in example["features"]]
    allowed = set(example["allowed"])
    logits: dict[str, float] = {}
    for label_index, label in enumerate(labels):
        if label not in support or label not in allowed:
            continue
        value = biases[label_index]
        for weight, feature in zip(weights[label_index], vector, strict=True):
            value = f32(value + f32(weight * feature))
        logits[label] = value
    require(bool(logits), "native inference has no supported feasible response")
    maximum = max(logits.values())
    shifted = {label: f32(math.exp(f32(value - maximum)))
               for label, value in logits.items()}
    total = f32(0.0)
    for label in labels:
        if label in shifted:
            total = f32(total + shifted[label])
    probabilities = {label: f32(shifted[label] / total)
                     for label in labels if label in shifted}
    response = min(probabilities,
                   key=lambda label: (-probabilities[label], labels.index(label)))
    return {"response": response, "probabilities": probabilities}


def bundle_bytes(dataset: dict[str, Any], tokenizer_artifact: dict[str, Any],
                 model: dict[str, Any], run_manifest: dict[str, Any]) -> bytes:
    writer = Writer()
    writer.raw(MAGIC)
    writer.integer(FORMAT_VERSION)
    for value in (
        "speakeasy-native-coordination-bundle", BUNDLE_ID, "fp32", "fp32",
        "strict-exp-fp32", COMPATIBILITY, model["contentSha256"],
        dataset["contentSha256"], tokenizer_artifact["contentSha256"],
        run_manifest["contentSha256"], model["outputConstraint"],
        tokenizer_artifact["rules"]["algorithm"],
        tokenizer_artifact["rules"]["normalization"],
        tokenizer_artifact["rules"]["textEncoding"],
    ):
        writer.string(value)

    specials = tokenizer_artifact["specialTokens"]
    writer.integer(len(specials))
    for name in sorted(specials):
        writer.string(name)
        writer.integer(specials[name])

    merges = tokenizer_artifact["merges"]
    writer.integer(len(merges))
    for left, right in merges:
        writer.integer(left)
        writer.integer(right)

    for values in (model["labels"], model["observedLabelSupport"],
                   model["unsupportedLabels"], model["adapter"]["featureNames"]):
        writer.integer(len(values))
        for value in values:
            writer.string(value)

    embeddings = model["base"]["weights"]
    writer.integer(len(embeddings))
    writer.integer(len(embeddings[0]))
    for row in embeddings:
        require(len(row) == len(embeddings[0]),
                "native embedding matrix is ragged")
        for value in row:
            writer.floating(value)

    weights = model["adapter"]["weights"]
    writer.integer(len(weights))
    writer.integer(len(weights[0]))
    for row in weights:
        require(len(row) == len(weights[0]), "native adapter matrix is ragged")
        for value in row:
            writer.floating(value)
    biases = model["adapter"]["biases"]
    writer.integer(len(biases))
    for value in biases:
        writer.floating(value)
    return writer.finish()


def inspect_bundle(value: bytes) -> dict[str, Any]:
    reader = Reader(value)
    require(reader.raw(len(MAGIC)) == MAGIC, "native bundle magic differs")
    require(reader.integer(64) == FORMAT_VERSION,
            "native bundle format version differs")
    names = ("schema", "bundleId", "parameterPrecision", "accumulationPrecision",
             "softmax", "compatibility", "modelSha256", "datasetSha256",
             "tokenizerSha256", "referenceRunSha256", "outputConstraint",
             "tokenizerAlgorithm", "normalization", "textEncoding")
    result = {name: reader.string() for name in names}
    result["specialTokens"] = {
        reader.string(): reader.integer(4096) for _ in range(reader.integer(256))}
    result["merges"] = [[reader.integer(4096), reader.integer(4096)]
                        for _ in range(reader.integer(8192))]
    for name in ("labels", "observedLabelSupport", "unsupportedLabels",
                 "featureNames"):
        result[name] = [reader.string() for _ in range(reader.integer(256))]
    embedding_rows, embedding_width = reader.integer(), reader.integer(256)
    result["embeddingShape"] = [embedding_rows, embedding_width]
    for _ in range(embedding_rows * embedding_width):
        reader.floating()
    adapter_rows, adapter_width = reader.integer(256), reader.integer(256)
    result["adapterShape"] = [adapter_rows, adapter_width]
    for _ in range(adapter_rows * adapter_width):
        reader.floating()
    bias_count = reader.integer(256)
    result["biasCount"] = bias_count
    for _ in range(bias_count):
        reader.floating()
    reader.exhausted()
    require(result["schema"] == "speakeasy-native-coordination-bundle"
            and result["bundleId"] == BUNDLE_ID
            and result["parameterPrecision"] == "fp32"
            and result["accumulationPrecision"] == "fp32"
            and result["compatibility"] == COMPATIBILITY,
            "native bundle identity or precision differs")
    require(result["labels"] == dataset_labels()
            and result["observedLabelSupport"] == list(Data.OBSERVED_RESPONSES)
            and result["unsupportedLabels"] == ["decline", "withdraw"]
            and result["featureNames"] == list(Reference.FEATURES),
            "native bundle task contract differs")
    require(result["embeddingShape"][1] == Reference.DEFAULT_CONFIG["embeddingDimension"]
            and result["adapterShape"] == [len(result["labels"]),
                                             len(Reference.FEATURES) +
                                             result["embeddingShape"][1]]
            and result["biasCount"] == len(result["labels"]),
            "native bundle tensor shape differs")
    return result


def dataset_labels() -> list[str]:
    return list(Data.RESPONSES)


def parity_bytes(dataset: dict[str, Any], tokenizer: Byte.Tokenizer,
                 model: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    reference = {row["rowId"]: row
                 for row in Reference.predictions(dataset, tokenizer, model)}
    lines = ["rowId\tinputBase64\ttokenIds\tfeatures\tallowed\tpredicted\tprobabilities"]
    maximum_delta = 0.0
    exact = True
    for example in Reference.examples(dataset, tokenizer):
        row_id = example["row"]["rowId"]
        result = fp32_predict(example, model)
        expected = reference[row_id]
        exact = exact and result["response"] == expected["predicted"]
        for label, probability in result["probabilities"].items():
            maximum_delta = max(maximum_delta,
                                abs(probability - expected["probabilities"][label]))
        canonical = Author.encoded(example["row"]["input"])
        fields = (
            row_id,
            base64.b64encode(canonical).decode("ascii"),
            ",".join(map(str, example["tokens"])),
            ",".join(f32_text(value) for value in example["features"]),
            ",".join(example["allowed"]),
            result["response"],
            ",".join(label + "=" + f32_text(result["probabilities"][label])
                     for label in model["labels"]
                     if label in result["probabilities"]),
        )
        require(all("\t" not in value and "\r" not in value and "\n" not in value
                    for value in fields), "native parity field is not one line")
        lines.append("\t".join(fields))
    require(exact, "FP32 native export changes an R66 response")
    value = ("\n".join(lines) + "\n").encode("utf-8")
    return value, {"rowCount": len(lines) - 1, "exactResponseParity": exact,
                   "maxProbabilityDeltaFromR66": float(f32_text(maximum_delta)),
                   "probabilityTolerance": 1e-6}


def tokenizer_vector_bytes(tokenizer_artifact: dict[str, Any]) -> bytes:
    vectors = Author.read(TOKENIZER_VECTORS)
    require(vectors["tokenizerSha256"] == tokenizer_artifact["contentSha256"],
            "tokenizer vectors bind a different tokenizer")
    lines = ["name\tbytesHex\ttokenIds"]
    for case in vectors["cases"]:
        lines.append("\t".join((case["name"], case["bytesHex"],
                                ",".join(map(str, case["tokenIds"])))))
    return ("\n".join(lines) + "\n").encode("ascii")


def output_files(dataset_path: Path = DATASET,
                 run_dir: Path = REFERENCE_RUN, *,
                 validate_reference: bool = True) -> dict[str, bytes]:
    if validate_reference:
        # This re-trains and byte-compares the complete sealed R66 run.  Callers
        # composing several in-memory checks may do it once and then regenerate
        # this deterministic projection without paying the training cost again.
        Reference.validate_run(dataset_path, run_dir)
    dataset = Data.validate_dataset(Author.read(dataset_path))
    tokenizer_artifact, tokenizer = Reference.load_tokenizer()
    model = Author.read(run_dir / "model.json")
    run_manifest = Author.read(run_dir / "manifest.json")
    if not validate_reference:
        Data.unseal(model, "speakeasy-coordination-reference-model")
    bundle = bundle_bytes(dataset, tokenizer_artifact, model, run_manifest)
    inspected = inspect_bundle(bundle)
    require(inspected["modelSha256"] == model["contentSha256"]
            and inspected["datasetSha256"] == dataset["contentSha256"]
            and inspected["tokenizerSha256"] == tokenizer_artifact["contentSha256"]
            and inspected["referenceRunSha256"] == run_manifest["contentSha256"],
            "native bundle source identity differs")
    parity, parity_summary = parity_bytes(dataset, tokenizer, model)
    token_vectors = tokenizer_vector_bytes(tokenizer_artifact)
    files = {"coordination.bundle": bundle, "parity.tsv": parity,
             "tokenizer-vectors.tsv": token_vectors}
    manifest = Author.seal({
        "schema": "speakeasy-native-bundle-manifest", "schemaVersion": 1,
        "bundleId": BUNDLE_ID, "task": "coordination-response",
        "standing": "native-shadow-candidate",
        "compatibility": {"consumer": COMPATIBILITY,
                          "externalRuntimeRequired": False},
        "precision": {"parameters": "fp32", "accumulation": "fp32",
                      "softmax": "strict-exp-fp32", "quantization": "none"},
        "source": {"referenceRunSha256": run_manifest["contentSha256"],
                   "modelSha256": model["contentSha256"],
                   "datasetSha256": dataset["contentSha256"],
                   "tokenizerSha256": tokenizer_artifact["contentSha256"]},
        "components": {name: sha256_bytes(value) for name, value in files.items()},
        "parity": parity_summary,
        "limits": [
            "Coordination output remains shadow-only and cannot select or revise a game response.",
            "The source family has no decline or withdraw target; both remain masked.",
            "The twenty rows are synthetic production situations, not sampled gameplay prevalence.",
            "Afflicted and Crossed share a registered ZAO execution owner but retain distinct state, maintenance and action policy outside this generic task input.",
        ],
    })
    files["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2,
                                          sort_keys=True).encode("utf-8") + b"\n")
    return files


def export_to(output: Path, dataset_path: Path = DATASET,
              run_dir: Path = REFERENCE_RUN, *,
              validate_reference: bool = True) -> dict[str, bytes]:
    files = output_files(dataset_path, run_dir,
                         validate_reference=validate_reference)
    require(not output.exists(), "native coordination output already exists")
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
    for name, value in files.items():
        require((output / name).read_bytes() == value,
                "native coordination export changed while publishing: " + name)
    return files


def validate(output: Path, dataset_path: Path = DATASET,
             run_dir: Path = REFERENCE_RUN, *,
             validate_reference: bool = True) -> dict[str, bytes]:
    expected = output_files(dataset_path, run_dir,
                            validate_reference=validate_reference)
    for name, value in expected.items():
        path = output / name
        require(path.is_file(), "native coordination file is missing: " + name)
        require(path.read_bytes() == value,
                "native coordination file does not reproduce: " + name)
    return expected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_subparsers(dest="command", required=True)
    export = command.add_parser("export")
    export.add_argument("--out", type=Path, required=True)
    export.add_argument("--dataset", type=Path, default=DATASET)
    export.add_argument("--run-dir", type=Path, default=REFERENCE_RUN)
    validate_command = command.add_parser("validate")
    validate_command.add_argument("--bundle-dir", type=Path, required=True)
    validate_command.add_argument("--dataset", type=Path, default=DATASET)
    validate_command.add_argument("--run-dir", type=Path, default=REFERENCE_RUN)
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            export_to(args.out, args.dataset, args.run_dir)
            manifest = Author.read(args.out / "manifest.json")
            print("exported native coordination bundle " + manifest["contentSha256"])
        else:
            validate(args.bundle_dir, args.dataset, args.run_dir)
            manifest = Author.read(args.bundle_dir / "manifest.json")
            print("validated native coordination bundle " + manifest["contentSha256"])
    except (Join.ContractError, OSError, UnicodeError, ValueError,
            OverflowError, struct.error) as error:
        print("REFUSED: " + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
