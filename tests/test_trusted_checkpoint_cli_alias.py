"""Disposable end-to-end CLI tests for trusted checkpoint aliases (draft PR #10).

The simulator is invoked as a subprocess, preserving the __main__.World pickle
identity that an import-only API test cannot establish. No user saves are read.
"""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "worldheart_v02_1.py"
SAVE_DIR = "WORLDHEART_V02_DATA"
SAVE_FILE = "worldheart_v02_latest.wh"


@unittest.skipUnless(hasattr(os, "symlink"), "symbolic links unavailable")
class TrustedCheckpointCliAliasTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="worldheart-cli-alias-")
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / SAVE_DIR
        self.latest = self.folder / SAVE_FILE
        self.target = self.folder / "private_world.wh"

        initial = self.run_cli("\nq\n")
        self.assertEqual(initial.returncode, 0, initial.stderr[-2000:])
        self.assertTrue(self.latest.is_file())
        self.latest.rename(self.target)
        try:
            self.latest.symlink_to(self.target.name)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("symlink unavailable on this filesystem: %s" % exc)

    def run_cli(self, user_input):
        return subprocess.run(
            [sys.executable, str(SOURCE)],
            input=user_input,
            text=True,
            capture_output=True,
            cwd=self.tmp.name,
            timeout=25,
            check=False,
        )

    def assert_alias_untouched(self):
        self.assertTrue(self.latest.is_symlink())
        self.assertEqual(os.readlink(str(self.latest)), self.target.name)
        self.assertTrue(self.target.is_file())
        self.assertFalse(Path(str(self.latest) + ".tmp").exists())

    def test_actual_cli_resume_and_quit_preserves_alias(self):
        before = self.target.read_bytes()
        result = self.run_cli("\nq\n")
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertIn("Recovered transition", result.stdout)
        self.assertIn("Preserved:", result.stdout)
        self.assert_alias_untouched()
        self.assertEqual(self.latest.read_bytes(), self.target.read_bytes())
        self.assertFalse(Path(str(self.target) + ".tmp").exists())
        self.assertGreater(len(before), 0)

        # A second process must recover the re-saved __main__.World checkpoint.
        next_run = self.run_cli("\nq\n")
        self.assertEqual(next_run.returncode, 0, next_run.stderr[-2000:])
        self.assertIn("Recovered transition", next_run.stdout)
        self.assert_alias_untouched()

    def test_actual_cli_explicit_genesis_refuses_to_replace_alias(self):
        before = self.target.read_bytes()
        result = self.run_cli("n\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Start a new world in a clean working directory", result.stdout)
        self.assert_alias_untouched()
        self.assertEqual(self.target.read_bytes(), before)

    def test_actual_cli_stale_target_temp_preserves_both_histories(self):
        before = self.target.read_bytes()
        unresolved = Path(str(self.target) + ".tmp")
        unresolved.write_bytes(b"recoverable-staging-evidence")
        result = self.run_cli("\nq\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Recovered transition", result.stdout)
        self.assertIn("Unresolved checkpoint temp", result.stderr)
        self.assert_alias_untouched()
        self.assertEqual(self.target.read_bytes(), before)
        self.assertEqual(unresolved.read_bytes(), b"recoverable-staging-evidence")


if __name__ == "__main__":
    unittest.main()
