"""Stale checkpoint-temp preservation tests; isolated synthetic worlds only.

Never touch an existing WORLDHEART_V02_DATA directory. Each test changes
into its own disposable directory and restores the working directory.
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
    "worldheart_v02_1_temp_safety", str(ROOT / "worldheart_v02_1.py")
)
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
worldheart = importlib.util.module_from_spec(SPEC)
sys.modules[LOADER.name] = worldheart
LOADER.exec_module(worldheart)


class CheckpointTempSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous_directory = os.getcwd()
        os.chdir(self.tmp.name)
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        os.chdir(self.previous_directory)
        self.tmp.cleanup()

    def _checkpoint(self):
        return Path(worldheart.SAVE_DIR) / worldheart.SAVE_FILE

    def test_stale_temp_survives_next_save_with_existing_primary(self):
        world = worldheart.World(seed=8101)
        world.save()
        primary = self._checkpoint()
        original = primary.read_bytes()
        pending = Path(str(primary) + ".tmp")
        evidence = b'{"partial":"interrupted checkpoint bytes'
        pending.write_bytes(evidence)
        events = Path(worldheart.SAVE_DIR) / worldheart.EVENT_FILE
        event_bytes = events.read_bytes()

        with self.assertRaises(FileExistsError):
            world.save()

        self.assertEqual(primary.read_bytes(), original)
        self.assertEqual(pending.read_bytes(), evidence)
        self.assertEqual(events.read_bytes(), event_bytes)

    def test_stale_temp_survives_when_primary_is_missing(self):
        world = worldheart.World(seed=8102)
        primary = self._checkpoint()
        self.assertFalse(primary.exists())
        pending = Path(str(primary) + ".tmp")
        evidence = b'{"partial":"recoverable before first save'
        pending.write_bytes(evidence)

        with self.assertRaises(FileExistsError):
            world.save()

        self.assertFalse(primary.exists())
        self.assertEqual(pending.read_bytes(), evidence)

    def test_normal_repeated_save_and_load_still_work(self):
        world = worldheart.World(seed=8103)
        first = world.save()
        self.assertTrue(Path(first).is_file())
        world.transition()
        second = world.save()
        self.assertEqual(first, second)
        self.assertFalse(Path(str(first) + ".tmp").exists())
        recovered = worldheart.World.load(first)
        self.assertEqual(recovered.seed, world.seed)
        self.assertEqual(recovered.tick, world.tick)


if __name__ == "__main__":
    unittest.main()
