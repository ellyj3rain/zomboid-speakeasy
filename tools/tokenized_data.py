"""Bind frozen tokenization to revalidated task data without changing admission."""
import argparse
import copy
from pathlib import Path

import byte_tokenizer as B
import cross_module_rows as J
import decision_authoring as A
import task_data as D

SCHEMA = "speakeasy-tokenized-task-preview"


def training_segments(preview):
    # No validation/test text, excluded candidates, review prose or audit owners.
    segments = []
    for task in sorted(preview["datasets"]):
        for row in preview["datasets"][task]["train"]:
            segments.append(A.encoded(row["input"]))
            if task != "retriever":
                segments.append(A.encoded(row["target"]))
    return segments


def _tokenize(preview, artifact):
    tokenizer = B.Tokenizer(artifact)
    special = B.SPECIAL_IDS
    datasets = {}
    for task, partitions in preview["datasets"].items():
        datasets[task] = {}
        for partition, rows in partitions.items():
            output = datasets[task][partition] = []
            for row in rows:
                inputs = tokenizer.encode_bytes(A.encoded(row["input"]))
                prefix = [special["bos"], special[task], special["schema"], special["input"]]
                target = None if task == "retriever" else tokenizer.encode_bytes(A.encoded(row["target"]))
                output.append({"rowSha256": row["rowSha256"], "task": task,
                    "objective": row["objective"], "sourceGroups": row["sourceGroups"],
                    "unavailableNativeInputs": row["unavailableNativeInputs"],
                    "inputIds": prefix + inputs + [special["eos"]],
                    "targetIds": None if target is None else [special["target"]] + target + [special["eos"]],
                    "targetLossMask": None if target is None else [False] + [True] * (len(target) + 1),
                    "claimTargets": copy.deepcopy(row["target"]["claims"]) if task == "retriever" else None})
    return A.seal({"schema": SCHEMA, "schemaVersion": 1,
        "preparationSha256": preview["contentSha256"], "tokenizerSha256": artifact["contentSha256"],
        "serialization": "canonical-json-utf8-v1", "datasets": datasets,
        "release": {"status": "ready-for-reference-training" if preview["release"]["status"] ==
                    "ready-for-tokenization" else "excluded",
                    "exclusions": copy.deepcopy(preview["release"]["exclusions"]),
                    "missingPartitions": copy.deepcopy(preview["release"]["missingPartitions"])},
        "limits": ["offline-authored-conversation-scope", "no-trained-model-or-runtime-admission",
                   "retriever-loss-uses-only-reviewed-claim-targets",
                   "reserved-tokens-do-not-enforce-factual-meaning", "java-token-parity-unverified"]})


def prepare(preview, merge_limit=64, evidence=None):
    D.validate(preview, evidence)
    artifact = B.train(training_segments(preview), merge_limit)
    return artifact, _tokenize(preview, artifact)


def validate(preview, artifact, tokenized, evidence=None):
    D.validate(preview, evidence)
    B.validate_training(artifact, training_segments(preview))
    A.unseal(tokenized, SCHEMA)
    A.require(A.encoded(tokenized) == A.encoded(_tokenize(preview, artifact)),
              "tokenized data differs from prepared evidence")
    return tokenized


def release(preview, artifact, tokenized, evidence=None):
    validate(preview, artifact, tokenized, evidence)
    D.release(preview, evidence)
    return copy.deepcopy(tokenized["datasets"])


def vectors(artifact):
    tokenizer = B.Tokenizer(artifact)
    cases = [("empty", b""), ("all-bytes", bytes(range(256))),
             ("overlap", b"aaaaaaa ababababa"),
             ("literal-structure", b"<bos><claim-ref><fenced-slot>"),
             ("whitespace", b" \t\r\n two  spaces\n"),
             ("names-and-unicode", "Mara, Jon, Zo\u00eb, \u674e, \U0001f642, e\u0301, \u00e9".encode("utf-8"))]
    return A.seal({"schema": "speakeasy-tokenizer-vectors", "schemaVersion": 1,
        "tokenizerSha256": artifact["contentSha256"],
        "cases": [{"name": name, "bytesHex": value.hex(), "tokenIds": tokenizer.encode_bytes(value)}
                  for name, value in cases]})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("preview", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--merge-limit", type=int, default=64)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    try:
        preview = A.read(args.preview)
        artifact, tokenized = prepare(preview, args.merge_limit)
        if args.require_ready:
            release(preview, artifact, tokenized)
        outputs = {"tokenizer.json": artifact, "preview.json": tokenized, "vectors.json": vectors(artifact)}
        encoded = {args.output_dir / name: A.encoded(value) + b"\n" for name, value in outputs.items()}
        # Check all destinations before creating any file; never overwrite evidence.
        for path, data in encoded.items():
            if args.check:
                A.require(path.read_bytes() == data, "saved tokenization differs: " + path.name)
            else:
                A.require(not path.exists() or path.read_bytes() == data,
                          "different data already exists: " + path.name)
        if not args.check:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            for path, data in encoded.items():
                if not path.exists():
                    with path.open("xb") as stream:
                        stream.write(data)
        print("tokenizer", artifact["contentSha256"], "merges", len(artifact["merges"]))
        print("preview", tokenized["contentSha256"], tokenized["release"]["status"])
    except (J.ContractError, OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, "REFUSED: " + str(error) + "\n")


if __name__ == "__main__":
    main()
