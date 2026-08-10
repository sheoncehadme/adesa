#!/usr/bin/env python3
"""Tests for tools/area_gen/gen_areas.py (stdlib unittest; pytest-compatible)."""
from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
import unittest
from pathlib import Path

GEN_PATH = Path(__file__).resolve().parent / "gen_areas.py"


def load_gen():
    spec = importlib.util.spec_from_file_location("gen_areas", GEN_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # dataclasses need the module registered before exec_module
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestGenAreas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gen = load_gen()

    def test_module_loads(self):
        self.assertTrue(hasattr(self.gen, "main"))
        self.assertTrue(hasattr(self.gen, "update_area_lst"))

    def test_wear_constants(self):
        self.assertEqual(self.gen.ITEM_WIELD, 8192)
        self.assertEqual(self.gen.ITEM_TAKE, 1)

    def test_generate_to_tmpdir(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "area"
            out.mkdir()
            lst = root / "area.lst"
            lst.write_text("$\n")  # gen_areas expects an existing list
            helps = root / "helps"
            helps.mkdir()

            old = sys.argv
            try:
                sys.argv = [
                    "gen_areas.py",
                    "--out",
                    str(out),
                    "--lst",
                    str(lst),
                    "--helps",
                    str(helps),
                    "--seed",
                    "42",
                ]
                rc = self.gen.main()
            finally:
                sys.argv = old

            self.assertIn(rc, (0, None))
            are_files = list(out.glob("*.are"))
            self.assertGreaterEqual(len(are_files), 5, f"got {len(are_files)} areas")

            sample = are_files[0].read_text(encoding="latin-1", errors="replace")
            self.assertTrue(sample.lstrip().startswith("#") or "#AREA" in sample.upper())
            self.assertRegex(sample, r"#(MOBILES|OBJECTS|ROOMS|RESETS)")

            self.assertTrue(lst.exists())
            self.assertIn(".are", lst.read_text(encoding="utf-8", errors="replace"))

    def test_deterministic_seed(self):
        def run(seed: str, dest: Path):
            dest.mkdir(parents=True, exist_ok=True)
            area = dest / "area"
            area.mkdir(exist_ok=True)
            lst = dest / "area.lst"
            lst.write_text("$\n")
            helps = dest / "helps"
            helps.mkdir(exist_ok=True)
            old = sys.argv
            try:
                sys.argv = [
                    "gen_areas.py",
                    "--out",
                    str(area),
                    "--lst",
                    str(lst),
                    "--helps",
                    str(helps),
                    "--seed",
                    seed,
                ]
                self.gen.main()
            finally:
                sys.argv = old
            files = sorted(area.glob("*.are"))
            return [(p.name, p.read_bytes()) for p in files]

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a = run("99", root / "a")
            b = run("99", root / "b")
            self.assertEqual([n for n, _ in a], [n for n, _ in b])
            self.assertEqual([d for _, d in a], [d for _, d in b])


if __name__ == "__main__":
    unittest.main()
