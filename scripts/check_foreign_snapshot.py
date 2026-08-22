#!/usr/bin/env python3
"""Validate foreign-campus public snapshots and enforce critical thresholds."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crawler.foreign_health import (
    foreign_quality_violations,
    validate_foreign_health,
    validate_foreign_snapshot,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate foreign-campus snapshots")
    parser.add_argument("--campaigns", type=Path, default=Path("data/foreign-campus.json"))
    parser.add_argument("--health", type=Path, default=Path("data/foreign-health.json"))
    args = parser.parse_args()
    try:
        campaigns = json.loads(args.campaigns.read_text(encoding="utf-8"))
        health = json.loads(args.health.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"foreign snapshot check failed: {error}")
        return 1
    errors = [*validate_foreign_snapshot(campaigns), *validate_foreign_health(health)]
    if health.get("currentTotal") != campaigns.get("total"):
        errors.append("foreign health.currentTotal does not match foreign.total")
    violations = foreign_quality_violations(campaigns, {}, health, datetime.now(timezone.utc))
    critical = [item for item in violations if item["severity"] == "critical"]
    for message in errors:
        print(f"[critical] {message}")
    for item in health.get("violations", []):
        print(f"[{item.get('severity', 'warning')}] {item.get('message', item.get('code'))}")
    if errors or critical:
        for item in critical:
            print(f"[critical] {item['message']}")
        return 1
    print(
        f"foreign snapshot healthy: total={campaigns['total']} "
        f"sources={health.get('enabledSourceCount', 0)} "
        f"success={health['sourceSuccessRate']:.1%} "
        f"official={health['officialSourceRatio']:.1%}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
