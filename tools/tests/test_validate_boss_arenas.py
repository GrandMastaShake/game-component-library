#!/usr/bin/env python3
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "validate_boss_arenas", ROOT / "tools" / "validate_boss_arenas.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
EXAMPLE = ROOT / "examples" / "boss-arena" / "foundry-archive.boss.json"


def valid_document():
    return json.loads(EXAMPLE.read_text())


class BossArenaValidatorTests(unittest.TestCase):
    def validate(self, documents=None):
        documents = [("test.boss.json", valid_document())] if documents is None else documents
        return MODULE.validate_bundle(documents)

    def test_valid_bundle_passes(self):
        errors, warnings = self.validate()
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_cross_file_arena_links_pass(self):
        document = valid_document()
        first = {"arenas": [document["arenas"][0]], "encounters": [document["encounters"][0]]}
        second = {"arenas": [document["arenas"][1]], "encounters": [document["encounters"][1]]}
        errors, _ = self.validate([("a.boss.json", first), ("b.boss.json", second)])
        self.assertEqual([], errors)

    def test_duplicate_cross_file_arena_and_encounter_fail(self):
        first = valid_document()
        second = copy.deepcopy(first)
        errors, _ = self.validate([("a.boss.json", first), ("b.boss.json", second)])
        self.assertTrue(any("duplicate arena id 'glassworks' across bundle" in error for error in errors))
        self.assertTrue(any("duplicate encounter id 'foundry_heart' across bundle" in error for error in errors))

    def test_unknown_arena_and_hazard_phase_fail(self):
        document = valid_document()
        document["encounters"][0]["arenaId"] = "missing"
        document["encounters"][1]["phases"][1]["hazardPhase"] = "missing"
        errors, _ = self.validate([("bad.boss.json", document)])
        self.assertTrue(any("unknown arenaId 'missing'" in error for error in errors))
        self.assertTrue(any("unknown hazardPhase 'missing'" in error for error in errors))

    def test_first_phase_and_multi_kind_triggers_fail(self):
        document = valid_document()
        phases = document["encounters"][0]["phases"]
        phases[0]["enterWhen"] = {"healthAtOrBelow": 0.9}
        phases[1]["enterWhen"] = {"healthAtOrBelow": 0.6, "elapsedSecondsAtLeast": 30}
        errors, _ = self.validate([("bad.boss.json", document)])
        self.assertTrue(any("first phase enters on engagement" in error for error in errors))
        self.assertTrue(any("exactly one" in error for error in errors))

    def test_transition_ranges_and_order_fail(self):
        document = valid_document()
        phases = document["encounters"][0]["phases"]
        phases[1]["enterWhen"]["healthAtOrBelow"] = 1.2
        phases[3]["enterWhen"]["elapsedSecondsAtLeast"] = 0
        archive = document["encounters"][1]["phases"]
        archive[1]["enterWhen"]["healthAtOrBelow"] = 0.5
        archive.append(copy.deepcopy(archive[1]))
        archive[-1]["id"] = "later_health"
        archive[-1]["enterWhen"]["healthAtOrBelow"] = 0.7
        archive[-1]["attacks"] = []
        errors, _ = self.validate([("bad.boss.json", document)])
        self.assertTrue(any("between 0 and 1" in error for error in errors))
        self.assertTrue(any("elapsedSecondsAtLeast" in error for error in errors))
        self.assertTrue(any("strictly descending" in error for error in errors))

    def test_condition_event_match_and_duplicate_id_fail(self):
        document = valid_document()
        first = document["encounters"][0]["phases"][2]["enterWhen"]
        first["conditionEvent"] = "combat.entityDefeated"
        first["conditionMatch"] = {"bad key": []}
        duplicate = copy.deepcopy(document["encounters"][0]["phases"][2])
        duplicate["id"] = "duplicate_condition"
        duplicate["attacks"] = []
        document["encounters"][0]["phases"].append(duplicate)
        errors, _ = self.validate([("bad.boss.json", document)])
        self.assertTrue(any("conditionEvent must be one of" in error for error in errors))
        self.assertTrue(any("conditionMatch entries" in error for error in errors))
        self.assertTrue(any("duplicate conditionId" in error for error in errors))

    def test_duplicate_phase_and_attack_ids_fail(self):
        document = valid_document()
        encounter = document["encounters"][0]
        encounter["phases"][1]["id"] = encounter["phases"][0]["id"]
        encounter["phases"][1]["attacks"][0]["id"] = encounter["phases"][0]["attacks"][0]["id"]
        errors, _ = self.validate([("bad.boss.json", document)])
        self.assertTrue(any("duplicate phase id" in error for error in errors))
        self.assertTrue(any("duplicate attack id" in error for error in errors))

    def test_bad_attack_shape_and_timing_fail(self):
        document = valid_document()
        attack = document["encounters"][0]["phases"][0]["attacks"][0]
        attack["windupSeconds"] = 0
        attack["cooldownSeconds"] = -1
        attack["shape"] = {"kind": "circle"}
        errors, _ = self.validate([("bad.boss.json", document)])
        self.assertTrue(any("windupSeconds" in error for error in errors))
        self.assertTrue(any("cooldownSeconds" in error for error in errors))
        self.assertTrue(any("radius" in error for error in errors))

    def test_bad_add_and_boss_stats_fail(self):
        document = valid_document()
        encounter = document["encounters"][0]
        encounter["boss"]["maxHealth"] = 0
        add = encounter["phases"][1]["adds"][0]
        add["count"] = 0
        add["baseHealth"] = -2
        errors, _ = self.validate([("bad.boss.json", document)])
        self.assertTrue(any("boss.maxHealth" in error for error in errors))
        self.assertTrue(any("count must be" in error for error in errors))
        self.assertTrue(any("baseHealth" in error for error in errors))

    def test_hazard_warning_overlap_and_regions_fail(self):
        document = valid_document()
        arena = document["arenas"][0]
        phase = arena["phases"][1]
        phase["warningSeconds"] = 0
        phase["disarm"] = phase["arm"]
        arena["hazards"][0]["regions"][0]["width"] = 0
        errors, _ = self.validate([("bad.boss.json", document)])
        self.assertTrue(any("warningSeconds" in error for error in errors))
        self.assertTrue(any("arm and disarm" in error for error in errors))
        self.assertTrue(any("width" in error for error in errors))

    def test_enrage_reference_modifier_and_duplicate_attack_fail(self):
        document = valid_document()
        encounter = document["encounters"][0]
        enrage = encounter["enrage"]
        enrage["afterSeconds"] = 0
        enrage["hazardPhase"] = "missing"
        enrage["behaviorModifiers"]["moveSpeed"] = 0
        enrage["attacks"][0]["id"] = encounter["phases"][0]["attacks"][0]["id"]
        errors, _ = self.validate([("bad.boss.json", document)])
        self.assertTrue(any("afterSeconds" in error for error in errors))
        self.assertTrue(any("unknown hazardPhase 'missing'" in error for error in errors))
        self.assertTrue(any("behaviorModifiers" in error for error in errors))
        self.assertTrue(any("duplicate attack id" in error for error in errors))

    def test_malformed_nested_values_return_errors_without_crashing(self):
        document = valid_document()
        document["arenas"][0]["hazards"][0]["regions"] = [{"x": {}, "y": 0, "width": 1, "height": 1}]
        document["arenas"][0]["phases"][1]["arm"] = [{"id": "not-a-string"}]
        document["encounters"][0]["phases"][1]["adds"] = [{"archetype": [], "count": {}, "baseHealth": []}]
        errors, _ = self.validate([("bad.boss.json", document)])
        self.assertTrue(errors)
        self.assertTrue(any("well-formed id" in error for error in errors))
        self.assertTrue(any("must be finite" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
