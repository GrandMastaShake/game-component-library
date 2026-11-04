#!/usr/bin/env python3
"""Validate boss phases, arena hazards, adds, telegraphs, and enrages.

The component graph proves that the owners can be wired. This validator checks
whether authored encounters can actually transition, warn, spawn, escalate, and
complete deterministically. All encounters and balance remain host supplied.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
CONDITION_EVENTS = {
    "input.bossConditionSatisfied",
    "world.worldFlagChanged",
    "progression.questStageChanged",
}
SHAPE_DIMENSIONS = {
    "circle": ("radius",),
    "line": ("length", "width"),
    "cone": ("radius", "angle"),
    "single": (),
}
TRIGGER_FIELDS = {"healthAtOrBelow", "elapsedSecondsAtLeast", "conditionEvent"}


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _integer(value, minimum=0) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _valid_id(value) -> bool:
    return isinstance(value, str) and bool(ID_PATTERN.match(value))


def _id_array(value, label, errors, known=None, allow_empty=True):
    if not isinstance(value, list) or (not allow_empty and not value):
        suffix = "non-empty " if not allow_empty else ""
        errors.append(f"{label} must be a {suffix}array")
        return []
    result = []
    for index, item in enumerate(value):
        if not _valid_id(item):
            errors.append(f"{label}[{index}] must be a well-formed id")
        elif known is not None and item not in known:
            errors.append(f"{label}[{index}] unknown id '{item}'")
        else:
            result.append(item)
    if len(result) != len(set(result)):
        errors.append(f"{label} contains duplicate ids")
    return result


def _regions(value, label, errors):
    if not isinstance(value, list) or not value:
        errors.append(f"{label} must be a non-empty array")
        return
    for index, region in enumerate(value):
        rlabel = f"{label}[{index}]"
        if not isinstance(region, dict):
            errors.append(f"{rlabel} must be an object")
            continue
        for field in ("x", "y"):
            if not _number(region.get(field)):
                errors.append(f"{rlabel}.{field} must be finite")
        for field in ("width", "height"):
            if not _number(region.get(field)) or region.get(field) <= 0:
                errors.append(f"{rlabel}.{field} must be a finite number > 0")


def _shape(shape, label, errors):
    if not isinstance(shape, dict):
        errors.append(f"{label} must be an object")
        return
    kind = shape.get("kind")
    if kind not in SHAPE_DIMENSIONS:
        errors.append(f"{label}: kind must be one of {sorted(SHAPE_DIMENSIONS)}")
        return
    for dimension in SHAPE_DIMENSIONS[kind]:
        if not _number(shape.get(dimension)) or shape.get(dimension) <= 0:
            errors.append(f"{label}.{dimension} must be a finite number > 0")


def _attacks(value, label, errors, attack_ids):
    if not isinstance(value, list):
        errors.append(f"{label} must be an array")
        return
    for index, attack in enumerate(value):
        alabel = f"{label}[{index}]"
        if not isinstance(attack, dict):
            errors.append(f"{alabel} must be an object")
            continue
        attack_id = attack.get("id")
        if not _valid_id(attack_id):
            errors.append(f"{alabel}: id must match {ID_PATTERN.pattern}")
        elif attack_id in attack_ids:
            errors.append(f"{label}: duplicate attack id '{attack_id}' in encounter")
        else:
            attack_ids.add(attack_id)
        if not _number(attack.get("windupSeconds")) or attack.get("windupSeconds") <= 0:
            errors.append(f"{alabel}: windupSeconds must be a finite number > 0")
        if not _number(attack.get("cooldownSeconds")) or attack.get("cooldownSeconds") < 0:
            errors.append(f"{alabel}: cooldownSeconds must be a finite number >= 0")
        if not _number(attack.get("damage")) or attack.get("damage") <= 0:
            errors.append(f"{alabel}: damage must be a finite number > 0")
        _shape(attack.get("shape"), alabel + ":shape", errors)


def _adds(value, label, errors):
    if not isinstance(value, list):
        errors.append(f"{label} must be an array")
        return
    for index, add in enumerate(value):
        alabel = f"{label}[{index}]"
        if not isinstance(add, dict):
            errors.append(f"{alabel} must be an object")
            continue
        if not _valid_id(add.get("archetype")):
            errors.append(f"{alabel}: archetype must be a well-formed id")
        if not _integer(add.get("count"), 1):
            errors.append(f"{alabel}: count must be an integer >= 1")
        if not _number(add.get("baseHealth")) or add.get("baseHealth") <= 0:
            errors.append(f"{alabel}: baseHealth must be a finite number > 0")
        if "socket" in add and not _valid_id(add.get("socket")):
            errors.append(f"{alabel}: socket must be a well-formed id")
        _id_array(add.get("masteryTags", []), alabel + ":masteryTags", errors)


def _trigger(phase, label, errors, condition_ids, first):
    if first:
        if "enterWhen" in phase:
            errors.append(f"{label}: the first phase enters on engagement and cannot declare enterWhen")
        return
    trigger = phase.get("enterWhen")
    if not isinstance(trigger, dict):
        errors.append(f"{label}: enterWhen must be an object with exactly one transition kind")
        return
    present = TRIGGER_FIELDS & set(trigger)
    if len(present) != 1:
        errors.append(f"{label}: enterWhen needs exactly one of {sorted(TRIGGER_FIELDS)}")
        return
    if "healthAtOrBelow" in present:
        value = trigger.get("healthAtOrBelow")
        if not _number(value) or not 0 < value < 1:
            errors.append(f"{label}: healthAtOrBelow must be between 0 and 1 exclusive")
    elif "elapsedSecondsAtLeast" in present:
        value = trigger.get("elapsedSecondsAtLeast")
        if not _number(value) or value <= 0:
            errors.append(f"{label}: elapsedSecondsAtLeast must be a finite number > 0")
    else:
        event = trigger.get("conditionEvent")
        if event not in CONDITION_EVENTS:
            errors.append(f"{label}: conditionEvent must be one of {sorted(CONDITION_EVENTS)}")
        condition_id = trigger.get("conditionId")
        if not _valid_id(condition_id):
            errors.append(f"{label}: conditionId must be a well-formed stable id")
        elif condition_id in condition_ids:
            errors.append(f"{label}: duplicate conditionId '{condition_id}'")
        else:
            condition_ids.add(condition_id)
        match = trigger.get("conditionMatch")
        if not isinstance(match, dict) or not match:
            errors.append(f"{label}: conditionMatch must be a non-empty object")
        else:
            for key, value in match.items():
                if not _valid_id(key) or not isinstance(value, (str, int, float, bool)):
                    errors.append(f"{label}: conditionMatch entries need valid fields and scalar values")


def _arena(arena, label, errors):
    hazards = arena.get("hazards")
    phases = arena.get("phases")
    if not isinstance(hazards, list) or not hazards:
        errors.append(f"{label}: hazards must be a non-empty array")
        hazards = []
    if not isinstance(phases, list) or not phases:
        errors.append(f"{label}: phases must be a non-empty array")
        phases = []
    hazard_ids = set()
    for index, hazard in enumerate(hazards):
        hlabel = f"{label}:hazards[{index}]"
        if not isinstance(hazard, dict):
            errors.append(f"{hlabel} must be an object")
            continue
        hazard_id = hazard.get("id")
        if not _valid_id(hazard_id):
            errors.append(f"{hlabel}: id must match {ID_PATTERN.pattern}")
            continue
        if hazard_id in hazard_ids:
            errors.append(f"{label}: duplicate hazard id '{hazard_id}'")
            continue
        hazard_ids.add(hazard_id)
        hlabel = f"{label}:{hazard_id}"
        _regions(hazard.get("regions"), hlabel + ":regions", errors)
        if not _number(hazard.get("damage")) or hazard.get("damage") <= 0:
            errors.append(f"{hlabel}: damage must be a finite number > 0")
        if not _number(hazard.get("retriggerSeconds")) or hazard.get("retriggerSeconds") <= 0:
            errors.append(f"{hlabel}: retriggerSeconds must be a finite number > 0")
        if not isinstance(hazard.get("instantlyLethal"), bool):
            errors.append(f"{hlabel}: instantlyLethal must be boolean")
    phase_ids = set()
    for index, phase in enumerate(phases):
        plabel = f"{label}:phases[{index}]"
        if not isinstance(phase, dict):
            errors.append(f"{plabel} must be an object")
            continue
        phase_id = phase.get("id")
        if not _valid_id(phase_id):
            errors.append(f"{plabel}: id must match {ID_PATTERN.pattern}")
            continue
        if phase_id in phase_ids:
            errors.append(f"{label}: duplicate hazard phase id '{phase_id}'")
            continue
        phase_ids.add(phase_id)
        plabel = f"{label}:{phase_id}"
        arm = _id_array(phase.get("arm", []), plabel + ":arm", errors, hazard_ids)
        disarm = _id_array(phase.get("disarm", []), plabel + ":disarm", errors, hazard_ids)
        overlap = set(arm) & set(disarm)
        if overlap:
            errors.append(f"{plabel}: cannot arm and disarm {sorted(overlap)} in one phase")
        if arm and (not _number(phase.get("warningSeconds")) or phase.get("warningSeconds") <= 0):
            errors.append(f"{plabel}: arming phases require warningSeconds > 0")
        if "warningSeconds" in phase and (not _number(phase.get("warningSeconds")) or phase.get("warningSeconds") <= 0):
            errors.append(f"{plabel}: warningSeconds must be a finite number > 0")
        mutate = phase.get("mutate", {})
        if not isinstance(mutate, dict):
            errors.append(f"{plabel}: mutate must be an object keyed by hazard id")
        else:
            for hazard_id, mutation in mutate.items():
                if hazard_id not in hazard_ids:
                    errors.append(f"{plabel}: mutate references unknown hazard '{hazard_id}'")
                if not isinstance(mutation, dict):
                    errors.append(f"{plabel}: mutate.{hazard_id} must be an object")


def validate_boss_document(document, source="<bosses>", known_arenas=None):
    """Return (errors, warnings) for one boss/arena content document."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(document, dict):
        return [f"{source}: root must be an object"], warnings
    raw_arenas = document.get("arenas")
    encounters = document.get("encounters")
    if not isinstance(raw_arenas, list) or not isinstance(encounters, list):
        return [f"{source}: arenas and encounters must be arrays"], warnings

    arenas = {}
    for index, arena in enumerate(raw_arenas):
        label = f"{source}:arenas[{index}]"
        if not isinstance(arena, dict):
            errors.append(f"{label} must be an object")
            continue
        arena_id = arena.get("id")
        if not _valid_id(arena_id):
            errors.append(f"{label}: id must match {ID_PATTERN.pattern}")
            continue
        if arena_id in arenas:
            errors.append(f"{source}: duplicate arena id '{arena_id}'")
            continue
        arenas[arena_id] = arena
        _arena(arena, f"{source}:{arena_id}", errors)

    arena_docs = arenas if known_arenas is None else known_arenas
    encounter_ids = set()
    for index, encounter in enumerate(encounters):
        label = f"{source}:encounters[{index}]"
        if not isinstance(encounter, dict):
            errors.append(f"{label} must be an object")
            continue
        encounter_id = encounter.get("id")
        if not _valid_id(encounter_id):
            errors.append(f"{label}: id must match {ID_PATTERN.pattern}")
            continue
        if encounter_id in encounter_ids:
            errors.append(f"{source}: duplicate encounter id '{encounter_id}'")
            continue
        encounter_ids.add(encounter_id)
        label = f"{source}:{encounter_id}"
        arena_id = encounter.get("arenaId")
        if not _valid_id(arena_id):
            errors.append(f"{label}: arenaId must be a well-formed id")
        elif arena_id not in arena_docs:
            errors.append(f"{label}: unknown arenaId '{arena_id}'")
        if not _integer(encounter.get("level"), 1):
            errors.append(f"{label}: level must be an integer >= 1")
        boss = encounter.get("boss")
        if not isinstance(boss, dict):
            errors.append(f"{label}: boss must be an object")
            boss = {}
        if not _valid_id(boss.get("archetype")):
            errors.append(f"{label}: boss.archetype must be a well-formed id")
        if not _number(boss.get("maxHealth")) or boss.get("maxHealth") <= 0:
            errors.append(f"{label}: boss.maxHealth must be a finite number > 0")
        if "socket" in boss and not _valid_id(boss.get("socket")):
            errors.append(f"{label}: boss.socket must be a well-formed id")
        _id_array(boss.get("masteryTags", []), label + ":boss.masteryTags", errors)

        arena = arena_docs.get(arena_id, {})
        raw_hazard_phases = arena.get("phases", []) if isinstance(arena, dict) else []
        hazard_phase_ids = {
            phase.get("id") for phase in raw_hazard_phases
            if isinstance(phase, dict) and _valid_id(phase.get("id"))
        } if isinstance(raw_hazard_phases, list) else set()
        phases = encounter.get("phases")
        if not isinstance(phases, list) or not phases:
            errors.append(f"{label}: phases must be a non-empty array")
            phases = []
        phase_ids, condition_ids, attack_ids = set(), set(), set()
        health_thresholds, time_thresholds = [], []
        for phase_index, phase in enumerate(phases):
            plabel = f"{label}:phases[{phase_index}]"
            if not isinstance(phase, dict):
                errors.append(f"{plabel} must be an object")
                continue
            phase_id = phase.get("id")
            if not _valid_id(phase_id):
                errors.append(f"{plabel}: id must match {ID_PATTERN.pattern}")
            elif phase_id in phase_ids:
                errors.append(f"{label}: duplicate phase id '{phase_id}'")
            else:
                phase_ids.add(phase_id)
            plabel = f"{label}:{phase_id}" if _valid_id(phase_id) else plabel
            _trigger(phase, plabel + ":enterWhen", errors, condition_ids, phase_index == 0)
            trigger = phase.get("enterWhen", {})
            if isinstance(trigger, dict):
                if _number(trigger.get("healthAtOrBelow")):
                    health_thresholds.append(trigger["healthAtOrBelow"])
                if _number(trigger.get("elapsedSecondsAtLeast")):
                    time_thresholds.append(trigger["elapsedSecondsAtLeast"])
            hazard_phase = phase.get("hazardPhase")
            if hazard_phase is not None and hazard_phase not in hazard_phase_ids:
                errors.append(f"{plabel}: unknown hazardPhase '{hazard_phase}'")
            _attacks(phase.get("attacks", []), plabel + ":attacks", errors, attack_ids)
            _adds(phase.get("adds", []), plabel + ":adds", errors)
        if any(b >= a for a, b in zip(health_thresholds, health_thresholds[1:])):
            errors.append(f"{label}: health-triggered phases must use strictly descending thresholds")
        if any(b <= a for a, b in zip(time_thresholds, time_thresholds[1:])):
            errors.append(f"{label}: time-triggered phases must use strictly increasing times")

        enrage = encounter.get("enrage")
        if enrage is not None:
            elabel = label + ":enrage"
            if not isinstance(enrage, dict):
                errors.append(f"{elabel} must be an object")
                continue
            if not _number(enrage.get("afterSeconds")) or enrage.get("afterSeconds") <= 0:
                errors.append(f"{elabel}: afterSeconds must be a finite number > 0")
            hazard_phase = enrage.get("hazardPhase")
            if hazard_phase is not None and hazard_phase not in hazard_phase_ids:
                errors.append(f"{elabel}: unknown hazardPhase '{hazard_phase}'")
            modifiers = enrage.get("behaviorModifiers", {})
            if not isinstance(modifiers, dict):
                errors.append(f"{elabel}: behaviorModifiers must be an object")
            else:
                for key, value in modifiers.items():
                    if not _valid_id(key) or not _number(value) or value <= 0:
                        errors.append(f"{elabel}: behaviorModifiers need valid ids and finite values > 0")
            _attacks(enrage.get("attacks", []), elabel + ":attacks", errors, attack_ids)
    return errors, warnings


