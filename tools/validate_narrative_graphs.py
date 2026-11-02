#!/usr/bin/env python3
"""Validate staged quest and branching dialogue content before runtime.

The component graph proves that narrative owners exist and can be wired. This
validator answers a different question: can the supplied content actually be
traversed, completed, restored, and connected without dangling quest actions?

Quest files use *.quest.json and contain {"quests": [...]}. Dialogue files use
*.dialogue.json and contain {"dialogueGraphs": {...}}. Stage cycles, dangling
transitions, unreachable quest stages, missing completion terminals, malformed
conditions, duplicate identifiers, and malformed rewards are content errors. Dialogue
cycles are legal because conversation hubs commonly return to an earlier node.
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
QUEST_STATES = {"locked", "offered", "active", "ready", "completed", "failed"}
QUEST_ACTIONS = {"offer", "accept", "credit", "advance", "fail", "turnIn"}
GRANT_KINDS = {"currency", "xp", "item"}


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _integer(value, minimum=0) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _valid_id(value) -> bool:
    return isinstance(value, str) and bool(ID_PATTERN.match(value))


def _condition(condition, label, errors, known_quests=None, local_objectives=None):
    if not isinstance(condition, dict):
        errors.append(f"{label}: condition must be an object")
        return
    operators = [key for key in ("all", "any", "not", "flag", "quest", "objective", "attribute") if key in condition]
    if len(operators) != 1:
        errors.append(f"{label}: condition must declare exactly one supported operator")
        return
    operator = operators[0]
    if operator in ("all", "any"):
        children = condition[operator]
        if not isinstance(children, list) or not children:
            errors.append(f"{label}: {operator} must be a non-empty condition array")
            return
        for index, child in enumerate(children):
            _condition(child, f"{label}.{operator}[{index}]", errors, known_quests, local_objectives)
    elif operator == "not":
        _condition(condition[operator], f"{label}.not", errors, known_quests, local_objectives)
    elif operator == "flag":
        if not _valid_id(condition["flag"]):
            errors.append(f"{label}: flag must be a well-formed id")
        if "equals" not in condition:
            errors.append(f"{label}: flag condition requires equals")
    elif operator == "quest":
        if not _valid_id(condition["quest"]):
            errors.append(f"{label}: quest must be a well-formed id")
        elif known_quests is not None and condition["quest"] not in known_quests:
            errors.append(f"{label}: unknown quest '{condition['quest']}'")
        if condition.get("state") not in QUEST_STATES:
            errors.append(f"{label}: quest state must be one of {sorted(QUEST_STATES)}")
    elif operator == "objective":
        if local_objectives is None:
            errors.append(f"{label}: objective conditions are only valid on quest-stage transitions")
        if not _valid_id(condition["objective"]):
            errors.append(f"{label}: objective must be a well-formed id")
        elif local_objectives is not None and condition["objective"] not in local_objectives:
            errors.append(f"{label}: objective is not declared in this stage")
        if not _integer(condition.get("atLeast"), 1):
            errors.append(f"{label}: objective atLeast must be an integer >= 1")
    elif operator == "attribute":
        if not _valid_id(condition["attribute"]):
            errors.append(f"{label}: attribute must be a well-formed id")
        if not _number(condition.get("atLeast")):
            errors.append(f"{label}: attribute atLeast must be a finite number")


def _conditions(value, label, errors, known_quests=None, local_objectives=None):
    if value is None:
        return
    if not isinstance(value, list):
        errors.append(f"{label}: conditions must be an array")
        return
    for index, condition in enumerate(value):
        _condition(condition, f"{label}[{index}]", errors, known_quests, local_objectives)


def _grant(grant, label, errors):
    if not isinstance(grant, dict):
        errors.append(f"{label}: grant must be an object")
        return
    kind = grant.get("kind")
    if kind not in GRANT_KINDS:
        errors.append(f"{label}: kind must be currency, xp, or item")
    if not _number(grant.get("amount")) or grant.get("amount") <= 0:
        errors.append(f"{label}: amount must be a finite number > 0")
    if kind == "item" and not _valid_id(grant.get("itemId")):
        errors.append(f"{label}: item grants require a well-formed itemId")


def _stage_index(quests):
    return {
        quest_id: {
            stage.get("id"): {
                objective.get("id")
                for objective in stage.get("objectives", [])
                if isinstance(objective, dict)
            }
            for stage in quest.get("stages", [])
            if isinstance(stage, dict)
        }
        for quest_id, quest in quests.items()
    }


def validate_quest_document(document, source="<quests>", known_quests=None):
    """Return (errors, warnings) for one {"quests": [...]} document."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(document, dict) or not isinstance(document.get("quests"), list):
        return [f"{source}: root must be an object with a quests array"], warnings
    if not document["quests"]:
        warnings.append(f"{source}: no quests declared")

    local_ids = set()
    for quest_index, quest in enumerate(document["quests"]):
        qlabel = f"{source}:quests[{quest_index}]"
        if not isinstance(quest, dict):
            errors.append(f"{qlabel} must be an object")
            continue
        quest_id = quest.get("id")
        if not _valid_id(quest_id):
            errors.append(f"{qlabel}: id must match {ID_PATTERN.pattern}")
            continue
        if quest_id in local_ids:
            errors.append(f"{source}: duplicate quest id '{quest_id}'")
            continue
        local_ids.add(quest_id)
        qlabel = f"{source}:{quest_id}"
        if not isinstance(quest.get("title"), str) or not quest.get("title").strip():
            errors.append(f"{qlabel}: title must be a non-empty string")

        prerequisites = quest.get("prerequisites", [])
        if not isinstance(prerequisites, list):
            errors.append(f"{qlabel}: prerequisites must be an array")
            prerequisites = []
        for index, prerequisite in enumerate(prerequisites):
            plabel = f"{qlabel}:prerequisites[{index}]"
            if not isinstance(prerequisite, dict):
                errors.append(f"{plabel} must be an object")
                continue
            required = prerequisite.get("quest")
            if not _valid_id(required):
                errors.append(f"{plabel}: quest must be a well-formed id")
            elif required == quest_id:
                errors.append(f"{plabel}: a quest cannot require itself")
            elif known_quests is not None and required not in known_quests:
                errors.append(f"{plabel}: unknown quest '{required}'")
            if prerequisite.get("state") not in QUEST_STATES:
                errors.append(f"{plabel}: invalid required state")

        stages = quest.get("stages")
        if not isinstance(stages, list) or not stages:
            errors.append(f"{qlabel}: stages must be a non-empty array")
            continue
        stage_map = {}
        for stage_index, stage in enumerate(stages):
            slabel = f"{qlabel}:stages[{stage_index}]"
            if not isinstance(stage, dict):
                errors.append(f"{slabel} must be an object")
                continue
            stage_id = stage.get("id")
            if not _valid_id(stage_id):
                errors.append(f"{slabel}: id must match {ID_PATTERN.pattern}")
                continue
            if stage_id in stage_map:
                errors.append(f"{qlabel}: duplicate stage id '{stage_id}'")
                continue
            stage_map[stage_id] = stage

        if quest.get("start") not in stage_map:
            errors.append(f"{qlabel}: start must name a declared stage")

        for stage_id, stage in stage_map.items():
            slabel = f"{qlabel}:{stage_id}"
            terminal = stage.get("terminal")
            if terminal not in (None, "completed", "failed"):
                errors.append(f"{slabel}: terminal must be completed or failed when present")
            objectives = stage.get("objectives", [])
            if not isinstance(objectives, list):
                errors.append(f"{slabel}: objectives must be an array")
                objectives = []
            objective_ids = set()
            for objective_index, objective in enumerate(objectives):
                olabel = f"{slabel}:objectives[{objective_index}]"
                if not isinstance(objective, dict):
                    errors.append(f"{olabel} must be an object")
                    continue
                objective_id = objective.get("id")
                if not _valid_id(objective_id):
                    errors.append(f"{olabel}: id must match {ID_PATTERN.pattern}")
                elif objective_id in objective_ids:
                    errors.append(f"{slabel}: duplicate objective id '{objective_id}'")
                else:
                    objective_ids.add(objective_id)
                event = objective.get("event")
                if not isinstance(event, str) or "." not in event:
                    errors.append(f"{olabel}: event must be a namespaced event name")
                if not isinstance(objective.get("match", {}), dict):
                    errors.append(f"{olabel}: match must be an object of payload equality checks")
                if not _integer(objective.get("target", 1), 1):
                    errors.append(f"{olabel}: target must be an integer >= 1")
                if not isinstance(objective.get("optional", False), bool):
                    errors.append(f"{olabel}: optional must be boolean")
                if "amountFrom" in objective and not _valid_id(objective["amountFrom"]):
                    errors.append(f"{olabel}: amountFrom must name a payload field")
                if "dedupeBy" in objective and not _valid_id(objective["dedupeBy"]):
                    errors.append(f"{olabel}: dedupeBy must name a payload field")

            transitions = stage.get("transitions", [])
            if not isinstance(transitions, list):
                errors.append(f"{slabel}: transitions must be an array")
                transitions = []
            if terminal and transitions:
                errors.append(f"{slabel}: terminal stages cannot declare transitions")
            if not terminal and not transitions:
                errors.append(f"{slabel}: nonterminal stage has no transition and cannot advance")
            for transition_index, transition in enumerate(transitions):
                tlabel = f"{slabel}:transitions[{transition_index}]"
                if not isinstance(transition, dict):
                    errors.append(f"{tlabel} must be an object")
                    continue
                target = transition.get("to")
                if target not in stage_map:
                    errors.append(f"{tlabel}: unknown destination '{target}'")
                elif target == stage_id:
                    errors.append(f"{tlabel}: self-transitions are not allowed")
                _conditions(transition.get("conditions"), tlabel + ":conditions", errors, known_quests, objective_ids)

        # Stage cycles are prohibited: replay belongs to a new quest instance,
        # not to a loop that can repeatedly enter completion or failure logic.
        visiting, visited, reported = set(), set(), set()

        def visit(stage_id, trail):
            if stage_id in visiting:
                cycle = frozenset(trail[trail.index(stage_id):])
                if cycle not in reported:
                    errors.append(f"{qlabel}: stage cycle contains {', '.join(sorted(cycle))}")
                    reported.add(cycle)
                return
            if stage_id in visited or stage_id not in stage_map:
                return
            visiting.add(stage_id)
            for transition in stage_map[stage_id].get("transitions", []):
                if isinstance(transition, dict):
                    visit(transition.get("to"), trail + [stage_id])
            visiting.remove(stage_id)
            visited.add(stage_id)

        for stage_id in stage_map:
            visit(stage_id, [])

        reachable = set()
        frontier = [quest.get("start")]
        while frontier:
            stage_id = frontier.pop()
            if stage_id in reachable or stage_id not in stage_map:
                continue
            reachable.add(stage_id)
            frontier.extend(
                transition.get("to")
                for transition in stage_map[stage_id].get("transitions", [])
                if isinstance(transition, dict)
            )
        for stage_id in sorted(set(stage_map) - reachable):
            errors.append(f"{qlabel}: stage '{stage_id}' is unreachable from start")
        if not any(stage_map[s].get("terminal") == "completed" for s in reachable):
            errors.append(f"{qlabel}: no reachable completed terminal")

        rewards = quest.get("rewards", [])
        if not isinstance(rewards, list):
            errors.append(f"{qlabel}: rewards must be an array")
        else:
            for reward_index, reward in enumerate(rewards):
                _grant(reward, f"{qlabel}:rewards[{reward_index}]", errors)

    return errors, warnings


