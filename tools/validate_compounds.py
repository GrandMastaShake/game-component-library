#!/usr/bin/env python3
"""Validate compound recipes against component descriptors and event contracts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_components(root: Path) -> dict[str, dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}
    for path in (root / "components").rglob("*.component.json"):
        component = json.loads(path.read_text(encoding="utf-8"))
        registry[component["id"]] = component
    return registry


def validate_compound(path: Path, compound: dict[str, Any], registry: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    platform = compound.get("targetPlatform")
    members = compound.get("components", [])
    member_ids = [member.get("id") for member in members if isinstance(member, dict)]

    for component_id in member_ids:
        component = registry.get(component_id)
        if component is None:
            errors.append(f"{path}: unknown component '{component_id}'")
            continue
        if platform not in component["platform"] and "agnostic" not in component["platform"]:
            errors.append(f"{path}: '{component_id}' does not support platform '{platform}'")

    for connection in compound.get("connections", []):
        source_id = connection.get("from")
        target_id = connection.get("to")
        event = connection.get("event")
        if source_id not in member_ids:
            errors.append(f"{path}: connection source '{source_id}' is not a compound member")
            continue
        if target_id not in member_ids:
            errors.append(f"{path}: connection target '{target_id}' is not a compound member")
            continue
        source = registry.get(source_id, {})
        target = registry.get(target_id, {})
        if event not in source.get("events", {}).get("emits", []):
            errors.append(f"{path}: '{source_id}' does not emit '{event}'")
        if event not in target.get("events", {}).get("listensTo", []):
            errors.append(f"{path}: '{target_id}' does not listen to '{event}'")

    for critical_id in compound.get("criticalComponents", []):
        if critical_id not in member_ids:
            errors.append(f"{path}: critical component '{critical_id}' is not a compound member")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    registry = load_components(root)
    errors: list[str] = []
    validated = []
    for path in sorted((root / "compounds").glob("*.compound.json")):
        compound = json.loads(path.read_text(encoding="utf-8"))
        errors.extend(validate_compound(path, compound, registry))
        validated.append(compound.get("id", str(path)))

    report = {
        "status": "PASS" if not errors else "FAIL",
        "compoundCount": len(validated),
        "validatedCompounds": validated,
        "errors": errors,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Compound validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
