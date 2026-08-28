#!/usr/bin/env python3
"""Evaluate a compiled component manifest against a release-readiness mode."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

MODES = ("prototype", "demo", "production")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--report", type=Path, help="Optional readiness report output")
    args = parser.parse_args()

    manifest: dict[str, Any] = json.loads(args.manifest.read_text(encoding="utf-8"))
    components = manifest.get("buildOrder", [])
    if not isinstance(components, list):
        raise ValueError("Manifest buildOrder must be a list")

    statuses = Counter(component.get("adapterStatus", "unknown") for component in components)
    critical = [component for component in components if component.get("critical")]
    failures: list[str] = []
    warnings: list[str] = []

    if args.mode == "prototype":
        warnings.extend(
            f"{component['id']}: {component.get('adapterStatus', 'unknown')}"
            for component in components
            if component.get("adapterStatus") in {"scaffold", "not-implemented"}
        )

    elif args.mode == "demo":
        for component in critical:
            status = component.get("adapterStatus")
            if status == "not-implemented":
                failures.append(f"Critical component lacks adapter: {component['id']}")
            elif status == "scaffold":
                warnings.append(f"Critical component is scaffold-only: {component['id']}")
        warnings.extend(
            f"Noncritical component lacks adapter: {component['id']}"
            for component in components
            if not component.get("critical") and component.get("adapterStatus") == "not-implemented"
        )

    elif args.mode == "production":
        for component in components:
            status = component.get("adapterStatus")
            if status != "constructor-verified":
                failures.append(
                    f"Production requires constructor-verified adapter: {component['id']} ({status})"
                )

    report = {
        "gameName": manifest.get("gameName"),
        "targetPlatform": manifest.get("targetPlatform"),
        "mode": args.mode,
        "status": "PASS" if not failures else "FAIL",
        "resolvedComponentCount": len(components),
        "criticalComponentCount": len(critical),
        "adapterStatusCounts": dict(sorted(statuses.items())),
        "failures": failures,
        "warnings": warnings,
    }

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Readiness evaluation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
