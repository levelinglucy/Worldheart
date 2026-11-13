#!/usr/bin/env python3
"""Stopped-world hard-link checkpoint copy-out experiment for Worldheart PR #10.

This standalone standard-library experiment never imports Worldheart or unpickles
anything. It is NOT an in-app migration or an automated repair command. It only
copies a trusted *single file* (not the journal/fossils/whole data directory)
into an existing, separate, trusted directory under a new, unused filename.

The caller must stop every writer, preserve the COMPLETE source directory and
any .tmp evidence first, and verify the new copy separately before use. The
same-directory target must not be attacker-controlled or modified concurrently.
No race-free transaction, cross-process lock, power-loss durability, device
portability, or authenticity guarantee is claimed.

Run synthetic tests only: python3 experiments/hardlink_copyout_spike.py
"""

import hashlib
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock


_BLOCK = 64 * 1024


def _fingerprint(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink,
            s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _digest_open_fd(fd):
    os.lseek(fd, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    while True:
        block = os.read(fd, _BLOCK)
        if not block:
            return digest.hexdigest()
        digest.update(block)


def copy_out_hardlinked_checkpoint(source, destination):
    """Publish a separate, complete copy of a multiply-linked *trusted* file.

    Refuses aliases, specials, unresolved source-name .tmp, occupied destination,
    missing descriptor guards, and changed source metadata/digest observed during
    the copy. Atomic exclusive final-file publication requires os.link support.
    The return value is a diagnostic, not proof of full-world recovery.
    """
    source = os.path.abspath(os.fspath(source))
    destination = os.path.abspath(os.fspath(destination))
    src_parent = os.path.dirname(source)
    dst_parent = os.path.dirname(destination)

    if not (hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_NONBLOCK")):
        raise OSError("descriptor guards unavailable; copy-out not supported here")
    for parent in (src_parent, dst_parent):
        info = os.lstat(parent)
        if not stat.S_ISDIR(info.st_mode):
            raise OSError("copy-out requires trusted, nonsymlinked immediate folders")
    sdir = os.stat(src_parent)
    ddir = os.stat(dst_parent)
    if (sdir.st_dev, sdir.st_ino) == (ddir.st_dev, ddir.st_ino):
        raise OSError("copy-out destination must be a different trusted directory")
    if os.path.lexists(source + ".tmp"):
        raise FileExistsError("unresolved source checkpoint staging evidence")

    before = os.lstat(source)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink < 2:
        raise OSError("source is not a directly named multiply-linked regular file")
    if os.path.lexists(destination):
        raise FileExistsError("copy-out destination already occupied")

    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    stage = None
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or _fingerprint(opened) != _fingerprint(before):
            raise OSError("checkpoint changed before guarded source open")
        stage_fd, stage = tempfile.mkstemp(prefix=".worldheart-copyout-", suffix=".tmp", dir=dst_parent)
        try:
            source_hash = hashlib.sha256()
            with os.fdopen(stage_fd, "wb") as output:
                while True:
                    block = os.read(fd, _BLOCK)
                    if not block:
                        break
                    output.write(block)
                    source_hash.update(block)
                output.flush()
                os.fsync(output.fileno())  # file only; NOT crash-safe directory publication

            if (_fingerprint(os.fstat(fd)) != _fingerprint(before)
                    or _fingerprint(os.lstat(source)) != _fingerprint(before)
                    or _digest_open_fd(fd) != source_hash.hexdigest()):
                raise OSError("source checkpoint changed during copy; no publication")
            with open(stage, "rb") as probe:
                if hashlib.sha256(probe.read()).hexdigest() != source_hash.hexdigest():
                    raise OSError("staged copy hash mismatch")
            if os.path.lexists(source + ".tmp"):
                raise FileExistsError("source staging evidence appeared during copy")
            # Atomic no-overwrite publication. os.link refuses ANY occupied final,
            # including symlinks, instead of replacing a history entry.
            os.link(stage, destination)
            os.unlink(stage)
            stage = None
            result = os.lstat(destination)
            if not stat.S_ISREG(result.st_mode) or result.st_nlink != 1:
                raise OSError("copy published, but destination link count is unexpected")
            return {"sha256": source_hash.hexdigest(), "bytes": result.st_size,
                    "source_links_at_check": before.st_nlink,
                    "new_file_links": result.st_nlink}
        finally:
            if stage is not None:
                os.unlink(stage)
    finally:
        os.close(fd)


class HardlinkCopyOutTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="wh-copyout-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.old = self.root / "old"
        self.new = self.root / "new"
        self.old.mkdir()
        self.new.mkdir()
        self.original = self.old / "original.wh"
        self.original.write_bytes(b"synthetic-trusted-checkpoint-v1")
        self.latest = self.old / "latest.wh"
        os.link(self.original, self.latest)
        self.dest = self.new / "latest.wh"

    def test_copyout_breaks_hardlink_only_in_fresh_directory(self):
        old_inode = self.original.stat().st_ino
        proof = copy_out_hardlinked_checkpoint(self.latest, self.dest)
        self.assertEqual(proof["source_links_at_check"], 2)
        self.assertEqual(proof["new_file_links"], 1)
        self.assertEqual(self.original.stat().st_ino, old_inode)
        self.assertEqual(self.original.stat().st_ino, self.latest.stat().st_ino)
        self.assertNotEqual(self.dest.stat().st_ino, old_inode)
        self.assertEqual(self.dest.read_bytes(), self.original.read_bytes())
        self.dest.write_bytes(b"independent-future-save")
        self.assertEqual(self.original.read_bytes(), b"synthetic-trusted-checkpoint-v1")
        self.assertEqual(self.latest.read_bytes(), b"synthetic-trusted-checkpoint-v1")

    def test_existing_destination_stays_unchanged(self):
        self.dest.write_bytes(b"other-world")
        with self.assertRaises(FileExistsError):
            copy_out_hardlinked_checkpoint(self.latest, self.dest)
        self.assertEqual(self.dest.read_bytes(), b"other-world")
        self.assertEqual(self.latest.read_bytes(), self.original.read_bytes())

    def test_occupied_symlink_destination_stays_unchanged(self):
        self.dest.symlink_to("missing.wh")
        with self.assertRaises(FileExistsError):
            copy_out_hardlinked_checkpoint(self.latest, self.dest)
        self.assertTrue(self.dest.is_symlink())
        self.assertEqual(os.readlink(self.dest), "missing.wh")

    def test_refuse_source_symlink_and_direct_singlelink(self):
        link = self.old / "indirect.wh"
        link.symlink_to("latest.wh")
        for source in (link, self.original):
            # original only becomes single-linked after unlinking the other name
            if source == self.original:
                self.latest.unlink()
            with self.assertRaises(OSError):
                copy_out_hardlinked_checkpoint(source, self.dest)
        self.assertFalse(self.dest.exists())

    def test_refuse_stale_temp_without_touching_evidence(self):
        temp = Path(str(self.latest) + ".tmp")
        temp.write_bytes(b"incomplete-but-important")
        with self.assertRaises(FileExistsError):
            copy_out_hardlinked_checkpoint(self.latest, self.dest)
        self.assertEqual(temp.read_bytes(), b"incomplete-but-important")
        self.assertFalse(self.dest.exists())

    def test_refuse_fifo_without_blocking(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO unavailable")
        pipe = self.old / "pipe.wh"
        os.mkfifo(pipe)
        with self.assertRaises(OSError):
            copy_out_hardlinked_checkpoint(pipe, self.dest)
        self.assertFalse(self.dest.exists())

    def test_link_publication_failure_keeps_original_and_no_final(self):
        original_link = os.link
        def fail_final(a, b, *args, **kwargs):
            if os.fspath(b) == os.fspath(self.dest):
                raise OSError("simulated filesystem lacking hardlinks")
            return original_link(a, b, *args, **kwargs)
        with mock.patch.object(os, "link", side_effect=fail_final):
            with self.assertRaisesRegex(OSError, "simulated"):
                copy_out_hardlinked_checkpoint(self.latest, self.dest)
        self.assertEqual(self.original.read_bytes(), b"synthetic-trusted-checkpoint-v1")
        self.assertEqual(list(self.new.iterdir()), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
