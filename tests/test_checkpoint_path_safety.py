"""Checkpoint path integrity regressions with only disposable synthetic worlds.

These tests never open a user's save. The FIFO reader check runs in a bounded
subprocess so a broken loader cannot stall the test suite indefinitely.
"""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "worldheart_v02_1.py"
loader = importlib.machinery.SourceFileLoader("worldheart_checkpoint_paths", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
worldheart = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = worldheart
loader.exec_module(worldheart)


class CheckpointPathSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="worldheart-checkpoint-path-")
        previous = os.getcwd()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(os.chdir, previous)
        os.chdir(self.temp.name)
        self.folder = Path(worldheart.SAVE_DIR)
        self.folder.mkdir()
        self.latest = self.folder / worldheart.SAVE_FILE

    def test_symlink_latest_is_not_read_or_replaced(self):
        world = worldheart.World(seed=9301)
        target = self.folder / "other_world.wh"
        world.save(str(target))
        original = target.read_bytes()
        try:
            self.latest.symlink_to(target.resolve())
        except (OSError, NotImplementedError) as exc:
            self.skipTest("symlinks unavailable: %s" % exc)
        journal = self.folder / worldheart.EVENT_FILE
        before_journal = journal.read_bytes()

        with self.assertRaisesRegex(OSError, "Unsafe checkpoint path"):
            worldheart.World.load(str(self.latest))
        with self.assertRaisesRegex(OSError, "Unsafe checkpoint path"):
            world.save()

        self.assertTrue(self.latest.is_symlink())
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(journal.read_bytes(), before_journal)
        self.assertFalse(Path(str(self.latest) + ".tmp").exists())

    def test_multiple_hard_links_cannot_split_checkpoint_history(self):
        world = worldheart.World(seed=9302)
        target = self.folder / "other_world.wh"
        world.save(str(target))
        original = target.read_bytes()
        try:
            os.link(str(target), str(self.latest))
        except (OSError, NotImplementedError) as exc:
            self.skipTest("hard links unavailable: %s" % exc)
        journal = self.folder / worldheart.EVENT_FILE
        before_journal = journal.read_bytes()

        with self.assertRaisesRegex(OSError, "Unsafe checkpoint path"):
            worldheart.World.load(str(self.latest))
        with self.assertRaisesRegex(OSError, "Unsafe checkpoint path"):
            world.save()

        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(self.latest.read_bytes(), original)
        self.assertEqual(journal.read_bytes(), before_journal)
        self.assertFalse(Path(str(self.latest) + ".tmp").exists())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO creation unavailable")
    def test_fifo_latest_is_not_replaced_by_save(self):
        try:
            os.mkfifo(str(self.latest))
        except OSError as exc:
            self.skipTest("FIFO unavailable: %s" % exc)
        world = worldheart.World(seed=9303)
        with self.assertRaisesRegex(OSError, "Unsafe checkpoint path"):
            world.save()
        self.assertTrue(self.latest.is_fifo())
        self.assertFalse(Path(str(self.latest) + ".tmp").exists())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO creation unavailable")
    def test_fifo_latest_cannot_block_loading(self):
        try:
            os.mkfifo(str(self.latest))
        except OSError as exc:
            self.skipTest("FIFO unavailable: %s" % exc)
        script = (
            "import importlib.machinery,importlib.util,sys;"
            "p=" + repr(str(SOURCE)) + ";"
            "loader=importlib.machinery.SourceFileLoader('wh_fifo_load',p);"
            "spec=importlib.util.spec_from_loader(loader.name,loader);"
            "m=importlib.util.module_from_spec(spec);"
            "sys.modules[loader.name]=m;loader.exec_module(m);"
            "m.World.load()"
        )
        try:
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=self.temp.name, capture_output=True, text=True,
                check=False, timeout=4
            )
        except subprocess.TimeoutExpired:
            self.fail("Loading a FIFO checkpoint blocked indefinitely")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unsafe checkpoint path", result.stderr)
        self.assertTrue(self.latest.is_fifo())


if __name__ == "__main__":
    unittest.main()
