#!/usr/bin/env python3
"""Small bounded HTTP client for publishing durable Mousecat review work."""
from __future__ import annotations

import json
from urllib import error, parse, request


PROTOCOL = "2025-06-18"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class MousecatError(RuntimeError):
    def __init__(self, message, *, code=None, value=None):
        super().__init__(message)
        self.code = code
        self.value = value


def endpoint(value: str) -> str:
    parsed = parse.urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Mousecat endpoint must use http or https")
    path = parsed.path.rstrip("/")
    if not path.endswith("/mcp"):
        path += "/mcp"
    return parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _body(response, expected_id):
    raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise MousecatError("Mousecat response exceeds the byte limit")
    if not raw:
        return None
    text = raw.decode("utf-8")
    if "text/event-stream" in response.headers.get("content-type", "").lower():
        for event in text.replace("\r\n", "\n").split("\n\n"):
            data = "\n".join(line[5:].lstrip() for line in event.splitlines()
                             if line.startswith("data:"))
            if data:
                value = json.loads(data)
                if value.get("id") == expected_id:
                    return value
        return None
    return json.loads(text)


def _post(url, payload, session_id=None, timeout=5):
    headers = {"content-type": "application/json",
               "accept": "application/json, text/event-stream",
               "mcp-protocol-version": PROTOCOL}
    if session_id:
        headers["mcp-session-id"] = session_id
    call = request.Request(url, data=json.dumps(payload, ensure_ascii=False,
                                                allow_nan=False).encode("utf-8"),
                           headers=headers, method="POST")
    try:
        response = request.urlopen(call, timeout=timeout)
    except error.HTTPError as failure:
        raw = failure.read(4096).decode("utf-8", errors="replace")
        raise MousecatError(f"Mousecat HTTP {failure.code}: {raw}") from failure
    except error.URLError as failure:
        raise MousecatError("Mousecat service is unavailable") from failure
    with response:
        value = _body(response, payload.get("id"))
        issued = response.headers.get("mcp-session-id")
    if payload.get("id") is not None:
        if not isinstance(value, dict) or value.get("jsonrpc") != "2.0" or value.get("id") != payload["id"]:
            raise MousecatError("Mousecat returned an uncorrelated response")
        if value.get("error"):
            remote = value["error"]
            raise MousecatError(remote.get("message", "Mousecat JSON-RPC error"),
                                code=remote.get("code"), value=remote)
    return value, issued


def _close(url, session_id, timeout):
    call = request.Request(url, headers={"mcp-session-id": session_id,
        "mcp-protocol-version": PROTOCOL}, method="DELETE")
    try:
        with request.urlopen(call, timeout=timeout):
            return
    except (error.HTTPError, error.URLError):
        # The interaction is durable in Mousecat; transport cleanup is not an
        # authority boundary and cannot make an accepted review disappear.
        return


def invoke_skill(url: str, packet: dict, timeout=5) -> dict:
    """Queue one invocation and return its path-free Mousecat receipt."""
    url = endpoint(url)
    initialized, session_id = _post(url, {"jsonrpc": "2.0", "id": 1,
        "method": "initialize", "params": {"protocolVersion": PROTOCOL,
        "clientInfo": {"name": "speakeasy-review-outbox", "version": "1"},
        "capabilities": {}}}, timeout=timeout)
    if not session_id or initialized.get("result", {}).get("protocolVersion") != PROTOCOL:
        raise MousecatError("Mousecat did not establish the expected MCP session")
    try:
        _post(url, {"jsonrpc": "2.0", "method": "notifications/initialized"},
              session_id, timeout)
        response, _ = _post(url, {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "mousecat.skill", "arguments": packet}}, session_id, timeout)
        result = response.get("result", {})
        value = result.get("structuredContent")
        if not isinstance(value, dict):
            raise MousecatError("Mousecat tool response omitted structured content")
        if result.get("isError") or value.get("ok") is False:
            code = value.get("code")
            if code == "skill-continuation-token-required" and value.get("interactionId"):
                return {"schema": "speakeasy-mousecat-review-queue/1",
                        "status": "already-queued", "interactionId": value["interactionId"]}
            raise MousecatError(code or "Mousecat rejected the review", code=code, value=value)
        interaction_id = value.get("interactionId") or value.get("result", {}).get("interactionId")
        if not isinstance(interaction_id, str) or not interaction_id:
            raise MousecatError("Mousecat review receipt omitted interaction identity")
        return {"schema": "speakeasy-mousecat-review-queue/1",
                "status": "queued", "interactionId": interaction_id}
    finally:
        _close(url, session_id, timeout)
