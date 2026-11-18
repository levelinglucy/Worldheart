"""Regressions for observer journals and fossils on unsafe paths.

Only synthetic events and fossils in disposable directories; no user world is loaded.
"""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "worldheart_v02_1.py"
loader = importlib.machinery.SourceFileLoader("worldheart_journal_paths", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
worldheart = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = worldheart
loader.exec_module(worldheart)


class JournalPathTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="worldheart-journal-")
        previous_cwd = os.getcwd()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(os.chdir, previous_cwd)
        os.chdir(self.temp.name)
        self.folder = Path(worldheart.SAVE_DIR)
        self.folder.mkdir()

    def test_regular_journal_still_appends_parseable_events(self):
        world = worldheart.World(seed=901)
        world.event("TEST_EVENT", {"value": 3})
        journal = self.folder / worldheart.EVENT_FILE
        records = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([record["kind"] for record in records], ["GENESIS", "TEST_EVENT"])
        self.assertEqual(records[-1]["data"], {"value": 3})

    def test_journal_symlink_does_not_modify_other_file(self):
        target = Path(self.temp.name) / "untouched.txt"
        target.write_text("PROTECTED\\n", encoding="utf-8")
        journal = self.folder / worldheart.EVENT_FILE
        try:
            journal.symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("symlinks unavailable: %s" % exc)

        world = worldheart.World(seed=902)
        world.event("TEST_EVENT", {"value": 3})
        self.assertEqual(target.read_text(encoding="utf-8"), "PROTECTED\\n")
        self.assertTrue(journal.is_symlink())
        self.assertEqual([record["kind"] for record in world.events],
                         ["GENESIS", "TEST_EVENT"])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO creation unavailable")
    def test_fifo_event_journal_cannot_block_world_startup(self):
        journal = self.folder / worldheart.EVENT_FILE
        try:
            os.mkfifo(str(journal))
        except OSError as exc:
            self.skipTest("FIFO unavailable: %s" % exc)

        script = (
            "import importlib.machinery, importlib.util, sys; "
            "p = " + repr(str(SOURCE)) + "; "
            "loader = importlib.machinery.SourceFileLoader('wh_journal_subproc', p); "
            "spec = importlib.util.spec_from_loader(loader.name, loader); "
            "m = importlib.util.module_from_spec(spec); "
            "sys.modules[loader.name] = m; loader.exec_module(m); "
            "w = m.World(seed=903); "
            "assert w.events[-1]['kind'] == 'GENESIS'; "
            "print('ok')"
        )
        try:
            finished = subprocess.run(
                [sys.executable, "-c", script], cwd=self.temp.name,
                text=True, capture_output=True, timeout=8, check=False
            )
        except subprocess.TimeoutExpired:
            self.fail("world startup blocked on FIFO event journal")
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("ok", finished.stdout)
        self.assertTrue(journal.is_fifo())


    @unittest.skipUnless(hasattr(os, "link"), "hard links unavailable")
    def test_hardlinked_journal_does_not_modify_protected_history(self):
        # A hard link shares an inode: appending journal events would mutate
        # any other historical file bearing that inode, even without symlinks.
        protected = Path(self.temp.name) / "protected-history.txt"
        before = b"ORIGINAL HISTORY\\n"
        protected.write_bytes(before)
        journal = self.folder / worldheart.EVENT_FILE
        try:
            os.link(protected, journal)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("hard link unavailable: %s" % exc)
        original_inode = protected.stat().st_ino

        world = worldheart.World(seed=906)
        world.event("TEST_EVENT", {"value": 42})
        self.assertEqual(protected.read_bytes(), before)
        self.assertEqual(journal.read_bytes(), before)
        self.assertEqual(protected.stat().st_ino, original_inode)
        self.assertEqual(journal.stat().st_ino, original_inode)
        self.assertEqual([entry["kind"] for entry in world.events],
                         ["GENESIS", "TEST_EVENT"])

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_symlinked_save_directory_does_not_modify_external_journal(self):
        # O_NOFOLLOW applies to the final journal path component, not its
        # parent. A redirected save directory must not append to another
        # location's otherwise regular, single-linked historical journal.
        external = Path(self.temp.name) / "protected-external-directory"
        external.mkdir()
        external_journal = external / worldheart.EVENT_FILE
        before = b"EXTERNAL HISTORY\\n"
        external_journal.write_bytes(before)
        self.folder.rmdir()
        try:
            self.folder.symlink_to(external, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("directory symlinks unavailable: %s" % exc)

        world = worldheart.World(seed=907)
        world.event("TEST_EVENT", {"value": 42})
        self.assertEqual(external_journal.read_bytes(), before)
        self.assertTrue(self.folder.is_symlink())
        self.assertEqual([entry["kind"] for entry in world.events],
                         ["GENESIS", "TEST_EVENT"])

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_symlinked_ancestor_does_not_modify_external_journal(self):
        # SAVE_DIR itself is a real directory, but one of the components
        # leading to it redirects to an independent historical location.
        external_parent = Path(self.temp.name) / "protected-external-parent"
        real_save = external_parent / "actual-save"
        real_save.mkdir(parents=True)
        external_journal = real_save / worldheart.EVENT_FILE
        before = b"PROTECTED ANCESTOR HISTORY\\n"
        external_journal.write_bytes(before)

        alias_parent = Path(self.temp.name) / "redirecting-parent"
        try:
            alias_parent.symlink_to(external_parent, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("directory symlinks unavailable: %s" % exc)
        redirected_save = alias_parent / "actual-save"
        self.assertFalse(os.path.islink(redirected_save))
        self.assertTrue(os.path.islink(alias_parent))

        with mock.patch.object(worldheart, "SAVE_DIR", str(redirected_save)):
            world = worldheart.World(seed=908)
            world.event("TEST_EVENT", {"value": 42})

        self.assertEqual(external_journal.read_bytes(), before)
        self.assertEqual([entry["kind"] for entry in world.events],
                         ["GENESIS", "TEST_EVENT"])

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_symlinked_ancestor_does_not_publish_fossil_outside_save_dir(self):
        # A fossil is an observer artifact too. A redirected ancestor must
        # not create new names in a separate historical directory.
        external_parent = Path(self.temp.name) / "fossil-protected-parent"
        real_save = external_parent / "real-save"
        real_save.mkdir(parents=True)
        protected = real_save / "protected-history.txt"
        protected.write_bytes(b"PRESERVE ORIGINAL\\n")
        alias_parent = Path(self.temp.name) / "fossil-redirect-parent"
        try:
            alias_parent.symlink_to(external_parent, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("directory symlinks unavailable: %s" % exc)
        redirected = alias_parent / "real-save"
        before_names = sorted(p.name for p in real_save.iterdir())

        with mock.patch.object(worldheart, "SAVE_DIR", str(redirected)):
            world = worldheart.World(seed=909)
            world.preserve_fossil(["synthetic anomaly"], {"marker": 1})

        self.assertEqual(sorted(p.name for p in real_save.iterdir()), before_names)
        self.assertEqual(protected.read_bytes(), b"PRESERVE ORIGINAL\\n")
        self.assertEqual(len(world.fossils), 1)
        self.assertIn("ANOMALY", [entry["kind"] for entry in world.events])

    def test_missing_os_guard_keeps_memory_and_skips_disk_journal(self):
        world = worldheart.World(seed=904)
        journal = self.folder / worldheart.EVENT_FILE
        before = journal.read_bytes()
        with mock.patch.object(worldheart.os, "O_NOFOLLOW", None):
            world.event("SKIPPED_TO_DISK", {"why": "unsafe platform"})
        self.assertEqual(journal.read_bytes(), before)
        self.assertEqual(world.events[-1]["kind"], "SKIPPED_TO_DISK")

    @unittest.skipUnless(hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK"),
                         "nonblocking FIFO support unavailable")
    def test_fifo_with_reader_does_not_receive_event_bytes(self):
        journal = self.folder / worldheart.EVENT_FILE
        try:
            os.mkfifo(str(journal))
        except OSError as exc:
            self.skipTest("FIFO unavailable: %s" % exc)
        reader_fd = os.open(str(journal), os.O_RDONLY | os.O_NONBLOCK)
        try:
            world = worldheart.World(seed=905)
            self.assertEqual(world.events[-1]["kind"], "GENESIS")
            self.assertEqual(os.read(reader_fd, 4096), b"")
        finally:
            os.close(reader_fd)


if __name__ == "__main__":
    unittest.main()
