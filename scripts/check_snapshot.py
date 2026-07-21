#!/usr/bin/env python3
"""Validate local public snapshots and enforce critical health thresholds."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crawler.health import quality_violations, validate_health, validate_jobs


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Job Radar snapshots")
    parser.add_argument("--jobs", type=Path, default=Path("data/jobs.json"))
    parser.add_argument("--health", type=Path, default=Path("data/health.json"))
    args = parser.parse_args()
    try:
        jobs = json.loads(args.jobs.read_text(encoding="utf-8"))
        health = json.loads(args.health.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"snapshot check failed: {error}")
        return 1

    errors = [*validate_jobs(jobs), *validate_health(health)]
    if health.get("currentTotal") != jobs.get("total"):
        errors.append("health.currentTotal does not match jobs.total")
    violations = quality_violations(jobs, {}, health, datetime.now(timezone.utc))
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
        f"snapshot healthy: total={jobs['total']} "
        f"sources={health.get('enabledSourceCount', 0)} "
        f"success={health['sourceSuccessRate']:.1%}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
