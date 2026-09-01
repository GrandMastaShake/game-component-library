#!/usr/bin/env python3
"""Add a per-target `implementations` list to every descriptor.

Why
---
`platform` is a flat list of engine names, and fixtures 10 and 11 in the
consuming application argue it cannot carry what anyone needs from it: status
is a property of a (brick, target) PAIR, not of a brick. The old field cannot
say that world_builder runs on one target and blocks another, and measuring it
(tools/validate_platforms.py) found 214 backing claims of which 8 could be
substantiated.

This writes the spine of the new format. It derives every entry from something
checkable and invents nothing:

    roblox    adapter file present, naming a verified source constructor
                -> constructor-verified
              adapter file present, calls not verified
                -> scaffold
              no adapter, but sourceModule names an upstream module
                -> not-implemented   (the target is intended; the adapter is not written)
              no adapter and no sourceModule
                -> unmapped          (nobody has attempted this target)

    web       -> target `canvas2d`, status `external`
              The Canvas 2D bricks live in the consuming application, so this
              repository cannot verify them. `external` says exactly that
              rather than claiming a status it cannot check.

    unity     -> unmapped
    godot     -> unmapped
              Neither has an implementation anywhere in this repository, and
              `unmapped` is the honest status for a target nobody has tried.

    agnostic  -> no entry. It is a claim about the design, not about a runtime,
              so there is nothing to point at.

What it deliberately does NOT do
--------------------------------
Fixture 11's worked example carries methodMap, extras and gap per target. Those
are hand-researched per brick — writing 71 of them mechanically would be
inventing exactly the kind of unverified detail this library exists to prevent.
The spine goes in; the research is per-brick work that follows.

`platform` is left in place. Both shapes carry during the migration, which is
the answer to fixture 11's first open question, and nothing that reads
`platform` today breaks. tools/compile_build_manifest.py in particular gates
builds on it, and switching that gate to `implementations` would fail 32 of the
40 components in the example Roblox build — a real consequence that deserves
its own change rather than being smuggled in with a format migration.

Idempotent: a descriptor that already has `implementations` is left alone
unless --force is given.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PLATFORM_ARRAY = re.compile(r'"platform"\s*:\s*\[[^\]]*\]')

# `agnostic` is a claim about the design, not a runtime target.
NOT_A_RUNTIME = {"agnostic"}

# The old enum's names, mapped to the target names the new format uses.
TARGET_RENAMES = {"web": "canvas2d"}


def roblox_entry(root: Path, component_id: str, source_module: str | None) -> dict[str, Any]:
    adapter = Path("roblox-adapters") / f"{component_id}.adapter.lua"
    if (root / adapter).exists():
        text = (root / adapter).read_text(encoding="utf-8", errors="replace")
        verified = "Verified source constructor:" in text
        return {
            "target": "roblox",
            "status": "constructor-verified" if verified else "scaffold",
            "module": adapter.as_posix(),
        }
    if source_module:
        return {
            "target": "roblox",
            "status": "not-implemented",
            "module": source_module,
            "note": "Upstream module named; no adapter written.",
        }
    return {"target": "roblox", "status": "unmapped", "module": None}


def build_implementations(root: Path, component: dict[str, Any]) -> list[dict[str, Any]]:
    component_id = component.get("id")
    source_module = component.get("sourceModule")
    entries: list[dict[str, Any]] = []
    for raw in component.get("platform") or []:
        if not isinstance(raw, str) or raw in NOT_A_RUNTIME:
            continue
        target = TARGET_RENAMES.get(raw, raw)
        if target == "roblox":
            entries.append(roblox_entry(root, component_id, source_module))
        elif target == "canvas2d":
            entries.append(
                {
                    "target": "canvas2d",
                    "status": "external",
                    "module": None,
                    "note": "Implemented in the consuming application; not verifiable from this repository.",
                }
            )
        else:
            entries.append({"target": target, "status": "unmapped", "module": None})
    entries.sort(key=lambda e: e["target"])
    return entries


def render(entries: list[dict[str, Any]], minified: bool) -> str:
    """Match the file's own shape. The catalogue keeps one object per line inside
    arrays; four descriptors are single-line and stay that way."""
    objects = [json.dumps(e, ensure_ascii=False, separators=(", ", ": ")) for e in entries]
    if minified:
        return '"implementations":[' + ",".join(
            json.dumps(e, ensure_ascii=False, separators=(",", ":")) for e in entries
        ) + "]"
    body = ",\n".join("    " + o for o in objects)
    return '"implementations": [\n' + body + "\n  ]"


def migrate(path: Path, root: Path, force: bool) -> str:
    text = path.read_text(encoding="utf-8")
    component = json.loads(text)
    if "implementations" in component and not force:
        return "skipped"

    entries = build_implementations(root, component)
    if not entries:
        return "no-targets"

    match = PLATFORM_ARRAY.search(text)
    if not match:
        return "no-platform-field"

    minified = len(text.splitlines()) <= 3
    block = render(entries, minified)
    insertion = ("," + block) if minified else (",\n  " + block)
    updated = text[: match.end()] + insertion + text[match.end():]

    # Never write something that will not parse, and never lose a field.
    reparsed = json.loads(updated)
    assert reparsed["implementations"] == entries, "implementations did not round-trip"
    assert {k: v for k, v in reparsed.items() if k != "implementations"} == component, (
        "migration changed a field other than implementations"
    )
    path.write_text(updated, encoding="utf-8")
    return "migrated"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--force", action="store_true", help="Rewrite descriptors that already have implementations")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    counts: dict[str, int] = {}
    statuses: dict[str, int] = {}
    for path in sorted((root / "components").rglob("*.component.json")):
        if args.dry_run:
            component = json.loads(path.read_text(encoding="utf-8"))
            entries = build_implementations(root, component)
            for e in entries:
                statuses[f"{e['target']}:{e['status']}"] = statuses.get(f"{e['target']}:{e['status']}", 0) + 1
            counts["would-migrate"] = counts.get("would-migrate", 0) + 1
            continue
        result = migrate(path, root, args.force)
        counts[result] = counts.get(result, 0) + 1
        if result == "migrated":
            component = json.loads(path.read_text(encoding="utf-8"))
            for e in component["implementations"]:
                statuses[f"{e['target']}:{e['status']}"] = statuses.get(f"{e['target']}:{e['status']}", 0) + 1

    print(json.dumps({"files": counts, "entriesByTargetStatus": dict(sorted(statuses.items()))}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
