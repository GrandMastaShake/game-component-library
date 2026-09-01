#!/usr/bin/env python3
"""Check what a descriptor's `platform` list is actually backed by.

Why this exists
---------------
Every other declaration in this library is load-bearing. `dependencies` is
resolved, `events` is wired, `inputs` is audited against the implementation,
`topology` is validated. `platform` is the one list nothing has ever checked,
and the numbers say why that matters: 71 descriptors claim `roblox` and 8 have
a Roblox adapter; 59 claim `godot` and 57 claim `unity`, with no implementation
of either anywhere in the repository.

That is not necessarily 62 lies. `platform` is ambiguous — it can be read as
"this design applies to these engines" or as "this runs on these engines", and
the two readings disagree about almost every descriptor in the catalogue. The
ambiguity is the finding. This tool does not resolve it; it measures it, so the
migration to a per-target format (see fixtures 10 and 11: status is a property
of a brick-target PAIR, not of a brick) can be sized instead of guessed at.

What it can and cannot know
---------------------------
A target is checkable only where this repository defines where an
implementation would live. Today that is exactly one:

    roblox  ->  roblox-adapters/<component id>.adapter.lua

Canvas 2D implementations live in the consuming application, not here, so
`web` is unverifiable from inside this repo — and saying so is more useful than
quietly passing it.

Rules
-----
Blocking:
  PLAT001  `platform` claims a target this repo can check, implementation absent
  PLAT002  an `implementations` entry asserts a module that is not on disk
  PLAT003  an `implementations` status contradicts what is on disk

Advisory (worth a human look, not a failure):
  PLAT010  claims a runtime target this repo has no way to check
  PLAT011  a `platform` target with no matching `implementations` entry
  PLAT020  sourceModule names a path outside this repository, so nothing here
           can verify it — and being a single string it can only ever describe
           one target's implementation

PLAT002 only applies to statuses that ASSERT a module is present. A
`not-implemented` entry deliberately points at an upstream module that is not
here, which is the whole reason that status exists.

Exit code is non-zero only for PLAT001 findings that are not in the baseline,
so the advisories can accumulate visibly without wedging CI.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

# `agnostic` is not a runtime. It says the design is not engine-specific, which
# is a claim about the descriptor rather than about any implementation, so there
# is nothing to look for.
NOT_A_RUNTIME = {"agnostic"}

# Where an implementation for a given target would live, relative to the repo
# root. A target absent from this table is one this repository cannot check.
TARGET_LOCATIONS: dict[str, Callable[[str], str]] = {
    "roblox": lambda component_id: f"roblox-adapters/{component_id}.adapter.lua",
}

# The old platform enum's names, mapped to the target names implementations uses.
TARGET_RENAMES = {"web": "canvas2d"}

# Statuses that claim an implementation is present HERE. `not-implemented`
# points at an upstream module on purpose, and `external` at another repo, so
# neither asserts anything this validator could look for.
ASSERTS_MODULE_PRESENT = {"running", "constructor-verified", "scaffold"}


@dataclass(frozen=True)
class Finding:
    code: str
    component: str
    target: str
    detail: str
    severity: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "component": self.component,
            "target": self.target,
            "detail": self.detail,
            "severity": self.severity,
        }


def load_components(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    out: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted((root / "components").rglob("*.component.json")):
        try:
            out.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"warning: skipping {path} ({exc})", file=sys.stderr)
    return out


def check_component(root: Path, component: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    component_id = component.get("id")
    if not isinstance(component_id, str):
        return findings

    platforms = component.get("platform")
    if not isinstance(platforms, list):
        return findings

    for target in platforms:
        if not isinstance(target, str) or target in NOT_A_RUNTIME:
            continue
        locate = TARGET_LOCATIONS.get(target)
        if locate is None:
            findings.append(
                Finding(
                    "PLAT010",
                    component_id,
                    target,
                    f"claims '{target}', which this repository has no way to check",
                    "warning",
                )
            )
            continue
        relative = locate(component_id)
        if not (root / relative).exists():
            findings.append(
                Finding(
                    "PLAT001",
                    component_id,
                    target,
                    f"claims '{target}' but {relative} does not exist",
                    "error",
                )
            )

    implementations = component.get("implementations")
    if isinstance(implementations, list):
        declared_targets = {
            e.get("target") for e in implementations if isinstance(e, dict)
        }
        for raw in platforms:
            if not isinstance(raw, str) or raw in NOT_A_RUNTIME:
                continue
            target = TARGET_RENAMES.get(raw, raw)
            if target not in declared_targets:
                findings.append(
                    Finding(
                        "PLAT011",
                        component_id,
                        target,
                        f"platform claims '{raw}' with no matching implementations entry",
                        "warning",
                    )
                )
        for entry in implementations:
            if not isinstance(entry, dict):
                continue
            target = entry.get("target") or "?"
            status = entry.get("status")
            module = entry.get("module")
            # Only statuses that assert a module is present are checked for it.
            if status in ASSERTS_MODULE_PRESENT:
                if not isinstance(module, str) or not (root / module).exists():
                    findings.append(
                        Finding(
                            "PLAT002",
                            component_id,
                            target,
                            f"status '{status}' asserts a module, but {module!r} is not on disk",
                            "error",
                        )
                    )
            locate = TARGET_LOCATIONS.get(target)
            if locate is not None and isinstance(component_id, str):
                on_disk = (root / locate(component_id)).exists()
                asserts = status in ASSERTS_MODULE_PRESENT
                if asserts != on_disk:
                    findings.append(
                        Finding(
                            "PLAT003",
                            component_id,
                            target,
                            (
                                f"status '{status}' says the implementation is "
                                f"{'present' if asserts else 'absent'}, but "
                                f"{locate(component_id)} is "
                                f"{'present' if on_disk else 'absent'}"
                            ),
                            "error",
                        )
                    )

    source_module = component.get("sourceModule")
    if isinstance(source_module, str) and not (root / source_module).exists():
        findings.append(
            Finding(
                "PLAT020",
                component_id,
                "-",
                f"sourceModule '{source_module}' is not in this repository",
                "warning",
            )
        )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--report", type=Path, help="Optional JSON report output path")
    parser.add_argument(
        "--baseline",
        type=Path,
        help=(
            "Path to a baseline of accepted findings. Anything listed there is "
            "reported as known and does not fail the build."
        ),
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Rewrite the baseline from the current findings instead of checking against it",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    components = load_components(root)
    if not components:
        print(f"error: no descriptors under {root / 'components'}", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    for _, component in components:
        findings.extend(check_component(root, component))

    # Same reasoning as the topology baseline: a check that lands red on an
    # existing catalogue gets switched off by whoever it blocks. Recording what
    # is already true lets this fail on NEW findings from the day it lands,
    # while the file stays a visible ledger of how much there is to work off.
    baseline: set[tuple[str, str, str]] = set()
    if args.baseline and args.baseline.exists() and not args.write_baseline:
        try:
            recorded = json.loads(args.baseline.read_text(encoding="utf-8"))
            baseline = {
                (item["code"], item["component"], item["target"])
                for item in recorded.get("accepted", [])
            }
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            print(f"warning: could not read baseline ({exc}); checking without it", file=sys.stderr)

    if args.write_baseline:
        if not args.baseline:
            print("error: --write-baseline requires --baseline", file=sys.stderr)
            return 2
        payload = {
            "note": (
                "Descriptors claiming a target this repository can check, where the "
                "implementation is absent. Accepted at the time platform validation "
                "was introduced. Removing an entry is either the implementation "
                "landing or the claim being corrected; adding one should be a "
                "deliberate, reviewed decision. See fixtures 10 and 11 in the "
                "consuming app: the durable fix is a per-target implementation list, "
                "because status belongs to a brick-target pair rather than to a brick."
            ),
            "accepted": sorted(
                (
                    {"code": f.code, "component": f.component, "target": f.target}
                    for f in findings
                    if f.severity == "error"
                ),
                key=lambda item: (item["code"], item["component"], item["target"]),
            ),
        }
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {len(payload['accepted'])} accepted findings to {args.baseline}")
        return 0

    known = [f for f in findings if f.severity == "error" and (f.code, f.component, f.target) in baseline]
    errors = [f for f in findings if f.severity == "error" and (f.code, f.component, f.target) not in baseline]
    warnings = [f for f in findings if f.severity == "warning"]

    claimed = Counter()
    backed = Counter()
    for _, component in components:
        component_id = component.get("id")
        for target in component.get("platform") or []:
            if not isinstance(target, str) or target in NOT_A_RUNTIME:
                continue
            claimed[target] += 1
            locate = TARGET_LOCATIONS.get(target)
            if locate and isinstance(component_id, str) and (root / locate(component_id)).exists():
                backed[target] += 1

    report = {
        "status": "FAIL" if errors else "PASS",
        "componentCount": len(components),
        "checkableTargets": sorted(TARGET_LOCATIONS),
        "claimsByTarget": dict(sorted(claimed.items())),
        "backedByTarget": {t: backed.get(t, 0) for t in sorted(claimed)},
        "errorCount": len(errors),
        "knownCount": len(known),
        "warningCount": len(warnings),
        "migratedToImplementations": sum(
            1 for _, c in components if isinstance(c.get("implementations"), list)
        ),
        "implementationStatuses": dict(
            sorted(
                Counter(
                    f"{e.get('target')}:{e.get('status')}"
                    for _, c in components
                    for e in (c.get("implementations") or [])
                    if isinstance(e, dict)
                ).items()
            )
        ),
        "findingsByCode": dict(sorted(Counter(f.code for f in findings).items())),
        "errors": [f.as_dict() for f in errors],
        "warnings": [f.as_dict() for f in warnings],
    }

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
