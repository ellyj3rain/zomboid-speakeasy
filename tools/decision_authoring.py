#!/usr/bin/env python3
"""Build auditable knowledge views and unratified choices over frozen events.

This is an evidence compiler, not an acquisition producer or approval authority.
The original capture, approved documents, and choices remain immutable.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

import cross_module_rows as Join

VERSION = 1
RECONSTRUCTION = "explicit-acquisition-1"
CHECKS = {"age", "carrier", "access", "retention"}
PATHS = {"read", "heard", "lived", "told"}
CLAIM_REVIEW_SCHEMA = "speakeasy-claim-extraction-review"
ACQUISITION_REVIEW_SCHEMA = "speakeasy-acquisition-adjudication"
RESOLVED_SOURCE_EXCLUSIONS = {"person-knowledge-not-reconstructed"}
ACQUISITION_CORRECTIONS = Path(__file__).resolve().parents[1] / "decisions/acquisition-corrections.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Join.ContractError(message)


def acquisition_correction(record: dict[str, Any], claim: dict[str, Any]) -> str | None:
    """Current applicability is separate from the integrity of a sealed review."""
    corrections = read(ACQUISITION_CORRECTIONS)
    require(corrections.get("schema") == "speakeasy-acquisition-corrections"
            and corrections.get("schemaVersion") == 1
            and isinstance(corrections.get("corrections"), list)
            and corrections["corrections"], "acquisition correction registry unavailable")
    for correction in corrections["corrections"]:
        require(isinstance(correction, dict) and correction.get("id")
                and correction.get("reason") and correction.get("revoked"),
                "invalid acquisition correction")
        exact = digest(record) == correction["revoked"]["acquisitionSha256"]
        basis = (claim["source"]["path"] == correction["sourcePath"]
                 and claim["source"]["excerptSha256"] == correction["sourceExcerptSha256"]
                 and record["path"] == correction["rejectedPath"])
        revoked = correction["revoked"].get("evidenceSha256")
        require(isinstance(revoked, list) and bool(revoked), "missing revoked evidence basis")
        for value in revoked:
            hash_value(value, "revoked acquisition evidence")
        supporting = list(record.get("evidence", []))
        for check in record.get("checks", {}).values():
            supporting.extend(check.get("evidence", []))
        revoked_basis = any(item.get("sha256") in revoked for item in supporting)
        if exact or basis or revoked_basis:
            return correction["id"] + ":" + correction["reason"]
    return None


def encoded(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, TypeError) as error:
        raise Join.ContractError(f"non-canonical JSON: {error}") from error


def digest(value: Any) -> str:
    return hashlib.sha256(encoded(value)).hexdigest()


def seal(value: dict[str, Any]) -> dict[str, Any]:
    output = copy.deepcopy(value)
    output["contentSha256"] = digest(output)
    return output


def unseal(value: Any, name: str) -> dict[str, Any]:
    schema(value, name)
    hash_value(value.get("contentSha256"), f"{name} contentSha256")
    body = copy.deepcopy(value)
    content_hash = body.pop("contentSha256")
    require(digest(body) == content_hash, f"{name} content hash differs")
    return value


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in output, f"duplicate JSON key: {key}")
        output[key] = value
    return output


def loads(text: str) -> Any:
    def invalid(value: str) -> None:
        raise Join.ContractError(f"non-finite JSON number: {value}")
    try:
        return json.loads(text, object_pairs_hook=strict_object,
                          parse_constant=invalid)
    except (ValueError, UnicodeError) as error:
        raise Join.ContractError(f"invalid JSON: {error}") from error


def read(path: Path) -> Any:
    return loads(path.read_text(encoding="utf-8"))


def schema(value: Any, name: str) -> None:
    require(isinstance(value, dict) and value.get("schema") == name
            and type(value.get("schemaVersion")) is int
            and value["schemaVersion"] == VERSION,
            f"requires {name} version {VERSION}")


def fields(value: Any, names: set[str], where: str) -> None:
    require(isinstance(value, dict) and set(value) == names,
            f"{where} requires exactly {', '.join(sorted(names))}")


def identifier(value: Any, where: str) -> None:
    require(Join.nonempty_string(value), f"{where} must be a nonempty string")


def hash_value(value: Any, where: str) -> None:
    require(isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value)
            is not None, f"{where} must be a lowercase SHA-256")


def reference(value: Any) -> None:
    fields(value, {"owner", "recordId", "sha256"}, "evidence reference")
    identifier(value["owner"], "evidence owner")
    identifier(value["recordId"], "evidence recordId")
    hash_value(value["sha256"], "evidence sha256")


def reviewer(value: Any) -> None:
    fields(value, {"kind", "id", "procedureSha256"}, "reviewer")
    require(value["kind"] in {"repository-review", "human"},
            "reviewer kind must be repository-review or human")
    identifier(value["id"], "reviewer id")
    hash_value(value["procedureSha256"], "reviewer procedureSha256")


def receipt_index(paths: list[Path] | None) -> dict[str, Any]:
    result: dict[str, Any] = {"claim": {}, "acquisition": {}, "hashes": []}
    seen_names: set[str] = set()
    for path in paths or []:
        require(path.name not in seen_names, "receipt filenames must be unique")
        seen_names.add(path.name)
        value = read(path)
        name = value.get("schema") if isinstance(value, dict) else None
        require(name in {CLAIM_REVIEW_SCHEMA, ACQUISITION_REVIEW_SCHEMA},
                "unsupported knowledge receipt schema")
        unseal(value, name)
        result["hashes"].append(Join.sha256(path))
        if name == CLAIM_REVIEW_SCHEMA:
            key = value.get("claimSha256")
            hash_value(key, "claim review claimSha256")
            require(key not in result["claim"], "duplicate claim extraction review")
            result["claim"][key] = value
        else:
            key = value.get("acquisitionSha256")
            hash_value(key, "acquisition adjudication acquisitionSha256")
            require(key not in result["acquisition"], "duplicate acquisition adjudication")
            result["acquisition"][key] = value
    result["hashes"].sort()
    return result


def instant(value: Any) -> datetime:
    require(isinstance(value, str) and re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value) is not None,
        "calendar instants require YYYY-MM-DDTHH:MM:SS in local game time")
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise Join.ContractError(f"invalid calendar instant: {value}") from error


def native_option_context(option: dict[str, Any], ns: dict[str, Any]) -> None:
    """Bind native SourceUse proofs to their actor and decision moment."""
    parameters = option["parameters"]
    require(parameters.get("actorId") == ns["personId"],
            "C65 option actor differs from namespace")
    private_kinds = ("private-source-revision", "private-source-inspection")
    admission_kinds = ("attempt-admission", "current-transfer-admission")
    private_seen = admission_seen = False
    for evidence in option["eligibility"]["evidence"]:
        kind = evidence.get("kind")
        if "actorId" in evidence or kind in private_kinds:
            require(evidence.get("actorId") == ns["personId"],
                    "C65 private evidence actor differs from namespace")
        # Source revision observations carry ticks, not county hours. Only the
        # explicit county-hour fields can be compared without inventing a map.
        if "atHours" in evidence or kind in ("attempt-admission", "private-source-inspection"):
            require(Join.finite_number(evidence.get("atHours"))
                    and evidence["atHours"] == ns["hour"],
                    "C65 option evidence time differs from namespace")
        if kind in private_kinds:
            private_seen = True
            require(evidence.get("sourceId") == parameters.get("sourceId")
                    and evidence.get("revision") == parameters.get("revision"),
                    "C65 private evidence source/revision differs from option")
        if kind in admission_kinds:
            admission_seen = True
            require(evidence.get("admission") == parameters.get("admission"),
                    "C65 admission evidence differs from option")
    require(private_seen and admission_seen, "C65 option lacks private/admission evidence")


def event_view(raw: dict[str, Any], path: Path, line: int) -> dict[str, Any]:
    """Read the native C65 envelope or a v3 SAO row; retain the raw hash."""
    if raw.get("schema") == "sao-source-decision-event":
        schema(raw, "sao-source-decision-event")
        decision = raw.get("decision")
        require(isinstance(decision, dict), "C65 decision is missing")
        require(decision.get("eventType") == "source-use", "unsupported C65 decision type")
        person, situation = decision.get("person"), decision.get("situation")
        require(isinstance(person, dict) and isinstance(situation, dict),
                "C65 person/situation is missing")
        ns = {"runId": raw.get("runId"), "county": raw.get("county"),
              "personId": person.get("id"), "eventId": raw.get("eventId"),
              "hour": decision.get("hours")}
        for field in ("runId", "county", "eventId"):
            require(decision.get(field) == ns[field],
                    f"C65 decision {field} differs from envelope")
        offer = situation.get("sourceOffer")
        require(isinstance(offer, dict)
                and offer.get("actorId") == ns["personId"]
                and offer.get("atHours") == ns["hour"],
                "C65 offered actor/time differs from namespace")
        options = offer.get("options")
        conditioning = raw.get("conditioning")
        require(isinstance(conditioning, dict)
                and conditioning.get("status") == "ineligible"
                and isinstance(conditioning.get("reasons"), list)
                and conditioning["reasons"]
                and all(Join.nonempty_string(x) for x in conditioning["reasons"]),
                "C65 capture must retain its ineligible conditioning")
        exclusions = conditioning["reasons"]
        observation = raw.get("observation")
        require(isinstance(observation, dict)
                and observation.get("decisionHours") == ns["hour"]
                and Join.finite_number(observation.get("atHours"))
                and Join.finite_number(ns["hour"])
                and observation["atHours"] >= ns["hour"],
                "C65 observation clock differs from the decision")
        require(isinstance(raw.get("result"), dict)
                and Join.nonempty_string(raw["result"].get("status")), "C65 result is missing")
        runtime = raw.get("choice")
        require(isinstance(runtime, dict) and runtime.get("status") in ("selected", "declined"),
                "C65 runtime choice is missing")
        if runtime["status"] == "selected":
            require(runtime.get("ratified") is False
                    and runtime.get("authorship") == "runtime-policy"
                    and Join.nonempty_string(runtime.get("optionId")),
                    "C65 runtime choice must retain its unratified standing")
        else:
            require("optionId" not in runtime, "declined C65 choice names an option")
    else:
        Join.validate_sao_row(raw, path, line)
        ns = raw["namespace"]
        person, situation, options = raw["person"], raw["situation"], raw["options"]
        exclusions = raw["conditioning"]["exclusions"]
    Join.namespace({"namespace": ns}, path, line)
    require(set(ns) == set(Join.NAMESPACE_FIELDS), "namespace has extra fields")
    require(isinstance(person, dict) and person.get("id") == ns["personId"],
            "person differs from namespace")
    require(isinstance(situation, dict) and situation.get("county") == ns["county"]
            and situation.get("hour") == ns["hour"],
            "situation differs from namespace")
    # Both adapters admit the same original-context surface. Native captures
    # nest that surface inside decision, but cannot acquire join additions.
    Join.validate_unenriched_context({**raw, "person": person, "situation": situation}, path, line)
    if raw.get("schema") == "sao-source-decision-event":
        Join.validate_unenriched_context(raw["decision"], path, line)
    require(isinstance(options, list) and options, "event has no offered options")
    # Option validation is independent of the runtime choice, which may decline.
    Join.validate_options({"options": options,
                           "choice": {"optionId": options[0].get("id")
                                      if isinstance(options[0], dict) else None}},
                          path, line)
    if raw.get("schema") == "sao-source-decision-event":
        for option in options:
            native_option_context(option, ns)
    runtime = raw.get("choice")
    require(isinstance(runtime, dict), "event choice is missing")
    if runtime.get("optionId") is not None:
        require(runtime["optionId"] in {x["id"] for x in options},
                "runtime choice was not offered")
    return {"namespace": copy.deepcopy(ns), "eventSha256": digest(raw),
            "person": copy.deepcopy(person), "situation": copy.deepcopy(situation),
            "options": copy.deepcopy(options), "sourceExclusions": copy.deepcopy(exclusions)}


def events(path: Path) -> dict[tuple[Any, ...], dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    try:
        root = loads(text)
    except Join.ContractError:
        raw_rows = [loads(line) for line in text.splitlines() if line.strip()]
    else:
        if isinstance(root, dict) and root.get("schema") == "sao-source-decision-capture":
            schema(root, "sao-source-decision-capture")
            require(root.get("status") == "observed"
                    and root.get("captureFailureCount") == 0
                    and root.get("failures") in ([], {}), "source capture is unavailable or failed")
            raw_rows = root.get("events")
            require(isinstance(raw_rows, list)
                    and root.get("eventCount") == len(raw_rows)
                    and root.get("attemptedEvents") == len(raw_rows),
                    "source capture accounting is incomplete")
        else:
            raw_rows = [root]
    require(bool(raw_rows), "capture contains no events")
    result = {}
    for line, raw in enumerate(raw_rows, 1):
        require(isinstance(raw, dict), "each event must be an object")
        event = event_view(raw, path, line)
        key = Join.namespace(event, path, line)
        require(key not in result, "duplicate full event namespace")
        result[key] = event
    return result


def protected_excerpt(value: Any, protected: dict[str, Any]) -> None:
    fields(value, {"role", "path", "sha256", "startLine", "endLine",
                   "excerptSha256"}, "claim review rule source")
    identifier(value["role"], "claim review rule source role")
    identifier(value["path"], "claim review rule source path")
    hash_value(value["sha256"], "claim review rule source sha256")
    hash_value(value["excerptSha256"], "claim review rule source excerptSha256")
    path = Join.ROOT / value["path"]
    artifact = protected.get(Join.canonical(path))
    require(artifact is not None and artifact["standing"] == "approved-knowledge"
            and value["sha256"] == artifact["sha256"],
            "claim review rule source must be a hash-matched protected approved document")
    lines = path.read_text(encoding="utf-8").splitlines()
    start, end = value["startLine"], value["endLine"]
    require(type(start) is int and type(end) is int
            and 1 <= start <= end <= len(lines),
            "claim review rule source range is outside document")
    excerpt = "\n".join(lines[start - 1:end])
    require(hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
            == value["excerptSha256"],
            "claim review rule source excerpt hash differs")


def claim_review(receipt: Any, claim: dict[str, Any],
                 protected: dict[str, Any]) -> None:
    fields(receipt, {"schema", "schemaVersion", "claimId", "claimSha256",
                     "source", "ruleSources", "review", "reviewer", "findings",
                     "contentSha256"}, "claim extraction review")
    require(receipt["claimId"] == claim["id"]
            and receipt["claimSha256"] == digest(claim),
            "claim extraction review binds a different claim")
    require(receipt["source"] == claim["source"],
            "claim extraction review source differs")
    rule_sources = receipt["ruleSources"]
    require(isinstance(rule_sources, list) and rule_sources,
            "claim extraction review needs rule sources")
    roles: set[str] = set()
    for rule_source in rule_sources:
        protected_excerpt(rule_source, protected)
        require(rule_source["role"] not in roles,
                "claim extraction review rule-source roles must be unique")
        roles.add(rule_source["role"])
    review = receipt["review"]
    fields(review, {"status", "textBoundary", "knowableAt", "carrier",
                    "acquisitionRules", "confidence"}, "claim extraction review body")
    require(review["status"] == "reviewed"
            and review["textBoundary"] == "literal-substring",
            "claim extraction review standing differs")
    require(review["knowableAt"] == claim["knowableAt"]
            and review["carrier"] == claim["carrier"]
            and review["acquisitionRules"] == claim["acquisitionRules"],
            "claim extraction review boundary differs")
    confidence = review["confidence"]
    fields(confidence, {"value", "basis", "sourceLineHasLiteralConfidence"},
           "claim confidence review")
    require(confidence["value"] == claim["confidence"]
            and isinstance(confidence["sourceLineHasLiteralConfidence"], bool),
            "claim confidence review differs")
    identifier(confidence["basis"], "claim confidence review basis")
    reviewer(receipt["reviewer"])
    require(isinstance(receipt["findings"], list) and receipt["findings"]
            and all(Join.nonempty_string(item) for item in receipt["findings"]),
            "claim extraction review needs findings")


def acquisition_review(receipt: Any, record: dict[str, Any], claim: dict[str, Any],
                       ns: dict[str, Any], event_sha256: str) -> None:
    require(acquisition_correction(record, claim) is None,
            "acquisition adjudication superseded by current correction")
    fields(receipt, {"schema", "schemaVersion", "claimId", "claimSha256",
                     "acquisitionSha256", "namespace", "eventSha256",
                     "importEvidence", "checks", "status", "reviewer",
                     "limitations", "contentSha256"},
           "acquisition adjudication")
    require(receipt["claimId"] == claim["id"]
            and receipt["claimSha256"] == digest(claim),
            "acquisition adjudication binds a different claim")
    require(receipt["acquisitionSha256"] == digest(record),
            "acquisition adjudication binds different evidence")
    require(receipt["namespace"] == ns and receipt["eventSha256"] == event_sha256,
            "acquisition adjudication event differs")
    reference(receipt["importEvidence"])
    require(receipt["checks"] == record["checks"],
            "acquisition adjudication checks differ")
    require(receipt["status"] == "adjudicated", "acquisition standing differs")
    reviewer(receipt["reviewer"])
    require(isinstance(receipt["limitations"], list) and receipt["limitations"]
            and all(Join.nonempty_string(item) for item in receipt["limitations"]),
            "acquisition adjudication needs limitations")


def source_claim(claim: Any, protected: dict[str, Any],
                 review_receipt: dict[str, Any] | None = None) -> None:
    fields(claim, {"id", "text", "confidence", "knowableAt", "carrier",
                   "acquisitionRules", "source"}, "claim")
    for name in ("id", "text", "carrier"):
        identifier(claim[name], f"claim {name}")
    require(isinstance(claim["confidence"], str)
            and claim["confidence"] in {"LOW", "MEDIUM", "HIGH"}, "unknown confidence")
    instant(claim["knowableAt"])
    rules = claim["acquisitionRules"]
    require(isinstance(rules, list) and rules
            and all(isinstance(x, str) and x in PATHS for x in rules)
            and len(set(rules)) == len(rules), "invalid acquisition rules")
    source = claim["source"]
    fields(source, {"path", "sha256", "line", "excerptSha256"}, "claim source")
    identifier(source["path"], "claim source path")
    hash_value(source["sha256"], "claim source sha256")
    hash_value(source["excerptSha256"], "claim excerpt sha256")
    path = Join.ROOT / source["path"]
    artifact = protected.get(Join.canonical(path))
    require(artifact is not None and artifact["standing"] == "approved-knowledge"
            and source["sha256"] == artifact["sha256"],
            "claim source must be a hash-matched protected approved document")
    lines = path.read_text(encoding="utf-8").splitlines()
    line = source["line"]
    require(isinstance(line, int) and not isinstance(line, bool) and 1 <= line <= len(lines),
            "claim source line is outside document")
    excerpt = lines[line - 1]
    require(hashlib.sha256(excerpt.encode("utf-8")).hexdigest() == source["excerptSha256"],
            "claim source excerpt hash differs")
    require(claim["text"] in excerpt and claim["carrier"] in excerpt,
            "claim text/carrier must occur literally in the source line")
    literal_confidence = re.search(
        r"\|\s*" + claim["confidence"] + r"\b", excerpt) is not None
    if review_receipt is not None:
        claim_review(review_receipt, claim, protected)
        declared = review_receipt["review"]["confidence"][
            "sourceLineHasLiteralConfidence"]
        require(declared == literal_confidence,
                "claim confidence review misstates the source line")
    require(literal_confidence or review_receipt is not None,
            "claim confidence is absent from source line and has no review")
    require(claim["confidence"] == "LOW" or not re.search(r"\bLOW\b", excerpt),
            "LOW source material cannot be promoted")


def evidence_reason(record: Any, claim: dict[str, Any], ns: dict[str, Any],
                    calendar: dict[str, Any]) -> str | None:
    fields(record, {"claimId", "claimSha256", "namespace", "acquiredHour", "asOfHour",
                    "path", "retained", "checks", "evidence"}, "acquisition")
    require(record["claimId"] == claim["id"] and record["claimSha256"] == digest(claim),
            "acquisition claim hash differs")
    Join.namespace(record, Path("acquisition"), 1)
    require(set(record["namespace"]) == set(Join.NAMESPACE_FIELDS), "acquisition namespace has extra fields")
    require(Join.finite_number(record["acquiredHour"])
            and Join.finite_number(record["asOfHour"]), "acquisition hours must be finite")
    require(isinstance(record["path"], str) and record["path"] in PATHS
            and isinstance(record["retained"], bool),
            "invalid acquisition path/retention")
    require(isinstance(record["evidence"], list) and record["evidence"],
            "acquisition needs evidence references")
    for item in record["evidence"]:
        reference(item)
    require(isinstance(record["checks"], dict) and set(record["checks"]) == CHECKS,
            "acquisition requires age, carrier, access and retention checks")
    for check in record["checks"].values():
        fields(check, {"status", "evidence"}, "acquisition check")
        require(isinstance(check["status"], str)
                and check["status"] in {"supported", "unsupported", "unknown"}, "invalid check status")
        require(isinstance(check["evidence"], list), "check evidence must be a list")
        if check["status"] == "supported":
            require(bool(check["evidence"]), "supported checks need evidence")
        for item in check["evidence"]:
            reference(item)
    correction = acquisition_correction(record, claim)
    if correction:
        return correction
    if record["namespace"] != ns:
        return "other-person-or-event"
    if record["acquiredHour"] > ns["hour"] or record["asOfHour"] != ns["hour"]:
        return "outside-decision-time"
    acquired_at = instant(calendar["anchorAt"]) + timedelta(
        hours=record["acquiredHour"] - calendar["anchorHour"])
    if acquired_at < instant(claim["knowableAt"]):
        return "acquisition-before-knowable-time"
    if record["path"] not in claim["acquisitionRules"]:
        return "unavailable-acquisition-path"
    if not record["retained"]:
        return "not-retained"
    if any(check["status"] != "supported" for check in record["checks"].values()):
        return "person-checks-incomplete"
    return None


def compile_view(capture_path: Path, bundle_path: Path,
                 receipt_paths: list[Path] | None = None) -> dict[str, Any]:
    protected = Join.protected_artifacts()
    receipts = receipt_index(receipt_paths)
    captured = events(capture_path)
    bundle = read(bundle_path)
    schema(bundle, "speakeasy-knowledge-input")
    fields(bundle, {"schema", "schemaVersion", "namespace", "eventSha256",
                    "calendar", "claims", "acquisitions"}, "knowledge input")
    key = Join.namespace(bundle, bundle_path, 1)
    require(set(bundle["namespace"]) == set(Join.NAMESPACE_FIELDS), "namespace has extra fields")
    event = captured.get(key)
    require(event is not None and event["eventSha256"] == bundle["eventSha256"],
            "knowledge input namespace/event hash does not match capture")
    ns, calendar = event["namespace"], bundle["calendar"]
    fields(calendar, {"anchorHour", "anchorAt", "horizonHour", "evidence"}, "calendar")
    require(Join.finite_number(calendar["anchorHour"])
            and Join.finite_number(calendar["horizonHour"])
            and calendar["horizonHour"] <= ns["hour"], "calendar horizon exceeds decision")
    anchor = instant(calendar["anchorAt"])
    reference(calendar["evidence"])
    horizon = min(anchor + timedelta(hours=calendar["horizonHour"] - calendar["anchorHour"]),
                  datetime(1993, 12, 31, 23, 59, 59))
    require(isinstance(bundle["claims"], list) and isinstance(bundle["acquisitions"], list),
            "claims/acquisitions must be lists")
    claims = {}
    claim_reviewed: dict[str, bool] = {}
    for claim in bundle["claims"]:
        claim_hash = digest(claim)
        review_receipt = receipts["claim"].get(claim_hash)
        source_claim(claim, protected, review_receipt)
        require(claim["id"] not in claims, "duplicate claim id")
        claims[claim["id"]] = claim
        claim_reviewed[claim["id"]] = review_receipt is not None
    acquisitions: dict[str, list[tuple[Any, str | None, bool]]] = {}
    for record in bundle["acquisitions"]:
        require(isinstance(record, dict) and isinstance(record.get("claimId"), str)
                and record["claimId"] in claims,
                "acquisition refers to an unknown claim")
        reason = evidence_reason(record, claims[record["claimId"]], ns, calendar)
        adjudication = receipts["acquisition"].get(digest(record))
        if adjudication is not None and acquisition_correction(record, claims[record["claimId"]]) is None:
            acquisition_review(adjudication, record, claims[record["claimId"]],
                               ns, event["eventSha256"])
        acquisitions.setdefault(record["claimId"], []).append(
            (record, reason, adjudication is not None))
    available, excluded = [], []
    for identity, claim in sorted(claims.items()):
        reason = None
        if claim["confidence"] == "LOW":
            reason = "low-confidence"
        elif instant(claim["knowableAt"]) > horizon:
            reason = "future-to-person-horizon"
        candidates = acquisitions.get(identity, [])
        valid_entries = [(record, adjudicated)
                         for record, why, adjudicated in candidates if why is None]
        valid = [record for record, _ in valid_entries]
        if reason is None and not valid:
            reason = ("missing-acquisition" if not candidates else
                      ";".join(sorted({why for _, why, _ in candidates})))
        if reason:
            # Excluded claim text is deliberately absent from the conditioning surface.
            excluded.append({"claimId": identity, "claimSha256": digest(claim), "reason": reason})
        else:
            available.append({"claim": copy.deepcopy(claim),
                              "claimSha256": digest(claim),
                              "acquisitions": sorted(copy.deepcopy(valid), key=digest),
                              "sourceStanding": "approved-knowledge",
                              "extractionStanding": ("reviewed"
                                                     if claim_reviewed[identity]
                                                     else "unreviewed"),
                              "acquisitionStanding": ("adjudicated"
                                                       if all(x for _, x in valid_entries)
                                                       else "unadjudicated")})
    # Source exclusions describe what the runtime capture itself did not yet
    # contain. This compiler preserves those bytes under sourceExclusions, but
    # removes limitations that the explicit reconstruction has now resolved
    # from the active conditioning reasons.
    exclusions = set(event["sourceExclusions"]) - RESOLVED_SOURCE_EXCLUSIONS
    exclusions.add("knowledge-coverage-not-established")
    if any(row["extractionStanding"] == "unreviewed" for row in available):
        exclusions.add("claim-extraction-not-reviewed")
    if any(row["acquisitionStanding"] == "unadjudicated" for row in available):
        exclusions.add("acquisition-evidence-not-adjudicated")
    return seal({"schema": "speakeasy-knowledge-view", "schemaVersion": VERSION,
                 "reconstructionVersion": RECONSTRUCTION, **event,
                 "calendar": copy.deepcopy(calendar), "availableClaims": available,
                 "excludedClaims": excluded,
                 "provenance": {"captureSha256": Join.sha256(capture_path),
                                "inputSha256": Join.sha256(bundle_path),
                                "protectedManifestSha256": Join.sha256(Join.PROTECTED_MANIFEST),
                                "receiptSha256": receipts["hashes"],
                                "acquisitionCorrectionsSha256": Join.sha256(ACQUISITION_CORRECTIONS)},
                 "conditioning": {"status": "ineligible",
                                  "exclusions": sorted(exclusions)}})


def proposal(capture_path: Path, bundle_path: Path, view_path: Path,
             request_path: Path,
             receipt_paths: list[Path] | None = None) -> dict[str, Any]:
    expected = compile_view(capture_path, bundle_path, receipt_paths)
    view = read(view_path)
    require(view == expected, "knowledge view differs from reproducible source evidence")
    request = read(request_path)
    schema(request, "speakeasy-choice-request")
    fields(request, {"schema", "schemaVersion", "namespace", "eventSha256",
                     "knowledgeViewSha256", "optionId", "optionSha256", "author", "rationale"},
           "choice request (approval is not an authoring field)")
    require(request["namespace"] == view["namespace"]
            and request["eventSha256"] == view["eventSha256"]
            and request["knowledgeViewSha256"] == view["contentSha256"],
            "choice namespace/event/knowledge view differs")
    selected = next((option for option in view["options"]
                     if option["id"] == request["optionId"]), None)
    require(selected is not None and digest(selected) == request["optionSha256"],
            "choice option identity/content differs from the frozen offer")
    fields(request["author"], {"kind", "id", "version", "promptSha256"}, "author")
    require(isinstance(request["author"]["kind"], str)
            and request["author"]["kind"] in {"human", "model"}, "author kind must be human/model")
    for name in ("id", "version"):
        identifier(request["author"][name], f"author {name}")
    hash_value(request["author"]["promptSha256"], "author promptSha256")
    identifier(request["rationale"], "rationale")
    return seal({"schema": "speakeasy-choice-proposal", "schemaVersion": VERSION,
                 "namespace": copy.deepcopy(view["namespace"]),
                 "eventSha256": view["eventSha256"],
                 "knowledgeViewSha256": view["contentSha256"],
                 "choice": {"optionId": selected["id"], "optionSha256": digest(selected)},
                 "author": copy.deepcopy(request["author"]), "rationale": request["rationale"],
                 "approval": {"status": "unratified"},
                 "conditioning": {"status": "ineligible", "exclusions": sorted(set(
                     view["conditioning"]["exclusions"] + ["authored-choice-not-ratified"]))},
                 "provenance": {**view["provenance"], "requestSha256": Join.sha256(request_path)}})


def publish(output: Path, value: dict[str, Any], inputs: list[Path]) -> None:
    protected = Join.protected_artifacts()
    key = Join.canonical(output)
    forbidden = {Join.canonical(path) for path in inputs + [Join.PROTECTED_MANIFEST, ACQUISITION_CORRECTIONS]}
    require(key not in forbidden and key not in protected,
            "output cannot replace an input, protected artifact, or protected manifest")
    Join.atomic_write(output, [value])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--capture", type=Path, required=True)
    for command in ("view", "propose"):
        child = commands.add_parser(command)
        child.add_argument("--capture", type=Path, required=True)
        child.add_argument("--knowledge", type=Path, required=True)
        child.add_argument("--receipt", type=Path, action="append", default=[])
        child.add_argument("--out", type=Path, required=True)
        if command == "propose":
            child.add_argument("--view", type=Path, required=True)
            child.add_argument("--request", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            for event in events(args.capture).values():
                print(encoded({"namespace": event["namespace"],
                               "eventSha256": event["eventSha256"],
                               "options": [{"optionId": x["id"], "optionSha256": digest(x)}
                                           for x in event["options"]]}).decode("utf-8"))
            return 0
        inputs = [args.capture, args.knowledge, *args.receipt]
        if args.command == "view":
            value = compile_view(args.capture, args.knowledge, args.receipt)
        else:
            inputs += [args.view, args.request]
            value = proposal(args.capture, args.knowledge, args.view,
                             args.request, args.receipt)
        publish(args.out, value, inputs)
    except (Join.ContractError, OSError, OverflowError) as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 2
    print(f"wrote {value['schema']} {value['contentSha256']} to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
