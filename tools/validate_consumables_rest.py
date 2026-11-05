#!/usr/bin/env python3
"""Validate original consumable/rest content with a deterministic reference model."""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("validate_status_effects", ROOT / "tools" / "validate_status_effects.py")
_status = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_status)
StatusModel = _status.StatusModel

TOP = {"schemaVersion", "id", "description", "statusDocumentIds", "initialInventory", "units", "resourcePools", "consumables", "restProfiles", "scenarios"}
CONSUMABLE = {"id", "description", "targetMode", "usePolicy", "cooldownGroupId", "cooldownSeconds", "consume", "recovery", "statusApplications", "cleanseRequests"}
REST = {"id", "description", "durationSeconds", "requiresSafeZone", "allowInCombat", "ambushChance", "recovery"}
RECOVERY = {"resourceId", "mode", "amount"}
RESERVED = {"health", "action_points", "card_energy", "prepared_casts", "hunger", "thirst", "temperature", "stamina"}
STATUS_EVENTS = {
    "applied": "combat.effectApplied", "refreshed": "combat.effectRefreshed",
    "stacked": "combat.effectStacked", "rejected": "combat.effectRejected",
    "expired": "combat.effectExpired", "cleansed": "combat.effectCleansed",
    "removed": "combat.effectRemoved",
}
_id = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]*$")

def valid_id(value): return isinstance(value, str) and bool(_id.fullmatch(value))
def number(value): return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
def integer(value, minimum=0): return isinstance(value, int) and not isinstance(value, bool) and value >= minimum

def _operation(row, label, errors, allow_health=True):
    if not isinstance(row, dict):
        errors.append(f"{label} must be an object"); return
    unknown = set(row) - RECOVERY
    if unknown: errors.append(f"{label}: unknown fields {sorted(unknown)}")
    if not valid_id(row.get("resourceId")):
        errors.append(f"{label}: resourceId must be a well-formed id")
    elif not allow_health and row["resourceId"] == "health":
        errors.append(f"{label}: health belongs to Unit Roster, not Resource Pools")
    if row.get("mode") not in {"flat", "percentMax", "full"}:
        errors.append(f"{label}: mode must be flat, percentMax, or full")
    amount = row.get("amount")
    if row.get("mode") == "flat" and (not number(amount) or amount <= 0):
        errors.append(f"{label}: flat amount must be finite and > 0")
    if row.get("mode") == "percentMax" and (not number(amount) or not 0 < amount <= 1):
        errors.append(f"{label}: percentMax amount must be in (0,1]")
    if row.get("mode") == "full" and "amount" in row:
        errors.append(f"{label}: full recovery must not carry amount")

def _rows(value, label, errors):
    if not isinstance(value, list):
        errors.append(f"{label} must be an array"); return []
    return value

