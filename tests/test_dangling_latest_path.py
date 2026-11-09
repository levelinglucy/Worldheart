"""A dangling latest-checkpoint symlink is existing recovery evidence, not an empty slot.

Only synthetic paths in an isolated temporary directory are touched.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "worldheart_v02_1.py"


class DanglingCheckpointRecoveryTests(unittest.TestCase):
    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_dangling_latest_symlink_cannot_be_replaced_by_genesis(self):
        with tempfile.TemporaryDirectory(prefix="worldheart-dangling-") as tmp:
            root = Path(tmp)
            data = root / "WORLDHEART_V02_DATA"
            data.mkdir()
            target = "previous-world-recovery.wh"
            latest = data / "worldheart_v02_latest.wh"
            try:
                latest.symlink_to(target)
            except (OSError, NotImplementedError) as exc:
                self.skipTest("symlinks unsupported: %s" % exc)

            journal = data / "worldheart_v02_events.jsonl"
            journal.write_bytes(b"previous world events\n")
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            # A missing-slot mistake currently skips the resume prompt;
            # this seed and quit would replace the existing symlink.
            result = subprocess.run(
                [sys.executable, str(CANDIDATE)],
                input="4242\nq\n",
                text=True, encoding="utf-8", errors="replace",
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                cwd=str(root), env=env, timeout=30, check=False,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout[-1500:])
            self.assertIn("Recovery failed:", result.stdout)
            self.assertIn("preserv", result.stdout.lower())
            self.assertNotIn("Genesis seed [", result.stdout)
            self.assertTrue(latest.is_symlink())
            self.assertEqual(os.readlink(latest), target)
            self.assertEqual(journal.read_bytes(), b"previous world events\n")
            self.assertEqual(sorted(p.name for p in data.iterdir()),
                             ["worldheart_v02_events.jsonl", "worldheart_v02_latest.wh"])


if __name__ == "__main__":
    unittest.main()
