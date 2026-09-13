#!/usr/bin/env python3
"""Emit cross-module decision rows from an SAO dump and a ZAO state dump.

The input SAO rows are the four-half row shape from record 24. The ZAO rows
are keyed by person id and carry two blocks: `pathogen` and `visibleForms`.
The output keeps the SAO row unchanged and adds those two blocks in the
places the cross-module contract names.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterator


SAO_HALVES = {"person", "situation", "options", "choice"}
ZAO_BLOCKS = {"id", "hour", "pathogen", "visibleForms"}


def read_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise SystemExit(
                    f"{path}:{line_number}: invalid JSON: {error.msg}"
                ) from error
            if not isinstance(row, dict):
                raise SystemExit(
                    f"{path}:{line_number}: each row must be a JSON object"
                )
            yield line_number, row


def load_zao(path: Path) -> dict[str, dict[str, Any]]:
    state: dict[tuple[str, Any], dict[str, Any]] = {}
    for line_number, row in read_jsonl(path):
        missing = ZAO_BLOCKS - row.keys()
        if missing:
            names = ", ".join(sorted(missing))
            raise SystemExit(
                f"{path}:{line_number}: missing ZAO block(s): {names}"
            )
        key = (row["id"], row["hour"])
        if key in state:
            raise SystemExit(
                f"{path}:{line_number}: duplicate ZAO state for {key!r}"
            )
        state[key] = row
    return state


def export_rows(sao_path: Path, zao_path: Path, out_path: Path) -> int:
    zao_state = load_zao(zao_path)
    written = 0
    with out_path.open("w", encoding="utf-8", newline="\n") as out:
        for line_number, row in read_jsonl(sao_path):
            missing = SAO_HALVES - row.keys()
            if missing:
                names = ", ".join(sorted(missing))
                raise SystemExit(
                    f"{sao_path}:{line_number}: missing SAO half(s): {names}"
                )
            person = row["person"]
            if not isinstance(person, dict) or "id" not in person:
                raise SystemExit(
                    f"{sao_path}:{line_number}: person half has no id"
                )
            situation = row["situation"]
            if not isinstance(situation, dict) or "hour" not in situation:
                raise SystemExit(
                    f"{sao_path}:{line_number}: situation half has no hour"
                )
            key = (person["id"], situation["hour"])
            zao = zao_state.get(key)
            if zao is None:
                raise SystemExit(
                    f"{sao_path}:{line_number}: no ZAO state for {key!r}"
                )
            person["pathogen"] = zao["pathogen"]
            situation["visibleForms"] = zao["visibleForms"]
            out.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            out.write("\n")
            written += 1
    return written


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit cross-module decision rows from SAO and ZAO dumps."
    )
    parser.add_argument(
        "--sao",
        type=Path,
        required=True,
        help="SAO decision rows, one JSON object per line",
    )
    parser.add_argument(
        "--zao",
        type=Path,
        required=True,
        help="ZAO state rows, one JSON object per line, keyed by id",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="output cross-module rows, one JSON object per line",
    )
    args = parser.parse_args()
    written = export_rows(args.sao, args.zao, args.out)
    print(f"wrote {written} cross-module row(s) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
