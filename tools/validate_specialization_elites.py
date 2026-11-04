#!/usr/bin/env python3
"""Validate specialization, mastery, elite-affix, and encounter content.

The component graph proves that the owners can be wired. This validator checks
whether designer content can actually be selected, earned, rolled, and completed:
gated identities and actives, deduplicated mastery sources, legal affix sets,
and finite waves with real elites. All content and balance remain host supplied.
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
MASTERY_EVENTS = {
    "combat.abilityCast",
    "combat.entityDefeated",
    "progression.questCompleted",
    "combat.eliteEncounterCompleted",
    "combat.bossEncounterCompleted",
}
SHAPE_DIMENSIONS = {
    "circle": ("radius",),
    "line": ("length", "width"),
    "cone": ("radius", "angle"),
    "single": (),
}


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _integer(value, minimum=0) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _valid_id(value) -> bool:
    return isinstance(value, str) and bool(ID_PATTERN.match(value))


def _id_array(value, label, errors, known=None, self_id=None):
    if not isinstance(value, list):
        errors.append(f"{label} must be an array")
        return []
    result = []
    for index, item in enumerate(value):
        if not _valid_id(item):
            errors.append(f"{label}[{index}] must be a well-formed id")
        elif item == self_id:
            errors.append(f"{label}[{index}] cannot reference itself")
        elif known is not None and item not in known:
            errors.append(f"{label}[{index}] unknown id '{item}'")
        else:
            result.append(item)
    if len(result) != len(set(result)):
        errors.append(f"{label} contains duplicate ids")
    return result


def _effect(effect, label, errors, positive=False):
    if not isinstance(effect, dict):
        errors.append(f"{label} must be an object of named modifiers")
        return
    for key, value in effect.items():
        if not _valid_id(key):
            errors.append(f"{label}: invalid modifier key '{key}'")
        if not _number(value) or (positive and value <= 0):
            suffix = " > 0" if positive else " finite"
            errors.append(f"{label}.{key} must be{suffix}")


def _sources(sources, label, errors):
    if not isinstance(sources, list) or not sources:
        errors.append(f"{label} must be a non-empty array")
        return
    for index, source in enumerate(sources):
        slabel = f"{label}[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{slabel} must be an object")
            continue
        if source.get("event") not in MASTERY_EVENTS:
            errors.append(f"{slabel}: event must be one of {sorted(MASTERY_EVENTS)}")
        match = source.get("match", {})
        if not isinstance(match, dict):
            errors.append(f"{slabel}: match must be an object of scalar payload equality checks")
        else:
            for key, value in match.items():
                if not _valid_id(key) or not isinstance(value, (str, int, float, bool)):
                    errors.append(f"{slabel}: match entries need valid fields and scalar values")
        has_amount = "amount" in source
        has_amount_from = "amountFrom" in source
        if has_amount and has_amount_from:
            errors.append(f"{slabel}: declare amount or amountFrom, not both")
        if has_amount and (not _number(source["amount"]) or source["amount"] <= 0):
            errors.append(f"{slabel}: amount must be a finite number > 0")
        if has_amount_from and not _valid_id(source["amountFrom"]):
            errors.append(f"{slabel}: amountFrom must name a payload field")
        if not _valid_id(source.get("dedupeBy")):
            errors.append(f"{slabel}: dedupeBy must name a stable payload id field")


def validate_specialization_document(
    document,
    source="<specializations>",
    known_specializations=None,
    known_tracks=None,
    known_skills=None,
):
    """Return (errors, warnings) for one specialization/mastery document."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(document, dict):
        return [f"{source}: root must be an object"], warnings
    raw_specs = document.get("specializations")
    raw_tracks = document.get("masteryTracks")
    if not isinstance(raw_specs, list) or not isinstance(raw_tracks, list):
        return [f"{source}: specializations and masteryTracks must be arrays"], warnings

    specs = {}
    for index, spec in enumerate(raw_specs):
        label = f"{source}:specializations[{index}]"
        if not isinstance(spec, dict):
            errors.append(f"{label} must be an object")
            continue
        spec_id = spec.get("id")
        if not _valid_id(spec_id):
            errors.append(f"{label}: id must match {ID_PATTERN.pattern}")
            continue
        if spec_id in specs:
            errors.append(f"{source}: duplicate specialization id '{spec_id}'")
            continue
        specs[spec_id] = spec
        label = f"{source}:{spec_id}"
        if not isinstance(spec.get("name"), str) or not spec.get("name").strip():
            errors.append(f"{label}: name must be a non-empty string")
        if not _integer(spec.get("requiredLevel", 1), 1):
            errors.append(f"{label}: requiredLevel must be an integer >= 1")
        skills = spec.get("requiredSkills", [])
        if not isinstance(skills, list):
            errors.append(f"{label}: requiredSkills must be an array")
        else:
            for skill_index, skill in enumerate(skills):
                slabel = f"{label}:requiredSkills[{skill_index}]"
                if not isinstance(skill, dict) or not _valid_id(skill.get("id")):
                    errors.append(f"{slabel} must be an object with a skill id")
                    continue
                rank = skill.get("rank", 1)
                if not _integer(rank, 1):
                    errors.append(f"{slabel}: rank must be an integer >= 1")
                if known_skills is not None:
                    skill_id = skill["id"]
                    if skill_id not in known_skills:
                        errors.append(f"{slabel}: unknown skill '{skill_id}'")
                    elif _integer(rank, 1) and rank > known_skills[skill_id].get("maxRank", 1):
                        errors.append(f"{slabel}: rank {rank} exceeds skill maximum {known_skills[skill_id].get('maxRank', 1)}")
        group = spec.get("exclusiveGroup")
        if group is not None and (not isinstance(group, str) or not group.strip()):
            errors.append(f"{label}: exclusiveGroup must be a non-empty string")
        _effect(spec.get("effect", {}), label + ":effect", errors)

    known_specs = set(specs) if known_specializations is None else known_specializations
    for spec_id, spec in specs.items():
        _id_array(
            spec.get("requiresSpecializations", []),
            f"{source}:{spec_id}:requiresSpecializations",
            errors,
            known_specs,
            spec_id,
        )

    tracks = {}
    for index, track in enumerate(raw_tracks):
        label = f"{source}:masteryTracks[{index}]"
        if not isinstance(track, dict):
            errors.append(f"{label} must be an object")
            continue
        track_id = track.get("id")
        if not _valid_id(track_id):
            errors.append(f"{label}: id must match {ID_PATTERN.pattern}")
            continue
        if track_id in tracks:
            errors.append(f"{source}: duplicate mastery track id '{track_id}'")
            continue
        tracks[track_id] = track
        label = f"{source}:{track_id}"
        if not isinstance(track.get("name"), str) or not track.get("name").strip():
            errors.append(f"{label}: name must be a non-empty string")
        specialization = track.get("specialization")
        if specialization is not None and specialization not in known_specs:
            errors.append(f"{label}: unknown specialization '{specialization}'")
        thresholds = track.get("thresholds")
        if not isinstance(thresholds, list) or not thresholds:
            errors.append(f"{label}: thresholds must be a non-empty array")
            thresholds = []
        elif any(not _number(value) or value <= 0 for value in thresholds):
            errors.append(f"{label}: every threshold must be a finite number > 0")
        elif any(b <= a for a, b in zip(thresholds, thresholds[1:])):
            errors.append(f"{label}: thresholds must be strictly increasing")
        effects = track.get("effectByRank", [{} for _ in thresholds])
        if not isinstance(effects, list) or len(effects) != len(thresholds):
            errors.append(f"{label}: effectByRank must contain one object per threshold")
        else:
            for rank, effect in enumerate(effects, 1):
                _effect(effect, f"{label}:effectByRank[{rank}]", errors)
        _sources(track.get("sources", document.get("sources", [])), label + ":sources", errors)

    known_track_ids = set(tracks) if known_tracks is None else known_tracks
    known_track_docs = tracks if known_tracks is None else known_tracks
    abilities = document.get("abilityCatalog", [])
    if not isinstance(abilities, list):
        errors.append(f"{source}: abilityCatalog must be an array")
        return errors, warnings
    ability_ids = set()
    for index, ability in enumerate(abilities):
        label = f"{source}:abilityCatalog[{index}]"
        if not isinstance(ability, dict):
            errors.append(f"{label} must be an object")
            continue
        ability_id = ability.get("id")
        if not _valid_id(ability_id):
            errors.append(f"{label}: id must match {ID_PATTERN.pattern}")
        elif ability_id in ability_ids:
            errors.append(f"{source}: duplicate ability id '{ability_id}'")
        else:
            ability_ids.add(ability_id)
        source_node_id = ability.get("sourceNodeId")
        if not _valid_id(source_node_id):
            errors.append(f"{label}: sourceNodeId must be a well-formed skill id")
        min_rank = ability.get("minRank", 1)
        if not _integer(min_rank, 1):
            errors.append(f"{label}: minRank must be an integer >= 1")
        if known_skills is not None and _valid_id(source_node_id):
            if source_node_id not in known_skills:
                errors.append(f"{label}: unknown sourceNodeId '{source_node_id}'")
            elif _integer(min_rank, 1) and min_rank > known_skills[source_node_id].get("maxRank", 1):
                errors.append(f"{label}: minRank {min_rank} exceeds skill maximum {known_skills[source_node_id].get('maxRank', 1)}")
        specialization = ability.get("specialization")
        if specialization is not None and specialization not in known_specs:
            errors.append(f"{label}: unknown specialization '{specialization}'")
        track_id = ability.get("masteryTrack")
        if track_id is not None:
            if track_id not in known_track_ids:
                errors.append(f"{label}: unknown masteryTrack '{track_id}'")
            minimum = ability.get("minMasteryRank", 1)
            if not _integer(minimum, 1):
                errors.append(f"{label}: minMasteryRank must be an integer >= 1")
            elif track_id in known_track_docs:
                maximum = len(known_track_docs[track_id].get("thresholds", []))
                if minimum > maximum:
                    errors.append(f"{label}: minMasteryRank {minimum} exceeds track maximum {maximum}")
        elif "minMasteryRank" in ability:
            errors.append(f"{label}: minMasteryRank requires masteryTrack")
        if not isinstance(ability.get("ability"), dict):
            errors.append(f"{label}: ability execution data must be an object")
    return errors, warnings


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


