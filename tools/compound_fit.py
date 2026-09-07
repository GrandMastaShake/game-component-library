#!/usr/bin/env python3
"""What would it cost to drop a compound into a genre pack?

THE QUESTION THIS EXISTS TO ANSWER. The catalogue's whole promise is that the
pieces built for one genre are grabbable for the next. That promise is either
true or it is not, and until now the only way to find out was to read a genre
pack, read a compound, and do the set arithmetic by hand -- which nobody does,
so the promise went unchecked and the answer drifted.

It CHANGES NOTHING. No pack is edited, no component is added; this reports the
delta and stops. Wiring a kit into a pack is a decision about that genre, made
when that genre is being built, and a tool that quietly did it would be making
thirty-four such decisions on nobody's behalf.

Cost is the TRANSITIVE cost. Naming a component pulls its dependencies in
behind it, so "add six components" is the wrong number whenever one of them
drags four more -- and that difference is exactly what decides whether a kit is
cheap to adopt or is a second genre in a trench coat.

    python3 tools/compound_fit.py                                # every compound, every genre
    python3 tools/compound_fit.py compound.real_time_encounter   # one compound
    python3 tools/compound_fit.py compound.real_time_encounter genre.dungeon_crawler
    python3 tools/compound_fit.py --report reports/compound-fit.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_components() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(ROOT.glob("components/**/*.component.json")):
        data = load_json(path)
        out[data["id"]] = data
    return out


def load_compounds() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(ROOT.glob("compounds/*.compound.json")):
        data = load_json(path)
        out[data["id"]] = data
    return out


def load_genres() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(ROOT.glob("genres/*.genre.json")):
        data = load_json(path)
        out[data["id"]] = data
    return out


def load_web_targets() -> set[str]:
    """Component ids the app declares a canvas2d implementation for.

    Read from web-implementations.json rather than from each descriptor's own
    `implementations` block, because that block is the CLAIM and this file is
    the reviewed record -- declare_implementations.py exists to keep them in
    step, and this reads the side that was checked.
    """
    path = ROOT / "web-implementations.json"
    if not path.exists():
        return set()
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, list):
            if node and all(isinstance(x, str) for x in node):
                found.update(x for x in node if "." in x)
            else:
                for item in node:
                    walk(item)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)

    walk(load_json(path))
    return found


def closure(ids: set[str], components: dict[str, dict]) -> tuple[set[str], set[str]]:
    """Everything those ids need, and the ids that do not exist at all.

    A missing component is reported rather than skipped: "this kit needs three
    things nobody has written" is the most important thing a fit report can say
    and the easiest to lose by treating an unknown id as a no-op.
    """
    seen: set[str] = set()
    unknown: set[str] = set()
    queue = list(ids)
    while queue:
        current = queue.pop()
        if current in seen or current in unknown:
            continue
        component = components.get(current)
        if component is None:
            unknown.add(current)
            continue
        seen.add(current)
        queue.extend(component.get("dependencies") or [])
    return seen, unknown


def fit(compound: dict, genre: dict, components: dict[str, dict], web: set[str]) -> dict:
    members = {c["id"] for c in compound.get("components", [])}
    named = set(genre.get("memberComponents") or []) | set(genre.get("newComponents") or [])

    needed, unknown = closure(members, components)
    missing = sorted(needed - named)
    already = sorted(needed & named)

    # The members themselves, separately from what they drag in: a pack that has
    # five of six members and is missing one dependency reads very differently
    # from one missing five members.
    members_missing = sorted(members - named)
    pulled_in = sorted(set(missing) - members)

    return {
        "genre": genre["id"],
        "genreName": genre.get("name", genre["id"]),
        # WHAT'S THE RELATION? A bare "5 to add" is a number with nothing to
        # measure itself against. Five members of six is a kit this pack nearly
        # has; five of twenty is a kit it barely touches; and five added to a
        # pack of twelve is a different proposition from five added to a pack of
        # thirty. All three are the same "5" until the denominators sit beside it.
        "membersTotal": len(members),
        "membersNamed": len(members & named),
        "packSize": len(named),
        "membersAlreadyNamed": sorted(members & named),
        "membersMissing": members_missing,
        "dependenciesPulledIn": pulled_in,
        "unknownComponents": sorted(unknown),
        "totalToAdd": len(missing),
        # A component that has no reviewed canvas2d implementation is one this
        # app cannot run yet, whatever the pack says. Named so "cheap to adopt"
        # and "cheap to actually play" stay different questions.
        "missingWithoutWebImplementation": sorted(x for x in missing if x not in web),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("compound", nargs="?", help="compound id, e.g. compound.real_time_encounter")
    parser.add_argument("genre", nargs="?", help="genre id, e.g. genre.dungeon_crawler")
    parser.add_argument("--report", help="write the full result as JSON")
    parser.add_argument("--max-rows", type=int, default=12, help="genres to print per compound (0 for all)")
    args = parser.parse_args()

    components = load_components()
    compounds = load_compounds()
    genres = load_genres()
    web = load_web_targets()

    if args.compound and args.compound not in compounds:
        print(f"no such compound: {args.compound}", file=sys.stderr)
        print("known: " + ", ".join(sorted(compounds)), file=sys.stderr)
        return 2
    if args.genre and args.genre not in genres:
        print(f"no such genre: {args.genre}", file=sys.stderr)
        return 2

    chosen = [compounds[args.compound]] if args.compound else list(compounds.values())
    targets = [genres[args.genre]] if args.genre else list(genres.values())

    report: dict[str, Any] = {"compounds": {}}
    for compound in chosen:
        rows = [fit(compound, genre, components, web) for genre in targets]
        # Cheapest first: the point of the report is "where does this already
        # nearly fit", and a list sorted by id buries that under the alphabet.
        rows.sort(key=lambda r: (len(r["membersMissing"]), r["totalToAdd"], r["genre"]))
        report["compounds"][compound["id"]] = {
            "name": compound.get("name", compound["id"]),
            "members": [c["id"] for c in compound.get("components", [])],
            "fits": rows,
        }

        member_ids = [c["id"] for c in compound.get("components", [])]
        print(f"\n{compound.get('name', compound['id'])}  ({compound['id']})")
        print(f"  {len(member_ids)} members: {', '.join(member_ids)}")
        # FITTING IS ABOUT MEMBERS, NOT DEPENDENCIES. A genre pack names what it
        # is built FROM; resolve() closes the dependency graph behind it, so a
        # dependency the pack does not mention costs nothing to adopt and is
        # not a reason to say the kit does not fit. Counting them made this
        # report claim the kit fitted 0 of 35 genres while the pack it was
        # written for was sitting at the top of its own list.
        # A THIRD COMPARISON, kept off the table because it is a different
        # question: adoptable and playable are not the same. A member with no
        # reviewed canvas2d implementation costs nothing to NAME and cannot be
        # run, and a pack that adopts three of those has adopted a promise.
        no_web = [m for m in member_ids if m not in web]
        if no_web:
            print(f"  {len(no_web)} of {len(member_ids)} members have no reviewed canvas2d "
                  f"implementation: {', '.join(no_web)}")
        ready = [r for r in rows if not r["membersMissing"]]
        print(f"  fits {len(ready)} of {len(rows)} genres with no member to add"
              + (f": {', '.join(r['genre'].replace('genre.', '') for r in ready)}" if ready else ""))

        shown = rows if args.max_rows == 0 else rows[: args.max_rows]
        # COMPARED TO WHAT? Two comparisons, because a cost with none is just
        # a number: what fraction of the kit the pack already holds, and how
        # the addition compares to the pack's own size. Four members is cheap
        # against a pack of thirty and is a rewrite against a pack of eight,
        # and the same figure reads both ways without the denominator.
        print(f"  {'genre':<26} {'has':>7} {'pack':>5} {'add':>4} {'% of pack':>10}  what it would take")
        for row in shown:
            what = ", ".join(x.split(".", 1)[1] for x in row["membersMissing"][:3])
            if len(row["membersMissing"]) > 3:
                what += f", +{len(row['membersMissing']) - 3} more"
            add = len(row["membersMissing"])
            pct = (add / row["packSize"] * 100) if row["packSize"] else 0
            print(
                f"  {row['genre'].replace('genre.', ''):<26}"
                f" {row['membersNamed']:>3}/{row['membersTotal']:<3}"
                f" {row['packSize']:>5} {add:>4} {pct:>9.0f}%"
                f"  {what or 'nothing: it already names every member'}"
            )
        if args.max_rows and len(rows) > args.max_rows:
            print(f"  ... and {len(rows) - args.max_rows} more (use --max-rows 0)")

        blocked = sorted({x for r in rows for x in r["unknownComponents"]})
        if blocked:
            print(f"  REFERENCES COMPONENTS THAT DO NOT EXIST: {', '.join(blocked)}")

    if args.report:
        out = ROOT / args.report
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
        print(f"\nwrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
