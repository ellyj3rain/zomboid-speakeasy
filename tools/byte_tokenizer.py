"""Frozen byte BPE reference. Ordinary bytes never become structural tokens."""
from collections import Counter
import hashlib

import decision_authoring as A

SCHEMA = "speakeasy-byte-tokenizer"
SPECIALS = ("bos", "eos", "pad", "understander", "retriever", "speaker",
            "schema", "input", "target", "claim-ref", "fenced-slot")
SPECIAL_IDS = {name: 256 + i for i, name in enumerate(SPECIALS)}
FIRST_MERGE = 256 + len(SPECIALS)
RULES = {"algorithm": "byte-bpe-ranked-left-to-right-v1",
         "normalization": "none", "textEncoding": "utf-8-strict",
         "pairSelection": "highest-count-then-lowest-token-id-pair",
         "minimumPairCount": 2, "maximumTokenBytes": 1024}


def _replace(tokens, pair, replacement):
    output, index = [], 0
    while index < len(tokens):
        if index + 1 < len(tokens) and (tokens[index], tokens[index + 1]) == pair:
            output.append(replacement)
            index += 2
        else:
            output.append(tokens[index])
            index += 1
    return output


def corpus_identity(segments):
    A.require(isinstance(segments, list) and segments and
              all(type(part) is bytes for part in segments), "byte corpus required")
    return {"segmentSha256": sorted(hashlib.sha256(part).hexdigest() for part in segments),
            "segmentCount": len(segments), "byteCount": sum(map(len, segments))}


def train(segments, merge_limit=64):
    """Fit on supplied independent segments; caller owns training-split selection."""
    corpus = corpus_identity(segments)
    A.require(type(merge_limit) is int and 0 <= merge_limit <= 8192, "invalid merge limit")
    sequences = [list(part) for part in sorted(segments)]
    vocabulary = {i: bytes([i]) for i in range(256)}
    seen = set(vocabulary.values())
    merges = []
    for index in range(merge_limit):
        counts = Counter(pair for seq in sequences for pair in zip(seq, seq[1:]))
        candidates = [pair for pair, count in counts.items() if count >= 2
                      and len(vocabulary[pair[0]]) + len(vocabulary[pair[1]]) <= 1024
                      and vocabulary[pair[0]] + vocabulary[pair[1]] not in seen]
        if not candidates:
            break
        pair = min(candidates, key=lambda item: (-counts[item], item))
        token = FIRST_MERGE + index
        vocabulary[token] = vocabulary[pair[0]] + vocabulary[pair[1]]
        seen.add(vocabulary[token])
        merges.append(list(pair))
        sequences = [_replace(seq, pair, token) for seq in sequences]
    return A.seal({"schema": SCHEMA, "schemaVersion": 1, "rules": RULES,
                   "specialTokens": SPECIAL_IDS, "mergeLimit": merge_limit,
                   "corpus": corpus, "merges": merges})


class Tokenizer:
    def __init__(self, artifact):
        A.unseal(artifact, SCHEMA)
        A.fields(artifact, {"schema", "schemaVersion", "rules", "specialTokens",
                            "mergeLimit", "corpus", "merges", "contentSha256"}, SCHEMA)
        A.require(A.encoded(artifact["rules"]) == A.encoded(RULES), "unsupported tokenizer rules")
        A.require(A.encoded(artifact["specialTokens"]) == A.encoded(SPECIAL_IDS),
                  "structural token IDs differ")
        limit = artifact["mergeLimit"]
        A.require(type(limit) is int and 0 <= limit <= 8192, "invalid merge limit")
        corpus = artifact["corpus"]
        A.fields(corpus, {"segmentSha256", "segmentCount", "byteCount"}, "tokenizer corpus")
        hashes = corpus["segmentSha256"]
        A.require(isinstance(hashes, list) and hashes, "corpus hashes required")
        for digest in hashes:
            A.hash_value(digest, "corpus segment hash")
        A.require(hashes == sorted(hashes) and type(corpus["segmentCount"]) is int
                  and corpus["segmentCount"] == len(hashes)
                  and type(corpus["byteCount"]) is int and corpus["byteCount"] >= 0,
                  "invalid corpus metadata")
        merges = artifact["merges"]
        A.require(isinstance(merges, list) and len(merges) <= limit, "invalid merges")
        self.vocabulary = {i: bytes([i]) for i in range(256)}
        seen = set(self.vocabulary.values())
        self.merges = []
        for index, pair in enumerate(merges):
            A.require(isinstance(pair, list) and len(pair) == 2
                      and all(type(i) is int and i in self.vocabulary for i in pair),
                      "merge must reference earlier byte tokens")
            value = self.vocabulary[pair[0]] + self.vocabulary[pair[1]]
            A.require(len(value) <= 1024 and value not in seen, "duplicate or oversized byte token")
            self.vocabulary[FIRST_MERGE + index] = value
            seen.add(value)
            self.merges.append(tuple(pair))
        self.sha256 = artifact["contentSha256"]

    def encode_bytes(self, value):
        A.require(type(value) is bytes, "encode_bytes requires bytes")
        tokens = list(value)
        for index, pair in enumerate(self.merges):
            tokens = _replace(tokens, pair, FIRST_MERGE + index)
        return tokens

    def decode_bytes(self, tokens):
        A.require(isinstance(tokens, list) and
                  all(type(i) is int and i in self.vocabulary for i in tokens),
                  "unknown or structural token in byte stream")
        return b"".join(self.vocabulary[i] for i in tokens)

    def encode_text(self, value):
        A.require(type(value) is str, "encode_text requires text")
        try:
            return self.encode_bytes(value.encode("utf-8", errors="strict"))
        except UnicodeError as error:
            raise ValueError("text contains an invalid Unicode scalar") from error

    def decode_text(self, tokens):
        return self.decode_bytes(tokens).decode("utf-8", errors="strict")


def validate_training(artifact, segments):
    Tokenizer(artifact)
    A.require(A.encoded(artifact) == A.encoded(train(segments, artifact["mergeLimit"])),
              "tokenizer differs from training corpus")
    return artifact
