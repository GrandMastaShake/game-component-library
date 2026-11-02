#!/usr/bin/env python3
"""Validate RPG skill-tree content before it reaches a runtime adapter.

The component graph proves that progression.skills_tree exists and is wired.
This validator answers a different question: is the designer-supplied tree a
purchasable, dependency-safe graph? It checks ranks, costs, prerequisites,
exclusive branches, and named per-rank effects without embedding any game's
content or balance rules.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
EFFECT_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _integer(value, minimum=0) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def validate_tree(tree, source="<tree>"):
    """Return (errors, warnings) for one tree-definition object."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(tree, dict):
        return [f"{source}: tree definition must be an object"], warnings

    starting_points = tree.get("startingPoints", 0)
    if not _integer(starting_points):
        errors.append(f"{source}: startingPoints must be a non-negative integer")

    skills = tree.get("skills")
    if not isinstance(skills, list):
        return errors + [f"{source}: skills must be an array"], warnings
    if not skills:
        warnings.append(f"{source}: tree has no skills")

    nodes = {}
    for index, node in enumerate(skills):
        label = f"{source}: skills[{index}]"
        if not isinstance(node, dict):
            errors.append(f"{label} must be an object")
            continue
        node_id = node.get("id")
        if not isinstance(node_id, str) or not ID_PATTERN.match(node_id):
            errors.append(f"{label}: id must match {ID_PATTERN.pattern}")
            continue
        if node_id in nodes:
            errors.append(f"{source}: duplicate skill id '{node_id}'")
            continue
        nodes[node_id] = node

        if not _integer(node.get("atLevel"), 1):
            errors.append(f"{source}:{node_id}: atLevel must be an integer >= 1")
        max_rank = node.get("maxRank", 1)
        if not _integer(max_rank, 1):
            errors.append(f"{source}:{node_id}: maxRank must be an integer >= 1")
            max_rank = 1
        costs = node.get("costByRank", [1] * max_rank)
        if not isinstance(costs, list) or len(costs) != max_rank:
            errors.append(f"{source}:{node_id}: costByRank must contain exactly maxRank entries")
        elif any(not _integer(cost, 1) for cost in costs):
            errors.append(f"{source}:{node_id}: every rank cost must be an integer >= 1")

        group = node.get("exclusiveGroup")
        if group is not None and (not isinstance(group, str) or not group.strip()):
            errors.append(f"{source}:{node_id}: exclusiveGroup must be a non-empty string")

        effect = node.get("effect", {})
        if not isinstance(effect, dict):
            errors.append(f"{source}:{node_id}: effect must be an object of named per-rank modifiers")
        else:
            for key, value in effect.items():
                if not isinstance(key, str) or not EFFECT_PATTERN.match(key):
                    errors.append(f"{source}:{node_id}: invalid effect key '{key}'")
                if not _number(value):
                    errors.append(f"{source}:{node_id}: effect.{key} must be a finite number")

    prerequisites: dict[str, list[tuple[str, int]]] = {}
    for node_id, node in nodes.items():
        raw = node.get("prerequisites", [])
        parsed = []
        if not isinstance(raw, list):
            errors.append(f"{source}:{node_id}: prerequisites must be an array")
            raw = []
        for entry in raw:
            if isinstance(entry, str):
                required_id, rank = entry, 1
            elif isinstance(entry, dict):
                required_id, rank = entry.get("id"), entry.get("rank", 1)
            else:
                errors.append(f"{source}:{node_id}: prerequisite must be an id or {{id, rank}} object")
                continue
            if required_id not in nodes:
                errors.append(f"{source}:{node_id}: unknown prerequisite '{required_id}'")
                continue
            if required_id == node_id:
                errors.append(f"{source}:{node_id}: a skill cannot require itself")
                continue
            target_max = nodes[required_id].get("maxRank", 1)
            if not _integer(rank, 1) or (_integer(target_max, 1) and rank > target_max):
                errors.append(
                    f"{source}:{node_id}: prerequisite {required_id} rank {rank} "
                    f"is outside 1..{target_max}"
                )
                continue
            parsed.append((required_id, rank))
        prerequisites[node_id] = parsed

    # Dependency cycles are always invalid, including cycles whose rank costs or
    # level requirements would otherwise look plausible in isolation.
    visiting: set[str] = set()
    visited: set[str] = set()
    reported_cycles: set[frozenset[str]] = set()

    def visit(node_id, stack):
        if node_id in visiting:
            cycle = set(stack[stack.index(node_id):])
            marker = frozenset(cycle)
            if marker not in reported_cycles:
                errors.append(f"{source}: prerequisite cycle contains {', '.join(sorted(cycle))}")
                reported_cycles.add(marker)
            return
        if node_id in visited:
            return
        visiting.add(node_id)
        stack.append(node_id)
        for parent, _ in prerequisites.get(node_id, []):
            visit(parent, stack)
        stack.pop()
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in nodes:
        visit(node_id, [])

    # Two nodes in one exclusive group cannot both hold ranks. If either depends
    # on the other, directly or through ancestors, neither path is purchasable.
    ancestors_cache: dict[str, set[str]] = {}

    def ancestors(node_id, seen=None):
        if node_id in ancestors_cache:
            return ancestors_cache[node_id]
        seen = set() if seen is None else seen
        if node_id in seen:
            return set()
        seen.add(node_id)
        result = set()
        for parent, _ in prerequisites.get(node_id, []):
            result.add(parent)
            result.update(ancestors(parent, seen.copy()))
        ancestors_cache[node_id] = result
        return result

    for node_id, node in nodes.items():
        group = node.get("exclusiveGroup")
        if not group:
            continue
        conflicts = sorted(
            parent for parent in ancestors(node_id)
            if nodes[parent].get("exclusiveGroup") == group
        )
        if conflicts:
            errors.append(
                f"{source}:{node_id}: exclusive group '{group}' also contains prerequisite "
                f"ancestor(s) {', '.join(conflicts)}; the branch is impossible"
            )

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="tree JSON files or directories")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    inputs = args.paths or [ROOT / "examples" / "skill-trees"]
    paths: list[Path] = []
    for path in inputs:
        if path.is_dir():
            paths.extend(sorted(path.rglob("*.tree.json")))
        else:
            paths.append(path)

    errors: list[str] = []
    warnings: list[str] = []
    tree_count = 0
    node_count = 0
    if not paths:
        errors.append("no *.tree.json files found")

    for path in paths:
        source = str(path.relative_to(ROOT)) if path.is_absolute() and ROOT in path.parents else str(path)
        try:
            tree = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{source}: unreadable ({exc})")
            continue
        tree_count += 1
        if isinstance(tree, dict) and isinstance(tree.get("skills"), list):
            node_count += len(tree["skills"])
        tree_errors, tree_warnings = validate_tree(tree, source)
        errors.extend(tree_errors)
        warnings.extend(tree_warnings)

    report = {
        "status": "PASS" if not errors else "FAIL",
        "treeCount": tree_count,
        "nodeCount": node_count,
        "warnings": warnings,
        "errors": errors,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(
        f"validate_skill_trees: {report['status']} ({tree_count} trees, "
        f"{node_count} nodes, {len(errors)} errors, {len(warnings)} warnings)"
    )
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
