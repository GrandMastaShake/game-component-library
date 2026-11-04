#!/usr/bin/env python3
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "validate_status_effects", ROOT / "tools" / "validate_status_effects.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
EXAMPLE = ROOT / "examples" / "status-effects" / "mirelight.status.json"


def valid_document():
    return json.loads(EXAMPLE.read_text())


def request(application_id, effect_id="mire_slick", target="scout", **fields):
    return {
        "applicationId": application_id,
        "effectId": effect_id,
        "targetId": target,
        **fields,
    }


class StatusEffectValidatorTests(unittest.TestCase):
    def validate(self, documents=None):
        documents = [("test.status.json", valid_document())] if documents is None else documents
        return MODULE.validate_bundle(documents)

    def test_valid_bundle_passes(self):
        errors, warnings = self.validate()
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_non_object_and_wrong_top_level_shapes_are_safe(self):
        errors, _ = self.validate([("bad.status.json", [])])
        self.assertEqual(["bad.status.json: document must be an object"], errors)
        document = valid_document()
        document["effects"] = {}
        document["immunities"] = None
        document["cleanseRules"] = "bad"
        document["scenarios"] = []
        document["unexpected"] = True
        errors, _ = self.validate([("bad.status.json", document)])
        self.assertTrue(any("effects must be" in error for error in errors))
        self.assertTrue(any("immunities must be" in error for error in errors))
        self.assertTrue(any("cleanseRules must be" in error for error in errors))
        self.assertTrue(any("unknown top-level" in error for error in errors))

    def test_duplicate_document_and_cross_file_effect_ids_fail(self):
        first = valid_document()
        second = copy.deepcopy(first)
        errors, _ = self.validate([("a.status.json", first), ("b.status.json", second)])
        self.assertTrue(any("duplicate status document id" in error for error in errors))
        self.assertTrue(any("duplicate effect id 'mire_slick' across bundle" in error for error in errors))

    def test_duplicate_effect_and_scenario_ids_fail(self):
        document = valid_document()
        document["effects"][1]["id"] = document["effects"][0]["id"]
        document["scenarios"][1]["id"] = document["scenarios"][0]["id"]
        errors, _ = self.validate([("bad.status.json", document)])
        self.assertTrue(any("duplicate effect id" in error for error in errors))
        # Definition errors intentionally stop execution; duplicate scenario ids
        # are checked by a separate otherwise-valid document below.
        other = valid_document()
        other["scenarios"][1]["id"] = other["scenarios"][0]["id"]
        errors, _ = self.validate([("bad.status.json", other)])
        self.assertTrue(any("duplicate scenario id" in error for error in errors))

    def test_invalid_stack_duration_and_grouping_fail(self):
        document = valid_document()
        effect = document["effects"][0]
        effect["durationSeconds"] = 0
        effect["stackPolicy"] = "addMore"
        effect["durationPolicy"] = "sometimes"
        effect["maxStacks"] = 2
        effect["grouping"] = "global"
        errors, _ = self.validate([("bad.status.json", document)])
        self.assertTrue(any("durationSeconds" in error for error in errors))
        self.assertTrue(any("stackPolicy" in error for error in errors))
        self.assertTrue(any("durationPolicy" in error for error in errors))
        self.assertTrue(any("grouping" in error for error in errors))

    def test_invalid_control_and_modifier_fail(self):
        document = valid_document()
        root = document["effects"][1]
        root["control"] = {"restrictions": ["move", "move", "charm"], "moveMultiplier": 0.5}
        fray = document["effects"][4]["modifiers"][0]
        fray["operation"] = "multiply"
        fray["value"] = 0
        fray["perStack"] = "yes"
        errors, _ = self.validate([("bad.status.json", document)])
        self.assertTrue(any("duplicate ids" in error for error in errors))
        self.assertTrue(any("unsupported control restrictions" in error for error in errors))
        self.assertTrue(any("move restriction requires" in error for error in errors))
        self.assertTrue(any("multiply value" in error for error in errors))
        self.assertTrue(any("perStack must be boolean" in error for error in errors))

    def test_unknown_rule_references_and_empty_selectors_fail(self):
        document = valid_document()
        document["immunities"][0]["effectIds"] = ["missing"]
        document["immunities"][0]["tags"] = []
        document["cleanseRules"][0]["tags"] = []
        document["cleanseRules"][0]["effectIds"] = []
        document["cleanseRules"][0]["maxEffects"] = 0
        document["cleanseRules"][0]["order"] = "random"
        errors, _ = self.validate([("bad.status.json", document)])
        self.assertTrue(any("unknown id 'missing'" in error for error in errors))
        self.assertTrue(any("at least one effectIds or tags selector" in error for error in errors))
        self.assertTrue(any("maxEffects" in error for error in errors))
        self.assertTrue(any("order must be" in error for error in errors))

    def test_bad_scenario_operations_are_errors_not_crashes(self):
        document = valid_document()
        document["scenarios"] = [{
            "id": "bad_steps",
            "steps": [
                {"op": "apply", "applicationId": "a", "effectId": "missing", "targetId": "scout"},
                {"op": "teleport"},
                {"op": "cleanse", "cleanseId": "c", "targetId": "scout", "ruleId": "missing"},
                {"op": "advance", "seconds": -1},
            ],
        }]
        errors, _ = self.validate([("bad.status.json", document)])
        self.assertEqual(4, len(errors))
        self.assertTrue(any("unknown effectId" in error for error in errors))
        self.assertTrue(any("unsupported op" in error for error in errors))
        self.assertTrue(any("unknown cleanse rule" in error for error in errors))
        self.assertTrue(any("advance.seconds" in error for error in errors))

    def test_failed_scenario_expectation_is_caught(self):
        document = valid_document()
        document["scenarios"] = [copy.deepcopy(document["scenarios"][0])]
        document["scenarios"][0]["steps"][0]["expect"]["moveMultiplier"] = 1
        errors, _ = self.validate([("bad.status.json", document)])
        self.assertTrue(any("moveMultiplier mismatch" in error for error in errors))

    def test_malformed_expectation_is_an_error_not_a_crash(self):
        document = valid_document()
        document["scenarios"] = [copy.deepcopy(document["scenarios"][0])]
        document["scenarios"][0]["steps"][0]["expect"]["active"] = None
        errors, _ = self.validate([("bad.status.json", document)])
        self.assertTrue(any("expect.active must be an array of objects" in error for error in errors))

    def test_compound_embeds_the_validated_original_content(self):
        compound = json.loads((ROOT / "compounds" / "StatusControlLoop.compound.json").read_text())
        status = next(member for member in compound["components"] if member["id"] == "combat.status_effects")
        document = valid_document()
        self.assertEqual(document["effects"], status["config"]["definitions"])
        self.assertEqual(document["immunities"], status["config"]["immunities"])
        self.assertEqual(document["cleanseRules"], status["config"]["cleanseRules"])

    def test_refresh_has_one_identity_and_stale_timer_is_inert(self):
        model = MODULE.StatusModel(valid_document())
        model.apply(request("a", durationSeconds=2))
        model.apply(request("b"))
        self.assertEqual(1, len(model.active))
        self.assertEqual("a", model.active[0]["applicationId"])
        self.assertEqual(2, model.active[0]["generation"])
        self.assertEqual(6, model.active[0]["remainingSeconds"])
        self.assertEqual("refreshed", model.events[-1]["event"])
        model.events = []
        model.expire({"applicationId": "a", "generation": 1})
        self.assertEqual([], model.events)
        self.assertEqual(1, len(model.active))

    def test_capacity_rejects_new_but_allows_refresh(self):
        model = MODULE.StatusModel(valid_document(), max_active=1)
        model.apply(request("a"))
        model.apply(request("root", "bound_steps"))
        self.assertEqual("capacity", model.last_rejected["reason"])
        self.assertEqual(1, len(model.active))
        model.apply(request("b"))
        self.assertEqual(1, len(model.active))
        self.assertEqual(2, model.active[0]["generation"])

    def test_target_effect_source_grouping_separates_focus(self):
        model = MODULE.StatusModel(valid_document())
        model.apply(request("focus_a", "battle_focus", sourceId="one"))
        model.apply(request("focus_b", "battle_focus", sourceId="two"))
        self.assertEqual(2, len(model.active))
        self.assertEqual({"focus_a", "focus_b"}, {i["applicationId"] for i in model.active})

    def test_cleanse_skips_nondispellable_and_replay_is_inert(self):
        model = MODULE.StatusModel(valid_document())
        model.apply(request("focus", "battle_focus"))
        model.apply(request("root", "bound_steps"))
        model.cleanse({"cleanseId": "cleanse", "targetId": "scout", "ruleId": "purge_control"})
        self.assertEqual(["focus"], [i["applicationId"] for i in model.active])
        model.apply(request("later_root", "bound_steps"))
        event_count = len(model.events)
        model.cleanse({"cleanseId": "cleanse", "targetId": "scout", "ruleId": "purge_control"})
        self.assertEqual(event_count, len(model.events))
        self.assertEqual(2, len(model.active))

    def test_restore_preserves_active_state_and_dedupe_ledgers(self):
        model = MODULE.StatusModel(valid_document())
        model.apply(request("a"))
        model.snapshot()
        model.cleanse({"cleanseId": "cleanse", "targetId": "scout", "ruleId": "purge_control"})
        self.assertEqual([], model.active)
        model.restore()
        self.assertEqual(1, len(model.active))
        self.assertNotIn("cleanse", model.processed_cleanses)
        model.cleanse({"cleanseId": "cleanse", "targetId": "scout", "ruleId": "purge_control"})
        model.apply(request("later"))
        model.snapshot()
        model.cleanse({"cleanseId": "new_cleanse", "targetId": "scout", "ruleId": "purge_control"})
        model.restore()
        # The old cleanse is in the restored ledger and cannot remove a later
        # application; the newer cleanse was not yet in that snapshot.
        model.cleanse({"cleanseId": "cleanse", "targetId": "scout", "ruleId": "purge_control"})
        self.assertEqual(["later"], [i["applicationId"] for i in model.active])

    def test_defeat_reset_and_manual_removal_have_distinct_scopes(self):
        model = MODULE.StatusModel(valid_document())
        model.apply(request("a", encounterId="one"))
        model.apply(request("b", target="other", encounterId="two"))
        model.reset("one")
        self.assertEqual(["b"], [i["applicationId"] for i in model.active])
        model.defeat("other")
        self.assertEqual([], model.active)
        model.apply(request("c"))
        model.remove({"removalId": "remove", "targetId": "scout", "applicationId": "c"})
        model.apply(request("d"))
        event_count = len(model.events)
        model.remove({"removalId": "remove", "targetId": "scout", "applicationId": "d"})
        self.assertEqual(event_count, len(model.events))
        self.assertEqual(["d"], [i["applicationId"] for i in model.active])

    def test_permanent_effect_and_ignore_duration_policy(self):
        document = valid_document()
        effect = copy.deepcopy(document["effects"][0])
        effect.update(id="permanent_slow", durationSeconds=None, durationPolicy="ignore")
        document["effects"] = [effect]
        document["immunities"] = []
        document["cleanseRules"] = []
        document["scenarios"] = [{"id": "permanent", "steps": [
            {"op": "apply", **request("a", "permanent_slow")},
            {"op": "apply", **request("b", "permanent_slow", durationSeconds=2)},
        ]}]
        model = MODULE.StatusModel(document)
        model.apply(request("a", "permanent_slow"))
        model.apply(request("b", "permanent_slow", durationSeconds=2))
        self.assertIsNone(model.active[0]["remainingSeconds"])
        self.assertEqual(2, model.active[0]["generation"])


if __name__ == "__main__":
    unittest.main()
