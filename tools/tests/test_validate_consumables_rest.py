#!/usr/bin/env python3
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("validate_consumables_rest", ROOT / "tools" / "validate_consumables_rest.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
EXAMPLE = ROOT / "examples" / "consumables-rest" / "glimmerfen.recovery.json"
STATUS = ROOT / "examples" / "status-effects" / "mirelight.status.json"

def valid_document(): return json.loads(EXAMPLE.read_text())
def status_document(): return json.loads(STATUS.read_text())
def status_pair(): return [("mirelight.status.json", status_document())]
def model(): return MODULE.RecoveryModel(valid_document(), status_document())
def use(use_id="use.test", item="redleaf_draught", source="scout", target="scout", **fields):
    return {"useId": use_id, "itemId": item, "sourceId": source, "targetId": target, **fields}
def rest(rest_id="rest.test", profile="watchfire_rest", **fields):
    return {"restId": rest_id, "profileId": profile, "memberIds": ["scout"], "safeZone": True, "inCombat": False, "ambushRoll": 0.9, **fields}

class ConsumablesRestValidatorTests(unittest.TestCase):
    def validate(self, documents=None, statuses=None):
        documents = [("test.recovery.json", valid_document())] if documents is None else documents
        return MODULE.validate_bundle(documents, status_pair() if statuses is None else statuses)

    def test_valid_bundle_passes(self):
        errors, warnings = self.validate()
        self.assertEqual([], errors); self.assertEqual([], warnings)

    def test_non_object_and_bad_top_level_shapes_are_safe(self):
        errors, _ = self.validate([("bad.recovery.json", [])])
        self.assertEqual(["bad.recovery.json: document must be an object"], errors)
        document = valid_document()
        document.update(consumables={}, restProfiles=None, scenarios=[], unexpected=True)
        errors, _ = self.validate([("bad.recovery.json", document)])
        self.assertTrue(any("unknown top-level" in error for error in errors))
        self.assertTrue(any("consumables must be an array" in error for error in errors))
        self.assertTrue(any("restProfiles must be an array" in error for error in errors))

    def test_cross_file_document_item_and_profile_ids_are_unique(self):
        first, second = valid_document(), copy.deepcopy(valid_document())
        errors, _ = self.validate([("a.recovery.json", first), ("b.recovery.json", second)])
        self.assertTrue(any("duplicate recovery document id" in error for error in errors))
        self.assertTrue(any("duplicate consumables id" in error for error in errors))
        self.assertTrue(any("duplicate restProfiles id" in error for error in errors))

    def test_invalid_consumable_rules_fail(self):
        document = valid_document(); item = document["consumables"][0]
        item.update(targetMode="area", usePolicy="sometimes", cooldownSeconds=-1, consume="yes", recovery=[], statusApplications=[], cleanseRequests=[])
        errors, _ = self.validate([("bad.recovery.json", document)])
        for text in ("targetMode", "usePolicy", "cooldownSeconds", "consume must be boolean", "at least one recovery"):
            self.assertTrue(any(text in error for error in errors), text)

    def test_invalid_recovery_operations_fail(self):
        document = valid_document()
        document["consumables"][0]["recovery"] = [
            {"resourceId": "health", "mode": "flat", "amount": 0},
            {"resourceId": "focus", "mode": "percentMax", "amount": 2},
            {"resourceId": "focus", "mode": "full", "amount": 1},
            {"resourceId": "focus", "mode": "random"},
        ]
        errors, _ = self.validate([("bad.recovery.json", document)])
        self.assertEqual(4, len([error for error in errors if "recovery[" in error]))

    def test_unknown_and_malformed_status_references_fail_safely(self):
        document = valid_document()
        document["consumables"][2]["cleanseRequests"] = [{"ruleId": "missing"}]
        document["consumables"][3]["statusApplications"] = [{"effectId": []}]
        document["statusDocumentIds"] = ["status.absent"]
        errors, _ = self.validate([("bad.recovery.json", document)])
        self.assertTrue(any("missing status document" in error for error in errors))
        self.assertTrue(any("unknown cleanse rule" in error for error in errors))
        self.assertTrue(any("effectId must be well-formed" in error for error in errors))

    def test_invalid_rest_profiles_fail(self):
        document = valid_document(); profile = document["restProfiles"][0]
        profile.update(durationSeconds=0, requiresSafeZone="yes", allowInCombat="no", ambushChance=2)
        errors, _ = self.validate([("bad.recovery.json", document)])
        for text in ("durationSeconds", "requiresSafeZone", "allowInCombat", "ambushChance"):
            self.assertTrue(any(text in error for error in errors), text)

    def test_malformed_inventory_units_and_pools_are_errors_not_crashes(self):
        document = valid_document()
        document["initialInventory"][0]["itemId"] = []
        document["units"][0].update(id=[], maxHealth="bad", health=2)
        document["resourcePools"][0].update(id="health", ownerId=[], maximum="bad", initial=2)
        errors, _ = self.validate([("bad.recovery.json", document)])
        self.assertTrue(any("itemId must be well-formed" in error for error in errors))
        self.assertTrue(any("malformed unit id" in error for error in errors))
        self.assertTrue(any("malformed pool or owner id" in error for error in errors))

    def test_reserved_pool_and_duplicate_owner_resource_fail(self):
        document = valid_document()
        document["resourcePools"][0]["id"] = "health"
        document["resourcePools"][1] = copy.deepcopy(document["resourcePools"][2])
        errors, _ = self.validate([("bad.recovery.json", document)])
        self.assertTrue(any("belongs to another resource owner" in error for error in errors))
        self.assertTrue(any("duplicate owner/resource pool" in error for error in errors))

    def test_bad_scenario_operations_are_errors_not_crashes(self):
        document = valid_document(); document["scenarios"] = [{"id": "bad", "steps": [
            {"op": "use", "useId": "u", "itemId": "missing", "sourceId": "scout", "targetId": "scout"},
            {"op": "rest", "restId": "r", "profileId": "watchfire_rest", "memberIds": [[], []], "safeZone": True, "inCombat": False, "ambushRoll": 0.5},
            {"op": "hit", "targetId": []}, {"op": "teleport"}, {"op": "advance", "seconds": -1},
        ]}]
        errors, _ = self.validate([("bad.recovery.json", document)])
        self.assertEqual(5, len(errors))
        self.assertTrue(any("unknown itemId" in error for error in errors))
        self.assertTrue(any("memberIds must be unique" in error for error in errors))

    def test_failed_and_malformed_expectations_are_safe(self):
        document = valid_document(); document["scenarios"] = [copy.deepcopy(document["scenarios"][0])]
        document["scenarios"][0]["steps"][0]["expect"]["health"]["scout"] = 2
        errors, _ = self.validate([("bad.recovery.json", document)])
        self.assertTrue(any("health.scout expected 2" in error for error in errors))
        document = valid_document(); document["scenarios"] = [copy.deepcopy(document["scenarios"][0])]
        document["scenarios"][0]["steps"][0]["expect"]["resources"] = []
        errors, _ = self.validate([("bad.recovery.json", document)])
        self.assertTrue(any("resources must be an object" in error for error in errors))

    def test_accepted_use_consumes_once_and_replay_is_silent(self):
        m = model(); m.use(use()); self.assertEqual(1, m.inventory["redleaf_draught"]); self.assertEqual(12, m.units["scout"]["health"])
        count = len(m.events); m.use(use()); self.assertEqual(count, len(m.events)); self.assertEqual(1, m.inventory["redleaf_draught"])

    def test_cooldown_rejection_preserves_item_and_stale_timer_is_inert(self):
        m = model(); m.use(use("one")); m.use(use("two", "focus_phial"))
        self.assertEqual(2, m.inventory["focus_phial"]); self.assertEqual("cooldown", m.last_rejected["reason"])
        m.expire_cooldown({"sourceId": "scout", "cooldownGroupId": "draught", "generation": 1})
        m.use(use("three", target="warden")); m.expire_cooldown({"sourceId": "scout", "cooldownGroupId": "draught", "generation": 1})
        self.assertEqual(2, m.cooldowns[0]["generation"])

    def test_downstream_full_health_rejection_does_not_refund_accepted_use(self):
        m = model(); m.use(use(target="warden"))
        self.assertEqual(1, m.inventory["redleaf_draught"]); self.assertEqual(10, m.units["warden"]["health"])
        self.assertEqual("alreadyFull", m.last_health_rejected["reason"])

    def test_status_and_cleanse_child_ids_reach_single_owner(self):
        m = model(); m.use(use("snare", "snaring_vial", target="bog_target"))
        self.assertEqual(["snare.effect.0"], [row["applicationId"] for row in m.status.active])
        m.use(use("clear", "clearwater_phial", target="bog_target"))
        self.assertEqual([], m.status.active); self.assertIn("clear.cleanse.0", m.status.processed_cleanses)

    def test_rest_rejection_and_interruption_never_recover(self):
        m = model(); m.rest(rest(safeZone=False)); self.assertEqual("unsafe", m.last_rejected["reason"]); self.assertEqual(7, m.units["scout"]["health"])
        m.rest(rest("rest.two", "field_break", safeZone=False)); m.interrupt_rest("rest.two", "manual"); m.finish_rest()
        self.assertEqual(7, m.units["scout"]["health"]); self.assertEqual(2, m.pools[("scout", "focus")]["current"])

    def test_completed_rest_recovers_and_replayed_request_is_silent(self):
        m = model(); m.rest(rest()); m.advance(8)
        self.assertEqual(12, m.units["scout"]["health"]); self.assertEqual(8, m.pools[("scout", "focus")]["current"]); self.assertEqual(3, m.pools[("scout", "resolve")]["current"])
        count = len(m.events); m.rest(rest()); self.assertEqual(count, len(m.events)); self.assertIn("rest.test", m.processed_health_rests)

    def test_ambush_and_damage_interrupt_without_completion(self):
        m = model(); m.rest(rest("rest.ambush", "field_break", safeZone=False, ambushRoll=0.1)); m.advance(4)
        names = [row["event"] for row in m.events]
        self.assertIn("world.restAmbushRequested", names); self.assertNotIn("world.restCompleted", names); self.assertEqual(7, m.units["scout"]["health"])
        m = model(); m.rest(rest("rest.hit", "field_break", safeZone=False))
        if "scout" in m.active_rest["memberIds"]: m.interrupt_rest("rest.hit", "damage")
        self.assertEqual(7, m.units["scout"]["health"])

    def test_snapshot_restore_preserves_pending_rest_and_ledgers(self):
        m = model(); m.use(use()); m.rest(rest()); m.snapshot(); m.advance(8); m.restore()
        self.assertEqual("rest.test", m.active_rest["restId"]); self.assertEqual(2, m.pools[("scout", "focus")]["current"])
        count = len(m.events); m.use(use()); self.assertEqual(count, len(m.events)); m.advance(8)
        self.assertEqual(8, m.pools[("scout", "focus")]["current"])

    def test_unknown_item_rejection_is_inert_and_remembered(self):
        m = model(); m.use(use(item="missing"))
        self.assertEqual("unknownItem", m.last_rejected["reason"])
        self.assertEqual(2, m.inventory["redleaf_draught"]); self.assertEqual(7, m.units["scout"]["health"])
        count = len(m.events); m.use(use(item="missing")); self.assertEqual(count, len(m.events))

    def test_rest_consumers_dedupe_independently(self):
        m = model(); m.rest(rest()); m.advance(8)
        m.units["scout"]["health"] = 5; m.pools[("scout", "focus")]["current"] = 2
        m.processed_resource_rests.remove("rest.test")
        m.active_rest = {"restId": "rest.test", "profileId": "watchfire_rest", "memberIds": ["scout"], "remainingSeconds": 0, "generation": 1, "ambushRoll": 0.9}
        m.finish_rest()
        self.assertEqual(5, m.units["scout"]["health"])
        self.assertEqual(8, m.pools[("scout", "focus")]["current"])

    def test_compound_embeds_exact_content_and_dependency_closure(self):
        compound = json.loads((ROOT / "compounds" / "ConsumableRestLoop.compound.json").read_text())
        members = {row["id"]: row for row in compound["components"]}; document = valid_document()
        self.assertEqual(document["consumables"], members["inventory.potion_belt"]["config"]["definitions"])
        self.assertEqual(document["restProfiles"], members["world.rest_camp"]["config"]["profiles"])
        self.assertEqual(document["resourcePools"], members["combat.resource_pools"]["config"]["definitions"])
        self.assertEqual(document["initialInventory"], members["inventory.slotted_bag"]["config"]["initialItems"])
        descriptors = {}
        for path in ROOT.glob("components/**/*.component.json"):
            descriptor = json.loads(path.read_text()); descriptors[descriptor["id"]] = descriptor
        for cid, descriptor in descriptors.items():
            if cid in members:
                for dependency in descriptor["dependencies"]: self.assertIn(dependency, members)

if __name__ == "__main__": unittest.main()
