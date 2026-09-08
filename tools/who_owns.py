#!/usr/bin/env python3
"""Before you build it: does something already own this?

THE QUESTION THAT WAS MISSING. The catalogue has a tool for "what would this kit
cost in that genre" (compound_fit) and seven for "is what we have consistent"
(the validators). It had nothing for the question that comes FIRST, which is
whether the thing about to be written already exists.

That gap has a cost and it is on the record: stepped isometric terrain was about
to be implemented a third time. `generator/iso/IsoWorld` had it, `world.tile_grid`
DECLARED it (`elevationAt`, `surfaceAt`), and the plan was to re-derive it inside
whatever painted the ground. Nobody was being careless — there was simply no way
to ask, short of reading 268 descriptors.

WHAT IT SEARCHES, and why the second half matters more than the first:

  1. Every descriptor's id, name, tags, description, input names, output names
     and event names. This finds a contract that already claims the concept.

  2. With --runtime, the consuming app's source. This finds a concept that is
     IMPLEMENTED somewhere the component system cannot see it — a runtime model,
     a helper module, a room. That is where the near-miss lived, and it is the
     half a descriptor search would have missed: `IsoWorld` is not a component
     and never appears in the catalogue at all.

It reports and stops. It cannot tell you whether the existing owner is the right
one, and it should not try: "something already does this" is a fact, and "extend
it or write a new one" is a judgement about whether the existing owner would end
up owning two things.

    python3 tools/who_owns.py elevation
    python3 tools/who_owns.py "line of sight" --runtime ../game-architect-studio/generator
    python3 tools/who_owns.py aggro threat --runtime ../game-architect-studio/generator
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# Where a hit was found, and how much it is worth. A term in an id or an output
# NAME is a claim the component makes about itself; the same word in prose is a
# component that happens to mention it. Ranking them the same buries the one
# answer that matters under thirty that do not.
WEIGHT = {
    "id": 10,
    "output": 8,
    "input": 6,
    "event": 5,
    "tag": 5,
    "name": 4,
    "description": 1,
}
DESCRIPTION_CAP = 3


def load_components() -> list[dict]:
    out = []
    for path in sorted(ROOT.glob("components/**/*.component.json")):
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        data["_path"] = str(path.relative_to(ROOT))
        out.append(data)
    return out


def hits_for(component: dict, terms: list[str]) -> tuple[int, list[str]]:
    """Score one component against the terms, and say where each hit landed."""
    score = 0
    where: list[str] = []

    def look(text: str, kind: str, label: str = "") -> None:
        nonlocal score
        low = (text or "").lower()
        for term in terms:
            if term not in low:
                continue
            if kind == "description":
                # Capped: a long descriptor that says "elevation" nine times is
                # not nine times the answer, and without a cap prose beats a
                # declared output every time.
                add = min(low.count(term), DESCRIPTION_CAP) * WEIGHT[kind]
            else:
                add = WEIGHT[kind]
            score += add
            where.append(f"{kind}{':' + label if label else ''}")

    look(component.get("id", ""), "id")
    look(component.get("name", ""), "name")
    for tag in component.get("tags") or []:
        look(tag, "tag")
    for field, kind in (("inputs", "input"), ("outputs", "output")):
        for item in component.get(field) or []:
            look(item.get("name", ""), kind, item.get("name", ""))
    events = component.get("events") or {}
    for key in ("emits", "listensTo"):
        for ev in events.get(key) or []:
            look(ev, "event", ev)
    look(component.get("description", ""), "description")

    # Deduplicate while keeping order, so "output:elevationAt, output:surfaceAt"
    # reads as two distinct claims rather than a repeated word.
    seen: set[str] = set()
    unique = [w for w in where if not (w in seen or seen.add(w))]
    return score, unique


def scan_runtime(root: Path, terms: list[str]) -> list[tuple[str, int, list[str]]]:
    """Concepts implemented where the component system cannot see them.

    Deliberately reports FILES rather than symbols. The finding is "there is
    already an implementation of this over here", and naming the file is enough
    to go and look; guessing which function is the one would be a parser
    pretending to understand the language.
    """
    if not root.exists():
        return []
    out: list[tuple[str, int, list[str]]] = []
    for path in sorted(root.rglob("*.ts")):
        if "node_modules" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # Comments are stripped: every file in this project explains itself at
        # length, and a header that mentions a concept is not an implementation
        # of it. The same mistake the isometric check made.
        code = re.sub(r"/\*[\s\S]*?\*/", " ", text)
        code = re.sub(r"//.*", " ", code)
        low = code.lower()
        found = [t for t in terms if t in low]
        if not found:
            continue
        count = sum(low.count(t) for t in found)
        out.append((str(path), count, found))
    out.sort(key=lambda r: -r[1])
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("terms", nargs="+", help="concept words, e.g. elevation surface")
    parser.add_argument(
        "--runtime",
        help="a consuming app's source directory, searched for implementations "
             "the component system cannot see",
    )
    parser.add_argument("--top", type=int, default=8, help="components to list (default 8)")
    args = parser.parse_args()

    terms = [t.lower() for t in args.terms]
    components = load_components()

    scored = []
    for component in components:
        score, where = hits_for(component, terms)
        if score:
            scored.append((score, component, where))
    scored.sort(key=lambda r: (-r[0], r[1]["id"]))

    print(f"\nwho owns: {', '.join(terms)}")
    print(f"  searched {len(components)} descriptors\n")

    if not scored:
        print("  NOTHING in the catalogue claims this.")
        print("  That is the green light for a new component — and the moment to write")
        print("  a `provenance` saying what you looked for and did not find.\n")
    else:
        declared = [r for r in scored if any(not w.startswith("description") for w in r[2])]
        print(f"  {len(scored)} descriptors mention it; {len(declared)} DECLARE it "
              f"(in an id, output, input, event or tag rather than in prose)\n")
        print(f"  {'component':<34} {'score':>5}  where it is claimed")
        for score, component, where in scored[: args.top]:
            shown = ", ".join(where[:4])
            if len(where) > 4:
                shown += f", +{len(where) - 4}"
            print(f"  {component['id']:<34} {score:>5}  {shown}")
        if len(scored) > args.top:
            print(f"  ... and {len(scored) - args.top} more (use --top 0 for all)"
                  if args.top else "")
        print()
        if declared:
            top = declared[0][1]
            print(f"  START HERE: {top['id']}  ({top['_path']})")
            print("  If it already owns the concept, the question is whether it can be")
            print("  EXTENDED — a declared input or output — rather than joined by a")
            print("  second component that owns half of the same thing.\n")

    if args.runtime:
        rows = scan_runtime(Path(args.runtime).resolve(), terms)
        print(f"  implementations outside the component system ({args.runtime}):")
        if not rows:
            print("    none — every implementation of this is behind a component.\n")
        else:
            for path, count, found in rows[:6]:
                print(f"    {count:>4} mentions  {path}  [{', '.join(found)}]")
            print()
            print("    A file here is a concept implemented where no descriptor covers it.")
            print("    That is not automatically wrong — a runtime model is allowed to")
            print("    exist — but it IS the place a third implementation gets written by")
            print("    somebody who searched the catalogue and found nothing.\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
