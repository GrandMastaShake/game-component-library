#!/usr/bin/env python3
"""Validate genre packs against the schema and the component catalogue.

`genre.schema.json` has existed since the genre packs landed and nothing read
it. Twenty genre descriptors reached `main` in PR #20 with no validator and no
CI step, and one of them names a component that does not exist:

    genres/exploration_collectathon.genre.json
      memberComponents:      world.collectible_scatter
      signatureCompound:     world.collectible_scatter
      actually on disk:      economy.collectible_scatter

That is not a missing component. The file is right there under
`components/economy/CollectibleScatter.component.json` -- the genre wrote the
wrong namespace. A consumer resolving that pack gets a signature compound one
member short and no explanation, which is exactly the failure mode
`validate_compounds.py` was written to stop for compounds.

So this applies the same rule to genres, in the same order: shape before
contents. Every key the schema requires is present, no key it does not define
is present, and then every component id a genre names resolves.

The namespace hint at the end is the part worth keeping. A dangling id whose
slug matches a real component under a different category is almost always a
typo rather than unbuilt work, and saying so turns a puzzled ten minutes into a
one-word fix.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    errors = []
    warnings = []

    # --- the catalogue, as the authority on which ids exist ------------------
    components = {}
    for path in sorted((ROOT / "components").rglob("*.component.json")):
        try:
            component = load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: invalid JSON ({exc})")
            continue
        cid = component.get("id")
        if isinstance(cid, str) and cid:
            components[cid] = component
    # slug -> the ids that end with it, for the namespace hint below
    by_slug = {}
    for cid in components:
        by_slug.setdefault(cid.split(".")[-1], []).append(cid)

    # --- shape, read from the schema rather than restated here ---------------
    try:
        schema = load_json(ROOT / "genre.schema.json")
        allowed = set(schema.get("properties", {}))
        required = list(schema.get("required", []))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"genre.schema.json: unreadable ({exc})")
        allowed, required = set(), []

    genre_dir = ROOT / "genres"
    paths = sorted(genre_dir.glob("*.genre.json")) if genre_dir.is_dir() else []

    genres = []
    for path in paths:
        try:
            genres.append((path, load_json(path)))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: invalid JSON ({exc})")

    seen_ids = {}
    referenced = 0
    for path, genre in genres:
        label = genre.get("id", path.stem)

        for key in required:
            if key not in genre:
                errors.append(f"{label}: missing required key '{key}' (genre.schema.json)")
        if allowed:
            for key in sorted(set(genre) - allowed):
                errors.append(f"{label}: unknown key '{key}' — genre.schema.json defines {sorted(allowed)}")

        gid = genre.get("id")
        if isinstance(gid, str) and gid:
            if gid in seen_ids:
                errors.append(f"duplicate genre id: {gid}")
            seen_ids[gid] = path

        # A loop with no arrow is a sentence, not a loop. Consumers split on the
        # arrow to get the stages, so a single-stage loop is worth saying.
        loop = genre.get("loop")
        if isinstance(loop, str) and "→" not in loop and "->" not in loop:
            warnings.append(f"{label}: loop has no stages — '{loop}'")

        views = genre.get("views")
        if not isinstance(views, list) or not views or not all(isinstance(v, str) and v for v in views):
            errors.append(f"{label}: views must be a non-empty array of strings")

        # --- contents: every named component resolves ------------------------
        signature = genre.get("signatureCompound") or {}
        named = {
            "memberComponents": genre.get("memberComponents", []),
            "newComponents": genre.get("newComponents", []),
            "signatureCompound.memberIds": signature.get("memberIds", []),
        }
        if not isinstance(signature.get("memberIds"), list):
            errors.append(f"{label}: signatureCompound.memberIds must be an array")

        for field, ids in named.items():
            if not isinstance(ids, list):
                errors.append(f"{label}: {field} must be an array")
                continue
            for cid in ids:
                referenced += 1
                if cid in components:
                    continue
                # The namespace hint. `world.collectible_scatter` against a real
                # `economy.collectible_scatter` is a typo, not unbuilt work, and
                # the two deserve different sentences.
                near = by_slug.get(str(cid).split(".")[-1], [])
                if near:
                    errors.append(
                        f"{label}: {field} names '{cid}', which does not exist — "
                        f"did you mean {' or '.join(sorted(near))}?"
                    )
                else:
                    errors.append(f"{label}: {field} names '{cid}', which no component declares")

        # A signature compound that is not drawn from the genre's own members is
        # describing a different genre.
        member_set = set(genre.get("memberComponents", []) or []) | set(genre.get("newComponents", []) or [])
        for cid in signature.get("memberIds", []) or []:
            if cid not in member_set:
                errors.append(
                    f"{label}: signatureCompound names '{cid}', which the genre does not list "
                    "in memberComponents or newComponents"
                )

    report = {
        "status": "PASS" if not errors else "FAIL",
        "genreCount": len(genres),
        "componentCount": len(components),
        "referencedComponentIds": referenced,
        "warnings": warnings,
        "errors": errors,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(
        f"validate_genres: {report['status']} ({len(genres)} genres, "
        f"{referenced} component references, {len(errors)} errors)"
    )
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
