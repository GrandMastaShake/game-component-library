#!/usr/bin/env python3
"""Validate art shape descriptors: schema shape, topology rules, LOD integrity.

Why this exists
---------------
Topology quality is invisible in a rendered mesh. A model renders identically
whether it is clean quad loops or triangle soup; the difference only appears
once the thing is deformed or subdivided. That is why the craft knowledge lives
in prose ("never use a UV sphere for a game asset") and why it is never
enforced.

This turns the checkable half into rules. It does not attempt to judge art. It
asserts that a descriptor does not contradict itself: a shape cannot be declared
as deforming with a rig AND described with topology that is known to pinch under
deformation. One of the two statements is wrong, and the author should say which.

Rules
-----
Blocking (a descriptor that trips these is internally inconsistent):
  TOPO001  deforming mesh below the quad floor
  TOPO002  deforming mesh with a triangle-fan cap
  TOPO003  deforming mesh carrying a pole

Data integrity (the numbers must be self-consistent):
  TOPO010  LOD triangle counts must be non-increasing
  TOPO011  LOD levels must start at 0 and increment by 1
  TOPO012  vertices cannot exceed 3x triangles

Advisory (worth a human look, not a failure):
  TOPO020  heavy mesh whose coarsest LOD does not reduce
  TOPO021  hazardous topology with no pitfall documented

Exit code is non-zero only for blocking and data-integrity findings, so
advisories can accumulate without wedging CI.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# A deforming surface needs quad loops to bend cleanly. Below this the mesh is
# triangle-dominant and will pinch at joints regardless of weighting.
QUAD_FLOOR = 60.0

# Above this triangle count, shipping the same density at the coarsest tier
# means the LOD chain is not doing any work.
HEAVY_TRIANGLES = 100

REQUIRED_FIELDS = {
    "id": str,
    "name": str,
    "category": str,
    "version": str,
    "topology": dict,
    "lod": list,
}

REQUIRED_TOPOLOGY = {
    "genus": int,
    "quadPct": (int, float),
    "capStyle": str,
    "hasPoles": bool,
    "deformsWithRig": bool,
}

VALID_CAP_STYLES = {"quad", "ngon", "fan_tri", "icosphere", "none"}


class Finding:
    __slots__ = ("code", "severity", "shape", "message")

    def __init__(self, code: str, severity: str, shape: str, message: str) -> None:
        self.code = code
        self.severity = severity
        self.shape = shape
        self.message = message

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "shape": self.shape,
            "message": self.message,
        }


def load_shapes(root: Path) -> tuple[list[tuple[Path, dict[str, Any]]], list[Finding]]:
    shapes: list[tuple[Path, dict[str, Any]]] = []
    findings: list[Finding] = []
    for path in sorted((root / "art" / "shapes").rglob("*.shape.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            findings.append(Finding("TOPO000", "error", path.name, f"invalid JSON ({exc})"))
            continue
        if not isinstance(payload, dict):
            findings.append(Finding("TOPO000", "error", path.name, "descriptor root must be an object"))
            continue
        shapes.append((path, payload))
    return shapes, findings


def check_structure(shape_id: str, shape: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for field, expected in REQUIRED_FIELDS.items():
        value = shape.get(field)
        if value is None:
            findings.append(Finding("TOPO000", "error", shape_id, f"missing required field '{field}'"))
        elif not isinstance(value, expected):
            findings.append(
                Finding("TOPO000", "error", shape_id, f"field '{field}' must be {expected.__name__}")
            )

    topology = shape.get("topology")
    if isinstance(topology, dict):
        for field, expected in REQUIRED_TOPOLOGY.items():
            value = topology.get(field)
            if value is None:
                findings.append(
                    Finding("TOPO000", "error", shape_id, f"missing required topology field '{field}'")
                )
            elif not isinstance(value, expected):
                findings.append(
                    Finding("TOPO000", "error", shape_id, f"topology.{field} has the wrong type")
                )
        cap = topology.get("capStyle")
        if isinstance(cap, str) and cap not in VALID_CAP_STYLES:
            findings.append(
                Finding("TOPO000", "error", shape_id, f"unknown capStyle '{cap}'")
            )
    return findings


def check_topology_rules(shape_id: str, shape: dict[str, Any]) -> list[Finding]:
    """The blocking rules. All of them are conditioned on deformsWithRig.

    A triangle-dominant static prop is fine — props do not bend. The same
    topology on a skinned limb is a defect. The rules therefore only fire where
    the descriptor itself claims the shape deforms.
    """
    findings: list[Finding] = []
    topology = shape.get("topology")
    if not isinstance(topology, dict):
        return findings
    if not topology.get("deformsWithRig"):
        return findings

    quad_pct = topology.get("quadPct")
    if isinstance(quad_pct, (int, float)) and quad_pct < QUAD_FLOOR:
        findings.append(
            Finding(
                "TOPO001",
                "error",
                shape_id,
                f"declared deformsWithRig but quadPct is {quad_pct}% (floor {QUAD_FLOOR}%); "
                "a triangle-dominant surface pinches at joints regardless of skin weights",
            )
        )

    if topology.get("capStyle") == "fan_tri":
        findings.append(
            Finding(
                "TOPO002",
                "error",
                shape_id,
                "declared deformsWithRig with a fan_tri cap; a triangle fan concentrates a pole "
                "at the cap centre, which collapses when the joint bends",
            )
        )

    if topology.get("hasPoles"):
        note = topology.get("poleNote") or "pole present"
        findings.append(
            Finding(
                "TOPO003",
                "error",
                shape_id,
                f"declared deformsWithRig while carrying a pole ({note}); "
                "poles must sit in flat, non-deforming regions",
            )
        )

    return findings


def check_lod(shape_id: str, shape: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    lod = shape.get("lod")
    if not isinstance(lod, list) or not lod:
        return findings

    previous_tris: int | None = None
    for index, tier in enumerate(lod):
        if not isinstance(tier, dict):
            findings.append(Finding("TOPO000", "error", shape_id, f"lod[{index}] must be an object"))
            continue

        level = tier.get("level")
        if level != index:
            findings.append(
                Finding("TOPO011", "error", shape_id, f"lod[{index}] has level {level}; expected {index}")
            )

        tris = tier.get("triangles")
        verts = tier.get("vertices")
        if not isinstance(tris, int) or not isinstance(verts, int):
            findings.append(Finding("TOPO000", "error", shape_id, f"lod[{index}] needs integer triangles and vertices"))
            continue

        # Every triangle contributes at most three corners, so a mesh cannot
        # have more vertices than that even with every seam split.
        if verts > 3 * tris:
            findings.append(
                Finding(
                    "TOPO012",
                    "error",
                    shape_id,
                    f"lod[{index}] has {verts} vertices for {tris} triangles; at most {3 * tris} is possible",
                )
            )

        if previous_tris is not None and tris > previous_tris:
            findings.append(
                Finding(
                    "TOPO010",
                    "error",
                    shape_id,
                    f"lod[{index}] rises to {tris} triangles from {previous_tris}; LOD must not add detail",
                )
            )
        previous_tris = tris

    first, last = lod[0], lod[-1]
    if (
        isinstance(first.get("triangles"), int)
        and isinstance(last.get("triangles"), int)
        and first["triangles"] > HEAVY_TRIANGLES
        and last["triangles"] == first["triangles"]
    ):
        findings.append(
            Finding(
                "TOPO020",
                "warning",
                shape_id,
                f"{first['triangles']} triangles at LOD0 and no reduction by the coarsest tier",
            )
        )

    return findings


def check_annotations(shape_id: str, shape: dict[str, Any]) -> list[Finding]:
    """A shape that is hazardous to use should carry the reason in writing.

    This is the one rule about documentation rather than geometry, and it is
    advisory: the pitfall text is what a future author actually needs, and its
    absence is worth surfacing without blocking a build.
    """
    topology = shape.get("topology")
    if not isinstance(topology, dict):
        return []
    quad_pct = topology.get("quadPct")
    hazardous = bool(topology.get("deformsWithRig")) and (
        topology.get("hasPoles")
        or topology.get("capStyle") == "fan_tri"
        or (isinstance(quad_pct, (int, float)) and quad_pct < QUAD_FLOOR)
    )
    if not hazardous:
        return []

    annotations = shape.get("annotations")
    pitfall = ""
    if isinstance(annotations, dict):
        pitfall = str(annotations.get("pitfall") or "").strip()
    if not pitfall or pitfall.lower().startswith("none"):
        return [
            Finding(
                "TOPO021",
                "warning",
                shape_id,
                "hazardous topology on a deforming shape with no pitfall documented",
            )
        ]
    return []


def seam_overhead(shape: dict[str, Any]) -> int | None:
    """Render vertices minus the closed-manifold minimum, i.e. seam duplication.

    Reported, never enforced. A closed triangle mesh satisfies V = F/2 + 2 - 2g;
    real assets exceed it wherever UV seams or hard normals split vertices, and
    that excess is a legitimate cost rather than an error.
    """
    topology = shape.get("topology")
    lod = shape.get("lod")
    if not isinstance(topology, dict) or not isinstance(lod, list) or not lod:
        return None
    if topology.get("capStyle") == "none":
        return None  # open mesh; the identity does not apply
    tier = lod[0]
    tris, verts = tier.get("triangles"), tier.get("vertices")
    genus = topology.get("genus")
    if not all(isinstance(v, int) for v in (tris, verts, genus)):
        return None
    return int(verts - (tris / 2 + 2 - 2 * genus))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--report", type=Path, help="Write a JSON report to this path")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat advisory findings as failures too",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        help=(
            "Path to a baseline of accepted findings. Anything listed there is "
            "reported as known and does not fail the run; anything new does."
        ),
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Rewrite the baseline from the current findings instead of checking against it",
    )
    args = parser.parse_args()

    shapes, findings = load_shapes(args.root)

    for path, shape in shapes:
        shape_id = shape.get("id") or path.name
        findings.extend(check_structure(shape_id, shape))
        findings.extend(check_topology_rules(shape_id, shape))
        findings.extend(check_lod(shape_id, shape))
        findings.extend(check_annotations(shape_id, shape))

    # A baseline lets this land on an existing library without a red build on
    # day one. Known findings are recorded once and stop failing; anything not
    # in the baseline fails immediately. The file doubles as a visible ledger of
    # art debt, which a suppression comment scattered through descriptors would
    # not be.
    baseline: set[tuple[str, str]] = set()
    if args.baseline and args.baseline.exists() and not args.write_baseline:
        try:
            recorded = json.loads(args.baseline.read_text(encoding="utf-8"))
            baseline = {(item["code"], item["shape"]) for item in recorded.get("accepted", [])}
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            print(f"warning: could not read baseline ({exc}); checking without it", file=sys.stderr)

    if args.write_baseline:
        if not args.baseline:
            print("error: --write-baseline requires --baseline", file=sys.stderr)
            return 2
        payload = {
            "note": (
                "Findings accepted at the time topology validation was introduced. "
                "Each entry is a shape whose descriptor contradicts itself and has "
                "not been resolved yet. Removing an entry is the fix landing; "
                "adding one should be a deliberate, reviewed decision."
            ),
            "accepted": sorted(
                ({"code": f.code, "shape": f.shape} for f in findings if f.severity == "error"),
                key=lambda item: (item["code"], item["shape"]),
            ),
        }
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {len(payload['accepted'])} accepted findings to {args.baseline}")
        return 0

    known = [f for f in findings if f.severity == "error" and (f.code, f.shape) in baseline]
    errors = [f for f in findings if f.severity == "error" and (f.code, f.shape) not in baseline]
    warnings = [f for f in findings if f.severity == "warning"]

    overheads = {}
    for _, shape in shapes:
        value = seam_overhead(shape)
        if value is not None and value > 0:
            overheads[shape.get("id", "?")] = value

    categories = Counter(
        shape["category"] for _, shape in shapes if isinstance(shape.get("category"), str)
    )
    deforming = [shape.get("id") for _, shape in shapes if (shape.get("topology") or {}).get("deformsWithRig")]

    failed = bool(errors) or (args.strict and bool(warnings))
    report = {
        "status": "FAIL" if failed else "PASS",
        "shapeCount": len(shapes),
        "categoryCounts": dict(sorted(categories.items())),
        "deformingShapeCount": len(deforming),
        "errorCount": len(errors),
        "knownCount": len(known),
        "warningCount": len(warnings),
        "findingsByCode": dict(sorted(Counter(f.code for f in findings).items())),
        "errors": [f.as_dict() for f in errors],
        "known": [f.as_dict() for f in known],
        "warnings": [f.as_dict() for f in warnings],
        "seamVertexOverhead": dict(sorted(overheads.items(), key=lambda kv: -kv[1])),
    }

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
