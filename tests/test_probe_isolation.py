"""Regression checks for Worldheart probe isolation (standard library only).

The legacy test intentionally demonstrates the original defect in a temporary
directory; it does NOT write to any user's real Worldheart data directory.
"""

import importlib.machinery
import importlib.util
import os
import pickle
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[1]


def load_module(path, name):
    loader = importlib.machinery.SourceFileLoader(name, str(ROOT / path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


legacy = load_module("Worldheart simulator", "worldheart_v02_legacy")
candidate = load_module("worldheart_v02_1.py", "worldheart_v02_candidate")


@contextmanager
def temp_workdir():
    old_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            yield Path(tmp)
        finally:
            os.chdir(old_cwd)


class CounterfactualIsolationTests(unittest.TestCase):

    def test_legacy_probe_does_write_live_artifacts(self):
        """Reproduce the legacy bug without touching actual user data."""
        with temp_workdir():
            legacy.CHECKPOINT_EVERY = 2
            world = legacy.World(seed=101)
            world.save()
            path = Path(legacy.SAVE_DIR) / legacy.SAVE_FILE
            before = path.read_bytes()
            legacy.counterfactual_probe(world, steps=2)
            self.assertNotEqual(before, path.read_bytes())

    def test_candidate_probe_preserves_world_and_files(self):
        with temp_workdir():
            candidate.CHECKPOINT_EVERY = 2
            world = candidate.World(seed=101)
            world.save()
            path = Path(candidate.SAVE_DIR) / candidate.SAVE_FILE
            events = Path(candidate.SAVE_DIR) / candidate.EVENT_FILE
            before_checkpoint = path.read_bytes()
            before_events = events.read_bytes()
            before_world = pickle.dumps(world)
            before_files = sorted(p.name for p in Path(candidate.SAVE_DIR).iterdir())

            result = candidate.counterfactual_probe(world, steps=2)
            self.assertIsNotNone(result)
            self.assertEqual(before_checkpoint, path.read_bytes())
            self.assertEqual(before_events, events.read_bytes())
            self.assertEqual(before_world, pickle.dumps(world))
            self.assertEqual(before_files, sorted(p.name for p in Path(candidate.SAVE_DIR).iterdir()))

    def test_private_fork_retains_in_memory_fossils_but_writes_nothing(self):
        with temp_workdir():
            world = candidate.World(seed=102)
            data_dir = Path(candidate.SAVE_DIR)
            before = {p.name: p.read_bytes() for p in data_dir.iterdir()}
            fork = world.fork(disk_writes_enabled=False)
            fork.event("PROBE_CHECK", {"ok": True})
            fork.preserve_fossil(["test event"], fork.metrics())
            self.assertTrue(fork.fossils)
            self.assertTrue(any(e["kind"] == "ANOMALY" for e in fork.events))
            self.assertEqual(before, {p.name: p.read_bytes() for p in data_dir.iterdir()})
            with self.assertRaisesRegex(RuntimeError, "disabled"):
                fork.save()
            with self.assertRaisesRegex(RuntimeError, "disabled"):
                fork.save_named("private")
            self.assertEqual(before, {p.name: p.read_bytes() for p in data_dir.iterdir()})

    def test_regular_fork_and_legacy_checkpoint_compatibility(self):
        with temp_workdir():
            world = candidate.World(seed=103)
            clone = world.fork()
            self.assertTrue(clone._can_write_disk())
            self.assertTrue(Path(clone.save_named("ordinary-fork")).is_file())
            # Simulate an old pickled instance without the new field.
            del world._disk_writes_enabled
            self.assertTrue(world._can_write_disk())
            self.assertTrue(Path(world.save()).is_file())


    def test_multicheckpoint_horizon_preserves_disk_and_live_state(self):
        """Cross several would-be auto-save boundaries without external writes."""
        with temp_workdir():
            candidate.CHECKPOINT_EVERY = 3
            candidate.METRICS_EVERY = 1
            world = candidate.World(seed=104)
            world.save()
            data_dir = Path(candidate.SAVE_DIR)
            before = {p.name: p.read_bytes() for p in data_dir.iterdir()}
            in_memory = pickle.dumps(world)
            probe = candidate.counterfactual_probe(world, steps=12)
            self.assertEqual(probe["steps"], 12)
            self.assertEqual(in_memory, pickle.dumps(world))
            self.assertEqual(before, {p.name: p.read_bytes() for p in data_dir.iterdir()})

    def test_seeded_transitions_remain_equivalent_to_original(self):
        """The IO fix must not change ordinary VM evolution or observer metrics."""
        with temp_workdir():
            legacy.CHECKPOINT_EVERY = 0
            candidate.CHECKPOINT_EVERY = 0
            old = legacy.World(seed=105)
            new = candidate.World(seed=105)
            self.assertEqual(old.metrics(), new.metrics())
            for _ in range(12):
                old.transition()
                new.transition()
            self.assertEqual(old.metrics(), new.metrics())


if __name__ == "__main__":
    unittest.main()
