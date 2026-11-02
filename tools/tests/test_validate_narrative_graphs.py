#!/usr/bin/env python3
import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "validate_narrative_graphs", ROOT / "tools" / "validate_narrative_graphs.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def valid_quest_document():
    return {
        "quests": [
            {
                "id": "errand",
                "title": "An Errand",
                "start": "report",
                "stages": [
                    {
                        "id": "report",
                        "objectives": [
                            {
                                "id": "reported",
                                "event": "input.questObjectiveCredited",
                                "target": 1,
                            }
                        ],
                        "terminal": "completed",
                    }
                ],
                "rewards": [{"kind": "currency", "amount": 1}],
            }
        ]
    }


def valid_dialogue_document():
    return {
        "dialogueGraphs": {
            "giver": {
                "start": "intro",
                "nodes": {
                    "intro": {
                        "text": "Will you help?",
                        "choices": [
                            {
                                "id": "accept",
                                "label": "Yes",
                                "to": None,
                                "consequences": [
                                    {"type": "quest", "action": "accept", "quest": "errand"}
                                ],
                            }
                        ],
                    }
                },
            }
        }
    }


class NarrativeGraphValidatorTests(unittest.TestCase):
    def validate(self, quests=None, dialogues=None):
        quests = [("test.quest.json", valid_quest_document())] if quests is None else quests
        dialogues = [("test.dialogue.json", valid_dialogue_document())] if dialogues is None else dialogues
        return MODULE.validate_bundle(quests, dialogues)

    def test_valid_bundle_passes(self):
        errors, warnings = self.validate()
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_duplicate_quest_and_unknown_prerequisite_fail(self):
        document = valid_quest_document()
        document["quests"].append(copy.deepcopy(document["quests"][0]))
        document["quests"][0]["prerequisites"] = [{"quest": "missing", "state": "completed"}]
        errors, _ = self.validate(quests=[("test.quest.json", document)], dialogues=[])
        self.assertTrue(any("duplicate quest id" in error for error in errors))
        self.assertTrue(any("unknown quest 'missing'" in error for error in errors))

    def test_stage_cycle_and_unreachable_stage_fail(self):
        document = {
            "quests": [
                {
                    "id": "loop",
                    "title": "Loop",
                    "start": "a",
                    "stages": [
                        {"id": "a", "transitions": [{"to": "b"}]},
                        {"id": "b", "transitions": [{"to": "a"}]},
                        {"id": "done", "terminal": "completed"},
                    ],
                }
            ]
        }
        errors, _ = self.validate(quests=[("cycle.quest.json", document)], dialogues=[])
        self.assertTrue(any("stage cycle" in error for error in errors))
        self.assertTrue(any("unreachable" in error for error in errors))
        self.assertTrue(any("no reachable completed terminal" in error for error in errors))

    def test_malformed_objective_and_reward_fail(self):
        document = valid_quest_document()
        objective = document["quests"][0]["stages"][0]["objectives"][0]
        objective["event"] = "not_namespaced"
        objective["target"] = 0
        document["quests"][0]["rewards"] = [{"kind": "item", "amount": -1}]
        errors, _ = self.validate(quests=[("bad.quest.json", document)], dialogues=[])
        self.assertTrue(any("namespaced event" in error for error in errors))
        self.assertTrue(any("target must be" in error for error in errors))
        self.assertTrue(any("amount must be" in error for error in errors))
        self.assertTrue(any("itemId" in error for error in errors))

    def test_dialogue_dead_link_and_unreachable_warning(self):
        document = valid_dialogue_document()
        nodes = document["dialogueGraphs"]["giver"]["nodes"]
        nodes["intro"]["choices"][0]["to"] = "missing"
        nodes["orphan"] = {
            "text": "Unreachable",
            "choices": [{"id": "leave", "label": "Leave", "to": None}],
        }
        errors, warnings = self.validate(dialogues=[("bad.dialogue.json", document)])
        self.assertTrue(any("unknown destination 'missing'" in error for error in errors))
        self.assertTrue(any("node 'orphan' is unreachable" in warning for warning in warnings))

    def test_cross_dialogue_quest_action_is_validated(self):
        document = valid_dialogue_document()
        consequence = document["dialogueGraphs"]["giver"]["nodes"]["intro"]["choices"][0]["consequences"][0]
        consequence.update({"action": "credit", "stage": "report", "objective": "missing"})
        errors, _ = self.validate(dialogues=[("bad.dialogue.json", document)])
        self.assertTrue(any("objective 'missing' is not in stage 'report'" in error for error in errors))
        consequence["quest"] = "unknown"
        errors, _ = self.validate(dialogues=[("bad.dialogue.json", document)])
        self.assertTrue(any("unknown quest 'unknown'" in error for error in errors))

    def test_cross_file_prerequisite_cycle_fails(self):
        first = valid_quest_document()
        second = valid_quest_document()
        second["quests"][0]["id"] = "second"
        first["quests"][0]["prerequisites"] = [{"quest": "second", "state": "completed"}]
        second["quests"][0]["prerequisites"] = [{"quest": "errand", "state": "completed"}]
        errors, _ = self.validate(
            quests=[("first.quest.json", first), ("second.quest.json", second)],
            dialogues=[],
        )
        self.assertTrue(any("quest prerequisite cycle" in error for error in errors))

    def test_malformed_condition_and_check_fail(self):
        document = valid_dialogue_document()
        choice = document["dialogueGraphs"]["giver"]["nodes"]["intro"]["choices"][0]
        choice.pop("to")
        choice["conditions"] = [{"flag": "bad flag"}]
        choice["check"] = {"attribute": "WIS", "onPass": None}
        errors, _ = self.validate(dialogues=[("bad.dialogue.json", document)])
        self.assertTrue(any("flag must be a well-formed id" in error for error in errors))
        self.assertTrue(any("requires equals" in error for error in errors))
        self.assertTrue(any("requires onFail" in error for error in errors))
        choice["conditions"] = [{"objective": "reported", "atLeast": 1}]
        errors, _ = self.validate(dialogues=[("bad.dialogue.json", document)])
        self.assertTrue(any("only valid on quest-stage transitions" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