def _consequence(consequence, label, errors, known_quests=None, stages=None):
    if not isinstance(consequence, dict):
        errors.append(f"{label}: consequence must be an object")
        return
    kind = consequence.get("type")
    if kind == "setFlag":
        if not _valid_id(consequence.get("flag")):
            errors.append(f"{label}: setFlag requires a well-formed flag")
        if "value" not in consequence:
            errors.append(f"{label}: setFlag requires value")
    elif kind == "journal":
        if not isinstance(consequence.get("entry"), str) or not consequence.get("entry").strip():
            errors.append(f"{label}: journal requires a non-empty entry")
        if "thread" in consequence and not _valid_id(consequence["thread"]):
            errors.append(f"{label}: journal thread must be a well-formed id")
    elif kind == "quest":
        action = consequence.get("action")
        if action not in QUEST_ACTIONS:
            errors.append(f"{label}: unsupported quest action '{action}'")
        quest_id = consequence.get("quest")
        if not _valid_id(quest_id):
            errors.append(f"{label}: quest action requires a well-formed quest id")
        elif known_quests is not None and quest_id not in known_quests:
            errors.append(f"{label}: unknown quest '{quest_id}'")
        if action == "credit":
            stage_id = consequence.get("stage")
            objective_id = consequence.get("objective")
            if not _valid_id(stage_id) or not _valid_id(objective_id):
                errors.append(f"{label}: credit requires stage and objective ids")
            elif stages is not None and quest_id in stages:
                if stage_id not in stages[quest_id]:
                    errors.append(f"{label}: unknown stage '{stage_id}' for quest '{quest_id}'")
                elif objective_id not in stages[quest_id][stage_id]:
                    errors.append(f"{label}: objective '{objective_id}' is not in stage '{stage_id}'")
        elif action == "advance":
            stage_id = consequence.get("stage")
            if not _valid_id(stage_id):
                errors.append(f"{label}: advance requires a stage id")
            elif stages is not None and quest_id in stages and stage_id not in stages[quest_id]:
                errors.append(f"{label}: unknown stage '{stage_id}' for quest '{quest_id}'")
        elif "stage" in consequence or "objective" in consequence:
            errors.append(f"{label}: stage/objective fields are only valid for credit or advance")
        if "amount" in consequence and (not _integer(consequence["amount"], 1)):
            errors.append(f"{label}: quest credit amount must be an integer >= 1")
    else:
        errors.append(f"{label}: type must be setFlag, quest, or journal")


