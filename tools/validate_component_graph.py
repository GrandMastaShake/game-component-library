#!/usr/bin/env python3
"""Validate Game Component Library descriptors and dependency graph."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = {
    "id": str,
    "name": str,
    "category": str,
    "version": str,
    "platform": list,
    "inputs": list,
    "outputs": list,
    "events": dict,
    "dependencies": list,
}


def load_components(root: Path) -> tuple[list[tuple[Path, dict[str, Any]]], list[str]]:
    components: list[tuple[Path, dict[str, Any]]] = []
    errors: list[str] = []
    for path in sorted((root / "components").rglob("*.component.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: invalid JSON ({exc})")
            continue
        if not isinstance(payload, dict):
            errors.append(f"{path}: descriptor root must be an object")
            continue
        components.append((path, payload))
    return components, errors


def validate_shape(path: Path, component: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field, expected_type in REQUIRED_FIELDS.items():
        value = component.get(field)
        if value is None:
            errors.append(f"{path}: missing required field '{field}'")
        elif not isinstance(value, expected_type):
            errors.append(f"{path}: '{field}' must be {expected_type.__name__}")
    events = component.get("events")
    if isinstance(events, dict):
        for event_field in ("emits", "listensTo"):
            if event_field not in events:
                errors.append(f"{path}: events missing '{event_field}'")
            elif not isinstance(events[event_field], list):
                errors.append(f"{path}: events.{event_field} must be a list")
    return errors


def topological_order(graph: dict[str, list[str]]) -> tuple[list[str], list[str]]:
    visited: set[str] = set()
    active: set[str] = set()
    order: list[str] = []
    cycles: list[str] = []

    def visit(node: str, trail: list[str]) -> None:
        if node in active:
            start = trail.index(node) if node in trail else 0
            cycles.append(" -> ".join(trail[start:] + [node]))
            return
        if node in visited:
            return
        active.add(node)
        for dependency in graph[node]:
            if dependency in graph:
                visit(dependency, trail + [node])
        active.remove(node)
        visited.add(node)
        order.append(node)

    for component_id in sorted(graph):
        visit(component_id, [])
    return order, cycles


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--report", type=Path, help="Optional JSON report output path")
    args = parser.parse_args()

    root = args.root.resolve()
    components, errors = load_components(root)
    if not components:
        errors.append(f"No component descriptors found under {root / 'components'}")

    ids = [component.get("id") for _, component in components if isinstance(component.get("id"), str)]
    duplicate_ids = sorted(component_id for component_id, count in Counter(ids).items() if count > 1)
    for component_id in duplicate_ids:
        errors.append(f"Duplicate component id: {component_id}")

    graph: dict[str, list[str]] = {}
    locations: dict[str, Path] = {}
    for path, component in components:
        errors.extend(validate_shape(path, component))
        component_id = component.get("id")
        dependencies = component.get("dependencies", [])
        if isinstance(component_id, str) and isinstance(dependencies, list):
            graph[component_id] = dependencies
            locations[component_id] = path

    missing_dependencies: list[dict[str, str]] = []
    for component_id, dependencies in graph.items():
        for dependency in dependencies:
            if not isinstance(dependency, str):
                errors.append(f"{locations[component_id]}: dependency ids must be strings")
            elif dependency not in graph:
                missing_dependencies.append({"component": component_id, "missing": dependency})
                errors.append(f"{locations[component_id]}: missing dependency '{dependency}'")

    order, cycles = topological_order(graph)
    for cycle in cycles:
        errors.append(f"Circular dependency: {cycle}")

    categories = Counter(
        component["category"] for _, component in components if isinstance(component.get("category"), str)
    )
    report = {
        "status": "PASS" if not errors else "FAIL",
        "componentCount": len(graph),
        "categoryCounts": dict(sorted(categories.items())),
        "missingDependencies": missing_dependencies,
        "cycles": cycles,
        "buildOrder": order,
        "errors": errors,
    }

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
