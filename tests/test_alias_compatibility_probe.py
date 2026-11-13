"""Test-only integration of alias recovery with real Worldheart checkpoints.

The production World.load(alias)/World.save(alias) policy has NOT changed.
This prototype explicitly resolves a narrowly trusted same-directory symlink
to an ordinary single-linked checkpoint path, then calls the real World API
with that direct target. Never test against personal saves or untrusted pickle.
These fixtures cannot prove race-free or crash-durable publication.
"""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "worldheart_v02_1.py"
loader = importlib.machinery.SourceFileLoader("worldheart_alias_probe", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
worldheart = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = worldheart
loader.exec_module(worldheart)


def prototype_private_target(alias):
    """Resolve one relative, final-component symlink; stable private paths only.

    Deliberately reject absolute, parent-traversing or chained symlinks, special
    targets and multi-linked targets. This has a TOCTOU race: do NOT ship as a
    production resolver or expose it to attacker-controlled directories.
    """
    link = os.readlink(str(alias))
    if not link or link in (".", "..") or os.path.basename(link) != link:
        raise OSError("unsafe alias location")
    target = alias.parent / link
    info = os.lstat(str(target))
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise OSError("unsafe alias target")
    return target


@unittest.skipUnless(hasattr(os, "symlink"), "symbolic links unavailable")
class IntegratedAliasProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="worldheart-integrated-alias-")
        previous = os.getcwd()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(os.chdir, previous)
        os.chdir(self.tmp.name)
        self.data = Path(self.tmp.name) / worldheart.SAVE_DIR
        self.data.mkdir()
        self.target = self.data / "trusted_original.wh"
        self.latest = self.data / worldheart.SAVE_FILE

    def make_fixture(self, seed):
        world = worldheart.World(seed=seed)
        world.save(str(self.target))
        return world

    def link_latest(self, target=None):
        try:
            self.latest.symlink_to(target or self.target.name)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("symlinks unsupported here: %s" % exc)

    def test_real_world_roundtrip_via_checked_direct_target_preserves_symlink(self):
        self.make_fixture(9701)
        previous_bytes = self.target.read_bytes()
        self.link_latest()
        # The current PR explicitly refuses this API call; migration would
        # have to safely choose the target before reading and publishing.
        with self.assertRaisesRegex(OSError, "Unsafe checkpoint path"):
            worldheart.World.load(str(self.latest))
        direct = prototype_private_target(self.latest)
        restored = worldheart.World.load(str(direct))
        self.assertEqual(restored.seed, 9701)
        restored.tick += 1
        restored.save(str(direct))
        self.assertTrue(self.latest.is_symlink())
        self.assertEqual(os.readlink(str(self.latest)), self.target.name)
        self.assertEqual(self.latest.read_bytes(), self.target.read_bytes())
        self.assertNotEqual(self.target.read_bytes(), previous_bytes)
        self.assertEqual(worldheart.World.load(str(direct)).tick, 1)
        self.assertFalse(Path(str(direct) + ".tmp").exists())

    def test_stale_target_temp_blocks_actual_save_and_preserves_alias(self):
        restored = self.make_fixture(9702)
        self.link_latest()
        original = self.target.read_bytes()
        stale = Path(str(self.target) + ".tmp")
        stale.write_bytes(b"partial recovery evidence")
        with self.assertRaises(FileExistsError):
            restored.save(str(prototype_private_target(self.latest)))
        self.assertEqual(stale.read_bytes(), b"partial recovery evidence")
        self.assertEqual(self.target.read_bytes(), original)
        self.assertTrue(self.latest.is_symlink())

    def test_external_alias_is_not_resolved(self):
        self.make_fixture(9703)
        with tempfile.TemporaryDirectory(prefix="worldheart-outside-") as other:
            outside = Path(other) / "outside.wh"
            outside.write_bytes(b"external sentinel")
            self.link_latest(str(outside))
            with self.assertRaisesRegex(OSError, "unsafe alias location"):
                prototype_private_target(self.latest)
            self.assertEqual(outside.read_bytes(), b"external sentinel")

    def test_hardlinked_target_cannot_be_safely_replaced(self):
        self.make_fixture(9704)
        twin = self.data / "twin.wh"
        try:
            os.link(str(self.target), str(twin))
        except (OSError, NotImplementedError) as exc:
            self.skipTest("hard links unavailable here: %s" % exc)
        self.link_latest()
        original = self.target.read_bytes()
        with self.assertRaisesRegex(OSError, "unsafe alias target"):
            prototype_private_target(self.latest)
        with self.assertRaisesRegex(OSError, "Unsafe checkpoint path"):
            worldheart.World.load(str(self.target))
        with self.assertRaisesRegex(OSError, "Unsafe checkpoint path"):
            worldheart.World(seed=9705).save(str(self.target))
        self.assertEqual(twin.read_bytes(), original)
        self.assertEqual(self.target.read_bytes(), original)

    def test_explicit_copy_migrates_hardlink_without_splitting_original(self):
        self.make_fixture(9706)
        try:
            os.link(str(self.target), str(self.latest))
        except (OSError, NotImplementedError) as exc:
            self.skipTest("hard links unavailable here: %s" % exc)
        original = self.target.read_bytes()
        migrated = self.data / "separate_recovery.wh"
        # This is a deliberately stationary synthetic fixture. Copying a live
        # checkpoint can be inconsistent; migration needs a quiescence rule.
        shutil.copyfile(str(self.target), str(migrated))
        restored = worldheart.World.load(str(migrated))
        self.assertEqual(restored.seed, 9706)
        restored.tick += 1
        restored.save(str(migrated))
        self.assertEqual(self.target.read_bytes(), original)
        self.assertEqual(self.latest.read_bytes(), original)
        self.assertEqual(worldheart.World.load(str(migrated)).tick, 1)
        self.assertNotEqual(migrated.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
