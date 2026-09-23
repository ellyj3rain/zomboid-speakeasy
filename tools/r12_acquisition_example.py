#!/usr/bin/env python3
"""Refuse regeneration of Record 52's superseded acquisition reference.

Historical import integrity remains available through import_sao_world_knowledge.
Record 55 preserves original artifacts and corrects their current applicability.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import cross_module_rows as Join


def build(example_dir: Path, claim_out: Path) -> None:
    raise Join.ContractError("Record 52 acquisition superseded: county presence does not prove acquisition")


def validate_reference(example_dir: Path):
    raise Join.ContractError("Record 52 acquisition superseded: historical import integrity is not current acceptance")


def validate(example_dir: Path, claim_out: Path) -> None:
    validate_reference(example_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "validate"))
    parser.add_argument("--example-dir", type=Path, required=True)
    parser.add_argument("--claim-out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        operation = build if args.command == "build" else validate
        operation(args.example_dir.resolve(), args.claim_out.resolve())
    except Join.ContractError as error:
        print("REFUSED: " + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
