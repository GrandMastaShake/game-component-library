#!/usr/bin/env python3
"""Validate POLYFORGE geometry DAGs and their derived assets independently.

The Python pass checks stable identities, typed sockets, single-input links,
outputs, and acyclicity before invoking the native compiler. It then requires
the committed runtime descriptor to equal a fresh graph bake and uses the Asset
Core validator's independent GLB parser for byte-level costs. Canonical forge
source is generated into the temporary build directory, not duplicated in Git.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from validate_polyforge_assets import check_glb  # noqa: E402

ID_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
NODE_ID = re.compile(r"^n[0-9]{6}$")
LINK_ID = re.compile(r"^l[0-9]{6}$")
NODE_SOCKETS: dict[str, dict[str, dict[str, str]]] = {
    "source.generate": {"inputs": {}, "outputs": {"asset": "asset"}},
    "source.asset": {"inputs": {}, "outputs": {"asset": "asset"}},
    "edit.move": {"inputs": {"asset": "asset"}, "outputs": {"asset": "asset"}},
    "edit.split": {"inputs": {"asset": "asset"}, "outputs": {"asset": "asset"}},
    "edit.extrudeFace": {"inputs": {"asset": "asset"}, "outputs": {"asset": "asset"}},
    "edit.deleteFace": {"inputs": {"asset": "asset"}, "outputs": {"asset": "asset"}},
    "modify.transform": {"inputs": {"asset": "asset"}, "outputs": {"asset": "asset"}},
    "configure.budgets": {"inputs": {"asset": "asset"}, "outputs": {"asset": "asset"}},
    "measure.asset": {"inputs": {"asset": "asset"}, "outputs": {"asset": "asset", "stats": "stats"}},
    "output.asset": {"inputs": {"asset": "asset"}, "outputs": {"asset": "asset"}},
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check_graph_shape(graph: dict[str, Any], schema: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    for key in schema.get("required", []):
        if key not in graph:
            errors.append(f"{label}: missing required key '{key}'")
    for key in sorted(set(graph) - set(schema.get("properties", {}))):
        errors.append(f"{label}: unknown key '{key}'")
    if graph.get("format") != "polyforge.geometry" or graph.get("version") != "1.0.0":
        errors.append(f"{label}: unsupported format/version")
    if not ID_RE.match(str(graph.get("id", ""))):
        errors.append(f"{label}: invalid dotted graph id")

    nodes = graph.get("nodes", [])
    links = graph.get("links", [])
    node_ids = [node.get("id") for node in nodes if isinstance(node, dict)]
    link_ids = [link.get("id") for link in links if isinstance(link, dict)]
    if len(node_ids) != len(nodes) or len(set(node_ids)) != len(node_ids) or any(not NODE_ID.match(str(value)) for value in node_ids):
        errors.append(f"{label}: nodes contain missing, malformed, or duplicate ids")
    if len(link_ids) != len(links) or len(set(link_ids)) != len(link_ids) or any(not LINK_ID.match(str(value)) for value in link_ids):
        errors.append(f"{label}: links contain missing, malformed, or duplicate ids")
    node_map = {node.get("id"): node for node in nodes if isinstance(node, dict)}
    for node in nodes:
        node_type = node.get("type")
        if node_type not in NODE_SOCKETS:
            errors.append(f"{label}: {node.get('id')} uses unknown node type {node_type}")
        if not isinstance(node.get("parameters"), dict):
            errors.append(f"{label}: {node.get('id')} parameters must be an object")
        if node_type == "source.generate":
            parameters = node.get("parameters", {})
            if not ID_RE.match(str(parameters.get("id", ""))) or not isinstance(parameters.get("settings"), dict):
                errors.append(f"{label}: {node.get('id')} needs an asset id and generation settings")

    occupied: set[tuple[str, str]] = set()
    usable_links: list[dict[str, Any]] = []
    for link in links:
        source = link.get("from", {})
        target = link.get("to", {})
        source_node = node_map.get(source.get("node"))
        target_node = node_map.get(target.get("node"))
        if source_node is None or target_node is None:
            errors.append(f"{label}: {link.get('id')} references an unknown node")
            continue
        source_type = NODE_SOCKETS.get(source_node.get("type"), {}).get("outputs", {}).get(source.get("socket"))
        target_type = NODE_SOCKETS.get(target_node.get("type"), {}).get("inputs", {}).get(target.get("socket"))
        if source_type is None or target_type is None:
            errors.append(f"{label}: {link.get('id')} references an unknown socket")
            continue
        if source_type != target_type:
            errors.append(f"{label}: {link.get('id')} connects {source_type} to {target_type}")
        key = (target["node"], target["socket"])
        if key in occupied:
            errors.append(f"{label}: {key[0]}.{key[1]} has multiple inbound links")
        occupied.add(key)
        usable_links.append(link)

    outputs = graph.get("outputs", {})
    if not isinstance(outputs, dict) or "asset" not in outputs:
        errors.append(f"{label}: missing asset output")
    else:
        for name, endpoint in outputs.items():
            if name not in {"asset", "stats"}:
                errors.append(f"{label}: unknown output {name}")
                continue
            node = node_map.get(endpoint.get("node"))
            if node is None or NODE_SOCKETS.get(node.get("type"), {}).get("outputs", {}).get(endpoint.get("socket")) != name:
                errors.append(f"{label}: output {name} references an incompatible socket")

    indegree = {node_id: 0 for node_id in node_ids}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for link in usable_links:
        indegree[link["to"]["node"]] += 1
        outgoing[link["from"]["node"]].append(link["to"]["node"])
    ready = sorted(node_id for node_id, count in indegree.items() if count == 0)
    visited = 0
    while ready:
        current = ready.pop(0)
        visited += 1
        for target in sorted(set(outgoing[current])):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
                ready.sort()
    if visited != len(nodes):
        errors.append(f"{label}: graph contains a cycle")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    graphs = sorted((root / "examples" / "polyforge-geometry-graph").glob("*.graph.json"))
    schema = load_json(root / "art" / "geometry-graph.schema.json")
    errors: list[str] = []
    reports: list[dict[str, Any]] = []
    if not graphs:
        errors.append("no POLYFORGE geometry graphs found")

    for graph_path in graphs:
        label = graph_path.name
        graph = load_json(graph_path)
        graph_errors = check_graph_shape(graph, schema, label)
        errors.extend(graph_errors)
        if graph_errors:
            continue
        with tempfile.TemporaryDirectory(prefix="polyforge-graph-") as temporary:
            output = Path(temporary)
            derived_path = output / "derived.forge.json"
            command = [
                "node", str(root / "tools" / "polyforge_geometry_graph.mjs"), "build",
                "--graph", str(graph_path), "--source-output", str(derived_path), "--output-dir", str(output),
            ]
            result = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=120)
            if result.returncode:
                errors.append(f"{label}: native build failed: {result.stderr.strip() or result.stdout.strip()}")
                continue
            derived = load_json(derived_path)
            descriptor_path = output / f"{derived['id']}.asset.json"
            generated = load_json(descriptor_path)
            committed_descriptor = root / "assets" / descriptor_path.name
            if not committed_descriptor.exists() or generated != load_json(committed_descriptor):
                errors.append(f"{label}: committed descriptor differs from fresh graph baking")

            budgets = {level["level"]: level["maxTriangles"] for level in derived["budgets"]["levels"]}
            level_reports = []
            for level in generated.get("levels", []):
                try:
                    measured = check_glb(output / level["file"])
                except (OSError, ValueError, KeyError, IndexError) as exc:
                    errors.append(f"{label}: {level['level']}: GLB readback failed: {exc}")
                    continue
                if measured["triangles"] != level["triangles"] or measured["bytes"] != level["bytes"]:
                    errors.append(f"{label}: {level['level']}: descriptor costs differ from independent GLB readback")
                if measured["triangles"] > budgets[level["level"]]:
                    errors.append(f"{label}: {level['level']}: measured triangles exceed budget")
                level_reports.append({"level": level["level"], **measured})
            reports.append({
                "id": graph["id"],
                "asset": derived["id"],
                "checksum": graph["checksum"],
                "nodes": len(graph["nodes"]),
                "links": len(graph["links"]),
                "levels": level_reports,
            })

    payload = {
        "status": "PASS" if not errors else "FAIL",
        "graphCount": len(graphs),
        "nodeCount": sum(report["nodes"] for report in reports),
        "linkCount": sum(report["links"] for report in reports),
        "levelCount": sum(len(report["levels"]) for report in reports),
        "graphs": reports,
        "errors": errors,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"validate_polyforge_geometry_graphs: {payload['status']} ({len(graphs)} graph(s), {payload['nodeCount']} node(s), {payload['levelCount']} GLB level(s), {len(errors)} error(s))")
    for error in errors:
        print(f"ERROR: {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