def validate_elite_document(document, source="<elites>", known_affixes=None, bundle_max_affixes=None):
    """Return (errors, warnings) for one elite-affix/encounter document."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(document, dict):
        return [f"{source}: root must be an object"], warnings
    raw_affixes = document.get("affixes")
    encounters = document.get("encounters")
    if not isinstance(raw_affixes, list) or not isinstance(encounters, list):
        return [f"{source}: affixes and encounters must be arrays"], warnings
    if not _integer(document.get("seed", 0)):
        errors.append(f"{source}: seed must be a non-negative integer")
    max_affixes = document.get("maxAffixes", 2)
    if not _integer(max_affixes):
        errors.append(f"{source}: maxAffixes must be a non-negative integer")
        max_affixes = 0
    if bundle_max_affixes is not None:
        max_affixes = bundle_max_affixes

    affixes = {}
    for index, affix in enumerate(raw_affixes):
        label = f"{source}:affixes[{index}]"
        if not isinstance(affix, dict):
            errors.append(f"{label} must be an object")
            continue
        affix_id = affix.get("id")
        if not _valid_id(affix_id):
            errors.append(f"{label}: id must match {ID_PATTERN.pattern}")
            continue
        if affix_id in affixes:
            errors.append(f"{source}: duplicate affix id '{affix_id}'")
            continue
        affixes[affix_id] = affix
        label = f"{source}:{affix_id}"
        if not _number(affix.get("weight")) or affix.get("weight") <= 0:
            errors.append(f"{label}: weight must be a finite number > 0")
        minimum = affix.get("minThreat", 0)
        maximum = affix.get("maxThreat")
        if not _number(minimum) or minimum < 0:
            errors.append(f"{label}: minThreat must be a finite number >= 0")
        if maximum is not None and (not _number(maximum) or maximum < minimum):
            errors.append(f"{label}: maxThreat must be finite and >= minThreat")
        _effect(affix.get("statMultipliers", {}), label + ":statMultipliers", errors, positive=True)
        _effect(affix.get("behaviorModifiers", {}), label + ":behaviorModifiers", errors, positive=True)
        attacks = affix.get("attacks", [])
        if not isinstance(attacks, list):
            errors.append(f"{label}: attacks must be an array")
            continue
        attack_ids = set()
        for attack_index, attack in enumerate(attacks):
            alabel = f"{label}:attacks[{attack_index}]"
            if not isinstance(attack, dict):
                errors.append(f"{alabel} must be an object")
                continue
            attack_id = attack.get("id")
            if not _valid_id(attack_id):
                errors.append(f"{alabel}: id must match {ID_PATTERN.pattern}")
            elif attack_id in attack_ids:
                errors.append(f"{label}: duplicate attack id '{attack_id}'")
            else:
                attack_ids.add(attack_id)
            if not _number(attack.get("windupSeconds")) or attack.get("windupSeconds") <= 0:
                errors.append(f"{alabel}: windupSeconds must be a finite number > 0")
            if not _number(attack.get("cooldownSeconds")) or attack.get("cooldownSeconds") < 0:
                errors.append(f"{alabel}: cooldownSeconds must be a finite number >= 0")
            if not _number(attack.get("damage")) or attack.get("damage") <= 0:
                errors.append(f"{alabel}: damage must be a finite number > 0")
            _shape(attack.get("shape"), alabel + ":shape", errors)

    known = set(affixes) if known_affixes is None else known_affixes
    for affix_id, affix in affixes.items():
        _id_array(affix.get("requires", []), f"{source}:{affix_id}:requires", errors, known, affix_id)
        _id_array(affix.get("excludes", []), f"{source}:{affix_id}:excludes", errors, known, affix_id)

    encounter_ids = set()
    for encounter_index, encounter in enumerate(encounters):
        label = f"{source}:encounters[{encounter_index}]"
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
        if not _valid_id(encounter.get("arenaId")):
            errors.append(f"{label}: arenaId must be a well-formed id")
        if not _integer(encounter.get("level"), 1):
            errors.append(f"{label}: level must be an integer >= 1")
        threat = encounter.get("threat")
        if not _number(threat) or threat < 0:
            errors.append(f"{label}: threat must be a finite number >= 0")
        waves = encounter.get("waves")
        if not isinstance(waves, list) or not waves:
            errors.append(f"{label}: waves must be a non-empty array")
            continue
        wave_ids = set()
        elite_count = 0
        for wave_index, wave in enumerate(waves):
            wlabel = f"{label}:waves[{wave_index}]"
            if not isinstance(wave, dict):
                errors.append(f"{wlabel} must be an object")
                continue
            wave_id = wave.get("id")
            if not _valid_id(wave_id):
                errors.append(f"{wlabel}: id must match {ID_PATTERN.pattern}")
            elif wave_id in wave_ids:
                errors.append(f"{label}: duplicate wave id '{wave_id}'")
            else:
                wave_ids.add(wave_id)
            units = wave.get("units")
            if not isinstance(units, list) or not units:
                errors.append(f"{wlabel}: units must be a non-empty array")
                continue
            for unit_index, unit in enumerate(units):
                ulabel = f"{wlabel}:units[{unit_index}]"
                if not isinstance(unit, dict):
                    errors.append(f"{ulabel} must be an object")
                    continue
                if not _valid_id(unit.get("archetype")):
                    errors.append(f"{ulabel}: archetype must be a well-formed id")
                count = unit.get("count")
                if not _integer(count, 1):
                    errors.append(f"{ulabel}: count must be an integer >= 1")
                    count = 0
                elite = unit.get("elite", True)
                if not isinstance(elite, bool):
                    errors.append(f"{ulabel}: elite must be boolean")
                    elite = False
                explicit = unit.get("affixIds")
                if explicit is not None and not isinstance(explicit, list):
                    errors.append(f"{ulabel}: affixIds must be an array")
                    explicit = []
                affix_count = unit.get("affixCount", len(explicit) if explicit else (1 if elite else 0))
                if not _integer(affix_count) or affix_count > max_affixes:
                    errors.append(f"{ulabel}: affixCount must be an integer from 0 to {max_affixes}")
                if elite:
                    elite_count += count
                elif affix_count or explicit:
                    errors.append(f"{ulabel}: non-elite units cannot request affixes")
                if explicit is None:
                    continue
                chosen = _id_array(explicit, ulabel + ":affixIds", errors, known)
                if len(chosen) != affix_count:
                    errors.append(f"{ulabel}: affixCount must equal the number of explicit affixIds")
                selected = set(chosen)
                for affix_id in chosen:
                    affix = known.get(affix_id, {})
                    raw_required = affix.get("requires", [])
                    required = {item for item in raw_required if _valid_id(item)} if isinstance(raw_required, list) else set()
                    if not required <= selected:
                        errors.append(f"{ulabel}: '{affix_id}' is missing required affixes {sorted(required - selected)}")
                    minimum = affix.get("minThreat", 0)
                    maximum = affix.get("maxThreat")
                    if _number(threat) and (threat < minimum or (maximum is not None and threat > maximum)):
                        errors.append(f"{ulabel}: '{affix_id}' is outside its threat band")
                    raw_excludes = affix.get("excludes", [])
                    excluded = ({item for item in raw_excludes if _valid_id(item)} if isinstance(raw_excludes, list) else set()) & selected
                    if excluded:
                        errors.append(f"{ulabel}: '{affix_id}' conflicts with {sorted(excluded)}")
        if elite_count == 0:
            errors.append(f"{label}: an elite encounter requires at least one elite unit")
    return errors, warnings


def _cycles(documents, label, prerequisites):
    visiting, visited, reported = set(), set(), set()
    errors = []

    def visit(item_id, trail):
        if item_id in visiting:
            cycle = frozenset(trail[trail.index(item_id):])
            if cycle not in reported:
                errors.append(f"{label} cycle contains {', '.join(sorted(cycle))}")
                reported.add(cycle)
            return
        if item_id in visited or item_id not in documents:
            return
        visiting.add(item_id)
        for parent in prerequisites(documents[item_id]):
            if parent in documents:
                visit(parent, trail + [item_id])
        visiting.remove(item_id)
        visited.add(item_id)

    for item_id in documents:
        visit(item_id, [])
    return errors


def _requirement_closure(item_id, documents, seen=None, field="requires"):
    seen = set() if seen is None else seen
    if item_id in seen or item_id not in documents:
        return set()
    seen.add(item_id)
    result = {item_id}
    for parent in documents[item_id].get(field, []):
        if _valid_id(parent):
            result.update(_requirement_closure(parent, documents, seen.copy(), field))
    return result


def validate_bundle(specialization_documents, elite_documents, skill_documents=None):
    """Validate parsed (source, document) pairs together, including cross-links."""
    errors: list[str] = []
    warnings: list[str] = []
    specs, tracks, affixes = {}, {}, {}
    skills = None if skill_documents is None else {}
    if skill_documents is not None:
        for source, document in skill_documents:
            if not isinstance(document, dict) or not isinstance(document.get("skills"), list):
                continue
            for skill in document["skills"]:
                if not isinstance(skill, dict) or not _valid_id(skill.get("id")):
                    continue
                skill_id = skill["id"]
                if skill_id in skills:
                    errors.append(f"{source}: duplicate skill id '{skill_id}' across supplied trees")
                else:
                    skills[skill_id] = skill
    for source, document in specialization_documents:
        if not isinstance(document, dict):
            continue
        for key, target, singular in (
            ("specializations", specs, "specialization"),
            ("masteryTracks", tracks, "mastery track"),
        ):
            values = document.get(key, [])
            if not isinstance(values, list):
                continue
            for value in values:
                if not isinstance(value, dict) or not _valid_id(value.get("id")):
                    continue
                item_id = value["id"]
                if item_id in target:
                    errors.append(f"{source}: duplicate {singular} id '{item_id}' across bundle")
                else:
                    target[item_id] = value
    for source, document in elite_documents:
        if not isinstance(document, dict) or not isinstance(document.get("affixes"), list):
            continue
        for affix in document["affixes"]:
            if not isinstance(affix, dict) or not _valid_id(affix.get("id")):
                continue
            affix_id = affix["id"]
            if affix_id in affixes:
                errors.append(f"{source}: duplicate affix id '{affix_id}' across bundle")
            else:
                affixes[affix_id] = affix

    maxima = {
        document.get("maxAffixes", 2)
        for _, document in elite_documents
        if isinstance(document, dict) and _integer(document.get("maxAffixes", 2))
    }
    if len(maxima) > 1:
        errors.append(f"elite bundle uses inconsistent maxAffixes values: {sorted(maxima)}")
    bundle_max = max(maxima) if maxima else 2

    for source, document in specialization_documents:
        found, cautions = validate_specialization_document(document, source, set(specs), tracks, skills)
        errors.extend(found)
        warnings.extend(cautions)
    for source, document in elite_documents:
        found, cautions = validate_elite_document(document, source, affixes, bundle_max)
        errors.extend(found)
        warnings.extend(cautions)

    errors.extend(_cycles(
        specs,
        "specialization prerequisite",
        lambda spec: [item for item in spec.get("requiresSpecializations", []) if _valid_id(item)]
        if isinstance(spec.get("requiresSpecializations", []), list) else [],
    ))
    errors.extend(_cycles(
        affixes,
        "affix prerequisite",
        lambda affix: [item for item in affix.get("requires", []) if _valid_id(item)]
        if isinstance(affix.get("requires", []), list) else [],
    ))

    for affix_id in affixes:
        closure = _requirement_closure(affix_id, affixes)
        if len(closure) > bundle_max:
            errors.append(f"affix '{affix_id}' requires {len(closure)} slots, above maxAffixes {bundle_max}")
    for spec_id, spec in specs.items():
        group = spec.get("exclusiveGroup")
        if not group:
            continue
        ancestors = _requirement_closure(spec_id, specs, field="requiresSpecializations")
        ancestors.discard(spec_id)
        conflicts = sorted(parent for parent in ancestors if specs[parent].get("exclusiveGroup") == group)
        if conflicts:
            errors.append(f"specialization '{spec_id}' shares exclusiveGroup '{group}' with prerequisite(s) {conflicts}")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="specialization/elite JSON files or directories")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    inputs = args.paths or [ROOT / "examples" / "specialization-elite", ROOT / "examples" / "skill-trees"]
    paths: list[Path] = []
    for path in inputs:
        if path.is_dir():
            paths.extend(sorted(path.rglob("*.specialization.json")))
            paths.extend(sorted(path.rglob("*.elite.json")))
            paths.extend(sorted(path.rglob("*.tree.json")))
        else:
            paths.append(path)
    if not paths:
        print("validate_specialization_elites: FAIL (no content files found)")
        return 1

    specialization_documents, elite_documents, skill_documents = [], [], []
    errors: list[str] = []
    for path in paths:
        source = str(path.relative_to(ROOT)) if path.is_absolute() and ROOT in path.parents else str(path)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{source}: unreadable ({exc})")
            continue
        pair = (source, document)
        if path.name.endswith(".specialization.json"):
            specialization_documents.append(pair)
        elif path.name.endswith(".elite.json"):
            elite_documents.append(pair)
        elif path.name.endswith(".tree.json"):
            skill_documents.append(pair)
        else:
            errors.append(f"{source}: expected *.specialization.json, *.elite.json, or *.tree.json")

    found, warnings = validate_bundle(
        specialization_documents,
        elite_documents,
        skill_documents if skill_documents else None,
    )
    if not skill_documents:
        warnings.append("no skill trees supplied; requiredSkills and sourceNodeId references are checked for shape only")
    errors.extend(found)
    count = lambda docs, key: sum(len(doc.get(key, [])) for _, doc in docs if isinstance(doc, dict) and isinstance(doc.get(key), list))
    wave_count = sum(
        len(encounter.get("waves", []))
        for _, document in elite_documents if isinstance(document, dict)
        for encounter in document.get("encounters", []) if isinstance(encounter, dict)
    )
    report = {
        "status": "PASS" if not errors else "FAIL",
        "specializationCount": count(specialization_documents, "specializations"),
        "masteryTrackCount": count(specialization_documents, "masteryTracks"),
        "affixCount": count(elite_documents, "affixes"),
        "encounterCount": count(elite_documents, "encounters"),
        "waveCount": wave_count,
        "skillTreeCount": len(skill_documents),
        "skillNodeCount": count(skill_documents, "skills"),
        "warnings": warnings,
        "errors": errors,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"validate_specialization_elites: {report['status']} "
        f"({report['specializationCount']} specializations, {report['masteryTrackCount']} mastery tracks, "
        f"{report['affixCount']} affixes, {report['encounterCount']} encounters, {wave_count} waves, "
        f"{len(errors)} errors, {len(warnings)} warnings)"
    )
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
