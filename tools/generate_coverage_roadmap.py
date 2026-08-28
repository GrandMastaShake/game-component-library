#!/usr/bin/env python3
"""Turn a compiled manifest into a prioritized Roblox adapter implementation roadmap."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

STATUS_RANK = {
    "not-implemented": 0,
    "scaffold": 1,
    "constructor-verified": 2,
}

NEXT_ACTION = {
    "not-implemented": "Create adapter shell, inject the upstream source module, then verify its constructor/API against source or tests.",
    "scaffold": "Replace TODO-marked source calls only after confirming exact upstream method and event contracts.",
    "constructor-verified": "Extract remaining public methods/events and add mocked plus in-Studio integration tests.",
}


def reverse_dependencies(components: list[dict[str, Any]]) -> dict[str, list[str]]:
    dependents: dict[str, list[str]] = defaultdict(list)
    for component in components:
        for dependency in component.get("dependencies", []):
            dependents[dependency].append(component["id"])
    return dependents


def downstream_count(component_id: str, dependents: dict[str, list[str]]) -> int:
    visited: set[str] = set()

    def visit(node: str) -> None:
        for child in dependents.get(node, []):
            if child not in visited:
                visited.add(child)
                visit(child)

    visit(component_id)
    return len(visited)


def priority_score(component: dict[str, Any], impact: int) -> int:
    status = component.get("adapterStatus", "not-implemented")
    missing_severity = 2 - STATUS_RANK.get(status, 0)
    critical_weight = 100 if component.get("critical") else 0
    return critical_weight + impact * 10 + missing_severity * 5


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest: dict[str, Any] = json.loads(args.manifest.read_text(encoding="utf-8"))
    components = manifest.get("buildOrder")
    if not isinstance(components, list):
        raise ValueError("Manifest buildOrder must be a list")

    dependents = reverse_dependencies(components)
    backlog = []
    for component in components:
        status = component.get("adapterStatus", "not-implemented")
        if status == "constructor-verified":
            continue
        impact = downstream_count(component["id"], dependents)
        backlog.append({
            "id": component["id"],
            "name": component.get("name"),
            "category": component.get("category"),
            "critical": bool(component.get("critical")),
            "currentAdapterStatus": status,
            "unlockedDownstreamComponents": impact,
            "priorityScore": priority_score(component, impact),
            "descriptor": component.get("descriptor"),
            "nextAction": NEXT_ACTION.get(status, NEXT_ACTION["not-implemented"]),
        })

    backlog.sort(key=lambda item: (-item["priorityScore"], -item["unlockedDownstreamComponents"], item["id"]))
    status_counts = Counter(component.get("adapterStatus", "unknown") for component in components)
    critical_gaps = [item for item in backlog if item["critical"]]

    roadmap = {
        "roadmapVersion": "1.0.0",
        "gameName": manifest.get("gameName"),
        "targetPlatform": manifest.get("targetPlatform"),
        "summary": {
            "resolvedComponentCount": len(components),
            "adapterStatusCounts": dict(sorted(status_counts.items())),
            "criticalGapCount": len(critical_gaps),
            "totalImplementationBacklog": len(backlog),
        },
        "demoReadinessRule": "Every critical component must have an adapter; scaffolds are permitted but warned.",
        "recommendedSprintOrder": backlog,
        "milestones": {
            "prototype": "Manifest compiles; adapter gaps are visible warnings.",
            "demo": "Implement every critical component currently marked not-implemented, then validate that the critical path has no missing adapter.",
            "production": "Upgrade every resolved component to constructor-verified and add runtime/integration evidence; readiness status alone is not a production test.",
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(roadmap, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(roadmap, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Coverage roadmap generation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
