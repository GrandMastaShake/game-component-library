#!/usr/bin/env python3
"""Every asset descriptor is well formed, internally consistent, and unique.

    python3 tools/validate_asset_contracts.py
    python3 tools/validate_asset_contracts.py --report reports/assets.json

WHAT THIS CAN AND CANNOT SEE. It reads `assets/*.asset.json` against
`asset.schema.json` and checks the things the descriptor can contradict on its
own: ids unique and well shaped, socket names unique, levels ordered coarsest
last with triangle counts that actually descend, and every declared band a real
one. It says nothing about whether the FILES exist or contain what is claimed,
because they live in the consuming repository and this one cannot see them —
the same boundary `web-implementations.json` sits on. The app's `check-assets`
is the other half, and it is the half that opens the glTF.

Not named `validate_assets` on purpose: the Blender addon already has a tool by
that name for Roblox upload limits, and two things called the same thing in one
pipeline is how a check gets run and believed to be a different check.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANDS = ["hero", "gameplay", "far", "proxy"]
ID_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
SOCKET_RE = re.compile(r"^[a-z][a-z0-9_]*$")
# An SPDX identifier, loosely: letters, digits, dots and dashes. Not a list of
# valid ones — this repository is not the authority on what licences exist, and
# a stale allowlist would reject a perfectly good licence for being new.
SPDX_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-+]*$")
LEVEL_RE = re.compile(r"^lod[0-9]$")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report")
    args = parser.parse_args()

    schema_path = ROOT / "asset.schema.json"
    if not schema_path.exists():
        print("asset.schema.json is missing — the contract has no shape to check against.")
        return 1
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    required = set(schema.get("required", []))
    allowed = set(schema.get("properties", {}).keys())

    errors: list[str] = []
    seen_ids: dict[str, str] = {}
    assets = sorted((ROOT / "assets").glob("*.asset.json")) if (ROOT / "assets").exists() else []

    for path in assets:
        label = path.name
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{label}: is not valid JSON ({exc})")
            continue

        missing = required - set(data)
        if missing:
            errors.append(f"{label}: missing required field(s) {', '.join(sorted(missing))}")
        extra = set(data) - allowed
        if extra:
            errors.append(f"{label}: unknown field(s) {', '.join(sorted(extra))}")

        aid = data.get("id", "")
        if not ID_RE.match(str(aid)):
            errors.append(f"{label}: id '{aid}' is not a dotted lowercase id")
        elif aid in seen_ids:
            errors.append(f"{label}: id '{aid}' is already declared by {seen_ids[aid]}")
        else:
            seen_ids[aid] = label

        # The filename and the id have to agree, or a reader looking for an
        # asset by id has to open every file to find it.
        if aid and path.name != f"{aid}.asset.json":
            errors.append(f"{label}: declares id '{aid}', so the file should be '{aid}.asset.json'")

        # --- where it came from, and on whose terms ------------------------
        # A SCHEMA IS DOCUMENTATION UNTIL SOMETHING REFUSES. This validator
        # reads `required` off the schema and checks presence, which cannot
        # express "vendored assets need a licence" — so the rule lives here,
        # where it can actually say no. The failure it exists to stop is a
        # third-party model landing in the repository with nobody able to say
        # who made it or what they allowed, which is not a style problem.
        source = data.get("source") or {}
        kind = source.get("kind", "generated")
        if kind not in ("generated", "vendored"):
            errors.append(f"{label}: source.kind '{kind}' is neither generated nor vendored")
        elif kind == "generated":
            if not source.get("script"):
                errors.append(f"{label}: is generated and names no script, so nobody can build it again")
            if data.get("license"):
                errors.append(f"{label}: is generated in this repository and carries a third-party licence")
        else:
            for field in ("url", "sha256"):
                if not source.get(field):
                    errors.append(f"{label}: is vendored and records no source.{field} — the archive it came from is not identifiable")
            lic = data.get("license")
            if not lic:
                errors.append(f"{label}: is vendored and carries no licence, so nothing says what may be done with it")
            else:
                for field in ("spdx", "holder", "url", "verifiedOn", "file"):
                    if not lic.get(field):
                        errors.append(f"{label}: licence records no {field}")
                # The terms have to be NAMED, not described. "free to use" is
                # somebody's recollection of a licence; CC0-1.0 is a licence.
                spdx = str(lic.get("spdx", ""))
                if spdx and not SPDX_RE.match(spdx):
                    errors.append(f"{label}: licence '{spdx}' is not an SPDX identifier")

        # --- sockets -------------------------------------------------------
        names: set[str] = set()
        for socket in data.get("sockets", []):
            name = socket.get("name", "")
            if not SOCKET_RE.match(str(name)):
                errors.append(f"{label}: socket name '{name}' is not lowercase_with_underscores")
            if name in names:
                errors.append(f"{label}: socket '{name}' is declared twice")
            names.add(name)
            pos = socket.get("position")
            if not (isinstance(pos, list) and len(pos) == 3 and all(isinstance(v, (int, float)) for v in pos)):
                errors.append(f"{label}: socket '{name}' has no three-number position")

        # --- levels --------------------------------------------------------
        levels = data.get("levels", [])
        if not levels:
            errors.append(f"{label}: declares no levels, so nothing can be loaded")
        prev_tris = None
        seen_levels: set[str] = set()
        for level in levels:
            lid = level.get("level", "")
            if not LEVEL_RE.match(str(lid)):
                errors.append(f"{label}: level id '{lid}' is not lodN")
            if lid in seen_levels:
                errors.append(f"{label}: level '{lid}' appears twice")
            seen_levels.add(lid)
            band = level.get("distanceBand")
            if band not in BANDS:
                errors.append(f"{label}: level '{lid}' has band '{band}', not one of {', '.join(BANDS)}")
            tris = level.get("triangles")
            if not isinstance(tris, int) or tris < 1:
                errors.append(f"{label}: level '{lid}' has no positive triangle count")
            elif prev_tris is not None and tris > prev_tris:
                # A LEVEL OF DETAIL THAT COSTS MORE THAN THE ONE BEFORE IT IS
                # NOT A LEVEL OF DETAIL. Cheap to state, and it catches a
                # levels array pasted in the wrong order — which reads as
                # correct right up until the far tier is the expensive one.
                errors.append(
                    f"{label}: level '{lid}' has {tris} triangles, more than the {prev_tris} "
                    "of the level before it — the list must run finest to coarsest"
                )
            if isinstance(tris, int):
                prev_tris = tris

        prov = str(data.get("provenance", ""))
        if len(prov.strip()) < 40:
            errors.append(f"{label}: provenance is {len(prov.strip())} characters; say what it was needed by")

    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"assets": len(assets), "errors": errors}, indent=2), encoding="utf-8")

    for err in errors:
        print("  " + err)
    print(f"validate_asset_contracts: {'PASS' if not errors else 'FAIL'} "
          f"({len(assets)} asset(s), {sum(len(json.loads(p.read_text(encoding='utf-8')).get('sockets', [])) for p in assets)} sockets, "
          f"{len(errors)} error(s))")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
