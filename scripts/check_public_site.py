#!/usr/bin/env python3
"""Smoke-check the deployed homepage and both public JSON snapshots."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crawler.health import check_public_site


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the deployed Job Radar site")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--attempts", type=int, default=6)
    parser.add_argument("--delay", type=float, default=10.0)
    args = parser.parse_args()
    checks = []
    for attempt in range(max(1, args.attempts)):
        checks = check_public_site(args.base_url)
        if all(check["ok"] for check in checks):
            break
        if attempt + 1 < args.attempts:
            time.sleep(max(0.0, args.delay))
    for check in checks:
        state = "ok" if check["ok"] else "error"
        detail = "; ".join(check["errors"]) if check["errors"] else f"HTTP {check['status']}"
        print(f"[{state}] {check['name']}: {detail}")
    return 0 if checks and all(check["ok"] for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
