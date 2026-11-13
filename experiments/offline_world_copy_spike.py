#!/usr/bin/env python3
"""Research-only whole-folder stopped-world copy-out for Worldheart PR #10.

Runs entirely on SYNTHETIC FIXTURES by default: python offline_world_copy_spike.py
Not a production migration command, not an automatic repair, and NEVER loads
pickle. The function is deliberately not exposed as a CLI for real user saves.

Preconditions: trusted private stationary source and destination-parent folders,
all Worldheart processes stopped, and a separate preserved source backup. The
experiment copies *every* directly named regular file (checkpoint, journal,
fossils and unresolved *.tmp evidence) into an exclusive new work directory.
It refuses symlinks, special files and subdirectories instead of guessing what
they mean. Multiple hard-link names become independent single-linked copies.

The resulting manifest records observed hash equality and whether *.tmp evidence
needs human recovery review; it is NOT authentication, an fsync durability proof,
a race-free transaction, or CLI replay equivalence. Never run a candidate while
its temp evidence is unresolved. Pythonista compatibility has not been tested.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock

SAVE_DIR = "WORLDHEART_V02_DATA"
SAVE_FILE = "worldheart_v02_latest.wh"
_BLOCK = 64 * 1024
_MAX_FILES = 1000
_MAX_FILE_BYTES = 128 * 1024 * 1024
_MAX_TOTAL_BYTES = 256 * 1024 * 1024


def _identity(st):
    """Detect observed changes; not a lock or adversarial race defense."""
    return (st.st_dev, st.st_ino, st.st_mode, st.st_nlink,
            st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _scan_regular(data):
    result = {}
    with os.scandir(data) as it:
        for entry in it:
            before = entry.stat(follow_symlinks=False)
            if not stat.S_ISREG(before.st_mode):
                raise OSError("source contains symlink, directory or special file: " + entry.name)
            if len(result) >= _MAX_FILES or before.st_size > _MAX_FILE_BYTES:
                raise OSError("source exceeds bounded copy limits")
            result[entry.name] = _identity(before)
    if SAVE_FILE not in result:
        raise OSError("missing expected primary Worldheart checkpoint")
    if result[SAVE_FILE][3] < 2:
        raise OSError("primary checkpoint is not multiply hard-linked; no copy-out needed")
    if sum(v[4] for v in result.values()) > _MAX_TOTAL_BYTES:
        raise OSError("source exceeds aggregate bounded copy limit")
    return result


def _copy_file(src, dst, before):
    if not (hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_NONBLOCK")):
        raise OSError("safe no-follow/nonblocking read flags unavailable")
    fd = os.open(src, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if _identity(os.fstat(fd)) != before:
            raise OSError("source entry changed before opening: " + src.name)
        digest = hashlib.sha256()
        count = 0
        with open(dst, "xb") as out:
            while True:
                block = os.read(fd, _BLOCK)
                if not block:
                    break
                count += len(block)
                if count > _MAX_FILE_BYTES:
                    raise OSError("file grew past bound: " + src.name)
                out.write(block)
                digest.update(block)
            out.flush()
            os.fsync(out.fileno())  # file flush only; directory commit not guaranteed
        if _identity(os.fstat(fd)) != before or _identity(os.lstat(src)) != before:
            raise OSError("source entry changed during copy: " + src.name)
        if count != before[4]:
            raise OSError("unexpected copied length: " + src.name)
        # Observe the staged bytes independently; a hash is not authenticity.
        check = hashlib.sha256()
        with open(dst, "rb") as handle:
            while True:
                chunk = handle.read(_BLOCK)
                if not chunk:
                    break
                check.update(chunk)
        if check.digest() != digest.digest():
            raise OSError("staged hash mismatch: " + src.name)
        return digest.hexdigest()
    finally:
        os.close(fd)


def prepare_offline_copy(source_data, destination_parent):
    """Copy a *stopped, trusted* Worldheart data folder to an isolated new root.

    Returns (new_root, manifest). A new root is NEVER reused. Any failure
    removes only attempt-owned scratch, leaving source files untouched.
    """
    source_data = Path(os.path.abspath(os.fspath(source_data)))
    destination_parent = Path(os.path.abspath(os.fspath(destination_parent)))
    src_parent = source_data.parent
    for directory in (src_parent, source_data, destination_parent):
        metadata = os.lstat(directory)
        if not stat.S_ISDIR(metadata.st_mode):
            raise OSError("directory is not a direct nonsymlinked directory")
    if (os.path.samefile(source_data, destination_parent) or
            os.path.samefile(src_parent, destination_parent)):
        raise OSError("choose an independent destination parent")
    initial = _scan_regular(source_data)
    root = Path(tempfile.mkdtemp(prefix=".worldheart-offline-", dir=destination_parent))
    try:
        dest_data = root / SAVE_DIR
        dest_data.mkdir(mode=0o700)
        hashes = {}
        for name in sorted(initial):
            hashes[name] = _copy_file(source_data / name, dest_data / name, initial[name])
        if initial != _scan_regular(source_data):
            raise OSError("source folder entries changed during copy; abort")
        # Recheck the final copied tree: exact names, file types, contents and
        # independently linked files, before publishing a COMPLETE marker.
        if set(os.listdir(dest_data)) != set(initial):
            raise OSError("copied entry set differs from source")
        for name, expected in hashes.items():
            copied = dest_data / name
            st = os.lstat(copied)
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
                raise OSError("copy not independently single-linked: " + name)
            digest = hashlib.sha256()
            with copied.open("rb") as handle:
                for block in iter(lambda: handle.read(_BLOCK), b""):
                    digest.update(block)
            if digest.hexdigest() != expected:
                raise OSError("copied content changed: " + name)
        temp_names = sorted(name for name in initial if name.endswith(".tmp"))
        manifest = {
            "experiment": "Worldheart stopped-world offline copy-out, synthetic research",
            "copy_complete": True,
            "recovery_review_required": bool(temp_names),
            "unresolved_temp_names": temp_names,
            "files": [{"name": name, "bytes": initial[name][4], "sha256": hashes[name],
                       "source_hardlink_count": initial[name][3]} for name in sorted(initial)],
            "warning": "Not a safe untrusted-checkpoint loader, transaction or crash-durable backup",
        }
        stage = root / "manifest.json.tmp"
        with stage.open("x", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(stage, root / "manifest.json")
        return root, manifest
    except BaseException:
        shutil.rmtree(root)
        raise


class WholeWorldCopyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="wh-whole-copy-")
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.source = self.home / "source" / SAVE_DIR
        self.destination = self.home / "prepared"
        self.source.mkdir(parents=True)
        self.destination.mkdir()
        self.latest = self.source / SAVE_FILE
        self.latest.write_bytes(b"synthetic-worldheart-save")
        self.alias = self.source / "snapshot_t000000000000.wh"
        os.link(self.latest, self.alias)
        (self.source / "worldheart_v02_events.jsonl").write_bytes(b'{"kind":"GENESIS"}\n')
        (self.source / "fossil_000000000000.json").write_bytes(b'{"tick":0}\n')

    def test_copy_preserves_all_files_and_breaks_hardlink(self):
        originals = {p.name: p.read_bytes() for p in self.source.iterdir()}
        inode = self.latest.stat().st_ino
        root, manifest = prepare_offline_copy(self.source, self.destination)
        self.assertTrue((root / "manifest.json").is_file())
        copied = root / SAVE_DIR
        self.assertEqual({p.name: p.read_bytes() for p in copied.iterdir()}, originals)
        self.assertEqual(len(manifest["files"]), 4)
        self.assertFalse(manifest["recovery_review_required"])
        self.assertEqual(self.latest.stat().st_ino, inode)
        self.assertEqual(self.alias.stat().st_ino, inode)
        self.assertNotEqual((copied / SAVE_FILE).stat().st_ino, inode)
        self.assertNotEqual((copied / SAVE_FILE).stat().st_ino, (copied / self.alias.name).stat().st_ino)
        (copied / SAVE_FILE).write_bytes(b"future-save")
        self.assertEqual(self.latest.read_bytes(), originals[SAVE_FILE])
        self.assertEqual((copied / self.alias.name).read_bytes(), originals[self.alias.name])

    def test_unresolved_temp_preserved_and_flagged(self):
        evidence = self.source / (SAVE_FILE + ".tmp")
        evidence.write_bytes(b"unfinished-evidence-do-not-erase")
        fossil_stage = self.source / "fossil_000000000000.json.tmp"
        fossil_stage.write_bytes(b"partial-observation")
        root, manifest = prepare_offline_copy(self.source, self.destination)
        self.assertTrue(manifest["recovery_review_required"])
        self.assertEqual(set(manifest["unresolved_temp_names"]), {evidence.name, fossil_stage.name})
        self.assertEqual((root / SAVE_DIR / evidence.name).read_bytes(), evidence.read_bytes())
        self.assertEqual((root / SAVE_DIR / fossil_stage.name).read_bytes(), fossil_stage.read_bytes())

    def test_source_symlink_refused_and_not_followed(self):
        (self.source / "fossil_escape.json").symlink_to("../private")
        with self.assertRaisesRegex(OSError, "symlink"):
            prepare_offline_copy(self.source, self.destination)
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_source_fifo_refused_without_reading(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO unavailable")
        os.mkfifo(self.source / "fossil_fifo.json")
        with self.assertRaisesRegex(OSError, "special"):
            prepare_offline_copy(self.source, self.destination)
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_source_subdirectory_refused(self):
        (self.source / "nested").mkdir()
        with self.assertRaisesRegex(OSError, "directory"):
            prepare_offline_copy(self.source, self.destination)

    def test_source_change_mid_copy_cleans_owned_scratch(self):
        real_copy = _copy_file
        count = 0
        def mutate_once(src, dst, before):
            nonlocal count
            result = real_copy(src, dst, before)
            count += 1
            if count == 1:
                (self.source / "new-unobserved-event.jsonl").write_bytes(b"extra")
            return result
        with mock.patch.object(sys.modules[__name__], "_copy_file", side_effect=mutate_once):
            with self.assertRaisesRegex(OSError, "changed during copy"):
                prepare_offline_copy(self.source, self.destination)
        self.assertEqual(list(self.destination.iterdir()), [])
        self.assertEqual(self.latest.read_bytes(), b"synthetic-worldheart-save")

    def test_copy_fault_removes_owned_scratch_not_source(self):
        with mock.patch.object(sys.modules[__name__], "_copy_file", side_effect=OSError("injected IO")):
            with self.assertRaisesRegex(OSError, "injected IO"):
                prepare_offline_copy(self.source, self.destination)
        self.assertEqual(list(self.destination.iterdir()), [])
        self.assertEqual(self.alias.read_bytes(), b"synthetic-worldheart-save")

    def test_no_hardlink_requires_explicit_other_workflow(self):
        self.alias.unlink()
        with self.assertRaisesRegex(OSError, "not multiply hard-linked"):
            prepare_offline_copy(self.source, self.destination)

    def test_nontrusted_destination_parent_rejected(self):
        link = self.home / "dest-link"
        link.symlink_to(self.destination, target_is_directory=True)
        with self.assertRaisesRegex(OSError, "nonsymlinked"):
            prepare_offline_copy(self.source, link)

    def test_destination_parent_must_be_independent(self):
        with self.assertRaisesRegex(OSError, "independent"):
            prepare_offline_copy(self.source, self.source.parent)


if __name__ == "__main__":
    unittest.main(verbosity=2)
