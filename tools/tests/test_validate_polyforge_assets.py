from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("validate_polyforge_assets", ROOT / "tools" / "validate_polyforge_assets.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PolyforgeAssetValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="polyforge-validator-test-")
        cls.source = ROOT / "examples" / "polyforge-asset-core" / "wayfinder.forge.json"
        result = subprocess.run(
            ["node", str(ROOT / "tools" / "polyforge_asset_pipeline.mjs"), "bake", "--source", str(cls.source), "--output-dir", cls.temporary.name],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=120,
        )
        if result.returncode:
            raise RuntimeError(result.stderr or result.stdout)
        cls.descriptor = json.loads((Path(cls.temporary.name) / "prop.wayfinder.asset.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_duplicate_topology_ids_are_rejected(self) -> None:
        document = json.loads(self.source.read_text(encoding="utf-8"))
        schema = json.loads((ROOT / "art" / "forge.schema.json").read_text(encoding="utf-8"))
        document["vertices"][1]["id"] = document["vertices"][0]["id"]
        errors = MODULE.check_document_shape(document, schema, "duplicate.forge.json")
        self.assertTrue(any("duplicate ids" in error for error in errors))

    def test_rising_lod_budgets_are_rejected(self) -> None:
        document = json.loads(self.source.read_text(encoding="utf-8"))
        schema = json.loads((ROOT / "art" / "forge.schema.json").read_text(encoding="utf-8"))
        document["budgets"]["levels"][2]["maxTriangles"] = document["budgets"]["levels"][1]["maxTriangles"] + 1
        errors = MODULE.check_document_shape(document, schema, "budget.forge.json")
        self.assertTrue(any("non-increasing" in error for error in errors))

    def test_independent_glb_readback_counts_real_indices_and_bytes(self) -> None:
        level = self.descriptor["levels"][0]
        measured = MODULE.check_glb(Path(self.temporary.name) / level["file"])
        self.assertEqual(measured["triangles"], level["triangles"])
        self.assertEqual(measured["bytes"], level["bytes"])
        self.assertEqual(measured["sockets"], ["attachment"])

    def test_glb_readback_rejects_a_bad_magic(self) -> None:
        level = self.descriptor["levels"][0]
        data = bytearray((Path(self.temporary.name) / level["file"]).read_bytes())
        data[0] = 0
        target = Path(self.temporary.name) / "corrupt.glb"
        target.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "header"):
            MODULE.check_glb(target)


if __name__ == "__main__":
    unittest.main()
