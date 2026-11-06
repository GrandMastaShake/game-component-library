from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "validate_polyforge_geometry_graphs",
    ROOT / "tools" / "validate_polyforge_geometry_graphs.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PolyforgeGeometryGraphValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = json.loads(
            (ROOT / "examples" / "polyforge-geometry-graph" / "wayfinder-relay.graph.json").read_text(encoding="utf-8")
        )
        self.schema = json.loads((ROOT / "art" / "geometry-graph.schema.json").read_text(encoding="utf-8"))

    def errors(self, graph: dict) -> list[str]:
        return MODULE.check_graph_shape(graph, self.schema, "test.graph.json")

    def test_original_example_has_coherent_typed_dag(self) -> None:
        self.assertEqual(self.errors(self.graph), [])

    def test_cycle_is_rejected(self) -> None:
        graph = copy.deepcopy(self.graph)
        graph["links"][1]["from"] = {"node": "n000004", "socket": "asset"}
        self.assertTrue(any("cycle" in error for error in self.errors(graph)))

    def test_type_mismatch_is_rejected(self) -> None:
        graph = copy.deepcopy(self.graph)
        graph["links"][6]["from"] = {"node": "n000006", "socket": "stats"}
        self.assertTrue(any("connects stats to asset" in error for error in self.errors(graph)))

    def test_multiple_inbound_links_are_rejected(self) -> None:
        graph = copy.deepcopy(self.graph)
        duplicate = copy.deepcopy(graph["links"][0])
        duplicate["id"] = "l000099"
        graph["links"].append(duplicate)
        self.assertTrue(any("multiple inbound" in error for error in self.errors(graph)))

    def test_unknown_node_type_and_duplicate_ids_are_rejected(self) -> None:
        graph = copy.deepcopy(self.graph)
        graph["nodes"][0]["type"] = "unknown.node"
        self.assertTrue(any("unknown node type" in error for error in self.errors(graph)))
        graph = copy.deepcopy(self.graph)
        graph["nodes"][1]["id"] = graph["nodes"][0]["id"]
        self.assertTrue(any("duplicate ids" in error for error in self.errors(graph)))


if __name__ == "__main__":
    unittest.main()
