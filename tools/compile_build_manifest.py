#!/usr/bin/env python3
"""Compile a requested set of game components into a dependency-safe build manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_registry(root: Path) -> dict[str, dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "components").rglob("*.component.json")):
        component = json.loads(path.read_text(encoding="utf-8"))
        component_id = component["id"]
        if component_id in registry:
            raise ValueError(f"Duplicate component id: {component_id}")
        component["_descriptorPath"] = str(path.relative_to(root))
        registry[component_id] = component
    return registry


def resolve(requested: list[str], registry: dict[str, dict[str, Any]], platform: str) -> list[str]:
    resolved: set[str] = set()
    active: set[str] = set()
    order: list[str] = []

    def visit(component_id: str, trail: list[str]) -> None:
        if component_id in active:
            raise ValueError("Circular dependency: " + " -> ".join(trail + [component_id]))
        if component_id in resolved:
            return
        component = registry.get(component_id)
        if component is None:
            raise ValueError(f"Unknown component: {component_id}")
        supported = component["platform"]
        if platform not in supported and "agnostic" not in supported:
            raise ValueError(
                f"Component '{component_id}' does not support target platform '{platform}'. "
                f"Supported: {supported}"
            )
        active.add(component_id)
        for dependency in component["dependencies"]:
            visit(dependency, trail + [component_id])
        active.remove(component_id)
        resolved.add(component_id)
        order.append(component_id)

    for component_id in requested:
        visit(component_id, [])
    return order


def adapter_status(root: Path, component_id: str) -> str:
    adapter_path = root / "roblox-adapters" / f"{component_id}.adapter.lua"
    if adapter_path.exists():
        text = adapter_path.read_text(encoding="utf-8")
        return "constructor-verified" if "Verified source constructor:" in text else "scaffold"
    return "not-implemented"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("request", type=Path, help="Path to a build request JSON file")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True, help="Destination manifest path")
    args = parser.parse_args()

    root = args.root.resolve()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    platform = request.get("targetPlatform")
    requested = request.get("requestedComponents")
    if not isinstance(platform, str):
        raise ValueError("Request requires string field 'targetPlatform'")
    if not isinstance(requested, list) or not all(isinstance(item, str) for item in requested):
        raise ValueError("Request requires string-array field 'requestedComponents'")

    registry = load_registry(root)
    build_order = resolve(requested, registry, platform)
    components = []
    for index, component_id in enumerate(build_order, start=1):
        component = registry[component_id]
        components.append({
            "sequence": index,
            "id": component_id,
            "name": component["name"],
            "category": component["category"],
            "descriptor": component["_descriptorPath"],
            "dependencies": component["dependencies"],
            "adapterStatus": adapter_status(root, component_id) if platform == "roblox" else "not-applicable",
        })

    manifest = {
        "manifestVersion": "1.0.0",
        "gameName": request.get("gameName", "Untitled Game"),
        "targetPlatform": platform,
        "requestedComponents": requested,
        "resolvedComponentCount": len(components),
        "buildOrder": components,
        "notes": [
            "Order is dependency-safe: every dependency precedes its dependent component.",
            "adapterStatus is an implementation signal, not a runtime test result.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Manifest compilation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
