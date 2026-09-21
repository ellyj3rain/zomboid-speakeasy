#!/usr/bin/env python3
"""Join fully namespaced SAO decision rows to same-moment ZAO state.

Version 3 joins are one-to-one on run, county, person, event, and hour. Every
input row is parsed and validated before an output path is created. Publication
uses a temporary sibling and one atomic replace. The ratified intent files,
approved world documents, and historical version 2 derivatives are bound by
decisions/PROTECTED.json and can never be output destinations.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent.parent
PROTECTED_MANIFEST = ROOT / "decisions" / "PROTECTED.json"
NAMESPACE_FIELDS = ("runId", "county", "personId", "eventId", "hour")
SAO_SCHEMA = "speakeasy-decision-row"
ZAO_SCHEMA = "zao-decision-state"
VERSION = 3


class ContractError(ValueError):
    """An input or destination cannot satisfy the version 3 contract."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(path: Path) -> str:
    return os.path.normcase(str(path.expanduser().resolve(strict=False)))


def protected_artifacts() -> dict[str, dict[str, Any]]:
    try:
        manifest = json.loads(PROTECTED_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContractError(
            f"protected artifact manifest is unreadable: {error}") from error
    if (manifest.get("schema") != "speakeasy-protected-artifacts"
            or manifest.get("schemaVersion") != 1
            or not isinstance(manifest.get("artifacts"), list)):
        raise ContractError("protected artifact manifest schema is unsupported")

    protected: dict[str, dict[str, Any]] = {}
    for index, artifact in enumerate(manifest["artifacts"], 1):
        if (not isinstance(artifact, dict)
                or set(artifact) != {"path", "sha256", "standing"}
                or not all(isinstance(artifact.get(field), str)
                           and artifact[field] for field in artifact)):
            raise ContractError(
                f"protected artifact manifest entry {index} is invalid")
        path = (ROOT / artifact["path"]).resolve(strict=False)
        key = canonical(path)
        if key in protected:
            raise ContractError(
                f"protected artifact manifest repeats {artifact['path']}")
        if not path.is_file():
            raise ContractError(f"protected artifact is absent: {artifact['path']}")
        actual = sha256(path)
        if actual != artifact["sha256"]:
            raise ContractError(
                f"protected artifact hash changed: {artifact['path']}")
        protected[key] = artifact
    return protected


def read_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    if not path.is_file():
        raise ContractError(f"input is not a file: {path}")
    rows: list[tuple[int, dict[str, Any]]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ContractError(
                        f"{path}:{line_number}: invalid JSON: {error.msg}") from error
                if not isinstance(row, dict):
                    raise ContractError(
                        f"{path}:{line_number}: each row must be a JSON object")
                rows.append((line_number, row))
    except UnicodeError as error:
        raise ContractError(f"{path}: input is not valid UTF-8") from error
    if not rows:
        raise ContractError(f"{path}: input contains no rows")
    return rows


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def finite_number(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def namespace(row: dict[str, Any], path: Path, line: int) -> tuple[Any, ...]:
    value = row.get("namespace")
    if not isinstance(value, dict):
        raise ContractError(f"{path}:{line}: namespace must be an object")
    missing = [field for field in NAMESPACE_FIELDS if field not in value]
    if missing:
        raise ContractError(
            f"{path}:{line}: namespace missing {', '.join(missing)}")
    for field in NAMESPACE_FIELDS[:-1]:
        if not nonempty_string(value[field]):
            raise ContractError(
                f"{path}:{line}: namespace {field} must be a nonempty string")
    if not finite_number(value["hour"]):
        raise ContractError(
            f"{path}:{line}: namespace hour must be a finite number")
    return tuple(value[field] for field in NAMESPACE_FIELDS)


def validate_schema(row: dict[str, Any], path: Path, line: int,
                    expected: str) -> None:
    if row.get("schema") != expected or row.get("schemaVersion") != VERSION:
        raise ContractError(
            f"{path}:{line}: requires {expected} schema version {VERSION}")


def validate_conditioning(row: dict[str, Any], hour: Any,
                          path: Path, line: int) -> None:
    conditioning = row.get("conditioning")
    if not isinstance(conditioning, dict):
        raise ContractError(
            f"{path}:{line}: conditioning must be an object")
    status = conditioning.get("status")
    if status not in {"eligible", "ineligible"}:
        raise ContractError(
            f"{path}:{line}: conditioning status must be eligible or ineligible")
    if conditioning.get("decisionHour") != hour:
        raise ContractError(
            f"{path}:{line}: conditioning decisionHour differs from namespace")
    latest = conditioning.get("latestEvidenceHour")
    if latest is not None and not finite_number(latest):
        raise ContractError(
            f"{path}:{line}: latestEvidenceHour must be finite or null")
    exclusions = conditioning.get("exclusions")
    if not isinstance(exclusions, list) or not all(
            nonempty_string(item) for item in exclusions):
        raise ContractError(
            f"{path}:{line}: conditioning exclusions must be a string list")
    if status == "eligible":
        if latest is None or latest > hour or exclusions:
            raise ContractError(
                f"{path}:{line}: eligible conditioning includes future or excluded evidence")


def validate_options(row: dict[str, Any], path: Path, line: int) -> None:
    options = row.get("options")
    if not isinstance(options, list) or not options:
        raise ContractError(
            f"{path}:{line}: options must be a nonempty executable action list")
    identities: set[str] = set()
    for index, option in enumerate(options, 1):
        where = f"{path}:{line}: option {index}"
        if not isinstance(option, dict):
            raise ContractError(f"{where} must be an object, not a label")
        for field in ("id", "owner"):
            if not nonempty_string(option.get(field)):
                raise ContractError(f"{where} {field} must be a nonempty string")
        if option["id"] in identities:
            raise ContractError(f"{where} repeats option id {option['id']!r}")
        identities.add(option["id"])
        if not isinstance(option.get("parameters"), dict):
            raise ContractError(f"{where} parameters must be an object")
        eligibility = option.get("eligibility")
        if (not isinstance(eligibility, dict)
                or eligibility.get("status") != "eligible"
                or not isinstance(eligibility.get("evidence"), list)
                or not eligibility["evidence"]
                or not all(isinstance(item, dict) and item
                           for item in eligibility["evidence"])):
            raise ContractError(
                f"{where} needs eligible status and nonempty evidence objects")
    choice = row.get("choice")
    if not isinstance(choice, dict) or choice.get("optionId") not in identities:
        raise ContractError(
            f"{path}:{line}: choice optionId must name one executable option")


def validate_unenriched_context(row: dict[str, Any], path: Path, line: int) -> None:
    """Original capture context cannot carry cross-module additions."""
    if "pathogen" in row["person"]:
        raise ContractError(
            f"{path}:{line}: SAO person is already cross-module enriched")
    if "visibleForms" in row["situation"]:
        raise ContractError(
            f"{path}:{line}: SAO situation is already cross-module enriched")
    if "crossModule" in row:
        raise ContractError(
            f"{path}:{line}: SAO row already carries join provenance")


def validate_sao_row(row: dict[str, Any], path: Path, line: int) -> tuple[Any, ...]:
    """The complete original-row admission shared by joins and authoring."""
    validate_schema(row, path, line, SAO_SCHEMA)
    missing = {"person", "situation", "options", "choice"} - row.keys()
    if missing:
        raise ContractError(
            f"{path}:{line}: missing SAO half(s): {', '.join(sorted(missing))}")
    key = namespace(row, path, line)
    _, county, person_id, _, hour = key
    person, situation = row["person"], row["situation"]
    if not isinstance(person, dict) or person.get("id") != person_id:
        raise ContractError(
            f"{path}:{line}: person id differs from namespace")
    if (not isinstance(situation, dict)
            or situation.get("county") != county
            or situation.get("hour") != hour):
        raise ContractError(
            f"{path}:{line}: situation county/hour differs from namespace")
    validate_unenriched_context(row, path, line)
    citation = row.get("citation")
    if citation is not None and (not isinstance(citation, dict)
            or citation.get("county") != county
            or citation.get("person") != person_id
            or citation.get("hour") != hour):
        raise ContractError(
            f"{path}:{line}: citation differs from namespace")
    validate_conditioning(row, hour, path, line)
    validate_options(row, path, line)
    return key


def validate_sao(path: Path) -> tuple[
        list[tuple[int, dict[str, Any], tuple[Any, ...]]],
        dict[tuple[Any, ...], tuple[int, dict[str, Any]]]]:
    ordered = []
    indexed = {}
    for line, row in read_jsonl(path):
        key = validate_sao_row(row, path, line)
        if key in indexed:
            raise ContractError(
                f"{path}:{line}: duplicate full namespace first seen at line {indexed[key][0]}")
        indexed[key] = (line, row)
        ordered.append((line, row, key))
    return ordered, indexed


def validate_zao(path: Path) -> dict[
        tuple[Any, ...], tuple[int, dict[str, Any]]]:
    indexed = {}
    for line, row in read_jsonl(path):
        validate_schema(row, path, line, ZAO_SCHEMA)
        key = namespace(row, path, line)
        hour = key[-1]
        if row.get("asOfHour") != hour:
            raise ContractError(
                f"{path}:{line}: asOfHour differs from namespace")
        if not isinstance(row.get("pathogen"), dict):
            raise ContractError(f"{path}:{line}: pathogen must be an object")
        if not isinstance(row.get("visibleForms"), list):
            raise ContractError(f"{path}:{line}: visibleForms must be a list")
        if key in indexed:
            raise ContractError(
                f"{path}:{line}: duplicate full namespace first seen at line {indexed[key][0]}")
        indexed[key] = (line, row)
    return indexed


def validate_destinations(sao_path: Path, zao_path: Path,
                          out_path: Path) -> dict[str, dict[str, Any]]:
    paths = [canonical(path) for path in (sao_path, zao_path, out_path)]
    if paths[0] == paths[1]:
        raise ContractError("SAO and ZAO inputs must be different files")
    if paths[2] in paths[:2]:
        raise ContractError("output destination must differ from both inputs")
    protected = protected_artifacts()
    if paths[2] in protected:
        artifact = protected[paths[2]]
        raise ContractError(
            f"output destination is protected {artifact['standing']}: {artifact['path']}")
    if out_path.exists() and not out_path.is_file():
        raise ContractError(f"output destination is not a file: {out_path}")
    return protected


def joined_rows(sao_path: Path, zao_path: Path,
                out_path: Path) -> list[dict[str, Any]]:
    validate_destinations(sao_path, zao_path, out_path)
    ordered, sao = validate_sao(sao_path)
    zao = validate_zao(zao_path)
    sao_keys, zao_keys = set(sao), set(zao)
    missing = sao_keys - zao_keys
    extra = zao_keys - sao_keys
    if missing:
        sample = sorted(repr(key) for key in missing)[0]
        raise ContractError(
            f"{zao_path}: missing ZAO state for full namespace {sample}")
    if extra:
        sample = sorted(repr(key) for key in extra)[0]
        raise ContractError(
            f"{zao_path}: unmatched ZAO state for full namespace {sample}")

    provenance = {
        "schema": "speakeasy-cross-module-join",
        "schemaVersion": VERSION,
        "saoSha256": sha256(sao_path),
        "zaoSha256": sha256(zao_path),
    }
    output = []
    for _, row, key in ordered:
        state = zao[key][1]
        joined = copy.deepcopy(row)
        joined["person"]["pathogen"] = copy.deepcopy(state["pathogen"])
        joined["situation"]["visibleForms"] = copy.deepcopy(
            state["visibleForms"])
        joined["crossModule"] = {
            **provenance,
            "namespace": {
                field: joined["namespace"][field] for field in NAMESPACE_FIELDS
            },
        }
        output.append(joined)
    return output


def atomic_write(out_path: Path, rows: Iterable[dict[str, Any]]) -> int:
    encoded = [json.dumps(row, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")) + "\n" for row in rows]
    if not encoded:
        raise ContractError("join produced no rows")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{out_path.name}.", suffix=".tmp", dir=out_path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.writelines(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, out_path)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise
    return len(encoded)


def export_rows(sao_path: Path, zao_path: Path, out_path: Path) -> int:
    rows = joined_rows(sao_path, zao_path, out_path)
    return atomic_write(out_path, rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Join namespaced SAO decisions to same-moment ZAO state.")
    parser.add_argument("--sao", type=Path, required=True,
                        help="version 3 SAO decision rows as JSONL")
    parser.add_argument("--zao", type=Path, required=True,
                        help="version 3 ZAO same-moment state as JSONL")
    parser.add_argument("--out", type=Path, required=True,
                        help="new or replaceable unprotected output JSONL")
    args = parser.parse_args(argv)
    try:
        written = export_rows(args.sao, args.zao, args.out)
    except (ContractError, OSError) as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 2
    print(f"wrote {written} version 3 cross-module row(s) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
