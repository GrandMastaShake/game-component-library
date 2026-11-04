#!/usr/bin/env python3
"""Validate authored status effects and execute their acceptance scenarios.

The descriptor graph proves that status, timer, cast, movement, attack, capture,
and save owners can be wired. This validator additionally executes stacking,
refresh, cleanse, immunity, timer-generation, cleanup, and restoration examples
so malformed or ambiguous content cannot pass merely because its JSON parses.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
STACK_POLICIES = {"refresh", "stack", "independent"}
DURATION_POLICIES = {"reset", "extend", "max", "ignore"}
GROUPINGS = {"targetEffect", "targetEffectSource"}
RESTRICTIONS = {"move", "cast", "attack"}
CLEANSE_ORDERS = {"highestPriority", "lowestPriority", "oldest", "newest"}
OPERATIONS = {"add", "multiply"}
TOP_LEVEL_FIELDS = {
    "schemaVersion", "id", "description", "effects", "immunities",
    "cleanseRules", "scenarios",
}


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


def _duration(value, label, errors):
    if value is not None and (not _number(value) or value <= 0):
        errors.append(f"{label} must be null or a finite number > 0")


def _effect(effect, label, errors):
    if not isinstance(effect, dict):
        errors.append(f"{label} must be an object")
        return
    if not _valid_id(effect.get("id")):
        errors.append(f"{label}: id must match {ID_PATTERN.pattern}")
    _duration(effect.get("durationSeconds"), label + ":durationSeconds", errors)
    if effect.get("stackPolicy") not in STACK_POLICIES:
        errors.append(f"{label}: stackPolicy must be one of {sorted(STACK_POLICIES)}")
    if effect.get("durationPolicy") not in DURATION_POLICIES:
        errors.append(f"{label}: durationPolicy must be one of {sorted(DURATION_POLICIES)}")
    if not _integer(effect.get("maxStacks"), 1):
        errors.append(f"{label}: maxStacks must be an integer >= 1")
    elif effect.get("stackPolicy") in {"refresh", "independent"} and effect.get("maxStacks") != 1:
        errors.append(f"{label}: refresh and independent effects require maxStacks=1")
    if effect.get("grouping") not in GROUPINGS:
        errors.append(f"{label}: grouping must be one of {sorted(GROUPINGS)}")
    _id_array(effect.get("tags"), label + ":tags", errors, allow_empty=False)
    if not isinstance(effect.get("dispellable"), bool):
        errors.append(f"{label}: dispellable must be boolean")
    if not _integer(effect.get("cleansePriority"), 0):
        errors.append(f"{label}: cleansePriority must be an integer >= 0")
    if not isinstance(effect.get("removeOnDefeat"), bool):
        errors.append(f"{label}: removeOnDefeat must be boolean")
    modifiers = effect.get("modifiers", [])
    if not isinstance(modifiers, list):
        errors.append(f"{label}: modifiers must be an array")
    else:
        for index, modifier in enumerate(modifiers):
            mlabel = f"{label}:modifiers[{index}]"
            if not isinstance(modifier, dict):
                errors.append(f"{mlabel} must be an object")
                continue
            if not _valid_id(modifier.get("stat")):
                errors.append(f"{mlabel}: stat must be a well-formed id")
            operation = modifier.get("operation")
            if operation not in OPERATIONS:
                errors.append(f"{mlabel}: operation must be add or multiply")
            value = modifier.get("value")
            if not _number(value):
                errors.append(f"{mlabel}: value must be finite")
            elif operation == "multiply" and value <= 0:
                errors.append(f"{mlabel}: multiply value must be > 0")
            elif operation == "add" and value == 0:
                errors.append(f"{mlabel}: add value must not be zero")
            if not isinstance(modifier.get("perStack"), bool):
                errors.append(f"{mlabel}: perStack must be boolean")
    control = effect.get("control")
    if control is not None:
        if not isinstance(control, dict):
            errors.append(f"{label}: control must be an object")
        else:
            restrictions = _id_array(control.get("restrictions"), label + ":control.restrictions", errors)
            unknown = set(restrictions) - RESTRICTIONS
            if unknown:
                errors.append(f"{label}: unsupported control restrictions {sorted(unknown)}")
            multiplier = control.get("moveMultiplier", 1)
            if not _number(multiplier) or not 0 <= multiplier <= 1:
                errors.append(f"{label}: control.moveMultiplier must be in [0, 1]")
            if "move" in restrictions and multiplier != 0:
                errors.append(f"{label}: a move restriction requires moveMultiplier=0")


def _rules(document, effect_ids, errors):
    immunities = document.get("immunities")
    if not isinstance(immunities, list):
        errors.append("immunities must be an array")
        immunities = []
    immunity_ids = set()
    for index, rule in enumerate(immunities):
        label = f"immunities[{index}]"
        if not isinstance(rule, dict):
            errors.append(f"{label} must be an object")
            continue
        rule_id = rule.get("id")
        if not _valid_id(rule_id):
            errors.append(f"{label}: id must be a well-formed stable id")
        elif rule_id in immunity_ids:
            errors.append(f"immunities: duplicate id '{rule_id}'")
        else:
            immunity_ids.add(rule_id)
        _id_array(rule.get("targetIds"), label + ":targetIds", errors, allow_empty=False)
        effect_refs = _id_array(rule.get("effectIds"), label + ":effectIds", errors, effect_ids)
        tags = _id_array(rule.get("tags"), label + ":tags", errors)
        if not effect_refs and not tags:
            errors.append(f"{label}: at least one effectIds or tags selector is required")
    cleanse_rules = document.get("cleanseRules")
    if not isinstance(cleanse_rules, list):
        errors.append("cleanseRules must be an array")
        cleanse_rules = []
    cleanse_ids = set()
    for index, rule in enumerate(cleanse_rules):
        label = f"cleanseRules[{index}]"
        if not isinstance(rule, dict):
            errors.append(f"{label} must be an object")
            continue
        rule_id = rule.get("id")
        if not _valid_id(rule_id):
            errors.append(f"{label}: id must be a well-formed stable id")
        elif rule_id in cleanse_ids:
            errors.append(f"cleanseRules: duplicate id '{rule_id}'")
        else:
            cleanse_ids.add(rule_id)
        effect_refs = _id_array(rule.get("effectIds"), label + ":effectIds", errors, effect_ids)
        tags = _id_array(rule.get("tags"), label + ":tags", errors)
        if not effect_refs and not tags:
            errors.append(f"{label}: at least one effectIds or tags selector is required")
        if not _integer(rule.get("maxEffects"), 1):
            errors.append(f"{label}: maxEffects must be an integer >= 1")
        if rule.get("order") not in CLEANSE_ORDERS:
            errors.append(f"{label}: order must be one of {sorted(CLEANSE_ORDERS)}")


class StatusModel:
    """Small deterministic reference model used only by content validation."""

    def __init__(self, document, max_active=6):
        self.document = document
        self.effects = {effect["id"]: effect for effect in document.get("effects", [])}
        self.immunities = document.get("immunities", [])
        self.cleanse_rules = {rule["id"]: rule for rule in document.get("cleanseRules", [])}
        self.max_active = max_active
        self.active = []
        self.processed_applications = set()
        self.processed_cleanses = set()
        self.processed_removals = set()
        self.last_rejected = None
        self.events = []
        self.insertion = 0
        self.snapshots = []

    def _state(self):
        return {
            "active": copy.deepcopy(self.active),
            "processed_applications": copy.deepcopy(self.processed_applications),
            "processed_cleanses": copy.deepcopy(self.processed_cleanses),
            "processed_removals": copy.deepcopy(self.processed_removals),
            "last_rejected": copy.deepcopy(self.last_rejected),
            "insertion": self.insertion,
        }

    def snapshot(self):
        self.snapshots.append(self._state())

    def restore(self):
        if self.snapshots:
            state = self.snapshots[-1]
            self.active = copy.deepcopy(state["active"])
            self.processed_applications = copy.deepcopy(state["processed_applications"])
            self.processed_cleanses = copy.deepcopy(state["processed_cleanses"])
            self.processed_removals = copy.deepcopy(state["processed_removals"])
            self.last_rejected = copy.deepcopy(state["last_rejected"])
            self.insertion = state["insertion"]

    def _definition(self, instance):
        return self.effects[instance["effectId"]]

    @staticmethod
    def _incoming_duration(definition, request):
        return request.get("durationSeconds", definition["durationSeconds"])

    def _group(self, request, definition):
        if definition["stackPolicy"] == "independent":
            return None
        for instance in self.active:
            if instance["targetId"] != request["targetId"] or instance["effectId"] != request["effectId"]:
                continue
            if definition["grouping"] == "targetEffectSource" and instance.get("sourceId") != request.get("sourceId"):
                continue
            return instance
        return None

    def _immune(self, request, definition):
        for rule in self.immunities:
            if request["targetId"] not in rule["targetIds"]:
                continue
            if request["effectId"] in rule["effectIds"] or set(definition["tags"]) & set(rule["tags"]):
                return True
        return False

    def _reject(self, request, reason):
        self.last_rejected = {"applicationId": request["applicationId"], "reason": reason}
        self.events.append({"event": "rejected", **self.last_rejected})

    def apply(self, request):
        application_id = request["applicationId"]
        if application_id in self.processed_applications:
            return
        self.processed_applications.add(application_id)
        definition = self.effects[request["effectId"]]
        if self._immune(request, definition):
            self._reject(request, "immunity")
            return
        existing = self._group(request, definition)
        if existing is None and sum(i["targetId"] == request["targetId"] for i in self.active) >= self.max_active:
            self._reject(request, "capacity")
            return
        incoming = self._incoming_duration(definition, request)
        if existing is None:
            self.insertion += 1
            instance = {
                "applicationId": application_id,
                "effectId": request["effectId"],
                "targetId": request["targetId"],
                "sourceId": request.get("sourceId"),
                "encounterId": request.get("encounterId"),
                "stacks": 1,
                "remainingSeconds": incoming,
                "generation": 1,
                "insertion": self.insertion,
            }
            self.active.append(instance)
            self.events.append({"event": "applied", "applicationId": application_id})
            return
        policy = definition["durationPolicy"]
        current = existing["remainingSeconds"]
        if policy == "reset":
            remaining = incoming
        elif policy == "extend":
            remaining = None if current is None or incoming is None else current + incoming
        elif policy == "max":
            if current is None or incoming is None:
                remaining = None
            else:
                remaining = max(current, incoming)
        else:
            remaining = current
        existing["remainingSeconds"] = remaining
        existing["generation"] += 1
        event = {"applicationId": existing["applicationId"], "requestedApplicationId": application_id}
        if definition["stackPolicy"] == "stack" and existing["stacks"] < definition["maxStacks"]:
            existing["stacks"] += 1
            event.update(event="stacked", stacks=existing["stacks"])
        else:
            event.update(event="refreshed", stacks=existing["stacks"])
        self.events.append(event)

    def _remove(self, instance, reason):
        self.active.remove(instance)
        self.events.append({"event": "removed", "applicationId": instance["applicationId"], "reason": reason})

    def expire(self, step):
        for instance in list(self.active):
            if instance["applicationId"] != step["applicationId"]:
                continue
            if instance["generation"] != step["generation"]:
                return
            self.events.append({"event": "expired", "applicationId": instance["applicationId"]})
            self._remove(instance, "expired")
            return

    def advance(self, seconds):
        for instance in self.active:
            if instance["remainingSeconds"] is not None:
                instance["remainingSeconds"] = max(0, instance["remainingSeconds"] - seconds)

    @staticmethod
    def _matches(rule, instance, definition):
        return instance["effectId"] in rule["effectIds"] or bool(set(rule["tags"]) & set(definition["tags"]))

    def cleanse(self, step):
        cleanse_id = step["cleanseId"]
        if cleanse_id in self.processed_cleanses:
            return
        self.processed_cleanses.add(cleanse_id)
        rule = self.cleanse_rules[step["ruleId"]]
        candidates = [
            instance for instance in self.active
            if instance["targetId"] == step["targetId"]
            and self._definition(instance)["dispellable"]
            and self._matches(rule, instance, self._definition(instance))
        ]
        order = rule["order"]
        if order == "highestPriority":
            candidates.sort(key=lambda i: (-self._definition(i)["cleansePriority"], i["insertion"]))
        elif order == "lowestPriority":
            candidates.sort(key=lambda i: (self._definition(i)["cleansePriority"], i["insertion"]))
        elif order == "newest":
            candidates.sort(key=lambda i: -i["insertion"])
        else:
            candidates.sort(key=lambda i: i["insertion"])
        for instance in candidates[:rule["maxEffects"]]:
            self.events.append({
                "event": "cleansed", "applicationId": instance["applicationId"],
                "cleanseId": cleanse_id,
            })
            self._remove(instance, "cleansed")

    def defeat(self, target_id):
        for instance in list(self.active):
            if instance["targetId"] == target_id and self._definition(instance)["removeOnDefeat"]:
                self._remove(instance, "defeat")

    def reset(self, encounter_id):
        for instance in list(self.active):
            if instance.get("encounterId") == encounter_id:
                self._remove(instance, "encounterReset")

    def remove(self, step):
        removal_id = step["removalId"]
        if removal_id in self.processed_removals:
            return
        self.processed_removals.add(removal_id)
        for instance in list(self.active):
            if instance["targetId"] != step["targetId"]:
                continue
            if step.get("applicationId") and instance["applicationId"] != step["applicationId"]:
                continue
            if step.get("effectId") and instance["effectId"] != step["effectId"]:
                continue
            self._remove(instance, "manual")

    def control(self, target_id):
        restrictions = set()
        multiplier = 1.0
        for instance in self.active:
            if instance["targetId"] != target_id:
                continue
            control = self._definition(instance).get("control", {})
            restrictions.update(control.get("restrictions", []))
            multiplier *= control.get("moveMultiplier", 1) ** instance["stacks"]
        if math.isclose(multiplier, 0, abs_tol=1e-12):
            multiplier = 0
        return sorted(restrictions), multiplier

    def assert_expectation(self, expected, label, errors):
        target_id = expected.get("targetId")
        if not _valid_id(target_id):
            errors.append(f"{label}: expect.targetId must be a well-formed id")
            return
        expected_active = expected.get("active", [])
        if not isinstance(expected_active, list) or not all(isinstance(row, dict) for row in expected_active):
            errors.append(f"{label}: expect.active must be an array of objects")
            return
        required_active = {"applicationId", "effectId", "stacks", "generation"}
        for index, row in enumerate(expected_active):
            if not required_active <= set(row):
                errors.append(f"{label}: expect.active[{index}] requires {sorted(required_active)}")
                return
            if not _valid_id(row.get("applicationId")) or not _valid_id(row.get("effectId")):
                errors.append(f"{label}: expect.active[{index}] needs well-formed applicationId and effectId")
                return
            if not _integer(row.get("stacks"), 1) or not _integer(row.get("generation"), 1):
                errors.append(f"{label}: expect.active[{index}] stacks and generation must be integers >= 1")
                return
            if "remainingSeconds" in row:
                remaining = row["remainingSeconds"]
                if remaining is not None and (not _number(remaining) or remaining < 0):
                    errors.append(f"{label}: expect.active[{index}].remainingSeconds must be null or finite >= 0")
        if not isinstance(expected.get("events", []), list) or not all(isinstance(row, dict) for row in expected.get("events", [])):
            errors.append(f"{label}: expect.events must be an array of objects")
            return
        expected_restrictions = expected.get("restrictions", [])
        if not isinstance(expected_restrictions, list) or any(item not in RESTRICTIONS for item in expected_restrictions):
            errors.append(f"{label}: expect.restrictions must contain only {sorted(RESTRICTIONS)}")
            return
        # Remaining time is asserted only where the scenario names it. The same
        # projection is used for every row so failures remain easy to read.
        keys = ["applicationId", "effectId", "stacks", "generation"]
        if any("remainingSeconds" in row for row in expected_active):
            keys.append("remainingSeconds")
        actual = [
            {key: instance[key] for key in keys}
            for instance in self.active if instance["targetId"] == target_id
        ]
        if actual != expected_active:
            errors.append(f"{label}: active mismatch; expected {expected_active}, got {actual}")
        if self.events != expected.get("events", []):
            errors.append(f"{label}: event mismatch; expected {expected.get('events', [])}, got {self.events}")
        restrictions, multiplier = self.control(target_id)
        if restrictions != expected.get("restrictions", []):
            errors.append(f"{label}: restrictions mismatch; expected {expected.get('restrictions', [])}, got {restrictions}")
        expected_multiplier = expected.get("moveMultiplier", 1)
        if not _number(expected_multiplier) or not math.isclose(multiplier, expected_multiplier, abs_tol=1e-9):
            errors.append(f"{label}: moveMultiplier mismatch; expected {expected_multiplier}, got {multiplier}")
        if "lastRejected" in expected and self.last_rejected != expected["lastRejected"]:
            errors.append(f"{label}: lastRejected mismatch; expected {expected['lastRejected']}, got {self.last_rejected}")

    def run_scenario(self, scenario, label, errors):
        self.events = []
        for index, step in enumerate(scenario.get("steps", [])):
            slabel = f"{label}:steps[{index}]"
            if not isinstance(step, dict):
                errors.append(f"{slabel} must be an object")
                continue
            self.events = []
            op = step.get("op")
            try:
                if op == "apply":
                    for field in ("applicationId", "effectId", "targetId"):
                        if not _valid_id(step.get(field)):
                            raise ValueError(f"{field} must be a well-formed id")
                    if step["effectId"] not in self.effects:
                        raise ValueError(f"unknown effectId '{step['effectId']}'")
                    for field in ("sourceId", "encounterId"):
                        if field in step and not _valid_id(step[field]):
                            raise ValueError(f"{field} must be a well-formed id when supplied")
                    _duration(step.get("durationSeconds", self.effects[step["effectId"]]["durationSeconds"]), slabel + ":durationSeconds", errors)
                    self.apply(step)
                elif op == "expire":
                    if not _valid_id(step.get("applicationId")) or not _integer(step.get("generation"), 1):
                        raise ValueError("expire requires applicationId and generation >= 1")
                    self.expire(step)
                elif op == "advance":
                    if not _number(step.get("seconds")) or step["seconds"] < 0:
                        raise ValueError("advance.seconds must be finite and >= 0")
                    self.advance(step["seconds"])
                elif op == "cleanse":
                    if not _valid_id(step.get("cleanseId")) or not _valid_id(step.get("targetId")):
                        raise ValueError("cleanse requires stable cleanseId and targetId")
                    if step.get("ruleId") not in self.cleanse_rules:
                        raise ValueError(f"unknown cleanse rule '{step.get('ruleId')}'")
                    self.cleanse(step)
                elif op == "defeat":
                    self.defeat(step["targetId"])
                elif op == "reset":
                    if not _valid_id(step.get("encounterId")):
                        raise ValueError("reset requires encounterId")
                    self.reset(step["encounterId"])
                elif op == "remove":
                    if not _valid_id(step.get("removalId")) or not _valid_id(step.get("targetId")):
                        raise ValueError("remove requires stable removalId and targetId")
                    self.remove(step)
                elif op == "snapshot":
                    self.snapshot()
                elif op == "restore":
                    self.restore()
                else:
                    raise ValueError(f"unsupported op '{op}'")
            except (KeyError, TypeError, ValueError) as exc:
                errors.append(f"{slabel}: {exc}")
                continue
            if "expect" in step:
                if not isinstance(step["expect"], dict):
                    errors.append(f"{slabel}: expect must be an object")
                else:
                    self.assert_expectation(step["expect"], slabel + ":expect", errors)


def validate_status_document(document, source="<status>"):
    """Return (errors, warnings) for one parsed status document."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(document, dict):
        return [f"{source}: document must be an object"], warnings
    unknown = set(document) - TOP_LEVEL_FIELDS
    if unknown:
        errors.append(f"{source}: unknown top-level fields {sorted(unknown)}")
    if document.get("schemaVersion") != 1:
        errors.append(f"{source}: schemaVersion must be 1")
    if not _valid_id(document.get("id")):
        errors.append(f"{source}: id must be a well-formed stable id")
    effects = document.get("effects")
    if not isinstance(effects, list) or not effects:
        errors.append(f"{source}: effects must be a non-empty array")
        effects = []
    effect_ids = set()
    for index, effect in enumerate(effects):
        label = f"{source}:effects[{index}]"
        _effect(effect, label, errors)
        if isinstance(effect, dict) and _valid_id(effect.get("id")):
            if effect["id"] in effect_ids:
                errors.append(f"{source}: duplicate effect id '{effect['id']}'")
            effect_ids.add(effect["id"])
    _rules(document, effect_ids, errors)
    scenarios = document.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        errors.append(f"{source}: scenarios must be a non-empty array")
        scenarios = []
    scenario_ids = set()
    # Do not execute a malformed definition/model: structure errors already
    # identify the repair and execution could otherwise hide them behind a crash.
    if not errors:
        for index, scenario in enumerate(scenarios):
            label = f"{source}:scenarios[{index}]"
            if not isinstance(scenario, dict):
                errors.append(f"{label} must be an object")
                continue
            scenario_id = scenario.get("id")
            if not _valid_id(scenario_id):
                errors.append(f"{label}: id must be a well-formed stable id")
                scenario_id = str(index)
            elif scenario_id in scenario_ids:
                errors.append(f"{label}: duplicate scenario id '{scenario_id}'")
            else:
                scenario_ids.add(scenario_id)
            if not isinstance(scenario.get("steps"), list) or not scenario["steps"]:
                errors.append(f"{label}: steps must be a non-empty array")
                continue
            StatusModel(document).run_scenario(scenario, f"{label}:{scenario_id}", errors)
    return errors, warnings


