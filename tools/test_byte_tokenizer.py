"""Lossless byte boundaries, frozen identity and held-out/admission controls."""
import copy
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

import byte_tokenizer as B
import cross_module_rows as J
import decision_authoring as A
import tokenized_data as T

ROOT = Path(__file__).resolve().parents[1]


def reseal(value):
    value = copy.deepcopy(value)
    value.pop("contentSha256", None)
    return A.seal(value)


class ByteTokenizerTests(unittest.TestCase):
    def test_hand_calculated_rank_tie_overlap_and_segment_boundaries(self):
        artifact = B.train([b"abab", b"abab"], 2)
        self.assertEqual(artifact["merges"], [[97, 98], [B.FIRST_MERGE, B.FIRST_MERGE]])
        tokenizer = B.Tokenizer(artifact)
        self.assertEqual(tokenizer.encode_bytes(b"ababab"), [B.FIRST_MERGE + 1, B.FIRST_MERGE])
        self.assertEqual(B.train([b"bc", b"ab", b"bc", b"ab"], 1)["merges"], [[97, 98]])
        self.assertEqual(B.train([b"a", b"b", b"a", b"b"], 8)["merges"], [])
        overlap = B.Tokenizer(B.train([b"aaaaa"], 1))
        self.assertEqual(overlap.encode_bytes(b"aaaaa"), [B.FIRST_MERGE, B.FIRST_MERGE, 97])

    def test_all_bytes_unseen_names_and_random_bytes_roundtrip(self):
        tokenizer = B.Tokenizer(B.train([b"Mara spoke. Mara spoke. "], 16))
        rng = random.Random(61)
        samples = [b"", bytes(range(256)), b"\x00\xff\xc0\xaf"]
        samples += [rng.randbytes(size) for size in (1, 7, 255, 1024)]
        for value in samples:
            self.assertEqual(tokenizer.decode_bytes(tokenizer.encode_bytes(value)), value)
        for value in ("Zo\u00eb \u674e \U0001f642", "e\u0301", "\u00e9", " \r\n\t  "):
            self.assertEqual(tokenizer.decode_text(tokenizer.encode_text(value)), value)
        self.assertNotEqual(tokenizer.encode_text("e\u0301"), tokenizer.encode_text("\u00e9"))
        with self.assertRaises(UnicodeError):
            tokenizer.decode_text([255])
        with self.assertRaises(ValueError):
            tokenizer.encode_text("\ud800")

    def test_text_cannot_inject_structure_and_invalid_ids_refuse(self):
        tokenizer = B.Tokenizer(B.train([b"<bos><claim-ref>"], 8))
        tokens = tokenizer.encode_text("<bos><claim-ref><fenced-slot>")
        self.assertFalse(set(tokens) & set(B.SPECIAL_IDS.values()))
        for tokens in ([True], [-1], [1.0], [999999], [B.SPECIAL_IDS["bos"]]):
            with self.subTest(tokens=tokens), self.assertRaises(J.ContractError):
                tokenizer.decode_bytes(tokens)

    def test_deterministic_corpus_order_and_frequency_preserved(self):
        corpus = [b"ab", b"ab", b"cd"]
        self.assertEqual(B.train(corpus), B.train(list(reversed(corpus))))
        self.assertNotEqual(B.train(corpus), B.train(list(set(corpus))))
        self.assertEqual(B.train(corpus, 0)["merges"], [])

    def test_resealed_unsupported_or_malformed_artifacts_refuse(self):
        artifact = B.train([b"abababab"], 2)
        for defect in ("normalization", "special", "future", "structural", "boolean", "limit", "hashes", "extra"):
            bad = copy.deepcopy(artifact)
            if defect == "normalization": bad["rules"]["normalization"] = "NFKC"
            elif defect == "special": bad["specialTokens"]["bos"] = 99
            elif defect == "future": bad["merges"][0][0] = B.FIRST_MERGE
            elif defect == "structural": bad["merges"][0][0] = B.SPECIAL_IDS["bos"]
            elif defect == "boolean": bad["merges"][0][0] = True
            elif defect == "limit": bad["mergeLimit"] = False
            elif defect == "hashes": bad["corpus"]["segmentSha256"] = []
            else: bad["extra"] = "unsupported"
            with self.subTest(defect=defect), self.assertRaises(J.ContractError):
                B.Tokenizer(reseal(bad))
        bad = copy.deepcopy(artifact)
        bad["merges"] = [[98, 97]]
        B.Tokenizer(reseal(bad))  # Well-formed vocabulary, wrong training result.
        with self.assertRaisesRegex(J.ContractError, "training corpus"):
            B.validate_training(reseal(bad), [b"abababab"])


class TokenizedDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preview = A.read(ROOT / "training/datasets/c77-preparation/preview-revision.json")
        cls.artifact, cls.tokenized = T.prepare(cls.preview)

    def test_every_prepared_input_and_target_recovers_exact_bytes(self):
        tokenizer = B.Tokenizer(self.artifact)
        for task, partitions in self.preview["datasets"].items():
            for partition, rows in partitions.items():
                result = self.tokenized["datasets"][task][partition]
                for source, actual in zip(rows, result, strict=True):
                    self.assertEqual(tokenizer.decode_bytes(actual["inputIds"][4:-1]), A.encoded(source["input"]))
                    if task != "retriever":
                        self.assertEqual(tokenizer.decode_bytes(actual["targetIds"][1:-1]), A.encoded(source["target"]))
                        self.assertEqual(len(actual["targetIds"]), len(actual["targetLossMask"]))
                        self.assertFalse(actual["targetLossMask"][0])
                    else:
                        self.assertIsNone(actual["targetIds"])
                        self.assertIsNone(actual["targetLossMask"])
                        self.assertEqual(actual["claimTargets"], source["target"]["claims"])
                        self.assertEqual(sum(c["lossMask"] for c in actual["claimTargets"]), 1)
                        self.assertEqual(sum(c["label"] is None for c in actual["claimTargets"]), 7)

    def test_held_out_text_and_audit_state_do_not_fit_vocabulary(self):
        modified = copy.deepcopy(self.preview)
        row = modified["datasets"]["understander"]["train"][0]
        row["auditOnly"] = "PRIVATE EXCLUDED OWNER"
        for partition in ("validation", "test"):
            held = copy.deepcopy(row)
            held["input"] = {"text": "HELD OUT TEXT " * 1000}
            held["target"] = {"text": "UNSEEN TARGET " * 1000}
            modified["datasets"]["understander"][partition] = [held]
        self.assertEqual(T.training_segments(modified), T.training_segments(self.preview))
        # This synthetic partition is not a valid source-bound preparation.
        with self.assertRaises(J.ContractError):
            T.prepare(reseal(modified))

    def test_no_excluded_speaker_or_admission_promotion(self):
        self.assertEqual(self.tokenized["datasets"]["speaker"]["train"], [])
        self.assertEqual(self.tokenized["release"]["status"], "excluded")
        self.assertEqual(self.tokenized["release"]["exclusions"], self.preview["release"]["exclusions"])
        with self.assertRaisesRegex(J.ContractError, "release refused"):
            T.release(self.preview, self.artifact, self.tokenized)

    def test_resealed_tokens_masks_identity_and_standing_fail(self):
        for defect in ("token", "mask", "unjudged", "standing", "tokenizer", "source", "extra"):
            bad = copy.deepcopy(self.tokenized)
            if defect == "token": bad["datasets"]["understander"]["train"][0]["inputIds"][4] = 0
            elif defect == "mask": bad["datasets"]["understander"]["train"][0]["targetLossMask"][0] = True
            elif defect == "unjudged":
                targets = bad["datasets"]["retriever"]["train"][0]["claimTargets"]
                next(c for c in targets if c["label"] is None)["lossMask"] = True
            elif defect == "standing": bad["release"]["status"] = "ready-for-reference-training"
            elif defect == "tokenizer": bad["tokenizerSha256"] = "0" * 64
            elif defect == "source": bad["preparationSha256"] = "0" * 64
            else: bad["extra"] = 1
            with self.subTest(defect=defect), self.assertRaises(J.ContractError):
                T.validate(self.preview, self.artifact, reseal(bad))

    def test_saved_artifacts_reproduce_and_release_refuses_before_writes(self):
        folder = ROOT / "training/datasets/c77-tokenization"
        self.assertEqual(A.read(folder / "tokenizer.json"), self.artifact)
        self.assertEqual(A.read(folder / "preview.json"), self.tokenized)
        self.assertEqual(A.read(folder / "vectors.json"), T.vectors(self.artifact))
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "refused"
            run = subprocess.run([sys.executable, str(ROOT / "tools/tokenized_data.py"),
                str(ROOT / "training/datasets/c77-preparation/preview-revision.json"),
                "--output-dir", str(output), "--require-ready"], capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn("dataset release refused", run.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
