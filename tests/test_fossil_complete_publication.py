"""Fossil publication must expose only complete JSON or no new final artifact.

All fixtures are synthetic and written inside disposable working directories.
"""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
LOADER = importlib.machinery.SourceFileLoader(
    "worldheart_fossil_complete", str(ROOT / "worldheart_v02_1.py")
)
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
worldheart = importlib.util.module_from_spec(SPEC)
sys.modules[LOADER.name] = worldheart
LOADER.exec_module(worldheart)


class CompleteFossilPublicationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="worldheart-complete-fossils-")
        previous_cwd = os.getcwd()
        os.chdir(self.directory.name)
        self.addCleanup(os.chdir, previous_cwd)
        self.addCleanup(self.directory.cleanup)

    def files(self):
        return sorted(Path(worldheart.SAVE_DIR).glob("fossil_*"))

    def test_serialization_failure_never_exposes_partial_final(self):
        world = worldheart.World(seed=9142)
        destination = Path(worldheart.SAVE_DIR) / "fossil_000000000000.json"

        def interrupted_dump(value, stream, **kwargs):
            stream.write('{"tick":')
            stream.flush()
            self.assertFalse(destination.exists(), "Final fossil must not appear mid-write")
            raise OSError("injected mid-serialization failure")

        with mock.patch.object(worldheart.json, "dump", side_effect=interrupted_dump):
            world.preserve_fossil(["interrupted"], world.metrics())

        self.assertFalse(destination.exists(), "Incomplete JSON must not be published")
        self.assertEqual(self.files(), [], "Failed attempt must clean its own staging file")
        self.assertEqual(world.fossils[-1]["reasons"], ["interrupted"])
        world.preserve_fossil(["later"], world.metrics())
        self.assertEqual(json.loads(destination.read_text(encoding="utf-8"))["reasons"], ["later"])

    def test_publish_failure_keeps_old_fossil_and_cleans_stage(self):
        world = worldheart.World(seed=9143)
        world.preserve_fossil(["first"], world.metrics())
        destination = Path(worldheart.SAVE_DIR) / "fossil_000000000000.json"
        first = destination.read_bytes()

        with mock.patch.object(worldheart.os, "link", side_effect=OSError("links disabled")):
            world.preserve_fossil(["later"], world.metrics())

        self.assertEqual(destination.read_bytes(), first)
        self.assertEqual(self.files(), [destination], "No incomplete alternative should be visible")
        self.assertEqual(world.fossils[-1]["reasons"], ["later"])


if __name__ == "__main__":
    unittest.main()
