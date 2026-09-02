#!/usr/bin/env python3
"""Check the assembly graph against itself and against the shape contracts.

`art/shapes/*.json` says what a part IS -- its topology and its LOD chain.
`art/assembly-graph.json` says where it goes and how it joins. Nothing has ever
compared the two, and the graph does not even agree with itself: 38 of its 139
edges attach a part to a socket its anchor does not declare.

Findings, in the order they are worth having:

  ASM001  edge names a socket the anchor does not have
          A generator following this edge places the part at an undefined
          socket -- no offset, so it lands at the anchor's origin.
  ASM002  edge's anchor is not in the part's attachesTo
  ASM003  edge jointType disagrees with the part's own jointType
  ASM004  canMirror on a socket that is not one of a left/right pair
          Mirroring across a centre socket puts both copies in one place.
  ASM005  lodDisappearsAt names a level the shape's LOD chain does not have
  ASM006  a deforming joint (hinge, ball_socket) onto a part whose topology
          says deformsWithRig is false
          Finds nothing today and is the point of the exercise anyway: it is
          the rule that stops someone hanging a hinge off a fan-capped horn.
  ASM007  anchor or part id is not a shape in art/shapes
  ASM008  edge names an anchor the graph does not declare as one
          Nine edges hang parts off art.crown, art.shield, art.snout and
          art.limb_paw, which are PARTS. Found only because the first version
          of this script guarded `if anchor is not None` and silently skipped
          them -- it reported 29 socket problems where a hand count found 38.
          A guard that skips the thing it cannot explain hides exactly the
          findings worth having, so every lookup failure is now a finding.
  ASM009  edge names a part the graph does not declare

What this CANNOT check, and the reason the interesting question stays open:
the graph records that a joint is a `hinge` and never how far it bends. Whether
a joint's RANGE exceeds what its topology supports needs angular limits that do
not exist in this data. ASM006 is the type-level shadow of that rule.

Baselined like the topology and platform checks: a check that lands red on work
nobody is doing today gets switched off. Recording what is already true lets it
fail on new findings from the day it lands.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

DEFORMING = {"hinge", "ball_socket"}
PAIRED_SUFFIXES = ("_left", "_right")


@dataclass(frozen=True)
class Finding:
    code: str
    subject: str
    detail: str

    def key(self) -> tuple[str, str, str]:
        return (self.code, self.subject, self.detail)

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "subject": self.subject, "detail": self.detail}


def load_shapes(root: Path) -> dict[str, dict]:
    shapes: dict[str, dict] = {}
    for path in sorted((root / "art" / "shapes").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        shapes[data["id"]] = data
    return shapes


def check(root: Path) -> list[Finding]:
    graph = json.loads((root / "art" / "assembly-graph.json").read_text(encoding="utf-8"))
    shapes = load_shapes(root)
    anchors = graph["anchors"]
    parts = graph["parts"]
    findings: list[Finding] = []

    for kind, table in (("anchor", anchors), ("part", parts)):
        for sid in table:
            if sid not in shapes:
                findings.append(Finding("ASM007", sid, f"{kind} is not a shape in art/shapes"))

    for edge in graph["edges"]:
        anchor_id = edge["anchor"]
        part_id = edge["part"]
        socket = edge["socket"]
        subject = f"{anchor_id} -{socket}-> {part_id}"
        anchor = anchors.get(anchor_id)
        part = parts.get(part_id)

        if anchor is None:
            findings.append(Finding(
                "ASM008", subject,
                f"{anchor_id} is not an anchor" +
                (" — it is a part" if anchor_id in parts else ""),
            ))
        if part is None:
            findings.append(Finding("ASM009", subject, f"{part_id} is not a part"))

        if anchor is not None and socket not in anchor["sockets"]:
            findings.append(Finding(
                "ASM001", subject,
                f"{anchor_id} declares sockets {sorted(anchor['sockets'])}, not '{socket}'",
            ))

        if part is not None and anchor_id not in part["attachesTo"]:
            findings.append(Finding(
                "ASM002", subject, f"{part_id} attachesTo {part['attachesTo']}",
            ))

        if part is not None and edge["jointType"] != part["jointType"]:
            findings.append(Finding(
                "ASM003", subject,
                f"edge says {edge['jointType']}, part says {part['jointType']}",
            ))

        if edge["canMirror"] and not socket.endswith(PAIRED_SUFFIXES):
            findings.append(Finding(
                "ASM004", subject,
                f"canMirror on '{socket}', which is not a left/right pair — "
                "both copies land in the same place",
            ))

        lod = edge.get("lodDisappearsAt")
        shape = shapes.get(part_id)
        if lod is not None and shape is not None:
            levels = {entry["level"] for entry in shape.get("lod", [])}
            if lod not in levels:
                findings.append(Finding(
                    "ASM005", subject,
                    f"lodDisappearsAt {lod}, chain has {sorted(levels)}",
                ))

        if edge["jointType"] in DEFORMING and shape is not None:
            topology = shape.get("topology", {})
            if topology.get("deformsWithRig") is False:
                findings.append(Finding(
                    "ASM006", subject,
                    f"{edge['jointType']} onto a part whose topology says "
                    f"deformsWithRig false (quadPct {topology.get('quadPct')}, "
                    f"caps {topology.get('capStyle')})",
                ))

    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--baseline", type=Path)
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()

    findings = check(args.root)

    baseline: set[tuple[str, str, str]] = set()
    if args.baseline and args.baseline.exists() and not args.write_baseline:
        recorded = json.loads(args.baseline.read_text(encoding="utf-8"))
        baseline = {
            (item["code"], item["subject"], item["detail"])
            for item in recorded.get("accepted", [])
        }

    fresh = [f for f in findings if f.key() not in baseline]

    by_code: dict[str, int] = {}
    for f in findings:
        by_code[f.code] = by_code.get(f.code, 0) + 1

    report = {
        "status": "PASS" if not fresh else "FAIL",
        "edges": len(json.loads(
            (args.root / "art" / "assembly-graph.json").read_text(encoding="utf-8")
        )["edges"]),
        "findings": len(findings),
        "byCode": dict(sorted(by_code.items())),
        "accepted": len(findings) - len(fresh),
        "new": [f.as_dict() for f in fresh],
    }

    if args.write_baseline and args.baseline:
        args.baseline.write_text(json.dumps({
            "note": (
                "Assembly-graph findings accepted when the graph was imported. "
                "Each line is a known defect in the imported data, not a rule "
                "being waived: removing one means the graph was corrected. "
                "Adding one should be a deliberate, reviewed decision."
            ),
            "accepted": [f.as_dict() for f in findings],
        }, indent=2) + "\n", encoding="utf-8")
        print(f"baseline written: {len(findings)} finding(s)")
        return 0

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    for f in fresh:
        print(f"  {f.code}  {f.subject}: {f.detail}", file=sys.stderr)
    return 0 if not fresh else 1


if __name__ == "__main__":
    raise SystemExit(main())
