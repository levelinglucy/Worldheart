# Worldheart — developer notes

## Development summary

**Candidate:** `v0.2.1-rc1` (six regression tests passed in CI; not designated stable). **Goal:** counterfactual probes cannot modify the live simulation's disk artifacts.  
**Historical baseline:** `Worldheart simulator` (`v0.2-primordial`), preserved byte-for-byte in the same repository.  
**Latest changes:** new candidate script with per-fork disk isolation, regression tests and GitHub Actions.  
**Latest recovery validation:** a genuine v0.2 CLI checkpoint generated in an isolated interpreter was resumed and re-saved by the candidate, with and without a counterfactual probe. **8/8 tests passed** on [the compatibility branch](https://github.com/levelinglucy/Worldheart/actions/runs/42181165055). This does not represent an actual user save or Pythonista device.  
**Next priorities:** test a trusted in-the-wild checkpoint in a disposable copy where available, verify rollback and assess the stable release gate. [Candidate PR #1 was merged](https://github.com/levelinglucy/Worldheart/pull/1).  
**Links:** [Changelog](./CHANGELOG.md) · [README](./README.md) · [Trusted recovery guide](./docs/RECOVERY.md) · [Probe tests](./tests/test_probe_isolation.py) · [CLI compatibility tests](./tests/test_legacy_cli_recovery.py).

## How the original code works

Worldheart starts from a seeded random graph and population of byte-string structures. Each transition processes VM instructions and environmental changes. An external observer keeps metrics, events, anomaly fossils and persistence snapshots. The `counterfactual_probe` function clones the world twice, removes one structure from the altered copy, advances both and compares metrics. The original probe used `World.fork()`, which clones *state* but does not automatically isolate external effects. This note describes verified source structure, not the original author's motivation.

### Why the change is needed

In `v0.2-primordial`, both forks share module-level `SAVE_DIR` and `SAVE_FILE`. At `CHECKPOINT_EVERY`, `transition()` calls `save()`, replacing the latest checkpoint with a fork; `event()` writes to the shared event journal and `preserve_fossil()` writes to the shared fossil directory. Thus a seemingly private experiment can contaminate the world that users expect to resume. This candidate's regression suite demonstrates the baseline checkpoint write in a temporary directory.

### Candidate design

`World._disk_writes_enabled` is a per-instance persistence permission, defaulting to `True`; `_can_write_disk()` treats old pickled instances without the new field as `True`, for backward compatibility. `World.fork(disk_writes_enabled=None)` preserves the source world's current permission unless explicitly overridden.

The counterfactual probe uses `world.fork(disk_writes_enabled=False)` for both experimental branches. In those branches, `event()` and `preserve_fossil()` still add to **in-memory** observer data, but do not write files; `transition()` skips automatic disk checkpoints; `save()` and `save_named()` fail explicitly rather than silently persisting an experimental universe. Ordinary worlds and ordinary forks retain previous save behaviour. No new dependencies or global monkeypatches are introduced.

**Security boundary:** Loading an untrusted checkpoint can execute code because checkpoints use `pickle`. The per-fork disk flag is not a sandbox or defence against untrusted pickle; do not use this candidate with untrusted checkpoint files.

## Engineering decision 001 — per-instance disk isolation

**Alternatives considered:** (A) change the module-level save directory temporarily; (B) run probes in a disposable directory; (C) keep a persistence guard per cloned world; (D) disable all persistence for all worlds.

**Chosen:** C. It remains local to each simulation, does not depend on changing process working directories, preserves normal save semantics, and explicitly rejects disk saves from private forks. A would risk global side effects if exceptions or concurrency intervene; B requires extra filesystem work and can still leak external writes; D removes expected checkpoint functionality.

**Trade-offs:** Adds a small state field and guards several I/O paths; any future disk output needs to respect the guard. Explicit `fork()` without an argument is still allowed to persist, maintaining compatibility but requiring future experimental callers to opt out. Reconsider a dedicated observer/storage abstraction if new disk effects proliferate, or a safer portable data format if untrusted-source interoperability becomes a product requirement.

**Evidence:** The candidate tests include legacy reproduction, checkpoint-and-journal byte comparisons, in-memory state equality, no fossil artifacts, and ordinary-save compatibility. The expanded six-test suite passed in [GitHub Actions run 42174740503](https://github.com/levelinglucy/Worldheart/actions/runs/42174740503), including a twelve-step multi-checkpoint horizon and seeded metric parity with the historical source. This does not establish safety for untrusted pickle checkpoints.

## Engineering decision 002 — cross-version CLI compatibility evidence

**Problem:** A fabricated old object with the new flag removed is not equivalent to a real legacy checkpoint. Python pickle stores class references such as `__main__.World`; changing how a script is imported can hide recovery failures.

**Options:** (A) keep only the simulated missing-field test; (B) import the historical script as a test module; (C) execute the unchanged v0.2 CLI as a separate process and resume with the candidate in another process. **Chosen:** C, with disposable directories and trusted locally generated fixtures. This exercises the actual script-entry-point class identity and normal save/recovery prompts, with no external checkpoint input.

**What is tested:** successful old-CLI resume, new save, no unexpected disk artifacts, an expected quit event, and exact candidate disk-artifact parity between matched control and counterfactual runs. The first test revision incorrectly required original and reserialized pickle streams to match byte-for-byte; [CI run 42180986385](https://github.com/levelinglucy/Worldheart/actions/runs/42180986385) failed that over-strict assumption in both cases. A pickle roundtrip need not be canonically byte-identical, so the test was corrected to compare **the same historical input under candidate control vs candidate probe**; [8/8 tests passed](https://github.com/levelinglucy/Worldheart/actions/runs/42181165055).

**Remaining uncertainty:** This is the published v0.2 CLI's generated format, not an in-the-wild saved game or Pythonista-specific test. The candidate still uses unsafe-for-untrusted-input `pickle`. A future portable structured checkpoint format would need a separate threat model and migration tests; see [recovery/rollback guidance](./docs/RECOVERY.md). Stable status remains unassigned.

## Roadmap and release gates

| Stage | Intended result | Acceptance | Status |
| --- | --- | --- | --- |
| v0.2 historical baseline | Preserve existing deterministic simulator | Original source remains unchanged | Preserved |
| v0.2.1-rc1 candidate | Disk-isolated counterfactual probe | Baseline issue reproduced; fork leaves disk and live state unchanged across 12 steps; ordinary saves and seeded dynamics pass | Merged on main, CI-validated candidate, not stable |
| v0.2.1 stable (proposed) | Safe recommended entry point | Exact candidate tests pass; authentic old-CLI recovery and rollback are documented; check a trusted user save/Pythonista if available; assess compatibility limits | Planned, not released |
| Future (optional) | Better portable checkpoints | Threat model, migration and replay equivalence tests | Idea only |

## Continuation checklist

1. **Completed in an isolated CI fixture:** run the unchanged v0.2 program as `__main__`, create a real-format checkpoint, then resume/re-save it through the candidate CLI; compare control with `c` probe. Both compatibility tests and all six existing tests passed.
2. **Pending:** check a trusted save from actual use (and Pythonista, if available) in a disposable directory, without ever loading untrusted pickle. Follow [the recovery and rollback guide](./docs/RECOVERY.md).
3. Recheck the precise candidate revision, review release limitations and decide whether to promote v0.2.1; preserve the old script and a recoverable backup.

**Design questions:** Should a dedicated persistence backend replace scattered file calls in a later feature version? Should saved games move from pickle to a versioned, validated structured format? Neither is required to make this specific probe fix.

**How to resume:** Start from the latest Worldheart branch/PR and check its exact head. Compare the candidate script with historical source, read the regression workflow, then update the roadmap and changelog only with verified outcomes.