def validate_bundle(status_documents):
    """Validate parsed (source, document) pairs and cross-file id ownership."""
    errors: list[str] = []
    warnings: list[str] = []
    document_ids = set()
    effect_ids = set()
    for source, document in status_documents:
        if not isinstance(document, dict):
            continue
        document_id = document.get("id")
        if _valid_id(document_id):
            if document_id in document_ids:
                errors.append(f"{source}: duplicate status document id '{document_id}'")
            document_ids.add(document_id)
        for effect in document.get("effects", []) if isinstance(document.get("effects"), list) else []:
            if not isinstance(effect, dict) or not _valid_id(effect.get("id")):
                continue
            if effect["id"] in effect_ids:
                errors.append(f"{source}: duplicate effect id '{effect['id']}' across bundle")
            effect_ids.add(effect["id"])
    for source, document in status_documents:
        found, cautions = validate_status_document(document, source)
        errors.extend(found)
        warnings.extend(cautions)
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="status JSON files or directories")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    inputs = args.paths or [ROOT / "examples" / "status-effects"]
    paths: list[Path] = []
    for path in inputs:
        if path.is_dir():
            paths.extend(sorted(path.rglob("*.status.json")))
        else:
            paths.append(path)
    if not paths:
        print("validate_status_effects: FAIL (no content files found)")
        return 1
    documents = []
    errors: list[str] = []
    for path in paths:
        source = str(path.relative_to(ROOT)) if path.is_absolute() and ROOT in path.parents else str(path)
        if not path.name.endswith(".status.json"):
            errors.append(f"{source}: expected *.status.json")
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
    step_count = sum(
        len(scenario.get("steps", [])) for _, document in documents if isinstance(document, dict)
        for scenario in document.get("scenarios", []) if isinstance(scenario, dict)
    ) if all(isinstance(document.get("scenarios", []), list) for _, document in documents if isinstance(document, dict)) else 0
    report = {
        "status": "PASS" if not errors else "FAIL",
        "documentCount": len(documents),
        "effectCount": count("effects"),
        "immunityCount": count("immunities"),
        "cleanseRuleCount": count("cleanseRules"),
        "scenarioCount": count("scenarios"),
        "scenarioStepCount": step_count,
        "warnings": warnings,
        "errors": errors,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"validate_status_effects: {report['status']} "
        f"({report['effectCount']} effects, {report['immunityCount']} immunities, "
        f"{report['cleanseRuleCount']} cleanse rules, {report['scenarioCount']} scenarios, "
        f"{step_count} steps, {len(errors)} errors, {len(warnings)} warnings)"
    )
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
