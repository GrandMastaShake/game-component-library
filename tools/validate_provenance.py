#!/usr/bin/env python3
"""Every NEW component has to say what it was found by, and what it is not.

WHY THIS IS A GATE AND NOT A STYLE NOTE. The catalogue's whole value is that a
piece written for one genre is grabbable for the next, and the thing that
destroys it is a second component quietly owning half of what an existing one
owns. That has nearly happened: stepped isometric terrain was about to be
implemented a third time, with `world.tile_grid` already declaring `elevationAt`
and `generator/iso/IsoWorld` already implementing it.

`provenance` is where the author records having looked. It is not paperwork —
it is the one field that turns "I could not find anything like this" from a
private belief into a reviewable claim, and it is the field a reader reaches for
when two components look similar and they need to know which came second and
why.

RATCHET, NOT BIG BANG. 51 components predate the rule and are baselined. They
are not a backlog to be closed on a schedule; they are a line that must not
move outward. Anything new complies, and a baselined component that GAINS
provenance is reported so the baseline shrinks — a baseline that only ever
grows is a permission slip.

    python3 tools/validate_provenance.py
    python3 tools/validate_provenance.py --baseline provenance-baseline.json
    python3 tools/validate_provenance.py --write-baseline provenance-baseline.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Short enough to be a shrug rather than a record. The number is a judgement and
# is deliberately low: the bar is "a sentence that would help the next person",
# not an essay, and a gate that demands an essay gets an essay nobody reads.
MIN_LENGTH = 40


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--baseline", default="provenance-baseline.json")
    parser.add_argument("--write-baseline", help="record today's gaps as the baseline")
    parser.add_argument("--report")
    args = parser.parse_args()

    missing: list[str] = []
    thin: list[tuple[str, int]] = []
    present: set[str] = set()

    for path in sorted(ROOT.glob("components/**/*.component.json")):
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        cid = data["id"]
        prov = (data.get("provenance") or "").strip()
        if not prov:
            missing.append(cid)
        else:
            present.add(cid)
            if len(prov) < MIN_LENGTH:
                thin.append((cid, len(prov)))

    if args.write_baseline:
        out = ROOT / args.write_baseline
        with out.open("w", encoding="utf-8") as fh:
            json.dump(
                {
                    "componentsWithoutProvenance": sorted(missing),
                    # Recorded separately from the absent ones because they are a
                    # different debt. A component whose provenance reads "Squad E
                    # pass 2" was written under a convention that did not ask for
                    # more; treating that as identical to one with no provenance
                    # at all would make both numbers useless.
                    "componentsWithThinProvenance": sorted(c for c, _ in thin),
                },
                fh,
                indent=2,
            )
            fh.write("\n")
        print(
            f"wrote {args.write_baseline}: {len(missing)} with no provenance, "
            f"{len(thin)} with a thin one"
        )
        return 0

    baseline_path = ROOT / args.baseline
    baselined: set[str] = set()
    baselined_thin: set[str] = set()
    if baseline_path.exists():
        with baseline_path.open(encoding="utf-8") as fh:
            doc = json.load(fh)
        baselined = set(doc.get("componentsWithoutProvenance") or [])
        baselined_thin = set(doc.get("componentsWithThinProvenance") or [])

    problems = 0
    new_gaps = sorted(set(missing) - baselined)
    for cid in new_gaps:
        print(f"provenance  {cid}: no `provenance`. Say what you searched for and did not "
              f"find, and which existing component this is NOT.")
        problems += 1
    for cid, n in thin:
        if cid in baselined or cid in baselined_thin:
            continue
        print(f"provenance  {cid}: `provenance` is {n} characters. That is a shrug, not a record.")
        problems += 1

    # The ratchet tightening. Not a failure — the opposite — but silent progress
    # is progress that gets undone.
    thin_now = {c for c, _ in thin}
    closed = sorted((baselined & present) | (baselined_thin - thin_now))
    if closed:
        print(f"provenance: {len(closed)} baselined components now HAVE provenance "
              f"({', '.join(closed[:4])}{', …' if len(closed) > 4 else ''}).")
        print("  Re-run with --write-baseline to shrink the baseline; a baseline that "
              "only grows is a permission slip.")

    print(
        f"provenance: {len(present)} of {len(present) + len(missing)} components record one; "
        f"{len(baselined) + len(baselined_thin)} grandfathered, {len(new_gaps)} new gaps"
    )

    if args.report:
        out = ROOT / args.report
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as fh:
            json.dump(
                {
                    "withProvenance": sorted(present),
                    "without": sorted(missing),
                    "baselined": sorted(baselined),
                    "newGaps": new_gaps,
                    "baselineNowClosed": closed,
                },
                fh,
                indent=2,
            )
            fh.write("\n")

    print(f"provenance problems: {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
