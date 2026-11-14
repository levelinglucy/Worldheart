"""Fault-injection checks for Worldheart's research-only offline folder copier.

These cases exercise caught Python exceptions, not sudden process death,
power loss, hostile races, or a production migration command. Every fixture
is synthetic and disposable; no pickle is opened.
"""
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from experiments import offline_world_copy_spike as copier


@unittest.skipUnless(
    hasattr(os, "link") and hasattr(os, "O_NOFOLLOW") and
    hasattr(os, "O_NONBLOCK"),
    "copy-out requires hard links and guarded file descriptors",
)
class OfflineCopyFaultTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="worldheart-copy-fault-")
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.source = self.home / "source" / copier.SAVE_DIR
        self.source.mkdir(parents=True)
        self.latest = self.source / copier.SAVE_FILE
        self.latest.write_bytes(b"original-synthetic-checkpoint")
        self.alias = self.source / "snapshot_t000000000000.wh"
        os.link(self.latest, self.alias)
        (self.source / "worldheart_v02_events.jsonl").write_bytes(
            b'{"kind":"GENESIS"}\n'
        )
        (self.source / "fossil_000000000000.json").write_bytes(b'{"tick":0}\n')
        self.destination = self.home / "prepared"
        self.destination.mkdir()
        # A pre-existing independent destination must never be removed.
        self.sentinel = self.destination / "keep-older-copy.txt"
        self.sentinel.write_bytes(b"preexisting-destination")
        self.original = {p.name: p.read_bytes() for p in self.source.iterdir()}
        self.inode = self.latest.stat().st_ino
        self.sentinel_inode = self.sentinel.stat().st_ino

    def assert_no_failed_copy_escapes(self):
        self.assertEqual(
            {p.name: p.read_bytes() for p in self.source.iterdir()},
            self.original,
        )
        self.assertEqual(self.latest.stat().st_ino, self.inode)
        self.assertEqual(self.alias.stat().st_ino, self.inode)
        self.assertEqual(
            {p.name for p in self.destination.iterdir()},
            {"keep-older-copy.txt"},
        )
        self.assertEqual(self.sentinel.read_bytes(), b"preexisting-destination")
        self.assertEqual(self.sentinel.stat().st_ino, self.sentinel_inode)

    def test_initial_source_scan_refusal_does_not_create_attempt_root(self):
        with mock.patch.object(
            copier, "_scan_regular", side_effect=OSError("injected scan refusal")
        ):
            with self.assertRaisesRegex(OSError, "injected scan refusal"):
                copier.prepare_offline_copy(self.source, self.destination)
        self.assert_no_failed_copy_escapes()

    def test_partially_written_copy_fault_removes_owned_attempt(self):
        actual_copy = copier._copy_file

        def fail_on_checkpoint(src, dst, before):
            if src.name == copier.SAVE_FILE:
                with open(dst, "xb") as partial:
                    partial.write(b"synthetic-partial-copy")
                raise OSError("injected partial copy")
            return actual_copy(src, dst, before)

        with mock.patch.object(copier, "_copy_file", side_effect=fail_on_checkpoint):
            with self.assertRaisesRegex(OSError, "injected partial copy"):
                copier.prepare_offline_copy(self.source, self.destination)
        self.assert_no_failed_copy_escapes()

    def test_partial_manifest_json_failure_removes_owned_attempt(self):
        def partial_json(_manifest, stream, **_kwargs):
            stream.write('{"copy_complete": ')
            raise OSError("injected manifest serialization")

        with mock.patch.object(copier.json, "dump", side_effect=partial_json):
            with self.assertRaisesRegex(OSError, "manifest serialization"):
                copier.prepare_offline_copy(self.source, self.destination)
        self.assert_no_failed_copy_escapes()

    def test_manifest_publication_refusal_removes_owned_attempt(self):
        def refuse_replace(stage, destination):
            self.assertEqual(Path(stage).name, "manifest.json.tmp")
            self.assertEqual(Path(destination).name, "manifest.json")
            self.assertTrue(Path(stage).is_file())
            self.assertFalse(Path(destination).exists())
            raise OSError("injected manifest publication")

        with mock.patch.object(copier.os, "replace", side_effect=refuse_replace):
            with self.assertRaisesRegex(OSError, "manifest publication"):
                copier.prepare_offline_copy(self.source, self.destination)
        self.assert_no_failed_copy_escapes()

    def test_caught_error_after_manifest_replace_removes_owned_attempt(self):
        actual_replace = os.replace

        def replace_then_error(stage, destination):
            actual_replace(stage, destination)
            self.assertTrue(Path(destination).is_file())
            self.assertFalse(Path(stage).exists())
            raise OSError("injected post-publication exception")

        with mock.patch.object(copier.os, "replace", side_effect=replace_then_error):
            with self.assertRaisesRegex(OSError, "post-publication exception"):
                copier.prepare_offline_copy(self.source, self.destination)
        self.assert_no_failed_copy_escapes()


if __name__ == "__main__":
    unittest.main()
