"""Protect existing named snapshots in disposable Worldheart directories.

Synthetic, locally generated worlds only. No user checkpoint is loaded.
"""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LOADER = importlib.machinery.SourceFileLoader(
    "worldheart_named_safety", str(ROOT / "worldheart_v02_1.py")
)
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
worldheart = importlib.util.module_from_spec(SPEC)
sys.modules[LOADER.name] = worldheart
LOADER.exec_module(worldheart)


class NamedSnapshotSafetyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="worldheart-named-")
        old_cwd = os.getcwd()
        os.chdir(self.directory.name)
        self.addCleanup(os.chdir, old_cwd)
        self.addCleanup(self.directory.cleanup)

    def test_existing_named_snapshot_survives_same_label_and_tick(self):
        first = worldheart.World(seed=4101)
        named = Path(first.save_named("keepsake"))
        original = named.read_bytes()

        # A different universe can start with the same label and tick.
        other = worldheart.World(seed=4102)
        journal = Path(worldheart.SAVE_DIR) / worldheart.EVENT_FILE
        before_events = journal.read_bytes()
        with self.assertRaises(FileExistsError):
            other.save_named("keepsake")
        self.assertEqual(named.read_bytes(), original)
        self.assertEqual(journal.read_bytes(), before_events)
        self.assertFalse(Path(str(named) + ".tmp").exists())
        self.assertEqual(worldheart.World.load(str(named)).seed, 4101)

    def test_existing_named_symlink_is_not_replaced(self):
        first = worldheart.World(seed=4103)
        directory = Path(worldheart.SAVE_DIR)
        directory.mkdir(exist_ok=True)
        target = Path(self.directory.name) / "original.txt"
        target.write_bytes(b"keep this outside checkpoint bytes")
        named = directory / "alias_t000000000000.wh"
        try:
            named.symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("symlinks unavailable: %s" % exc)
        with self.assertRaises(FileExistsError):
            first.save_named("alias")
        self.assertTrue(named.is_symlink())
        self.assertEqual(target.read_bytes(), b"keep this outside checkpoint bytes")
        self.assertFalse(Path(str(named) + ".tmp").exists())

    def test_different_tick_allows_distinct_named_snapshot(self):
        world = worldheart.World(seed=4104)
        first = world.save_named("keepsake")
        world.transition()
        second = world.save_named("keepsake")
        self.assertNotEqual(first, second)
        self.assertEqual(worldheart.World.load(first).tick, 0)
        self.assertEqual(worldheart.World.load(second).tick, 1)


if __name__ == "__main__":
    unittest.main()
