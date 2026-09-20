#!/usr/bin/env python3
"""Executable controls for the version 3 cross-module join."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import tempfile
import unittest

import cross_module_rows as Join


def namespace(run="run-a", county="County001", person="person-1",
              event="event-1", hour=24):
    return {
        "runId": run,
        "county": county,
        "personId": person,
        "eventId": event,
        "hour": hour,
    }


def sao_row(ns=None):
    ns = ns or namespace()
    return {
        "schema": Join.SAO_SCHEMA,
        "schemaVersion": Join.VERSION,
        "namespace": ns,
        "person": {"id": ns["personId"], "traits": {"nerve": 0.4}},
        "situation": {"county": ns["county"], "hour": ns["hour"]},
        "options": [{
            "id": "standing:watch",
            "owner": "SAO.Standing.perform",
            "parameters": {"role": "watch"},
            "eligibility": {
                "status": "eligible",
                "evidence": [{"kind": "owner-probe", "revision": 7}],
            },
        }],
        "choice": {"optionId": "standing:watch", "word": "watcher"},
        "conditioning": {
            "status": "eligible",
            "decisionHour": ns["hour"],
            "latestEvidenceHour": ns["hour"],
            "exclusions": [],
        },
        "citation": {
            "county": ns["county"],
            "person": ns["personId"],
            "hour": ns["hour"],
        },
    }


def zao_row(ns=None, terminal="alive"):
    ns = ns or namespace()
    return {
        "schema": Join.ZAO_SCHEMA,
        "schemaVersion": Join.VERSION,
        "namespace": ns,
        "asOfHour": ns["hour"],
        "pathogen": {"terminalState": terminal},
        "visibleForms": [{"personId": "seen-1", "form": "afflicted"}],
    }


def write_jsonl(path: pathlib.Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows),
                    encoding="utf-8")


class CrossModuleRowsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix="speakeasy-join-controls-")
        self.root = pathlib.Path(self.temporary.name)
        self.sao = self.root / "sao.jsonl"
        self.zao = self.root / "zao.jsonl"
        self.out = self.root / "joined.jsonl"

    def tearDown(self):
        self.temporary.cleanup()

    def write_valid(self, sao=None, zao=None):
        write_jsonl(self.sao, sao or [sao_row()])
        write_jsonl(self.zao, zao or [zao_row()])

    def test_full_namespace_keeps_same_person_hour_counties_distinct(self):
        first = namespace()
        second = namespace(run="run-b", county="County099", event="event-9")
        self.write_valid(
            [sao_row(first), sao_row(second)],
            [zao_row(first, "alive"), zao_row(second, "afflicted")])
        self.assertEqual(Join.export_rows(self.sao, self.zao, self.out), 2)
        rows = [json.loads(line) for line in self.out.read_text().splitlines()]
        states = {row["namespace"]["county"]:
                  row["person"]["pathogen"]["terminalState"] for row in rows}
        self.assertEqual(states, {"County001": "alive", "County099": "afflicted"})
        self.assertEqual(rows[0]["crossModule"]["schemaVersion"], 3)
        self.assertEqual(rows[0]["crossModule"]["saoSha256"],
                         hashlib.sha256(self.sao.read_bytes()).hexdigest())

    def test_late_invalid_row_leaves_existing_output_unchanged(self):
        invalid = sao_row(namespace(event="event-2", person="person-2"))
        invalid["options"] = ["watch"]
        write_jsonl(self.sao, [sao_row(), invalid])
        write_jsonl(self.zao, [zao_row(), zao_row(invalid["namespace"])])
        self.out.write_bytes(b"existing-output\n")
        with self.assertRaises(Join.ContractError):
            Join.export_rows(self.sao, self.zao, self.out)
        self.assertEqual(self.out.read_bytes(), b"existing-output\n")

    def test_invalid_input_does_not_create_output_parent(self):
        invalid = sao_row()
        invalid["conditioning"]["latestEvidenceHour"] = 25
        write_jsonl(self.sao, [invalid])
        write_jsonl(self.zao, [zao_row()])
        out = self.root / "absent" / "joined.jsonl"
        with self.assertRaises(Join.ContractError):
            Join.export_rows(self.sao, self.zao, out)
        self.assertFalse(out.parent.exists())

    def test_duplicate_and_unmatched_namespaces_refuse(self):
        self.write_valid([sao_row(), copy.deepcopy(sao_row())], [zao_row()])
        with self.assertRaisesRegex(Join.ContractError, "duplicate full namespace"):
            Join.export_rows(self.sao, self.zao, self.out)
        other = namespace(run="run-extra", event="event-extra")
        self.write_valid([sao_row()], [zao_row(), zao_row(other)])
        with self.assertRaisesRegex(Join.ContractError, "unmatched ZAO state"):
            Join.export_rows(self.sao, self.zao, self.out)

    def test_inputs_and_protected_artifacts_cannot_be_destinations(self):
        self.write_valid()
        original = self.sao.read_bytes()
        with self.assertRaisesRegex(Join.ContractError, "differ from both inputs"):
            Join.export_rows(self.sao, self.zao, self.sao)
        self.assertEqual(self.sao.read_bytes(), original)

        protected = Join.ROOT / "decisions" / "work-words.jsonl"
        protected_hash = hashlib.sha256(protected.read_bytes()).hexdigest()
        with self.assertRaisesRegex(Join.ContractError, "protected ratified-intent"):
            Join.export_rows(self.sao, self.zao, protected)
        self.assertEqual(hashlib.sha256(protected.read_bytes()).hexdigest(),
                         protected_hash)

    def test_version_two_and_bare_options_refuse(self):
        historical_sao = Join.ROOT / "decisions" / "work-words.jsonl"
        historical_zao = (Join.ROOT / "decisions" / "cross-module" /
                          "work-words.zao-state.jsonl")
        with self.assertRaisesRegex(Join.ContractError, "schema version 3"):
            Join.export_rows(historical_sao, historical_zao, self.out)
        self.assertFalse(self.out.exists())

        invalid = sao_row()
        invalid["options"] = ["watch", "scout"]
        self.write_valid([invalid], [zao_row()])
        with self.assertRaisesRegex(Join.ContractError, "not a label"):
            Join.export_rows(self.sao, self.zao, self.out)

    def test_atomic_replace_failure_preserves_prior_output(self):
        self.write_valid()
        rows = Join.joined_rows(self.sao, self.zao, self.out)
        self.out.write_bytes(b"prior\n")
        original = Join.os.replace
        Join.os.replace = lambda source, target: (_ for _ in ()).throw(
            OSError("controlled replace failure"))
        try:
            with self.assertRaises(OSError):
                Join.atomic_write(self.out, rows)
        finally:
            Join.os.replace = original
        self.assertEqual(self.out.read_bytes(), b"prior\n")
        self.assertEqual(list(self.root.glob(".joined.jsonl.*.tmp")), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
