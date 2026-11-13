#!/usr/bin/env python3
"""Disposable filesystem probe for Worldheart PR #10.

This does NOT import or modify Worldheart and does NOT establish transaction
safety. Run manually: python3 experiments/checkpoint_alias_semantics_spike.py
Only synthetic temporary-directory files are touched.
"""
import os
import pathlib
import stat
import tempfile
import unittest


def target_for_safe_rolling_save(path, private_dir):
    """Stable-path policy sketch ONLY; not safe against concurrent swaps.

    Limit final-component symlink targets to direct, single-linked regular files
    inside the same trusted private checkpoint directory. No symlink-parent,
    attacker-controlled directory, power-loss or cross-platform guarantee.
    """
    root = os.path.realpath(private_dir)
    path = str(path)
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode):
        real = os.path.realpath(path)
        if os.path.dirname(real) != root:
            raise OSError("alias escapes checkpoint directory")
        target_info = os.lstat(real)
        if not stat.S_ISREG(target_info.st_mode) or target_info.st_nlink != 1:
            raise OSError("alias target is unsafe")
        return real
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise OSError("unsafe direct path")
    return path


class AliasSemanticsSpike(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(prefix="worldheart-alias-spike-")
        self.addCleanup(self.t.cleanup)
        self.root = pathlib.Path(self.t.name)
        self.original = self.root / "original.wh"
        self.original.write_bytes(b"old")
        self.alias = self.root / "latest.wh"

    def test_symlink_target_updated_without_replacing_link(self):
        self.alias.symlink_to("original.wh")
        actual = target_for_safe_rolling_save(self.alias, self.root)
        with open(self.root / "stage.tmp", "xb") as f:
            f.write(b"new")
        os.replace(self.root / "stage.tmp", actual)
        self.assertTrue(self.alias.is_symlink())
        self.assertEqual(self.alias.read_bytes(), b"new")
        self.assertEqual(self.original.read_bytes(), b"new")

    def test_hardlink_refused_for_save(self):
        os.link(self.original, self.alias)
        with self.assertRaisesRegex(OSError, "unsafe direct path"):
            target_for_safe_rolling_save(self.alias, self.root)
        self.assertEqual(self.alias.read_bytes(), b"old")
        self.assertEqual(self.original.read_bytes(), b"old")

    def test_symlink_outside_private_dir_refused(self):
        with tempfile.TemporaryDirectory() as outside:
            other = pathlib.Path(outside) / "other.wh"
            other.write_bytes(b"old")
            self.alias.symlink_to(other)
            with self.assertRaisesRegex(OSError, "escapes"):
                target_for_safe_rolling_save(self.alias, self.root)
            self.assertEqual(other.read_bytes(), b"old")

    def test_symlink_to_hardlinked_target_refused(self):
        os.link(self.original, self.root / "other_link.wh")
        self.alias.symlink_to("original.wh")
        with self.assertRaisesRegex(OSError, "target is unsafe"):
            target_for_safe_rolling_save(self.alias, self.root)

    def test_fifo_refused_without_opening(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO unavailable")
        os.mkfifo(self.alias)
        with self.assertRaisesRegex(OSError, "unsafe direct"):
            target_for_safe_rolling_save(self.alias, self.root)

    def test_dangling_symlink_refused(self):
        self.alias.symlink_to("missing.wh")
        with self.assertRaises(FileNotFoundError):
            target_for_safe_rolling_save(self.alias, self.root)

    def test_symlink_loop_refused(self):
        self.alias.symlink_to("latest.wh")
        with self.assertRaises(OSError):
            target_for_safe_rolling_save(self.alias, self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
