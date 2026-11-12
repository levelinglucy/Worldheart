"""Read-only envelope tests using synthetic bytes; no pickle is executed."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
INSPECTOR = ROOT / "inspect_checkpoint.py"
spec = importlib.util.spec_from_file_location("worldheart_inspector", INSPECTOR)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def envelope(payload=b"synthetic untrusted bytes"):
    return {
        "version": "0.2.1", "seed": 7, "tick": 12,
        "payload": payload.hex(),
        "hash": hashlib.blake2b(payload, digest_size=8).hexdigest(),
    }


class InspectorTests(unittest.TestCase):
    def run_case(self, data, expected_status=0):
        with tempfile.TemporaryDirectory(prefix="worldheart-inspect-") as tmp:
            path = Path(tmp) / "example.wh"
            path.write_bytes(data)
            before = path.read_bytes()
            proc = subprocess.run([sys.executable, str(INSPECTOR), str(path)],
                                  text=True, capture_output=True, timeout=10)
            self.assertEqual(proc.returncode, expected_status, proc.stderr)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["example.wh"])
            return proc

    def test_valid_envelope_does_not_unpickle_or_decompress(self):
        result = self.run_case(json.dumps(envelope(b"not even valid compressed pickle")).encode())
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "checksum_matches")
        self.assertEqual(report["tick"], 12)
        self.assertIn("not authenticity", report["warning"])

    def test_checksum_mismatch_is_nonzero_and_preserved(self):
        item = envelope()
        item["hash"] = "0" * 16 if item["hash"] != "0" * 16 else "1" * 16
        proc = self.run_case(json.dumps(item).encode(), expected_status=1)
        self.assertEqual(json.loads(proc.stdout)["status"], "checksum_mismatch")

    def test_duplicate_and_nonstandard_json_refused(self):
        self.run_case(b'{"version":"a","version":"b"}', expected_status=2)
        item = json.dumps(envelope()).replace('"tick": 12', '"tick": NaN')
        self.run_case(item.encode(), expected_status=2)

    def test_bad_structure_and_hex_refused(self):
        self.run_case(b'[]', expected_status=2)
        item = envelope()
        item["payload"] = "zz"
        self.run_case(json.dumps(item).encode(), expected_status=2)
        item = envelope()
        item["seed"] = True
        self.run_case(json.dumps(item).encode(), expected_status=2)

    def test_size_bound_refuses_even_with_forged_size_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "oversized.wh"
            path.write_bytes(b" " * (module.MAX_FILE_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "16 MiB"):
                module.inspect(str(path))

    def test_symlink_and_fifo_are_not_followed(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real.wh"
            real.write_text(json.dumps(envelope()))
            link = Path(tmp) / "alias.wh"
            try:
                link.symlink_to(real)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks unsupported")
            proc = subprocess.run([sys.executable, str(INSPECTOR), str(link)],
                                  capture_output=True, text=True, timeout=10)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(real.read_text(), json.dumps(envelope()))
            if hasattr(os, "mkfifo"):
                fifo = Path(tmp) / "pipe.wh"
                os.mkfifo(fifo)
                proc = subprocess.run([sys.executable, str(INSPECTOR), str(fifo)],
                                      capture_output=True, text=True, timeout=10)
                self.assertEqual(proc.returncode, 2)

    def test_no_safe_open_flags_refuses_without_access(self):
        with mock.patch.object(module.os, "O_NOFOLLOW", None, create=True):
            with self.assertRaisesRegex(ValueError, "unavailable"):
                module.inspect("must-not-open")


if __name__ == "__main__":
    unittest.main()