def validate_recovery_document(document, status_documents, source="<recovery>"):
    errors, warnings = [], []
    if not isinstance(document, dict): return [f"{source}: document must be an object"], warnings
    unknown = set(document) - TOP
    if unknown: errors.append(f"{source}: unknown top-level fields {sorted(unknown)}")
    if document.get("schemaVersion") != 1: errors.append(f"{source}: schemaVersion must be 1")
    if not valid_id(document.get("id")): errors.append(f"{source}: id must be a well-formed stable id")
    if not isinstance(document.get("description"), str) or not document["description"].strip(): errors.append(f"{source}: description must be non-empty")
    required_status = _rows(document.get("statusDocumentIds"), f"{source}:statusDocumentIds", errors)
    available_status = {doc.get("id"): doc for _, doc in status_documents if isinstance(doc, dict)}
    for status_id in required_status:
        if not valid_id(status_id): errors.append(f"{source}: malformed status document id {status_id!r}")
        elif status_id not in available_status: errors.append(f"{source}: missing status document '{status_id}'")
    effects, cleanse_rules = {}, {}
    for status_id in required_status:
        status = available_status.get(status_id, {})
        effects.update({row.get("id"): row for row in status.get("effects", []) if isinstance(row, dict)})
        cleanse_rules.update({row.get("id"): row for row in status.get("cleanseRules", []) if isinstance(row, dict)})

    consumables = {}
    for index, row in enumerate(_rows(document.get("consumables"), f"{source}:consumables", errors)):
        label = f"{source}:consumables[{index}]"
        if not isinstance(row, dict): errors.append(f"{label} must be an object"); continue
        unknown = set(row) - CONSUMABLE
        if unknown: errors.append(f"{label}: unknown fields {sorted(unknown)}")
        cid = row.get("id")
        if not valid_id(cid): errors.append(f"{label}: id must be well-formed")
        elif cid in consumables: errors.append(f"{source}: duplicate consumable id '{cid}'")
        else: consumables[cid] = row
        if row.get("targetMode") not in {"self", "unit"}: errors.append(f"{label}: targetMode must be self or unit")
        if row.get("usePolicy") not in {"always", "outOfCombat"}: errors.append(f"{label}: usePolicy must be always or outOfCombat")
        if not valid_id(row.get("cooldownGroupId")): errors.append(f"{label}: cooldownGroupId must be well-formed")
        if not number(row.get("cooldownSeconds")) or row["cooldownSeconds"] < 0: errors.append(f"{label}: cooldownSeconds must be finite and >= 0")
        if not isinstance(row.get("consume"), bool): errors.append(f"{label}: consume must be boolean")
        recovery = _rows(row.get("recovery"), f"{label}:recovery", errors)
        applications = _rows(row.get("statusApplications"), f"{label}:statusApplications", errors)
        cleanses = _rows(row.get("cleanseRequests"), f"{label}:cleanseRequests", errors)
        if not recovery and not applications and not cleanses: errors.append(f"{label}: at least one recovery, status, or cleanse operation is required")
        for rindex, operation in enumerate(recovery): _operation(operation, f"{label}:recovery[{rindex}]", errors)
        for aindex, application in enumerate(applications):
            alabel = f"{label}:statusApplications[{aindex}]"
            if not isinstance(application, dict) or set(application) - {"effectId", "durationSeconds"}:
                errors.append(f"{alabel} must contain only effectId and optional durationSeconds"); continue
            if not valid_id(application.get("effectId")): errors.append(f"{alabel}: effectId must be well-formed")
            elif application["effectId"] not in effects: errors.append(f"{alabel}: unknown effectId '{application['effectId']}'")
            if "durationSeconds" in application and (not number(application["durationSeconds"]) or application["durationSeconds"] <= 0): errors.append(f"{alabel}: durationSeconds must be finite and > 0")
        for cindex, cleanse in enumerate(cleanses):
            if not isinstance(cleanse, dict) or set(cleanse) != {"ruleId"}: errors.append(f"{label}:cleanseRequests[{cindex}] must contain only ruleId")
            elif not valid_id(cleanse["ruleId"]): errors.append(f"{label}: cleanse rule id must be well-formed")
            elif cleanse["ruleId"] not in cleanse_rules: errors.append(f"{label}: unknown cleanse rule '{cleanse['ruleId']}'")

    rests = {}
    for index, row in enumerate(_rows(document.get("restProfiles"), f"{source}:restProfiles", errors)):
        label = f"{source}:restProfiles[{index}]"
        if not isinstance(row, dict): errors.append(f"{label} must be an object"); continue
        unknown = set(row) - REST
        if unknown: errors.append(f"{label}: unknown fields {sorted(unknown)}")
        rid = row.get("id")
        if not valid_id(rid): errors.append(f"{label}: id must be well-formed")
        elif rid in rests: errors.append(f"{source}: duplicate rest profile id '{rid}'")
        else: rests[rid] = row
        if not number(row.get("durationSeconds")) or row["durationSeconds"] <= 0: errors.append(f"{label}: durationSeconds must be finite and > 0")
        for field in ("requiresSafeZone", "allowInCombat"):
            if not isinstance(row.get(field), bool): errors.append(f"{label}: {field} must be boolean")
        if not number(row.get("ambushChance")) or not 0 <= row["ambushChance"] <= 1: errors.append(f"{label}: ambushChance must be in [0,1]")
        for rindex, operation in enumerate(_rows(row.get("recovery"), f"{label}:recovery", errors)): _operation(operation, f"{label}:recovery[{rindex}]", errors)

    inventory_ids = set()
    for index, row in enumerate(_rows(document.get("initialInventory"), f"{source}:initialInventory", errors)):
        label = f"{source}:initialInventory[{index}]"
        if not isinstance(row, dict) or set(row) != {"itemId", "quantity"}: errors.append(f"{label} must contain itemId and quantity"); continue
        if not valid_id(row["itemId"]): errors.append(f"{label}: itemId must be well-formed"); continue
        if row["itemId"] not in consumables: errors.append(f"{label}: unknown consumable '{row['itemId']}'")
        if row["itemId"] in inventory_ids: errors.append(f"{label}: duplicate item entry")
        inventory_ids.add(row["itemId"])
        if not integer(row["quantity"]): errors.append(f"{label}: quantity must be an integer >= 0")

    units = set()
    for index, row in enumerate(_rows(document.get("units"), f"{source}:units", errors)):
        label = f"{source}:units[{index}]"
        if not isinstance(row, dict) or set(row) != {"id", "health", "maxHealth"}: errors.append(f"{label} must contain id, health, and maxHealth"); continue
        if not valid_id(row["id"]): errors.append(f"{label}: malformed unit id"); continue
        if row["id"] in units: errors.append(f"{label}: duplicate unit id")
        units.add(row["id"])
        valid_maximum = number(row["maxHealth"]) and row["maxHealth"] > 0
        if not valid_maximum: errors.append(f"{label}: maxHealth must be finite and > 0")
        if not number(row["health"]) or (valid_maximum and not 0 <= row["health"] <= row["maxHealth"]): errors.append(f"{label}: health must be in [0,maxHealth]")

    pools = set()
    for index, row in enumerate(_rows(document.get("resourcePools"), f"{source}:resourcePools", errors)):
        label = f"{source}:resourcePools[{index}]"
        if not isinstance(row, dict) or set(row) != {"id", "ownerId", "initial", "maximum"}: errors.append(f"{label} must contain id, ownerId, initial, and maximum"); continue
        if not valid_id(row["id"]) or not valid_id(row["ownerId"]): errors.append(f"{label}: malformed pool or owner id"); continue
        if row["id"] in RESERVED: errors.append(f"{label}: '{row['id']}' belongs to another resource owner")
        if row["ownerId"] not in units: errors.append(f"{label}: unknown owner '{row['ownerId']}'")
        key = (row["ownerId"], row["id"])
        if key in pools: errors.append(f"{label}: duplicate owner/resource pool")
        pools.add(key)
        valid_maximum = number(row["maximum"]) and row["maximum"] > 0
        if not valid_maximum: errors.append(f"{label}: maximum must be finite and > 0")
        if not number(row["initial"]) or (valid_maximum and not 0 <= row["initial"] <= row["maximum"]): errors.append(f"{label}: initial must be in [0,maximum]")

    scenarios = _rows(document.get("scenarios"), f"{source}:scenarios", errors)
    if not scenarios: errors.append(f"{source}: scenarios must be non-empty")
    if not errors:
        merged_status = {"effects": list(effects.values()), "immunities": [], "cleanseRules": list(cleanse_rules.values())}
        for _, doc in status_documents:
            if isinstance(doc, dict) and doc.get("id") in required_status: merged_status["immunities"].extend(doc.get("immunities", []))
        scenario_ids = set()
        for index, scenario in enumerate(scenarios):
            label = f"{source}:scenarios[{index}]"
            if not isinstance(scenario, dict): errors.append(f"{label} must be an object"); continue
            sid = scenario.get("id")
            if not valid_id(sid): errors.append(f"{label}: malformed scenario id"); sid = str(index)
            elif sid in scenario_ids: errors.append(f"{label}: duplicate scenario id '{sid}'")
            scenario_ids.add(sid)
            if not isinstance(scenario.get("steps"), list) or not scenario["steps"]: errors.append(f"{label}: steps must be a non-empty array"); continue
            RecoveryModel(document, merged_status).run_scenario(scenario, f"{label}:{sid}", errors)
    return errors, warnings