def _consequences(value, label, errors, known_quests=None, stages=None):
    if value is None:
        return
    if not isinstance(value, list):
        errors.append(f"{label}: consequences must be an array")
        return
    for index, consequence in enumerate(value):
        _consequence(consequence, f"{label}[{index}]", errors, known_quests, stages)


def validate_dialogue_document(document, source="<dialogue>", known_quests=None, stages=None):
    """Return (errors, warnings) for one {"dialogueGraphs": {...}} document."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(document, dict) or not isinstance(document.get("dialogueGraphs"), dict):
        return [f"{source}: root must be an object with dialogueGraphs"], warnings
    graphs = document["dialogueGraphs"]
    if not graphs:
        warnings.append(f"{source}: no dialogue graphs declared")

    for graph_id, graph in graphs.items():
        glabel = f"{source}:{graph_id}"
        if not _valid_id(graph_id):
            errors.append(f"{glabel}: graph id must match {ID_PATTERN.pattern}")
        if not isinstance(graph, dict):
            errors.append(f"{glabel}: graph must be an object")
            continue
        nodes = graph.get("nodes")
        if not isinstance(nodes, dict) or not nodes:
            errors.append(f"{glabel}: nodes must be a non-empty object")
            continue
        if graph.get("start") not in nodes:
            errors.append(f"{glabel}: start must name a declared node")

        for node_id, node in nodes.items():
            nlabel = f"{glabel}:{node_id}"
            if not _valid_id(node_id):
                errors.append(f"{nlabel}: invalid node id")
            if not isinstance(node, dict):
                errors.append(f"{nlabel}: node must be an object")
                continue
            if not isinstance(node.get("text"), str) or not node.get("text").strip():
                errors.append(f"{nlabel}: text must be a non-empty string")
            _consequences(node.get("onEnter"), nlabel + ":onEnter", errors, known_quests, stages)
            choices = node.get("choices")
            if not isinstance(choices, list) or not choices:
                errors.append(f"{nlabel}: choices must be a non-empty array so Dialogue Box can close the node")
                continue
            choice_ids = set()
            for choice_index, choice in enumerate(choices):
                clabel = f"{nlabel}:choices[{choice_index}]"
                if not isinstance(choice, dict):
                    errors.append(f"{clabel} must be an object")
                    continue
                choice_id = choice.get("id")
                if not _valid_id(choice_id):
                    errors.append(f"{clabel}: extended choices require a stable well-formed id")
                elif choice_id in choice_ids:
                    errors.append(f"{nlabel}: duplicate choice id '{choice_id}'")
                else:
                    choice_ids.add(choice_id)
                if not isinstance(choice.get("label"), str) or not choice.get("label").strip():
                    errors.append(f"{clabel}: label must be a non-empty string")
                if not isinstance(choice.get("once", False), bool):
                    errors.append(f"{clabel}: once must be boolean")
                _conditions(choice.get("conditions"), clabel + ":conditions", errors, known_quests)
                _consequences(choice.get("consequences"), clabel + ":consequences", errors, known_quests, stages)

                has_to = "to" in choice
                has_check = "check" in choice
                if has_to == has_check:
                    errors.append(f"{clabel}: declare exactly one of to or check")
                if has_to and choice["to"] is not None and choice["to"] not in nodes:
                    errors.append(f"{clabel}: unknown destination '{choice['to']}'")
                if has_check:
                    check = choice["check"]
                    if not isinstance(check, dict):
                        errors.append(f"{clabel}: check must be an object")
                        continue
                    if not _valid_id(check.get("attribute")):
                        errors.append(f"{clabel}: check requires a well-formed attribute")
                    if not _number(check.get("difficulty", 10)) or check.get("difficulty", 10) < 0:
                        errors.append(f"{clabel}: check difficulty must be a finite number >= 0")
                    for outcome in ("onPass", "onFail"):
                        if outcome not in check:
                            errors.append(f"{clabel}: check requires {outcome}")
                        elif check[outcome] is not None and check[outcome] not in nodes:
                            errors.append(f"{clabel}: unknown {outcome} destination '{check[outcome]}'")

        reachable = set()
        frontier = [graph.get("start")]
        while frontier:
            node_id = frontier.pop()
            if node_id in reachable or node_id not in nodes or not isinstance(nodes[node_id], dict):
                continue
            reachable.add(node_id)
            for choice in nodes[node_id].get("choices", []):
                if not isinstance(choice, dict):
                    continue
                if "to" in choice:
                    frontier.append(choice["to"])
                if isinstance(choice.get("check"), dict):
                    frontier.extend([choice["check"].get("onPass"), choice["check"].get("onFail")])
        for node_id in sorted(set(nodes) - reachable):
            warnings.append(f"{glabel}: node '{node_id}' is unreachable from start")

    return errors, warnings


def validate_bundle(quest_documents, dialogue_documents):
    """Validate parsed (source, document) pairs together, including cross-links."""
    errors: list[str] = []
    warnings: list[str] = []
    quests = {}
    for source, document in quest_documents:
        if isinstance(document, dict) and isinstance(document.get("quests"), list):
            for quest in document["quests"]:
                if not isinstance(quest, dict) or not _valid_id(quest.get("id")):
                    continue
                quest_id = quest["id"]
                if quest_id in quests:
                    errors.append(f"{source}: duplicate quest id '{quest_id}' across bundle")
                else:
                    quests[quest_id] = quest
    known_quests = set(quests)
    stages = _stage_index(quests)

    for source, document in quest_documents:
        found, cautions = validate_quest_document(document, source, known_quests)
        errors.extend(found)
        warnings.extend(cautions)
    for source, document in dialogue_documents:
        found, cautions = validate_dialogue_document(document, source, known_quests, stages)
        errors.extend(found)
        warnings.extend(cautions)

    # Quest prerequisite cycles span files, so check them only after the bundle
    # has been assembled rather than declaring cross-file prerequisites valid.
    visiting, visited, reported = set(), set(), set()

    def visit(quest_id, trail):
        if quest_id in visiting:
            cycle = frozenset(trail[trail.index(quest_id):])
            if cycle not in reported:
                errors.append(f"quest prerequisite cycle contains {', '.join(sorted(cycle))}")
                reported.add(cycle)
            return
        if quest_id in visited or quest_id not in quests:
            return
        visiting.add(quest_id)
        for prerequisite in quests[quest_id].get("prerequisites", []):
            if isinstance(prerequisite, dict):
                visit(prerequisite.get("quest"), trail + [quest_id])
        visiting.remove(quest_id)
        visited.add(quest_id)

    for quest_id in quests:
        visit(quest_id, [])
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="narrative JSON files or directories")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    inputs = args.paths or [ROOT / "examples" / "quest-dialogue"]
    paths: list[Path] = []
    for path in inputs:
        if path.is_dir():
            paths.extend(sorted(path.rglob("*.quest.json")))
            paths.extend(sorted(path.rglob("*.dialogue.json")))
        else:
            paths.append(path)
    if not paths:
        print("validate_narrative_graphs: FAIL (no narrative files found)")
        return 1

    quest_documents = []
    dialogue_documents = []
    errors: list[str] = []
    for path in paths:
        source = str(path.relative_to(ROOT)) if path.is_absolute() and ROOT in path.parents else str(path)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{source}: unreadable ({exc})")
            continue
        if path.name.endswith(".quest.json"):
            quest_documents.append((source, document))
        elif path.name.endswith(".dialogue.json"):
            dialogue_documents.append((source, document))
        else:
            errors.append(f"{source}: expected *.quest.json or *.dialogue.json")

    found, warnings = validate_bundle(quest_documents, dialogue_documents)
    errors.extend(found)
    quest_count = sum(len(doc.get("quests", [])) for _, doc in quest_documents if isinstance(doc, dict))
    dialogue_count = sum(len(doc.get("dialogueGraphs", {})) for _, doc in dialogue_documents if isinstance(doc, dict))
    node_count = sum(
        len(graph.get("nodes", {}))
        for _, doc in dialogue_documents if isinstance(doc, dict)
        for graph in doc.get("dialogueGraphs", {}).values() if isinstance(graph, dict)
    )
    report = {
        "status": "PASS" if not errors else "FAIL",
        "questCount": quest_count,
        "dialogueCount": dialogue_count,
        "nodeCount": node_count,
        "warnings": warnings,
        "errors": errors,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"validate_narrative_graphs: {report['status']} "
        f"({quest_count} quests, {dialogue_count} dialogues, {node_count} nodes, "
        f"{len(errors)} errors, {len(warnings)} warnings)"
    )
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
