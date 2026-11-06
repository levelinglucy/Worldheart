"""Cross-version CLI recovery tests using genuine, locally generated v0.2 saves.

The historical script is executed as __main__ in a separate interpreter, just
as it was for users. The candidate is then started in another interpreter.
No external pickle is opened, no real user directory is accessed, and the
legacy source file remains unchanged. This is representative of the shipped
CLI format, not a test of an actual user's checkpoint or untrusted files.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "Worldheart simulator"
CANDIDATE = ROOT / "worldheart_v02_1.py"
DATA = "WORLDHEART_V02_DATA"
CHECKPOINT = "worldheart_v02_latest.wh"
EVENTS = "worldheart_v02_events.jsonl"


class LegacyCliRecoveryTests(unittest.TestCase):
    def run_script(self, script, cwd, commands):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        completed = subprocess.run(
            [sys.executable, str(script)],
            input=commands,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(cwd),
            env=env,
            timeout=90,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            f"{script.name} exited with {completed.returncode}:\n"
            + completed.stdout[-3500:],
        )
        return completed.stdout

    def make_legacy_save(self, cwd):
        # The legacy CLI produces __main__.World, Node and Structure pickle
        # classes. Importing it under a test-module alias is *not* equivalent.
        self.run_script(LEGACY, cwd, "777\ns\nq\n")
        data = cwd / DATA
        checkpoint = data / CHECKPOINT
        envelope = json.loads(checkpoint.read_text(encoding="utf-8"))
        self.assertEqual(envelope["version"], "0.2-primordial")
        self.assertEqual(envelope["seed"], 777)
        self.assertEqual(envelope["tick"], 0)
        return data, envelope

    @staticmethod
    def uncompressed_state(envelope):
        return zlib.decompress(bytes.fromhex(envelope["payload"]))

    def check_resume(self, commands, with_probe):
        with tempfile.TemporaryDirectory(prefix="worldheart-legacy-recovery-") as tmp:
            cwd = Path(tmp)
            data, legacy = self.make_legacy_save(cwd)
            original_state = self.uncompressed_state(legacy)
            self.assertIn(b"__main__", original_state)
            before_files = {p.name: p.read_bytes() for p in data.iterdir()}
            self.assertIn(EVENTS, before_files)

            stdout = self.run_script(CANDIDATE, cwd, commands)
            self.assertIn("Recovered transition 0", stdout)
            if with_probe:
                self.assertIn("Control active:", stdout)
                self.assertIn("Removed active:", stdout)

            after_files = {p.name: p.read_bytes() for p in data.iterdir()}
            self.assertEqual(set(before_files), set(after_files))
            updated = json.loads(after_files[CHECKPOINT].decode("utf-8"))
            self.assertEqual(updated["version"], "0.2.1-rc1")
            self.assertEqual((updated["seed"], updated["tick"]), (777, 0))

            # The user-visible quit/save must not alter the recovered ecology,
            # and running the optional counterfactual probe must not either.
            # The only expected disk-side change is the normal quit checkpoint.
            self.assertEqual(self.uncompressed_state(updated), original_state)
            old_events = before_files[EVENTS].decode("utf-8").splitlines()
            new_events = after_files[EVENTS].decode("utf-8").splitlines()
            self.assertEqual(new_events[:len(old_events)], old_events)
            self.assertEqual(len(new_events), len(old_events) + 1)
            self.assertEqual(json.loads(new_events[-1])["kind"], "CHECKPOINT")

    def test_legacy_cli_checkpoint_resumes_and_resaves(self):
        self.check_resume("y\nq\n", with_probe=False)

    def test_legacy_cli_checkpoint_survives_counterfactual_probe(self):
        self.check_resume("y\nc\n\nq\n", with_probe=True)


if __name__ == "__main__":
    unittest.main()
