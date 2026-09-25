#!/usr/bin/env python3
"""Determinism, precision and corruption controls for Record 67 export."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

import coordination_native_bundle as Native


class CoordinationNativeBundleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = Native.output_files()
        cls.manifest = json.loads(cls.files["manifest.json"].decode("utf-8"))

    def test_bundle_contract_and_all_twenty_rows(self):
        contract = Native.inspect_bundle(self.files["coordination.bundle"])
        self.assertEqual(contract["bundleId"], Native.BUNDLE_ID)
        self.assertEqual(contract["parameterPrecision"], "fp32")
        self.assertEqual(contract["accumulationPrecision"], "fp32")
        self.assertEqual(contract["featureNames"], list(Native.Reference.FEATURES))
        self.assertEqual(self.manifest["parity"]["rowCount"], 20)
        self.assertTrue(self.manifest["parity"]["exactResponseParity"])
        self.assertLessEqual(
            self.manifest["parity"]["maxProbabilityDeltaFromR66"], 1e-6)
        self.assertEqual(len(self.files["parity.tsv"].splitlines()), 21)

    def test_export_is_byte_reproducible(self):
        self.assertEqual(self.files,
                         Native.output_files(validate_reference=False))
        with tempfile.TemporaryDirectory(prefix="speakeasy-native-") as tmp:
            output = Path(tmp) / "candidate"
            Native.export_to(output, validate_reference=False)
            self.assertEqual(
                self.files,
                Native.validate(output, validate_reference=False))

    def test_corrupt_or_trailing_bundle_refuses(self):
        corrupt = bytearray(self.files["coordination.bundle"])
        corrupt[0] ^= 0x01
        with self.assertRaisesRegex(ValueError, "magic"):
            Native.inspect_bundle(bytes(corrupt))
        with self.assertRaisesRegex(ValueError, "trailing"):
            Native.inspect_bundle(self.files["coordination.bundle"] + b"x")

    def test_masked_labels_cannot_acquire_fp32_output(self):
        contract = Native.inspect_bundle(self.files["coordination.bundle"])
        self.assertEqual(contract["unsupportedLabels"], ["decline", "withdraw"])
        self.assertNotIn("decline", contract["observedLabelSupport"])
        self.assertNotIn("withdraw", contract["observedLabelSupport"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
