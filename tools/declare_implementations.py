#!/usr/bin/env python3
"""Apply web-implementations.json to the descriptors' `implementations` field.

The library has no way to see the consuming application, so every web-target
entry is status `external`. That is honest, but only if something keeps the
claim in step with reality — and nothing did: 39 of 71 descriptors named a
canvas2d implementation while the app registered all 71. The undercount was
invisible because the two lists were never compared.

So the list lives in `web-implementations.json`, in this repository, where it is
reviewable in a diff; this script applies it, and `--check` fails if the
descriptors have drifted from it. Ids in the manifest that name no descriptor
are an error either way — that is the failure mode this is really guarding
against, a manifest that quietly stops meaning anything.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MANIFEST = "web-implementations.json"
NOTE = "Implemented in the consuming application; not verifiable from this repository."


def descriptors(root: Path) -> dict[str, tuple[Path, dict]]:
    found: dict[str, tuple[Path, dict]] = {}
    for path in sorted(root.glob("components/**/*.component.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        found[data["id"]] = (path, data)
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument(
        "--check",
        action="store_true",
        help="Report drift and exit non-zero instead of writing anything",
    )
    args = ap.parse_args()

    manifest = json.loads((args.root / MANIFEST).read_text(encoding="utf-8"))
    known = descriptors(args.root)

    problems: list[str] = []
    changed: list[str] = []

    for target, ids in manifest["targets"].items():
        for cid in ids:
            if cid not in known:
                problems.append(f"{MANIFEST} names '{cid}' for {target}, which is not a descriptor")
                continue
            path, data = known[cid]
            impls = data.setdefault("implementations", [])
            entry = next((i for i in impls if i.get("target") == target), None)
            if entry is not None and entry.get("status") == "external":
                continue
            if entry is None:
                impls.append({"target": target, "status": "external", "module": None, "note": NOTE})
            else:
                entry["status"] = "external"
                entry.setdefault("note", NOTE)
            impls.sort(key=lambda i: i["target"])
            changed.append(f"{cid}: {target} -> external")
            if not args.check:
                path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    for line in changed:
        print(("drift: " if args.check else "set: ") + line)
    for line in problems:
        print("error: " + line, file=sys.stderr)

    if problems:
        return 1
    if args.check and changed:
        print(f"\n{len(changed)} descriptor(s) out of step with {MANIFEST}", file=sys.stderr)
        return 1
    print(f"implementations in step with {MANIFEST}" if args.check else f"applied {len(changed)} change(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
