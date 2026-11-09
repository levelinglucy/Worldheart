"""Refuse automatic genesis after a failed trusted checkpoint recovery.

All fixtures are synthetic JSON envelopes, never pickle payloads. CLI runs
only in disposable directories, protecting any real WORLDHEART_V02_DATA.
"""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "worldheart_v02_1.py"
DATA = "WORLDHEART_V02_DATA"
CHECKPOINT = "worldheart_v02_latest.wh"


class FailedRecoveryRefusalTests(unittest.TestCase):
    def check_failed_recovery_preserves_every_file(self, checkpoint_bytes):
        with tempfile.TemporaryDirectory(prefix="worldheart-failed-recovery-") as tmp:
            root = Path(tmp)
            data = root / DATA
            data.mkdir()
            checkpoint = data / CHECKPOINT
            checkpoint.write_bytes(checkpoint_bytes)
            events = data / "worldheart_v02_events.jsonl"
            events.write_bytes(b"prior events remain untouched\n")
            previous = {p.name: p.read_bytes() for p in data.iterdir()}
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"

            # Extra commands intentionally expose the old fallback: after a
            # failed resume, the old CLI accepted a fresh seed and 'q', which
            # replaced the existing (potentially recoverable) checkpoint.
            result = subprocess.run(
                [sys.executable, str(CANDIDATE)],
                input="y\n4242\nq\n",
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(root),
                env=env,
                timeout=30,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout[-1500:])
            self.assertIn("Recovery failed:", result.stdout)
            self.assertIn("preserv", result.stdout.lower())
            self.assertNotIn("Genesis seed [", result.stdout)
            after = {p.name: p.read_bytes() for p in data.iterdir()}
            self.assertEqual(after, previous)

    def test_malformed_json_checkpoint_cannot_be_replaced_by_fallback_genesis(self):
        self.check_failed_recovery_preserves_every_file(
            b'{"payload":"possibly recoverable interrupted checkpoint'
        )

    def test_integrity_mismatch_checkpoint_cannot_be_replaced_by_fallback_genesis(self):
        self.check_failed_recovery_preserves_every_file(
            b'{"version":"0.2-primordial","seed":77,"tick":23,'
            b'"payload":"00","hash":"not-the-payload-hash"}'
        )


if __name__ == "__main__":
    unittest.main()
