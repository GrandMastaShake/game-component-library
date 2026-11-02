#!/usr/bin/env python3
import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "validate_skill_trees", ROOT / "tools" / "validate_skill_trees.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def valid_tree():
    return {
        "startingPoints": 1,
        "skills": [
            {"id": "root", "atLevel": 1, "maxRank": 2, "effect": {"power": 1}},
            {
                "id": "branch",
                "atLevel": 2,
                "prerequisites": [{"id": "root", "rank": 2}],
                "effect": {"power": 2},
            },
        ],
    }


class SkillTreeValidatorTests(unittest.TestCase):
    def test_valid_tree_passes(self):
        errors, warnings = MODULE.validate_tree(valid_tree())
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_duplicate_and_unknown_prerequisite_fail(self):
        tree = valid_tree()
        tree["skills"].append(copy.deepcopy(tree["skills"][0]))
        tree["skills"][1]["prerequisites"] = ["missing"]
        errors, _ = MODULE.validate_tree(tree)
        self.assertTrue(any("duplicate skill id" in error for error in errors))
        self.assertTrue(any("unknown prerequisite" in error for error in errors))

    def test_prerequisite_cycle_fails(self):
        tree = valid_tree()
        tree["skills"][0]["prerequisites"] = ["branch"]
        errors, _ = MODULE.validate_tree(tree)
        self.assertTrue(any("prerequisite cycle" in error for error in errors))

    def test_rank_cost_and_prerequisite_bounds_fail(self):
        tree = valid_tree()
        tree["skills"][0]["costByRank"] = [1]
        tree["skills"][1]["prerequisites"] = [{"id": "root", "rank": 3}]
        errors, _ = MODULE.validate_tree(tree)
        self.assertTrue(any("exactly maxRank" in error for error in errors))
        self.assertTrue(any("outside 1..2" in error for error in errors))

    def test_exclusive_prerequisite_ancestor_fails(self):
        tree = valid_tree()
        tree["skills"][0]["exclusiveGroup"] = "focus"
        tree["skills"][1]["exclusiveGroup"] = "focus"
        errors, _ = MODULE.validate_tree(tree)
        self.assertTrue(any("branch is impossible" in error for error in errors))

    def test_malformed_effect_fails(self):
        tree = valid_tree()
        tree["skills"][0]["effect"] = {"bad key": float("nan")}
        errors, _ = MODULE.validate_tree(tree)
        self.assertTrue(any("invalid effect key" in error for error in errors))
        self.assertTrue(any("must be a finite number" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
