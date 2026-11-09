"""Regression: fossils must not overwrite previous observational evidence.

Only synthetic worlds and disposable directories; no user checkpoint is loaded.
"""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LOADER = importlib.machinery.SourceFileLoader(
    "worldheart_fossil_collision", str(ROOT / "worldheart_v02_1.py")
)
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
worldheart = importlib.util.module_from_spec(SPEC)
sys.modules[LOADER.name] = worldheart
LOADER.exec_module(worldheart)


class FossilPreservationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="worldheart-fossils-")
        previous_cwd = os.getcwd()
        os.chdir(self.directory.name)
        self.addCleanup(os.chdir, previous_cwd)
        self.addCleanup(self.directory.cleanup)

    def fossil_files(self):
        return sorted(Path(worldheart.SAVE_DIR).glob("fossil_*.json"))

    def test_same_tick_different_worlds_retain_both_fossils(self):
        first = worldheart.World(seed=5271)
        first.preserve_fossil(["original-world"], first.metrics())
        base = Path(worldheart.SAVE_DIR) / "fossil_000000000000.json"
        original = base.read_bytes()

        second = worldheart.World(seed=5272)
        second.preserve_fossil(["later-world"], second.metrics())

        self.assertEqual(base.read_bytes(), original)
        files = self.fossil_files()
        self.assertEqual(len(files), 2, files)
        self.assertEqual(
            {tuple(json.loads(p.read_text(encoding="utf-8"))["reasons"]) for p in files},
            {("original-world",), ("later-world",)},
        )

    def test_existing_dangling_symlink_is_not_replaced(self):
        world = worldheart.World(seed=5273)
        base = Path(worldheart.SAVE_DIR) / "fossil_000000000000.json"
        target = Path(self.directory.name) / "missing-target.json"
        try:
            base.symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("symlinks unavailable: %s" % exc)

        world.preserve_fossil(["new-fossil"], world.metrics())
        self.assertTrue(base.is_symlink())
        self.assertFalse(target.exists())
        new_files = [p for p in self.fossil_files() if p != base]
        self.assertEqual(len(new_files), 1, new_files)
        self.assertEqual(
            json.loads(new_files[0].read_text(encoding="utf-8"))["reasons"],
            ["new-fossil"],
        )

    def test_repeated_same_tick_preserves_each_fossil(self):
        world = worldheart.World(seed=5274)
        for reason in ("first", "second", "third"):
            world.preserve_fossil([reason], world.metrics())
        files = self.fossil_files()
        self.assertEqual([p.name for p in files], [
            "fossil_000000000000.json",
            "fossil_000000000000_001.json",
            "fossil_000000000000_002.json",
        ])
        self.assertEqual(
            [json.loads(p.read_text(encoding="utf-8"))["reasons"] for p in files],
            [["first"], ["second"], ["third"]],
        )


if __name__ == "__main__":
    unittest.main()
