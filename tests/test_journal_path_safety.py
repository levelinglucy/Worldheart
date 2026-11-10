"""Regressions for observer event journals named as unsafe filesystem objects.

Only synthetic events in disposable working directories; no user world is loaded.
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
