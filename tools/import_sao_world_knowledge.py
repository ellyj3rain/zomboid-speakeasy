#!/usr/bin/env python3
"""Import and verify one SAO person-specific world-knowledge evidence port."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import cross_module_rows as Join
import decision_authoring as Author


VERSION = 1
SOURCE_PATH = (
    "artifacts/audits/20260922-0204Z-1904PST-world-knowledge-evidence/example"
)
FILES = (
    "decision-capture.json",
    "world-knowledge-evidence.json",
    "manifest.json",
)
EXPECTED_CLAIM = "knox-telecommunications-outage-1993-07-02"
EXPECTED_SOURCE = "world/us-1993/knox-event.md"
EXPECTED_NAMESPACE = {
    "runId": "r12-knox-lived-source-example-v1",
    "county": "CountyR12Controlled",
    "personId": "actor",
    "eventId": "r12-knox-lived-source-example-v1/source-use/1",
    "hour": 48,
}
REPOSITORY = "https://github.com/ellyj3rain/sao"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Join.ContractError(message)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sealed(value: dict[str, Any]) -> dict[str, Any]:
    return Author.seal(value)


def unseal(value: Any, schema: str) -> dict[str, Any]:
    require(isinstance(value, dict) and value.get("schema") == schema
            and value.get("schemaVersion") == VERSION,
            f"requires {schema} version {VERSION}")
    content_hash = value.get("contentSha256")
    Author.hash_value(content_hash, f"{schema} contentSha256")
    body = dict(value)
    body.pop("contentSha256")
    require(Author.digest(body) == content_hash, f"{schema} content hash differs")
    return value


def git_bytes(root: Path, commit: str, relative: str) -> bytes:
    require(re.fullmatch(r"[a-f0-9]{40}", commit) is not None,
            "SAO source commit must be a full lowercase commit SHA")
    completed = subprocess.run(
        ["git", "-C", str(root), "show", f"{commit}:{relative}"],
        capture_output=True,
    )
    require(completed.returncode == 0,
            f"SAO source commit does not contain {relative}")
    return completed.stdout


def record_hashes(evidence: dict[str, Any]) -> dict[str, str]:
    rows = evidence.get("recordHashes")
    require(isinstance(rows, list) and rows, "SAO evidence has no record hashes")
    result: dict[str, str] = {}
    for row in rows:
        require(isinstance(row, dict) and set(row) == {"recordId", "sha256"},
                "SAO record hash entry is invalid")
        Author.identifier(row["recordId"], "SAO evidence recordId")
        Author.hash_value(row["sha256"], "SAO evidence record hash")
        require(row["recordId"] not in result, "duplicate SAO evidence recordId")
        result[row["recordId"]] = row["sha256"]
    return result


def validate_port(capture: Any, evidence: Any, manifest: Any,
                  file_bytes: dict[str, bytes]) -> None:
    require(isinstance(manifest, dict)
            and manifest.get("schema") == "sao-world-knowledge-evidence-manifest"
            and manifest.get("schemaVersion") == 1,
            "SAO evidence manifest schema differs")
    manifest_body = dict(manifest)
    manifest_hash = manifest_body.pop("contentSha256", None)
    Author.hash_value(manifest_hash, "SAO manifest contentSha256")
    require(Author.digest(manifest_body) == manifest_hash,
            "SAO manifest content hash differs")
    listed_files = manifest.get("files")
    require(isinstance(listed_files, dict)
            and set(listed_files) == {FILES[0], FILES[1]},
            "SAO manifest file set differs")
    for name in FILES[:2]:
        require(listed_files[name] == sha256_bytes(file_bytes[name]),
                f"SAO manifest hash differs for {name}")

    require(isinstance(capture, dict)
            and capture.get("schema") == "sao-source-decision-capture"
            and capture.get("schemaVersion") == 1
            and capture.get("status") == "observed"
            and capture.get("captureFailureCount") == 0
            and capture.get("eventCount") == 1
            and capture.get("attemptedEvents") == 1
            and capture.get("failures") in ({}, []),
            "SAO capture is incomplete or failed")
    events = capture.get("events")
    require(isinstance(events, list) and len(events) == 1,
            "SAO capture must contain one event")
    event = events[0]
    require(isinstance(evidence, dict)
            and evidence.get("schema") == "sao-world-knowledge-evidence"
            and evidence.get("schemaVersion") == 1
            and evidence.get("standing") == "produced-not-adjudicated",
            "SAO world-knowledge evidence schema or standing differs")
    require(evidence.get("eventSha256") == Author.digest(event),
            "SAO evidence event hash differs")
    namespace = evidence.get("namespace")
    expected_namespace = {
        "runId": event.get("runId"),
        "county": event.get("county"),
        "personId": event.get("decision", {}).get("person", {}).get("id"),
        "eventId": event.get("eventId"),
        "hour": event.get("decision", {}).get("hours"),
    }
    require(namespace == expected_namespace == EXPECTED_NAMESPACE,
            "SAO evidence namespace differs")
    person = event.get("decision", {}).get("person", {})
    choice = event.get("choice")
    require(person.get("id") == "actor" and person.get("name") == "Ada North"
            and person.get("age") == 31,
            "SAO frozen person differs from the reviewed example")
    require(isinstance(choice, dict) and choice == {
        "status": "selected", "optionId": "C:second:0",
        "owner": "SAO.SourceUse.chooseOption", "ratified": False,
        "authorship": "runtime-policy",
    }, "SAO controlled runtime choice differs")

    acquisition = evidence.get("acquisition")
    observation = evidence.get("retentionObservation")
    presence = evidence.get("presence")
    calendar = evidence.get("calendar")
    require(isinstance(acquisition, dict)
            and acquisition.get("claimId") == EXPECTED_CLAIM
            and acquisition.get("personId") == namespace["personId"]
            and acquisition.get("path") == "lived"
            and acquisition.get("carrier") == "county"
            and acquisition.get("access")
            == "area-wide-telephone-and-internet-outage"
            and acquisition.get("ageAtEvent") == 31
            and acquisition.get("acquiredHour") == -168
            and acquisition.get("retained") is True,
            "SAO acquisition identity differs")
    require(isinstance(observation, dict)
            and observation.get("acquisition") == acquisition
            and observation.get("personId") == namespace["personId"]
            and observation.get("asOfHour") == namespace["hour"]
            and observation.get("retained") is True,
            "SAO retention observation differs")
    require(isinstance(presence, dict)
            and presence.get("personId") == namespace["personId"]
            and acquisition.get("presenceRecordId") == presence.get("recordId")
            and presence.get("fromHour") == -192
            and presence.get("region") == "Muldraugh, KY",
            "SAO presence/acquisition binding differs")
    require(isinstance(calendar, dict)
            and calendar.get("claimEventHour") == acquisition.get("acquiredHour")
            and calendar.get("horizonHour") == namespace["hour"]
            and calendar.get("anchorHour") == 0
            and calendar.get("anchorAt") == "1993-07-09T00:00:00",
            "SAO calendar/acquisition binding differs")

    frozen = (event.get("decision", {}).get("person", {}).get("record", {})
              .get("worldKnowledge", {}).get("acquisitions"))
    require(isinstance(frozen, list) and frozen == [acquisition],
            "SAO frozen person does not contain the exact acquisition")
    hashes = record_hashes(evidence)
    for record in (calendar, presence, acquisition, observation):
        require(record.get("recordId") in hashes
                and hashes[record["recordId"]] == Author.digest(record),
                f"SAO record hash differs for {record.get('recordId')}")

    source = acquisition.get("source")
    require(isinstance(source, dict)
            and source.get("path") == EXPECTED_SOURCE
            and source.get("owner") == "Zomboid-Speakeasy",
            "SAO acquisition source identity differs")
    protected = Join.protected_artifacts().get(Join.canonical(Join.ROOT / EXPECTED_SOURCE))
    require(protected is not None and protected["standing"] == "approved-knowledge"
            and source.get("sha256") == protected["sha256"],
            "SAO acquisition source is not the protected document")
    source_lines = (Join.ROOT / EXPECTED_SOURCE).read_text(encoding="utf-8").splitlines()
    line = source.get("line")
    require(type(line) is int and 1 <= line <= len(source_lines),
            "SAO acquisition source line is outside the protected document")
    require(source.get("excerptSha256")
            == sha256_bytes(source_lines[line - 1].encode("utf-8")),
            "SAO acquisition excerpt hash differs from protected bytes")


def source_files(root: Path, commit: str) -> tuple[
        dict[str, bytes], dict[str, Any], dict[str, Any]]:
    values = {
        name: git_bytes(root, commit, f"{SOURCE_PATH}/{name}")
        for name in FILES
    }
    parsed = {name: Author.loads(value.decode("utf-8")) for name, value in values.items()}
    manifest = parsed["manifest.json"]
    source_hashes = manifest.get("sourceHashes")
    require(isinstance(source_hashes, dict) and source_hashes,
            "SAO manifest source hashes are absent")
    commit_hashes: dict[str, str] = {}
    normalizations: list[dict[str, str]] = []
    for relative, expected in source_hashes.items():
        Author.hash_value(expected, f"SAO source hash {relative}")
        if relative.startswith("installed/"):
            continue
        committed = git_bytes(root, commit, relative)
        committed_hash = sha256_bytes(committed)
        commit_hashes[relative] = committed_hash
        if committed_hash != expected:
            # C74's version machine wrote VERSION with CRLF before Git stored
            # its canonical LF blob. Admit only that exact, reversible text
            # normalization and preserve both hashes in the import receipt.
            converted = committed.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            require(relative == "VERSION" and sha256_bytes(converted) == expected,
                    f"SAO commit source hash differs for {relative}")
            normalizations.append({
                "path": relative,
                "commitSha256": committed_hash,
                "manifestSha256": expected,
                "normalization": "git-lf-blob-to-generator-crlf-checkout",
            })
    validate_port(parsed[FILES[0]], parsed[FILES[1]], manifest, values)
    return values, parsed, {
        "commitSourceHashes": commit_hashes,
        "sourceNormalizations": normalizations,
    }


def atomic_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(value)
    os.replace(temporary, path)


def import_port(root: Path, commit: str, destination: Path) -> dict[str, Any]:
    values, parsed, source_verification = source_files(root.resolve(), commit)
    for name in FILES:
        atomic_bytes(destination / "upstream" / name, values[name])
    manifest = parsed["manifest.json"]
    receipt = sealed({
        "schema": "speakeasy-sao-evidence-import",
        "schemaVersion": VERSION,
        "source": {
            "repository": REPOSITORY,
            "commit": commit,
            "path": SOURCE_PATH,
            "manifestSha256": sha256_bytes(values["manifest.json"]),
            "manifestContentSha256": manifest["contentSha256"],
        },
        "files": {name: sha256_bytes(values[name]) for name in FILES},
        "upstreamSourceHashes": manifest["sourceHashes"],
        **source_verification,
        "verification": {
            "commitFiles": "verified",
            "manifest": "verified",
            "eventAcquisitionBinding": "verified",
            "protectedSourceBinding": "verified",
            "installedRuntimeHashes": "recorded-upstream-not-reperformed",
        },
    })
    atomic_bytes(destination / "import.json",
                 json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    return receipt


def validate_import(destination: Path) -> dict[str, Any]:
    receipt = unseal(Author.read(destination / "import.json"),
                     "speakeasy-sao-evidence-import")
    require(set(receipt.get("files", {})) == set(FILES),
            "import receipt file set differs")
    values: dict[str, bytes] = {}
    parsed: dict[str, Any] = {}
    for name in FILES:
        path = destination / "upstream" / name
        require(path.is_file(), f"imported SAO file is missing: {name}")
        values[name] = path.read_bytes()
        require(receipt["files"][name] == sha256_bytes(values[name]),
                f"imported SAO file hash differs: {name}")
        parsed[name] = Author.loads(values[name].decode("utf-8"))
    require(receipt["source"]["manifestSha256"] == sha256_bytes(values["manifest.json"])
            and receipt["source"]["manifestContentSha256"]
            == parsed["manifest.json"].get("contentSha256"),
            "imported SAO manifest identity differs")
    commit_hashes = receipt.get("commitSourceHashes")
    require(isinstance(commit_hashes, dict) and commit_hashes,
            "import receipt commit source hashes are absent")
    normalizations = receipt.get("sourceNormalizations")
    require(normalizations == [{
        "path": "VERSION",
        "commitSha256": commit_hashes.get("VERSION"),
        "manifestSha256": parsed["manifest.json"]["sourceHashes"]["VERSION"],
        "normalization": "git-lf-blob-to-generator-crlf-checkout",
    }], "import receipt source normalization differs")
    validate_port(parsed[FILES[0]], parsed[FILES[1]], parsed[FILES[2]], values)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_subparsers(dest="command", required=True)
    create = command.add_parser("import")
    create.add_argument("--sao-root", required=True, type=Path)
    create.add_argument("--commit", required=True)
    create.add_argument("--out", required=True, type=Path)
    validate = command.add_parser("validate")
    validate.add_argument("--import-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "import":
            receipt = import_port(args.sao_root, args.commit, args.out)
            validate_import(args.out)
            print(f"imported SAO evidence {receipt['contentSha256']} to {args.out}")
        else:
            receipt = validate_import(args.import_dir)
            print(f"validated SAO evidence import {receipt['contentSha256']}")
    except (Join.ContractError, OSError, UnicodeError, ValueError) as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
