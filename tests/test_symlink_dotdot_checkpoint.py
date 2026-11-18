"""Regression: a symlink followed by '..' must not evade checkpoint path checks.

All checkpoint bytes are generated inside a disposable temporary directory.
"""

import importlib.machinery
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "worldheart_v02_1.py"
loader = importlib.machinery.SourceFileLoader("worldheart_dotdot_path_probe", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
worldheart = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = worldheart
loader.exec_module(worldheart)


@unittest.skipUnless(hasattr(os, "symlink"), "directory symlinks unavailable")
class SymlinkDotDotCheckpointPath(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="worldheart-dotdot-path-")
        self.addCleanup(self.temp.cleanup)
        original_cwd = os.getcwd()
        self.addCleanup(os.chdir, original_cwd)
        os.chdir(self.temp.name)

        root = Path(self.temp.name)
        work = root / "work"
        work.mkdir()
        protected = root / "protected"
        nested = protected / "nested"
        nested.mkdir(parents=True)
        self.target = protected / "checkpoint.wh"
        worldheart.World(seed=9901).save(str(self.target))
        self.before = self.target.read_bytes()

        link = work / "redirect"
        try:
            link.symlink_to(nested, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("directory symlinks unsupported: %s" % exc)
        # Filesystem resolution follows redirect -> protected/nested *before*
        # processing '..', whereas abspath() erases redirect/.. lexically.
        self.redirected = work / "redirect" / ".." / self.target.name
        self.new_named = work / "redirect" / ".." / "new_named.wh"
        self.assertTrue(self.redirected.exists())
        self.assertFalse((work / self.target.name).exists())

    def test_reject_redirected_checkpoint_load(self):
        with self.assertRaisesRegex(OSError, "Unsafe checkpoint path"):
            worldheart.World.load(str(self.redirected))
        self.assertEqual(self.target.read_bytes(), self.before)

    def test_reject_redirected_rolling_save(self):
        with self.assertRaisesRegex(OSError, "Unsafe checkpoint path"):
            worldheart.World(seed=9902).save(str(self.redirected))
        self.assertEqual(self.target.read_bytes(), self.before)
        self.assertFalse(Path(str(self.target) + ".tmp").exists())

    def test_reject_redirected_named_save(self):
        with self.assertRaisesRegex(OSError, "Unsafe checkpoint path"):
            worldheart.World(seed=9903).save(str(self.new_named), replace_existing=False)
        self.assertFalse((self.target.parent / "new_named.wh").exists())
        self.assertEqual(self.target.read_bytes(), self.before)


    def test_reject_redirected_relative_paths(self):
        # Resolution of '..' happens after following the directory alias.
        os.chdir(Path(self.temp.name) / "work")
        with self.assertRaisesRegex(OSError, "Unsafe checkpoint path"):
            worldheart.World.load("redirect/../checkpoint.wh")
        with self.assertRaisesRegex(OSError, "Unsafe checkpoint path"):
            worldheart.World(seed=9910).save("redirect/../checkpoint.wh")
        with self.assertRaisesRegex(OSError, "Unsafe checkpoint path"):
            worldheart.World(seed=9911).save(
                "redirect/../new_named.wh", replace_existing=False
            )
        self.assertEqual(self.target.read_bytes(), self.before)
        self.assertFalse(Path(str(self.target) + ".tmp").exists())
        self.assertFalse((self.target.parent / "new_named.wh").exists())

    def test_plain_relative_dotdot_still_loads_and_saves(self):
        # Lexical '..' alone is ordinary, not evidence of a symlink.
        os.chdir(Path(self.temp.name) / "work")
        restored = worldheart.World.load("../protected/checkpoint.wh")
        self.assertEqual(restored.seed, 9901)
        self.assertEqual(self.target.read_bytes(), self.before)

        filename = "../protected/ordinary_named.wh"
        fresh = worldheart.World(seed=9912)
        fresh.save(filename, replace_existing=False)
        self.assertEqual(worldheart.World.load(filename).seed, 9912)
        self.assertEqual(self.target.read_bytes(), self.before)


if __name__ == "__main__":
    unittest.main()