def validate_bundle(boss_documents):
    """Validate parsed (source, document) pairs with cross-file arena links."""
    errors: list[str] = []
    warnings: list[str] = []
    arenas = {}
    encounter_ids = set()
    for source, document in boss_documents:
        if not isinstance(document, dict):
            continue
        raw_arenas = document.get("arenas", [])
        if isinstance(raw_arenas, list):
            for arena in raw_arenas:
                if not isinstance(arena, dict) or not _valid_id(arena.get("id")):
                    continue
                arena_id = arena["id"]
                if arena_id in arenas:
                    errors.append(f"{source}: duplicate arena id '{arena_id}' across bundle")
                else:
                    arenas[arena_id] = arena
        raw_encounters = document.get("encounters", [])
        if isinstance(raw_encounters, list):
            for encounter in raw_encounters:
                if not isinstance(encounter, dict) or not _valid_id(encounter.get("id")):
                    continue
                encounter_id = encounter["id"]
                if encounter_id in encounter_ids:
                    errors.append(f"{source}: duplicate encounter id '{encounter_id}' across bundle")
                else:
                    encounter_ids.add(encounter_id)
    for source, document in boss_documents:
        found, cautions = validate_boss_document(document, source, arenas)
        errors.extend(found)
        warnings.extend(cautions)
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="boss JSON files or directories")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    inputs = args.paths or [ROOT / "examples" / "boss-arena"]
    paths: list[Path] = []
    for path in inputs:
        if path.is_dir():
            paths.extend(sorted(path.rglob("*.boss.json")))
        else:
            paths.append(path)
    if not paths:
        print("validate_boss_arenas: FAIL (no content files found)")
        return 1
    documents = []
    errors: list[str] = []
    for path in paths:
        source = str(path.relative_to(ROOT)) if path.is_absolute() and ROOT in path.parents else str(path)
        if not path.name.endswith(".boss.json"):
            errors.append(f"{source}: expected *.boss.json")
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{source}: unreadable ({exc})")
            continue
        documents.append((source, document))
    found, warnings = validate_bundle(documents)
    errors.extend(found)
    count = lambda key: sum(
        len(document.get(key, [])) for _, document in documents
        if isinstance(document, dict) and isinstance(document.get(key), list)
    )
    phase_count = sum(
        len(encounter.get("phases", [])) for _, document in documents if isinstance(document, dict)
        for encounter in document.get("encounters", []) if isinstance(encounter, dict)
    ) if all(isinstance(document.get("encounters", []), list) for _, document in documents if isinstance(document, dict)) else 0
    hazard_count = sum(
        len(arena.get("hazards", [])) for _, document in documents if isinstance(document, dict)
        for arena in document.get("arenas", []) if isinstance(arena, dict)
    ) if all(isinstance(document.get("arenas", []), list) for _, document in documents if isinstance(document, dict)) else 0
    report = {
        "status": "PASS" if not errors else "FAIL",
        "arenaCount": count("arenas"),
        "hazardCount": hazard_count,
        "encounterCount": count("encounters"),
        "bossPhaseCount": phase_count,
        "warnings": warnings,
        "errors": errors,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"validate_boss_arenas: {report['status']} "
        f"({report['arenaCount']} arenas, {hazard_count} hazards, {report['encounterCount']} encounters, "
        f"{phase_count} boss phases, {len(errors)} errors, {len(warnings)} warnings)"
    )
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
