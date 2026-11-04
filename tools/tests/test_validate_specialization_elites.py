#!/usr/bin/env python3
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "validate_specialization_elites", ROOT / "tools" / "validate_specialization_elites.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
EXAMPLES = ROOT / "examples" / "specialization-elite"


def valid_specialization_document():
    return json.loads((EXAMPLES / "disciplines.specialization.json").read_text())


def valid_elite_document():
    return json.loads((EXAMPLES / "crossing.elite.json").read_text())


def valid_tree_document():
    return json.loads((ROOT / "examples" / "skill-trees" / "buildcraft-example.tree.json").read_text())


class SpecializationEliteValidatorTests(unittest.TestCase):
    def validate(self, specializations=None, elites=None, trees=None):
        specializations = [("test.specialization.json", valid_specialization_document())] if specializations is None else specializations
        elites = [("test.elite.json", valid_elite_document())] if elites is None else elites
        trees = [("test.tree.json", valid_tree_document())] if trees is None else trees
        return MODULE.validate_bundle(specializations, elites, trees)

    def test_valid_bundle_passes(self):
        errors, warnings = self.validate()
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_duplicate_specialization_and_unknown_prerequisite_fail(self):
        first = valid_specialization_document()
        second = valid_specialization_document()
        second["masteryTracks"] = []
        second["abilityCatalog"] = []
        second["specializations"] = [copy.deepcopy(first["specializations"][0])]
        first["specializations"][0]["requiresSpecializations"] = ["missing"]
        errors, _ = self.validate(specializations=[("a.specialization.json", first), ("b.specialization.json", second)])
        self.assertTrue(any("duplicate specialization id 'warden' across bundle" in error for error in errors))
        self.assertTrue(any("unknown id 'missing'" in error for error in errors))

    def test_cross_file_specialization_cycle_fails(self):
        first = valid_specialization_document()
        second = valid_specialization_document()
        first["specializations"] = [{"id": "alpha", "name": "Alpha", "requiresSpecializations": ["beta"]}]
        second["specializations"] = [{"id": "beta", "name": "Beta", "requiresSpecializations": ["alpha"]}]
        for document in (first, second):
            document["masteryTracks"] = []
            document["abilityCatalog"] = []
        errors, _ = self.validate(specializations=[("a.specialization.json", first), ("b.specialization.json", second)])
        self.assertTrue(any("specialization prerequisite cycle" in error for error in errors))

    def test_malformed_mastery_threshold_source_and_gate_fail(self):
        document = valid_specialization_document()
        track = document["masteryTracks"][0]
        track["thresholds"] = [20, 20]
        track["sources"][0]["amountFrom"] = "xp"
        track["sources"][0]["dedupeBy"] = None
        document["masteryTracks"][1]["specialization"] = "missing"
        errors, _ = self.validate(specializations=[("bad.specialization.json", document)], elites=[])
        self.assertTrue(any("strictly increasing" in error for error in errors))
        self.assertTrue(any("amount or amountFrom, not both" in error for error in errors))
        self.assertTrue(any("dedupeBy" in error for error in errors))
        self.assertTrue(any("unknown specialization 'missing'" in error for error in errors))

    def test_ability_gate_references_and_rank_bounds_fail(self):
        document = valid_specialization_document()
        ability = document["abilityCatalog"][2]
        ability["specialization"] = "missing"
        ability["masteryTrack"] = "elite_hunter"
        ability["minMasteryRank"] = 3
        document["abilityCatalog"][0]["masteryTrack"] = "missing"
        errors, _ = self.validate(specializations=[("bad.specialization.json", document)], elites=[])
        self.assertTrue(any("unknown specialization 'missing'" in error for error in errors))
        self.assertTrue(any("exceeds track maximum 2" in error for error in errors))
        self.assertTrue(any("unknown masteryTrack 'missing'" in error for error in errors))

    def test_affix_cycle_unknown_exclusion_and_bad_attack_fail(self):
        document = valid_elite_document()
        affixes = {affix["id"]: affix for affix in document["affixes"]}
        affixes["fortified"]["requires"] = ["warded"]
        affixes["voltaic"]["excludes"].append("missing")
        attack = affixes["voltaic"]["attacks"][0]
        attack["windupSeconds"] = 0
        attack["shape"] = {"kind": "unknown"}
        errors, _ = self.validate(elites=[("bad.elite.json", document)])
        self.assertTrue(any("affix prerequisite cycle" in error for error in errors))
        self.assertTrue(any("unknown id 'missing'" in error for error in errors))
        self.assertTrue(any("windupSeconds" in error for error in errors))
        self.assertTrue(any("kind must be" in error for error in errors))

    def test_nonelite_affix_and_unknown_reference_fail(self):
        document = valid_elite_document()
        unit = document["encounters"][0]["waves"][0]["units"][0]
        unit["affixCount"] = 1
        unit["affixIds"] = ["missing"]
        errors, _ = self.validate(elites=[("bad.elite.json", document)])
        self.assertTrue(any("non-elite units cannot request affixes" in error for error in errors))
        self.assertTrue(any("unknown id 'missing'" in error for error in errors))

    def test_explicit_affix_requirements_and_threat_fail(self):
        document = valid_elite_document()
        encounter = document["encounters"][0]
        encounter["threat"] = 1
        champion = encounter["waves"][1]["units"][1]
        champion["affixIds"] = ["warded"]
        champion["affixCount"] = 1
        errors, _ = self.validate(elites=[("bad.elite.json", document)])
        self.assertTrue(any("missing required affixes ['fortified']" in error for error in errors))
        self.assertTrue(any("outside its threat band" in error for error in errors))

    def test_duplicate_wave_and_missing_elite_fail(self):
        document = valid_elite_document()
        encounter = document["encounters"][0]
        encounter["waves"][1]["id"] = encounter["waves"][0]["id"]
        for wave in encounter["waves"]:
            for unit in wave["units"]:
                unit["elite"] = False
                unit.pop("affixIds", None)
                unit["affixCount"] = 0
        errors, _ = self.validate(elites=[("bad.elite.json", document)])
        self.assertTrue(any("duplicate wave id" in error for error in errors))
        self.assertTrue(any("requires at least one elite unit" in error for error in errors))

    def test_inconsistent_affix_cap_and_cross_file_cycle_fail(self):
        first = {"maxAffixes": 2, "affixes": [{"id": "a", "weight": 1, "requires": ["b"]}], "encounters": []}
        second = {"maxAffixes": 3, "affixes": [{"id": "b", "weight": 1, "requires": ["a"]}], "encounters": []}
        errors, _ = self.validate(elites=[("a.elite.json", first), ("b.elite.json", second)])
        self.assertTrue(any("inconsistent maxAffixes" in error for error in errors))
        self.assertTrue(any("affix prerequisite cycle" in error for error in errors))

    def test_skill_references_and_rank_bounds_fail(self):
        document = valid_specialization_document()
        document["specializations"][0]["requiredSkills"][0]["id"] = "missing"
        document["abilityCatalog"][0]["sourceNodeId"] = "riposte"
        document["abilityCatalog"][0]["minRank"] = 2
        errors, _ = self.validate(specializations=[("bad.specialization.json", document)], elites=[])
        self.assertTrue(any("unknown skill 'missing'" in error for error in errors))
        self.assertTrue(any("minRank 2 exceeds skill maximum 1" in error for error in errors))

    def test_malformed_reference_types_return_errors_without_crashing(self):
        specializations = valid_specialization_document()
        specializations["specializations"][0]["requiresSpecializations"] = [{"id": "not-an-id-string"}]
        elites = valid_elite_document()
        elites["affixes"][0]["requires"] = [{"id": "also-not-a-string"}]
        errors, _ = self.validate(
            specializations=[("bad.specialization.json", specializations)],
            elites=[("bad.elite.json", elites)],
        )
        self.assertTrue(errors)
        self.assertTrue(any("well-formed id" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
