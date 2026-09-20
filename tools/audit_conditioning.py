#!/usr/bin/env python3
"""Measure temporal and namespace eligibility of the protected v2 rows."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path

import cross_module_rows as Join


DATASETS = ("work-words", "trade-hinges")


def rows(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def has_future_belief(row):
    decision_hour = row["situation"]["hour"]
    pending = [row["situation"].get("beliefs", {})]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            for key, child in value.items():
                if (key in {"atHours", "hour"}
                        and isinstance(child, (int, float))
                        and child > decision_hour):
                    return True
                pending.append(child)
        elif isinstance(value, list):
            pending.extend(value)
    return False


def audit(name):
    source = Join.ROOT / "decisions" / f"{name}.jsonl"
    state = (Join.ROOT / "decisions" / "cross-module" /
             f"{name}.zao-state.jsonl")
    decision_rows = rows(source)
    state_rows = rows(state)
    keys = defaultdict(list)
    for line, row in enumerate(decision_rows, 1):
        key = (row["person"]["id"], row["situation"]["hour"])
        keys[key].append((line, row["situation"]["county"]))
    duplicate_groups = {key: values for key, values in keys.items()
                        if len(values) > 1}
    future_deaths = sum(
        isinstance(row["person"].get("record", {}).get("diedAtHours"),
                   (int, float))
        and row["person"]["record"]["diedAtHours"] > row["situation"]["hour"]
        for row in decision_rows)
    future_lessons = sum(any(
        isinstance(claim, dict)
        and isinstance(claim.get("atHours"), (int, float))
        and claim["atHours"] > row["situation"]["hour"]
        for claim in row["person"].get("record", {})
        .get("lessonMeta", {}).values()) for row in decision_rows)
    return {
        "rows": len(decision_rows),
        "futureDeaths": future_deaths,
        "futureLessons": future_lessons,
        "futureBeliefs": sum(has_future_belief(row) for row in decision_rows),
        "bareStringOptions": sum(
            bool(row.get("options"))
            and all(isinstance(option, str) for option in row["options"])
            for row in decision_rows),
        "duplicatePersonHourGroups": len(duplicate_groups),
        "collapsedPersonHourRows": sum(
            len(values) - 1 for values in duplicate_groups.values()),
        "zaoStateRows": len(state_rows),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    Join.protected_artifacts()
    report = {name: audit(name) for name in DATASETS}
    report["total"] = {
        key: sum(report[name][key] for name in DATASETS)
        for key in ("rows", "futureDeaths", "futureLessons", "futureBeliefs",
                    "bareStringOptions", "collapsedPersonHourRows",
                    "zaoStateRows")
    }
    report["standing"] = {
        "approvedIntent": True,
        "conditioningEligible": False,
        "trainingEligible": False,
    }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("protected v2 conditioning audit")
        for name in DATASETS:
            item = report[name]
            print(f"  {name}: {item['rows']} rows; future death "
                  f"{item['futureDeaths']}, lesson {item['futureLessons']}, "
                  f"belief {item['futureBeliefs']}; bare options "
                  f"{item['bareStringOptions']}; collapsed joins "
                  f"{item['collapsedPersonHourRows']}")
        total = report["total"]
        print(f"  total: {total['rows']} approved choices; future death "
              f"{total['futureDeaths']}, lesson {total['futureLessons']}, "
              f"belief {total['futureBeliefs']}; all conditioning ineligible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