class RecoveryModel:
    def __init__(self, document, status_document):
        self.document = document
        self.consumables = {row["id"]: row for row in document["consumables"]}
        self.profiles = {row["id"]: row for row in document["restProfiles"]}
        self.inventory = {row["itemId"]: row["quantity"] for row in document["initialInventory"]}
        self.units = {row["id"]: {"health": row["health"], "maximum": row["maxHealth"]} for row in document["units"]}
        self.pools = {(row["ownerId"], row["id"]): {"current": row["initial"], "maximum": row["maximum"]} for row in document["resourcePools"]}
        self.status = StatusModel(status_document)
        self.cooldowns, self.cooldown_generations = [], {}
        self.active_rest, self.rest_generation = None, 0
        self.processed_uses, self.processed_rests = set(), set()
        self.processed_health, self.processed_health_rests = set(), set()
        self.processed_resources, self.processed_resource_rests = set(), set()
        self.last_rejected = self.last_health_rejected = self.last_resource_rejected = None
        self.events, self.snapshots = [], []

    def emit(self, event, **fields): self.events.append({"event": event, **fields})
    def _sync_status(self):
        for event in self.status.events:
            self.events.append({"event": STATUS_EVENTS[event["event"]], **{k: v for k, v in event.items() if k != "event"}})
        self.status.events = []

    def _state(self):
        return {key: copy.deepcopy(getattr(self, key)) for key in ("inventory", "units", "pools", "cooldowns", "cooldown_generations", "active_rest", "rest_generation", "processed_uses", "processed_rests", "processed_health", "processed_health_rests", "processed_resources", "processed_resource_rests", "last_rejected", "last_health_rejected", "last_resource_rejected")} | {"status": self.status._state()}

    def snapshot(self): self.snapshots.append(self._state())
    def restore(self):
        if not self.snapshots: return
        state = self.snapshots[-1]
        for key, value in state.items():
            if key != "status": setattr(self, key, copy.deepcopy(value))
        self.status.snapshots.append(state["status"]); self.status.restore()

    def reject_use(self, step, reason):
        self.last_rejected = {"owner": "consumable", "useId": step["useId"], "itemId": step["itemId"], "targetId": step["targetId"], "reason": reason}
        self.emit("inventory.useRejected", **self.last_rejected)

    def use(self, step):
        use_id, item_id = step["useId"], step["itemId"]
        if use_id in self.processed_uses: return
        self.processed_uses.add(use_id)
        item = self.consumables.get(item_id)
        if item is None:
            self.reject_use(step, "unknownItem"); return
        source, target = step["sourceId"], step["targetId"]
        if target not in self.units or (item["targetMode"] == "self" and source != target): self.reject_use(step, "invalidTarget"); return
        if self.inventory.get(item_id, 0) <= 0:
            self.emit("inventory.potionEmpty", useId=use_id, itemId=item_id); self.reject_use(step, "empty"); return
        if item["usePolicy"] == "outOfCombat" and step.get("inCombat", False): self.reject_use(step, "inCombat"); return
        key = (source, item["cooldownGroupId"])
        if any(row["sourceId"] == source and row["groupId"] == item["cooldownGroupId"] for row in self.cooldowns): self.reject_use(step, "cooldown"); return
        if item["consume"]:
            self.inventory[item_id] -= 1
        self.emit("inventory.potionUsed", useId=use_id, itemId=item_id, targetId=target)
        if item["consume"] and self.inventory[item_id] == 0: self.emit("inventory.potionEmpty", useId=use_id, itemId=item_id)
        if item["cooldownSeconds"] > 0:
            generation = self.cooldown_generations.get(key, 0) + 1
            self.cooldown_generations[key] = generation
            self.cooldowns.append({"sourceId": source, "groupId": item["cooldownGroupId"], "remainingSeconds": item["cooldownSeconds"], "generation": generation})
            self.emit("inventory.consumableCooldownStarted", useId=use_id, sourceId=source, groupId=item["cooldownGroupId"], generation=generation)
        for index, operation in enumerate(item["recovery"]):
            recovery_id = f"{use_id}.recovery.{index}"
            self.emit("inventory.recoveryRequested", recoveryId=recovery_id, targetId=target, resourceId=operation["resourceId"])
            if operation["resourceId"] == "health": self.health_recovery(recovery_id, target, operation)
            else: self.resource_recovery(recovery_id, target, operation)
        for index, application in enumerate(item["statusApplications"]):
            request = {"applicationId": f"{use_id}.effect.{index}", "effectId": application["effectId"], "targetId": target, "sourceId": source}
            if "durationSeconds" in application: request["durationSeconds"] = application["durationSeconds"]
            self.emit("inventory.effectApplicationRequested", **request)
            self.status.apply(request); self._sync_status()
        for index, cleanse in enumerate(item["cleanseRequests"]):
            request = {"cleanseId": f"{use_id}.cleanse.{index}", "ruleId": cleanse["ruleId"], "targetId": target}
            self.emit("inventory.cleanseRequested", **request)
            self.status.cleanse(request); self._sync_status()

    @staticmethod
    def amount(operation, maximum):
        if operation["mode"] == "full": return maximum
        return operation["amount"] if operation["mode"] == "flat" else maximum * operation["amount"]

    def health_recovery(self, recovery_id, target, operation, rest=False):
        if not rest:
            if recovery_id in self.processed_health: return
            self.processed_health.add(recovery_id)
        unit = self.units.get(target)
        reason = None if unit and unit["health"] > 0 else ("unknownTarget" if unit is None else "defeatedTarget")
        if reason is None and unit["health"] >= unit["maximum"]: reason = "alreadyFull"
        if reason:
            if not rest:
                self.last_health_rejected = {"recoveryId": recovery_id, "targetId": target, "reason": reason}
                self.emit("combat.healthRestoreRejected", **self.last_health_rejected)
            return
        actual = min(unit["maximum"] - unit["health"], self.amount(operation, unit["maximum"]))
        unit["health"] += actual
        if actual > 0: self.emit("combat.healthRestored", recoveryId=recovery_id, targetId=target, amount=actual)

    def resource_recovery(self, recovery_id, target, operation, rest=False):
        if not rest:
            if recovery_id in self.processed_resources: return
            self.processed_resources.add(recovery_id)
        pool = self.pools.get((target, operation["resourceId"]))
        if pool is None:
            if not rest:
                self.last_resource_rejected = {"recoveryId": recovery_id, "targetId": target, "resourceId": operation["resourceId"], "reason": "unknownPool"}
                self.emit("combat.resourceRestoreRejected", **self.last_resource_rejected)
            return
        if pool["current"] >= pool["maximum"]:
            if not rest:
                self.last_resource_rejected = {"recoveryId": recovery_id, "targetId": target, "resourceId": operation["resourceId"], "reason": "alreadyFull"}
                self.emit("combat.resourceRestoreRejected", **self.last_resource_rejected)
            return
        actual = min(pool["maximum"] - pool["current"], self.amount(operation, pool["maximum"]))
        pool["current"] += actual
        if actual > 0: self.emit("combat.resourceChanged", recoveryId=recovery_id, targetId=target, resourceId=operation["resourceId"], amount=actual)

    def rest(self, step):
        rest_id = step["restId"]
        if rest_id in self.processed_rests: return
        self.processed_rests.add(rest_id)
        profile = self.profiles[step["profileId"]]
        reason = None
        if profile["requiresSafeZone"] and not step.get("safeZone", False): reason = "unsafe"
        elif step.get("inCombat", False) and not profile["allowInCombat"]: reason = "inCombat"
        elif self.active_rest is not None: reason = "alreadyResting"
        if reason:
            self.last_rejected = {"owner": "rest", "restId": rest_id, "profileId": step["profileId"], "reason": reason}
            self.emit("world.restRejected", **self.last_rejected); return
        self.rest_generation += 1
        self.active_rest = {"restId": rest_id, "profileId": step["profileId"], "memberIds": list(step["memberIds"]), "remainingSeconds": profile["durationSeconds"], "generation": self.rest_generation, "ambushRoll": step["ambushRoll"]}
        self.emit("world.restStarted", restId=rest_id, profileId=step["profileId"], generation=self.rest_generation)

    def finish_rest(self):
        rest, self.active_rest = self.active_rest, None
        if rest is None: return
        profile = self.profiles[rest["profileId"]]
        if rest["ambushRoll"] < profile["ambushChance"]:
            self.emit("world.restInterrupted", restId=rest["restId"], reason="ambush")
            self.emit("world.restAmbushRequested", restId=rest["restId"]); return
        rest_id = rest["restId"]
        self.emit("world.restCompleted", restId=rest_id, profileId=rest["profileId"])
        health_seen = rest_id in self.processed_health_rests
        resource_seen = rest_id in self.processed_resource_rests
        if health_seen and resource_seen: return
        self.processed_health_rests.add(rest_id); self.processed_resource_rests.add(rest_id)
        for target in rest["memberIds"]:
            for index, operation in enumerate(profile["recovery"]):
                recovery_id = f"{rest_id}.recovery.{target}.{index}"
                if operation["resourceId"] == "health":
                    if not health_seen: self.health_recovery(recovery_id, target, operation, rest=True)
                elif not resource_seen: self.resource_recovery(recovery_id, target, operation, rest=True)

    def interrupt_rest(self, rest_id, reason):
        if not self.active_rest or self.active_rest["restId"] != rest_id: return
        self.active_rest = None; self.emit("world.restInterrupted", restId=rest_id, reason=reason)

    def expire_cooldown(self, step):
        for row in list(self.cooldowns):
            if row["sourceId"] == step["sourceId"] and row["groupId"] == step["cooldownGroupId"]:
                if row["generation"] != step["generation"]: return
                self.cooldowns.remove(row); self.emit("inventory.consumableCooldownCompleted", sourceId=row["sourceId"], groupId=row["groupId"], generation=row["generation"]); return

    def advance(self, seconds):
        for row in self.cooldowns: row["remainingSeconds"] = max(0, row["remainingSeconds"] - seconds)
        for row in list(self.cooldowns):
            if row["remainingSeconds"] == 0: self.expire_cooldown({"sourceId": row["sourceId"], "cooldownGroupId": row["groupId"], "generation": row["generation"]})
        self.status.advance(seconds)
        for instance in list(self.status.active):
            if instance["remainingSeconds"] == 0: self.status.expire({"applicationId": instance["applicationId"], "generation": instance["generation"]})
        self._sync_status()
        if self.active_rest:
            self.active_rest["remainingSeconds"] = max(0, self.active_rest["remainingSeconds"] - seconds)
            if self.active_rest["remainingSeconds"] == 0: self.finish_rest()

    def assert_expectation(self, expected, label, errors):
        allowed = {"inventory", "health", "resources", "cooldowns", "activeRest", "processedUseIds", "processedRestIds", "eventNames", "lastRejected", "statusApplications", "statusRejected"}
        if set(expected) - allowed: errors.append(f"{label}: unknown expectation fields {sorted(set(expected)-allowed)}"); return
        for field in ("inventory", "health"):
            if field in expected:
                if not isinstance(expected[field], dict): errors.append(f"{label}: {field} must be an object"); continue
                actual = self.inventory if field == "inventory" else {key: row["health"] for key, row in self.units.items()}
                for key, value in expected[field].items():
                    if key not in actual or not number(value) or not math.isclose(actual[key], value, abs_tol=1e-9): errors.append(f"{label}: {field}.{key} expected {value}, got {actual.get(key)}")
        if "resources" in expected:
            if not isinstance(expected["resources"], dict): errors.append(f"{label}: resources must be an object")
            else:
                for owner, rows in expected["resources"].items():
                    if not isinstance(rows, dict): errors.append(f"{label}: resources.{owner} must be an object"); continue
                    for resource, value in rows.items():
                        actual = self.pools.get((owner, resource), {}).get("current")
                        if actual is None or not number(value) or not math.isclose(actual, value, abs_tol=1e-9): errors.append(f"{label}: resources.{owner}.{resource} expected {value}, got {actual}")
        if "cooldowns" in expected:
            actual = sorted(self.cooldowns, key=lambda row: (row["sourceId"], row["groupId"]))
            if actual != expected["cooldowns"]: errors.append(f"{label}: cooldown mismatch; expected {expected['cooldowns']}, got {actual}")
        if "activeRest" in expected:
            wanted = expected["activeRest"]
            if wanted is None:
                if self.active_rest is not None: errors.append(f"{label}: expected no active rest, got {self.active_rest}")
            elif not isinstance(wanted, dict) or self.active_rest is None:
                errors.append(f"{label}: activeRest expectation does not match {self.active_rest}")
            else:
                for key, value in wanted.items():
                    if self.active_rest.get(key) != value: errors.append(f"{label}: activeRest.{key} expected {value}, got {self.active_rest.get(key)}")
        for field, actual in (("processedUseIds", self.processed_uses), ("processedRestIds", self.processed_rests)):
            if field in expected and sorted(actual) != expected[field]: errors.append(f"{label}: {field} expected {expected[field]}, got {sorted(actual)}")
        if "eventNames" in expected:
            actual = [row["event"] for row in self.events]
            if actual != expected["eventNames"]: errors.append(f"{label}: events expected {expected['eventNames']}, got {actual}")
        if "lastRejected" in expected:
            if not isinstance(expected["lastRejected"], dict): errors.append(f"{label}: lastRejected must be an object")
            else:
                for key, value in expected["lastRejected"].items():
                    if not self.last_rejected or self.last_rejected.get(key) != value: errors.append(f"{label}: lastRejected.{key} expected {value}, got {self.last_rejected}")
        if "statusApplications" in expected:
            actual = sorted(row["applicationId"] for row in self.status.active)
            if actual != expected["statusApplications"]: errors.append(f"{label}: status applications expected {expected['statusApplications']}, got {actual}")
        if "statusRejected" in expected and self.status.last_rejected != expected["statusRejected"]: errors.append(f"{label}: status rejection mismatch")

    def run_scenario(self, scenario, label, errors):
        for index, step in enumerate(scenario.get("steps", [])):
            slabel = f"{label}:steps[{index}]"; self.events = []; self.status.events = []
            if not isinstance(step, dict): errors.append(f"{slabel} must be an object"); continue
            op = step.get("op")
            try:
                if op == "use":
                    for field in ("useId", "itemId", "sourceId", "targetId"):
                        if not valid_id(step.get(field)): raise ValueError(f"{field} must be well-formed")
                    if step["itemId"] not in self.consumables: raise ValueError(f"unknown itemId '{step['itemId']}'")
                    if "inCombat" in step and not isinstance(step["inCombat"], bool): raise ValueError("inCombat must be boolean")
                    self.use(step)
                elif op == "rest":
                    for field in ("restId", "profileId"):
                        if not valid_id(step.get(field)): raise ValueError(f"{field} must be well-formed")
                    if step["profileId"] not in self.profiles: raise ValueError(f"unknown profileId '{step['profileId']}'")
                    members = step.get("memberIds")
                    if not isinstance(members, list) or not members or any(not valid_id(member) for member in members) or len(set(members)) != len(members) or any(member not in self.units for member in members): raise ValueError("memberIds must be unique known unit ids")
                    if not number(step.get("ambushRoll")) or not 0 <= step["ambushRoll"] <= 1: raise ValueError("ambushRoll must be in [0,1] for deterministic validation")
                    for field in ("safeZone", "inCombat"):
                        if not isinstance(step.get(field), bool): raise ValueError(f"{field} must be boolean")
                    self.rest(step)
                elif op == "advance":
                    if not number(step.get("seconds")) or step["seconds"] < 0: raise ValueError("seconds must be finite and >= 0")
                    self.advance(step["seconds"])
                elif op == "expireCooldown":
                    if not valid_id(step.get("sourceId")) or not valid_id(step.get("cooldownGroupId")) or not integer(step.get("generation"), 1): raise ValueError("expireCooldown requires sourceId, cooldownGroupId, and generation >= 1")
                    self.expire_cooldown(step)
                elif op == "expireRest":
                    if not valid_id(step.get("restId")) or not integer(step.get("generation"), 1): raise ValueError("expireRest requires restId and generation >= 1")
                    if self.active_rest and self.active_rest["restId"] == step["restId"] and self.active_rest["generation"] == step["generation"]: self.finish_rest()
                elif op == "interruptRest":
                    if not valid_id(step.get("restId")) or not valid_id(step.get("reason")): raise ValueError("interruptRest requires restId and reason")
                    self.interrupt_rest(step["restId"], step["reason"])
                elif op == "hit":
                    if not valid_id(step.get("targetId")) or step["targetId"] not in self.units: raise ValueError("hit target must be a known unit")
                    if self.active_rest and step["targetId"] in self.active_rest["memberIds"]: self.interrupt_rest(self.active_rest["restId"], "damage")
                elif op == "snapshot": self.snapshot()
                elif op == "restore": self.restore()
                else: raise ValueError(f"unsupported op '{op}'")
            except (KeyError, TypeError, ValueError) as exc:
                errors.append(f"{slabel}: {exc}"); continue
            if "expect" in step:
                if not isinstance(step["expect"], dict): errors.append(f"{slabel}: expect must be an object")
                else: self.assert_expectation(step["expect"], slabel + ":expect", errors)

