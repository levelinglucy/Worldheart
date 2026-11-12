"""Synthetic read-only comparison of two checkpoint envelopes; never load pickle."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

INSPECTOR = Path(__file__).resolve().parents[1] / "inspect_checkpoint.py"


def checkpoint(seed=7, tick=10, version="0.2.1", payload=b"synthetic"):
    return {
        "version": version, "seed": seed, "tick": tick,
        "payload": payload.hex(),
        "hash": hashlib.blake2b(payload, digest_size=8).hexdigest(),
    }


class CheckpointPairTests(unittest.TestCase):
    def compare(self, first, second, exit_code=0):
        with tempfile.TemporaryDirectory(prefix="worldheart-pair-") as tmp:
            left = Path(tmp) / "latest.wh"
            right = Path(tmp) / "interrupted.wh.tmp"
            left.write_bytes(first)
            right.write_bytes(second)
            before = {p.name: p.read_bytes() for p in (left, right)}
            proc = subprocess.run(
                [sys.executable, str(INSPECTOR), str(left), "--against", str(right)],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(proc.returncode, exit_code, proc.stderr)
            self.assertEqual(
                {p.name: p.read_bytes() for p in Path(tmp).iterdir()}, before
            )
            return proc

    def encoded(self, **kwargs):
        return json.dumps(checkpoint(**kwargs)).encode("utf-8")

    def test_pair_reports_relative_ticks_without_recovery_claim(self):
        proc = self.compare(self.encoded(tick=10), self.encoded(tick=27))
        output = json.loads(proc.stdout)
        self.assertEqual(output["first"]["tick"], 10)
        self.assertEqual(output["second"]["tick"], 27)
        self.assertEqual(output["comparison"], {
            "status": "same_recorded_identity",
            "second_minus_first_tick": 17,
            "higher_recorded_tick": "second",
        })
        self.assertIn("not proof", output["warning"])

    def test_equal_and_reverse_recorded_ticks(self):
        equal = json.loads(self.compare(
            self.encoded(tick=10), self.encoded(tick=10)).stdout)
        self.assertEqual(equal["comparison"]["higher_recorded_tick"], "equal")
        self.assertEqual(equal["comparison"]["second_minus_first_tick"], 0)
        reverse = json.loads(self.compare(
            self.encoded(tick=27), self.encoded(tick=10)).stdout)
        self.assertEqual(reverse["comparison"]["higher_recorded_tick"], "first")
        self.assertEqual(reverse["comparison"]["second_minus_first_tick"], -17)

    def test_different_recorded_seed_or_version_does_not_rank(self):
        for differing in ({"seed": 8}, {"version": "0.3"}):
            with self.subTest(differing=differing):
                output = json.loads(self.compare(
                    self.encoded(tick=10),
                    self.encoded(tick=27, **differing)).stdout)
                self.assertEqual(output["comparison"], {
                    "status": "different_recorded_identity",
                    "second_minus_first_tick": None,
                    "higher_recorded_tick": None,
                })

    def test_checksum_mismatch_suppresses_order_and_is_nonzero(self):
        altered = checkpoint(tick=27)
        altered["hash"] = "0" * 16 if altered["hash"] != "0" * 16 else "1" * 16
        output = json.loads(self.compare(
            self.encoded(tick=10), json.dumps(altered).encode(),
            exit_code=1).stdout)
        self.assertEqual(output["second"]["status"], "checksum_mismatch")
        self.assertEqual(output["comparison"]["status"], "checksum_mismatch")
        self.assertIsNone(output["comparison"]["higher_recorded_tick"])
        self.assertIsNone(output["comparison"]["second_minus_first_tick"])

    def test_malformed_second_is_refused_without_partial_report(self):
        proc = self.compare(self.encoded(), b'{"tick": 27, "tick": 28}',
                            exit_code=2)
        self.assertFalse(proc.stdout.strip())
        self.assertIn("Inspection refused", proc.stderr)


if __name__ == "__main__":
    unittest.main()
