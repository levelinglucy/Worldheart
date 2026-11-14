"""Trusted, stationary same-directory symlink checkpoint contract (draft PR only).

All fixtures use isolated, synthetic Worldheart worlds; never load unknown pickle.
A symlink is not a security boundary against hostile concurrent directory edits.
These checks assert conservative behavior under ordinary use and injected changes.
"""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
from unittest import mock
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "worldheart_v02_1.py"
loader = importlib.machinery.SourceFileLoader("worldheart_alias_contract", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
worldheart = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = worldheart
loader.exec_module(worldheart)


@unittest.skipUnless(hasattr(os, "symlink"), "symlink support unavailable")
class TrustedCheckpointAliasContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="worldheart-alias-contract-")
        old_cwd = os.getcwd()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(os.chdir, old_cwd)
        os.chdir(self.tmp.name)
        self.data = Path(worldheart.SAVE_DIR)
        self.data.mkdir()
        self.target = self.data / "original.wh"
        self.alias = self.data / worldheart.SAVE_FILE

    def make_alias(self, seed=9801):
        w = worldheart.World(seed=seed)
        w.save(str(self.target))
        try:
            self.alias.symlink_to(self.target.name)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("symlink unavailable: %s" % exc)
        return w

    def test_world_api_resumes_and_saves_through_trusted_relative_alias(self):
        self.make_alias()
        original = self.target.read_bytes()
        resumed = worldheart.World.load()
        self.assertEqual(resumed.seed, 9801)
        resumed.tick += 1
        resumed.save()
        self.assertTrue(self.alias.is_symlink())
        self.assertEqual(os.readlink(self.alias), self.target.name)
        self.assertEqual(self.alias.read_bytes(), self.target.read_bytes())
        self.assertNotEqual(original, self.target.read_bytes())
        self.assertEqual(worldheart.World.load().tick, 1)

    def test_alias_target_must_not_be_unresolved_staging_evidence(self):
        # A valid checkpoint envelope can survive an interrupted publication
        # under *.tmp. An alias must not promote that evidence to a live
        # checkpoint and then overwrite it during a routine rolling save.
        source = self.data / "older_world.wh"
        worldheart.World(seed=9822).save(str(source))
        unresolved = self.data / "older_world.wh.tmp"
        source.rename(unresolved)
        before = unresolved.read_bytes()
        self.alias.symlink_to(unresolved.name)
        with self.assertRaisesRegex(OSError, "Unsafe checkpoint path"):
            worldheart.World.load()
        with self.assertRaisesRegex(OSError, "Unsafe checkpoint path"):
            worldheart.World(seed=9823).save()
        self.assertEqual(unresolved.read_bytes(), before)
        self.assertTrue(self.alias.is_symlink())
        self.assertEqual(os.readlink(self.alias), unresolved.name)
        self.assertFalse(Path(str(unresolved) + ".tmp").exists())

    def test_stale_target_temp_refuses_save_without_touching_history(self):
        self.make_alias(seed=9802)
        original = self.target.read_bytes()
        stale = Path(str(self.target) + ".tmp")
        stale.write_bytes(b"do not erase recovery evidence")
        with self.assertRaises(FileExistsError):
            worldheart.World(seed=9803).save()
        self.assertEqual(self.target.read_bytes(), original)
        self.assertEqual(stale.read_bytes(), b"do not erase recovery evidence")
        self.assertTrue(self.alias.is_symlink())

    def test_alias_name_temp_also_blocks_save(self):
        self.make_alias(seed=9810)
        before = self.target.read_bytes()
        stale = Path(str(self.alias) + ".tmp")
        stale.write_bytes(b"older alias temp evidence")
        with self.assertRaises(FileExistsError):
            worldheart.World(seed=9811).save()
        self.assertEqual(before, self.target.read_bytes())
        self.assertEqual(stale.read_bytes(), b"older alias temp evidence")
        self.assertFalse(Path(str(self.target) + ".tmp").exists())

    def test_alias_to_another_link_is_refused(self):
        self.make_alias(seed=9812)
        self.alias.unlink()
        middle = self.data / "middle.wh"
        middle.symlink_to(self.target.name)
        self.alias.symlink_to(middle.name)
        with self.assertRaisesRegex(OSError, "Unsafe checkpoint path"):
            worldheart.World.load()
        with self.assertRaisesRegex(OSError, "Unsafe checkpoint path"):
            worldheart.World(seed=9813).save()
        self.assertEqual(os.readlink(self.alias), middle.name)

    def test_alias_repoint_during_serialization_aborts_publication(self):
        self.make_alias(seed=9804)
        original = self.target.read_bytes()
        outsider = self.data / "other.wh"
        outsider.write_bytes(b"sentinel")
        original_dumps = worldheart.pickle.dumps

        def swap_alias(*args, **kwargs):
            payload = original_dumps(*args, **kwargs)
            self.alias.unlink()
            self.alias.symlink_to(outsider.name)
            return payload

        with mock.patch.object(worldheart.pickle, "dumps", side_effect=swap_alias):
            with self.assertRaisesRegex(OSError, "Unsafe checkpoint path"):
                worldheart.World(seed=9805).save()
        self.assertEqual(self.target.read_bytes(), original)
        self.assertEqual(outsider.read_bytes(), b"sentinel")
        self.assertTrue(self.alias.is_symlink())

    def test_dangling_relative_alias_refused_and_retained(self):
        self.alias.symlink_to("missing.wh")
        with self.assertRaises(OSError):
            worldheart.World.load()
        with self.assertRaises(OSError):
            worldheart.World(seed=9806).save()
        self.assertTrue(self.alias.is_symlink())
        self.assertEqual(os.readlink(self.alias), "missing.wh")

    def test_start_new_world_via_aliased_history_requires_separate_directory(self):
        self.make_alias(seed=9807)
        original = self.target.read_bytes()
        with mock.patch.object(worldheart, "genesis_screen"), mock.patch("builtins.input", side_effect=["n", "123"]):
            with self.assertRaises(SystemExit):
                worldheart.choose_world()
        self.assertEqual(self.target.read_bytes(), original)
        self.assertTrue(self.alias.is_symlink())


if __name__ == "__main__":
    unittest.main()
