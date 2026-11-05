#!/usr/bin/env python3
"""Bake POLYFORGE sources and verify descriptors against actual GLB bytes.

The JavaScript baker performs its own readback. This independent Python pass
opens the resulting binary again, checks its chunk/accessor structure, counts
indices, compares sockets, and requires the committed asset descriptor to equal
a fresh deterministic bake. A descriptor can no longer drift from either its
editable source or the file a runtime would load.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ID_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
BANDS = {"hero", "gameplay", "far", "proxy"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check_document_shape(document: dict[str, Any], schema: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    for key in schema.get("required", []):
        if key not in document:
            errors.append(f"{label}: missing required key '{key}'")
    for key in sorted(set(document) - set(schema.get("properties", {}))):
        errors.append(f"{label}: unknown key '{key}'")
    if document.get("format") != "polyforge.forge" or document.get("version") != "1.0.0":
        errors.append(f"{label}: unsupported format/version")
    if not ID_RE.match(str(document.get("id", ""))):
        errors.append(f"{label}: invalid dotted asset id")

    for collection in ("vertices", "edges", "faces", "materials"):
        items = document.get(collection, [])
        ids = [item.get("id") for item in items if isinstance(item, dict)]
        if len(ids) != len(items) or len(set(ids)) != len(ids):
            errors.append(f"{label}: {collection} contain missing or duplicate ids")
    vertex_ids = {item.get("id") for item in document.get("vertices", [])}
    material_ids = {item.get("id") for item in document.get("materials", [])}
    corner_ids: list[str] = []
    for face in document.get("faces", []):
        corners = face.get("corners", [])
        if len(corners) < 3:
            errors.append(f"{label}: face {face.get('id')} has fewer than three corners")
        if face.get("materialId") not in material_ids:
            errors.append(f"{label}: face {face.get('id')} references an unknown material")
        polygon: set[str] = set()
        for corner in corners:
            corner_ids.append(corner.get("id"))
            vertex_id = corner.get("vertexId")
            if vertex_id not in vertex_ids:
                errors.append(f"{label}: corner {corner.get('id')} references unknown vertex {vertex_id}")
            if vertex_id in polygon:
                errors.append(f"{label}: face {face.get('id')} repeats vertex {vertex_id}")
            polygon.add(vertex_id)
    if len(corner_ids) != len(set(corner_ids)):
        errors.append(f"{label}: duplicate corner ids")

    previous = float("inf")
    for index, level in enumerate(document.get("budgets", {}).get("levels", [])):
        if level.get("level") != f"lod{index}":
            errors.append(f"{label}: budget {index} must be lod{index}")
        if level.get("distanceBand") not in BANDS:
            errors.append(f"{label}: invalid distance band in {level.get('level')}")
        maximum = level.get("maxTriangles")
        if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
            errors.append(f"{label}: {level.get('level')} needs a positive integer budget")
        elif maximum > previous:
            errors.append(f"{label}: LOD budgets must be non-increasing")
        else:
            previous = maximum
    return errors


def check_glb(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) < 28:
        raise ValueError("GLB is too short")
    magic, version, declared = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67 or version != 2 or declared != len(data):
        raise ValueError("invalid GLB header or declared length")
    json_length, json_kind = struct.unpack_from("<II", data, 12)
    if json_kind != 0x4E4F534A or 20 + json_length + 8 > len(data):
        raise ValueError("invalid GLB JSON chunk")
    binary_header = 20 + json_length
    binary_length, binary_kind = struct.unpack_from("<II", data, binary_header)
    if binary_kind != 0x004E4942 or binary_header + 8 + binary_length > len(data):
        raise ValueError("invalid GLB binary chunk")
    document = json.loads(data[20:binary_header].decode("utf-8"))
    if document.get("asset", {}).get("version") != "2.0":
        raise ValueError("not glTF 2.0")
    component_sizes = {5121: 1, 5123: 2, 5125: 4, 5126: 4}
    component_counts = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
    for accessor in document.get("accessors", []):
        view = document["bufferViews"][accessor["bufferView"]]
        size = component_sizes[accessor["componentType"]]
        count = component_counts[accessor["type"]]
        if view.get("byteOffset", 0) + accessor["count"] * size * count > binary_length:
            raise ValueError("accessor exceeds binary chunk")

    triangles = 0
    vertices = 0
    for mesh in document.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            if primitive.get("mode", 4) != 4:
                raise ValueError("non-triangle primitive")
            indices = document["accessors"][primitive["indices"]]
            position = document["accessors"][primitive["attributes"]["POSITION"]]
            if indices["count"] % 3:
                raise ValueError("index count is not divisible by three")
            triangles += indices["count"] // 3
            vertices += position["count"]
    sockets = sorted(
        node["name"][7:] for node in document.get("nodes", [])
        if node.get("name", "").startswith("socket_")
    )
    return {"triangles": triangles, "vertices": vertices, "bytes": len(data), "sockets": sockets}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    sources = sorted((root / "examples" / "polyforge-asset-core").glob("*.forge.json"))
    schema = load_json(root / "art" / "forge.schema.json")
    errors: list[str] = []
    reports: list[dict[str, Any]] = []
    if not sources:
        errors.append("no POLYFORGE example sources found")

    for source in sources:
        label = source.name
        document = load_json(source)
        document_errors = check_document_shape(document, schema, label)
        errors.extend(document_errors)
        if document_errors:
            continue
        with tempfile.TemporaryDirectory(prefix="polyforge-bake-") as temporary:
            output = Path(temporary)
            command = [
                "node", str(root / "tools" / "polyforge_asset_pipeline.mjs"), "bake",
                "--source", str(source), "--output-dir", str(output),
            ]
            result = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=120)
            if result.returncode:
                errors.append(f"{label}: bake failed: {result.stderr.strip() or result.stdout.strip()}")
                continue
            generated = load_json(output / f"{document['id']}.asset.json")
            committed_path = root / "assets" / f"{document['id']}.asset.json"
            if not committed_path.exists():
                errors.append(f"{label}: missing committed descriptor {committed_path.name}")
                continue
            committed = load_json(committed_path)
            if generated != committed:
                errors.append(f"{label}: committed descriptor differs from a fresh bake")

            budgets = {level["level"]: level["maxTriangles"] for level in document["budgets"]["levels"]}
            level_reports = []
            for level in generated.get("levels", []):
                glb_path = output / level["file"]
                try:
                    measured = check_glb(glb_path)
                except (OSError, ValueError, KeyError, IndexError, struct.error) as exc:
                    errors.append(f"{label}: {level['level']}: GLB readback failed: {exc}")
                    continue
                if measured["triangles"] != level["triangles"] or measured["bytes"] != level["bytes"]:
                    errors.append(f"{label}: {level['level']}: descriptor costs differ from independent GLB readback")
                if measured["triangles"] > budgets[level["level"]]:
                    errors.append(f"{label}: {level['level']}: {measured['triangles']} exceeds budget {budgets[level['level']]}")
                expected_sockets = sorted(socket["name"] for socket in document.get("sockets", []))
                if measured["sockets"] != expected_sockets:
                    errors.append(f"{label}: {level['level']}: socket readback differs from source")
                level_reports.append({"level": level["level"], **measured})
            reports.append({"id": document["id"], "checksum": document["checksum"], "levels": level_reports})

    payload = {
        "status": "PASS" if not errors else "FAIL",
        "sourceCount": len(sources),
        "levelCount": sum(len(report["levels"]) for report in reports),
        "assets": reports,
        "errors": errors,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"validate_polyforge_assets: {payload['status']} ({len(sources)} source(s), {payload['levelCount']} GLB level(s), {len(errors)} error(s))")
    for error in errors:
        print(f"ERROR: {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
