# Worldheart — developer notes

## Development summary

**Goal:** Preserve both the live simulation and its recoverable disk evidence when probes or checkpoint recovery fail. **Candidate:** `v0.2.1-rc1`, integrated source work but not a published stable release. The historical `Worldheart simulator` is preserved.
**Integration/validation/release:** [PR #4](https://github.com/levelinglucy/Worldheart/pull/4) holds the exact revision and results for the failed-resume refusal. Prior probe isolation, historical CLI compatibility and stale-temp refusal are documented below and in their preceding PRs. No stable tag/release or trusted real-use/iPhone recovery proof is asserted.
**Latest meaningful work:** If an existing checkpoint cannot be loaded, the candidate exits without beginning Genesis; opting out of resume is warned as a potentially destructive choice. See [decision 004](#engineering-decision-004--abort-on-failed-checkpoint-recovery).
**Next steps:** Confirm current test evidence and main integration; keep a trusted recovery/rollback copy; assess stable promotion only with documented scope. No personal-device testing is required for unrelated engineering progress.
[Changelog](./CHANGELOG.md) · [README](./README.md) · [Trusted recovery/rollback guide](./docs/RECOVERY.md) · [Tests](./tests/test_failed_recovery_refusal.py).

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

## Engineering decision 003 — preserve interrupted checkpoint temp evidence

**Confirmed failure:** The candidate's normal `save()` used a fixed `<checkpoint>.tmp` path opened in truncating write mode. After an interrupted save, the next ordinary save silently destroyed the old temporary bytes, potentially losing the only recoverable recent state. Test-first synthetic cases for both an existing primary and an absent primary failed on [the pre-fix Actions run](https://github.com/levelinglucy/Worldheart/actions/runs/42351103775). Historical source and real user checkpoints were not touched.

**Choice:** Keep the existing envelope format and replace the temporary-file open with exclusive creation (`open(..., "x")`). If an unresolved temp already exists, raise an informative `FileExistsError`, without changing either saved file or recording a successful checkpoint event. The normal create-and-replace path remains compatible; see `tests/test_stale_checkpoint_temp.py`.

**Alternatives:** Truncating/reusing the temp discards evidence; silently deleting it guesses which history matters; a random temp name would avoid the collision but could permit a new checkpoint to supersede a recoverable interrupted write. An explicit refusal is the smallest conservative behaviour for this candidate.

**Limits:** Exclusive creation is not a cross-process transaction lock. A save can still leave a partial new temp on I/O or crash; neither `fsync` durability nor real power-loss recovery is established, and independent writers are not coordinated. The format still uses trusted-only pickle. Copy and inspect saved evidence before any manual recovery; do not promote a `.tmp` automatically. Revisit with a tested, versioned recovery design rather than guessing freshness.

## Engineering decision 004 — abort on failed checkpoint recovery

**Confirmed defect:** When an existing primary checkpoint had malformed JSON or a mismatched integrity hash, the candidate printed a recovery error and silently offered Genesis. Accepting the seed and then saving on `q` replaced the original checkpoint and appended new-world events. Two isolated CLI tests first reproduced this exact overwrite on [red CI 42616290002](https://github.com/levelinglucy/Worldheart/actions/runs/42616290002). No real checkpoint or untrusted pickle was used.

**Choice:** On a failed attempted resume, print a recovery error and preservation/clean-directory instructions, then exit nonzero before Genesis or any subsequent save. Keep the explicit `n` path for users deliberately starting anew, but warn it can replace the old world on saving. Do not rename, delete, parse again, or auto-repair the suspect checkpoint. The historical program is untouched.

**Alternatives and trade-offs:** Continuing with a new world is convenient but can erase recoverable evidence; an automatic backup might itself overwrite or fail; automatic temp promotion would guess recovery state. Refusing this particular run is deliberately conservative, but requires the user to investigate or choose a separate working directory. This prevents one accidental overwrite path; it does **not** solve concurrent writers, crash durability, unsafe untrusted pickle, or every possible corrupt-world scenario. Reconsider with a versioned recovery manager and tested explicit replacement workflow.

## Roadmap and release gates

| Stage | Intended result | Acceptance | Status |
| --- | --- | --- | --- |
| v0.2 historical baseline | Preserve existing deterministic simulator | Original source remains unchanged | Preserved |
| v0.2.1-rc1 candidate | Disk-isolated counterfactual probe | Baseline issue reproduced; fork leaves disk and live state unchanged across 12 steps; failed CLI resume refuses fallback genesis; ordinary saves and seeded dynamics pass | Merged on main, CI-validated candidate, not stable |
| v0.2.1 stable (proposed) | Safe recommended entry point | Exact candidate tests pass; authentic old-CLI recovery and rollback are documented; check a trusted user save/Pythonista if available; assess compatibility limits | Planned, not released |
| Future (optional) | Better portable checkpoints | Threat model, migration and replay equivalence tests | Idea only |

## Continuation checklist

1. **Completed in an isolated CI fixture:** run the unchanged v0.2 program as `__main__`, create a real-format checkpoint, then resume/re-save it through the candidate CLI; compare control with `c` probe. Both compatibility tests and all six existing tests passed.
2. **Pending:** check a trusted save from actual use (and Pythonista, if available) in a disposable directory, without ever loading untrusted pickle. Follow [the recovery and rollback guide](./docs/RECOVERY.md).
3. Recheck the precise candidate revision, review release limitations and decide whether to promote v0.2.1; preserve the old script and a recoverable backup.

**Design questions:** Should a dedicated persistence backend replace scattered file calls in a later feature version? Should saved games move from pickle to a versioned, validated structured format? Neither is required to make this specific probe fix.

**How to resume:** Start from the latest Worldheart branch/PR and check its exact head. Compare the candidate script with historical source, read the regression workflow, then update the roadmap and changelog only with verified outcomes.