def validate_bundle(recovery_documents, status_documents):
    errors, warnings, document_ids, item_ids, rest_ids = [], [], set(), set(), set()
    for source, document in recovery_documents:
        if not isinstance(document, dict): continue
        if valid_id(document.get("id")):
            if document["id"] in document_ids: errors.append(f"{source}: duplicate recovery document id '{document['id']}'")
            document_ids.add(document["id"])
        for field, ids in (("consumables", item_ids), ("restProfiles", rest_ids)):
            for row in document.get(field, []) if isinstance(document.get(field), list) else []:
                if isinstance(row, dict) and valid_id(row.get("id")):
                    if row["id"] in ids: errors.append(f"{source}: duplicate {field} id '{row['id']}' across bundle")
                    ids.add(row["id"])
    for source, document in recovery_documents:
        found, cautions = validate_recovery_document(document, status_documents, source)
        errors.extend(found); warnings.extend(cautions)
    return errors, warnings

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--status", type=Path, default=ROOT / "examples" / "status-effects")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    paths = []
    for path in args.paths or [ROOT / "examples" / "consumables-rest"]:
        paths.extend(sorted(path.rglob("*.recovery.json")) if path.is_dir() else [path])
    status_paths = sorted(args.status.rglob("*.status.json")) if args.status.is_dir() else [args.status]
    def read(paths, suffix):
        documents, errors = [], []
        for path in paths:
            source = str(path.relative_to(ROOT)) if path.is_absolute() and ROOT in path.parents else str(path)
            if not path.name.endswith(suffix): errors.append(f"{source}: expected *{suffix}"); continue
            try: documents.append((source, json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError) as exc: errors.append(f"{source}: unreadable ({exc})")
        return documents, errors
    recovery, errors = read(paths, ".recovery.json")
    status, status_errors = read(status_paths, ".status.json"); errors.extend(status_errors)
    found, warnings = validate_bundle(recovery, status); errors.extend(found)
    count = lambda key: sum(len(doc.get(key, [])) for _, doc in recovery if isinstance(doc, dict) and isinstance(doc.get(key), list))
    steps = sum(len(scenario.get("steps", [])) for _, doc in recovery if isinstance(doc, dict) for scenario in doc.get("scenarios", []) if isinstance(scenario, dict))
    report = {"status": "PASS" if not errors else "FAIL", "documentCount": len(recovery), "consumableCount": count("consumables"), "restProfileCount": count("restProfiles"), "scenarioCount": count("scenarios"), "scenarioStepCount": steps, "warnings": warnings, "errors": errors}
    if args.report: args.report.parent.mkdir(parents=True, exist_ok=True); args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"validate_consumables_rest: {report['status']} ({count('consumables')} consumables, {count('restProfiles')} rest profiles, {count('scenarios')} scenarios, {steps} steps, {len(errors)} errors, {len(warnings)} warnings)")
    for warning in warnings: print(f"WARNING: {warning}")
    for error in errors: print(f"ERROR: {error}")
    return 0 if not errors else 1

if __name__ == "__main__": sys.exit(main())
