# Worldheart changelog

Changes are listed newest first. A version number in this document does not by itself indicate a published stable release.

## Unreleased — safe observational event journal paths

- Avoid following final-component event-journal symlinks or waiting on FIFO writers; only append to checked regular-file descriptors with no-follow/nonblocking OS guards, retaining in-memory observations when disk logging is unavailable.
- New journals are created owner-only; existing regular-file append and save formats remain. Five synthetic checks cover ordinary append, symlink preservation, both FIFO behaviours and guard-unavailable fallback. No parent-directory, hard-link, concurrent append, durability or iPhone guarantee. See [decision 009](./DEV_NOTES.md#engineering-decision-009--make-observer-journal-append-nonblocking-and-no-follow) and [PR #9](https://github.com/levelinglucy/Worldheart/pull/9).

## Unreleased — complete-only observational fossil publication

- Serialize each new fossil as a unique temporary JSON file before exclusively linking a fully written document to a free final name; keep prior fossils and occupied symlinks untouched, with in-memory evidence retained on I/O failure.
- Add two synthetic failure-injection regressions for incomplete serialization and unavailable hard links. No automatic fallback to unsafe writes; interrupted processes may leave staging evidence and power-loss, event-journal transactions and device compatibility remain unverified. See [decision 008](./DEV_NOTES.md#engineering-decision-008--complete-only-observational-fossil-publication) and [PR #8](https://github.com/levelinglucy/Worldheart/pull/8).

## Unreleased — observational fossil collision protection

- Retained distinct anomaly fossils from the same tick or different seeded universes by allocating an exclusive `fossil_<tick>[_NNN].json` filename; occupied files and symlinks are never truncated or followed.
- Added three test-first synthetic collision cases; normal first-file naming and private-fork isolation stay intact. See [decision 007](./DEV_NOTES.md#engineering-decision-007--preserve-colliding-observational-fossils) and [PR #7](https://github.com/levelinglucy/Worldheart/pull/7) for validation and trade-offs.
- Fossil publication remains best-effort and not crash-atomic, and iPhone/filesystem behaviour is unverified; this is still an unreleased source candidate.

## Unreleased — dangling latest-checkpoint path preservation

- A broken symlink at the rolling latest-checkpoint path now enters failed-recovery refusal instead of silently allowing Genesis and subsequent replacement of the link; legitimate missing paths and healthy resume are unchanged.
- Added a synthetic, disposable CLI regression reproducing the predecessor's destructive path; see [decision 006](./DEV_NOTES.md#engineering-decision-006--treat-a-dangling-latest-checkpoint-link-as-existing-evidence) and the associated PR for exact fixed-revision checks. Historical source and trusted-user data remain untouched.

## Unreleased — named-snapshot collision protection

- Named saves now publish only when the label/tick filename does not already exist, preserving older snapshot bytes and symlink destinations; normal rolling saves still replace `latest.wh`.
- Named publication uses an exclusive hard link from a complete staged file; filesystems without hard-link support refuse safely. A CLI collision reports an error without crashing. Three synthetic regressions cover collisions, symlinks and valid distinct ticks.
- This is a newly discovered data-integrity gate for the source candidate, not a stable release or an iPhone/power-loss certification. See [decision 005](./DEV_NOTES.md#engineering-decision-005--protect-named-snapshot-history).

## Unreleased — failed-resume checkpoint preservation

- Prevented failed checkpoint recovery from falling through to Genesis, where a normal quit/save could overwrite the checkpoint that failed to load; preserves existing disk evidence and exits nonzero with recovery guidance.
- Made the explicit start-new choice warn that saving can replace the existing world; two isolated CLI regression fixtures (malformed JSON and bad integrity hash) reproduce the predecessor overwrite without loading a pickle. See [PR #4](https://github.com/levelinglucy/Worldheart/pull/4) for exact revision and test evidence.
- Kept ordinary intentional Genesis and valid legacy checkpoint resume behaviour. The historical script is unchanged; no trusted user-save, device, power-loss or multiwriter certification is implied.

## Unreleased — interrupted-checkpoint evidence protection

- Fixed an additional normal-save integrity defect: a stale `*.wh.tmp` now blocks saving rather than being silently overwritten, whether or not the primary checkpoint exists. The historical `Worldheart simulator` remains unchanged.
- Added three disposable-directory tests covering stale temporary files and normal save/load compatibility. Test-first failures are documented in [red CI](https://github.com/levelinglucy/Worldheart/actions/runs/42351103775); exact post-fix verification belongs in the associated pull request.
- Kept the existing pickle envelope and replacement sequence. A refusal requires owner review of the temp and primary files; real power-loss durability, interprocess writer coordination and iPhone support remain unverified. See [decision 003](./DEV_NOTES.md#engineering-decision-003--preserve-interrupted-checkpoint-temp-evidence).

## 2026-11-06 — v0.2.1-rc1 recovery follow-up (candidate, not stable)

### Tests
- Added [two end-to-end historical CLI recovery tests](./tests/test_legacy_cli_recovery.py). They execute the unchanged v0.2 script as a real program to create a genuine old-format `__main__.World` pickle checkpoint in a temporary directory, then execute the v0.2.1 candidate to resume and re-save it.
- The probe test compares the exact same legacy fixture under candidate **control** and candidate **counterfactual probe**, verifying matching final disk artifacts and no additional probe journal/fossil outputs; the normal quit adds one expected checkpoint event.
- **8/8 tests passed** in [GitHub Actions run 42181165055](https://github.com/levelinglucy/Worldheart/actions/runs/42181165055). This validates generated legacy CLI saves only, not actual user/Pythonista checkpoints.

### Developer documentation
- Added [trusted recovery and rollback instructions](./docs/RECOVERY.md), including copy-first practice, checkpoint trust boundary, disposable test directory and fallback to the historical script.
- Updated the summary, roadmap and [decision 002](./DEV_NOTES.md#engineering-decision-002--cross-version-cli-compatibility-evidence) with explicit release limitations and continuation steps.

### Correction and release status
- The initial recovery test compared old and new pickled byte streams directly and failed in [CI run 42180986385](https://github.com/levelinglucy/Worldheart/actions/runs/42180986385). Cross-version pickle reserialization is not guaranteed to be byte-canonical; the final test compares matched candidate control and probe runs instead. This correction does **not** relax the actual probe noninterference criterion.
- **No stable release/tag** is created here. Testing a separately preserved, trusted real-use save and environment-specific behaviour remains a useful release gate; do not load untrusted pickle.

## 2026-11-06 — v0.2.1-rc1 (CI-validated candidate, not stable)

### Fixed — candidate
- Created `worldheart_v02_1.py` from the exact historical `Worldheart simulator` source. The original file is preserved unchanged.
- Isolated counterfactual fork disk output with `disk_writes_enabled=False` on both probe branches. Automatic checkpoints, event journaling and anomaly-fossil writes remain in memory for private forks.
- Refused explicit save attempts from disk-disabled forks; ordinary simulations and ordinary forks retain existing save functionality.
- Kept old pickled World instances readable through a backwards-compatible default when the new field is absent.

### Tests and documentation
- Added `tests/test_probe_isolation.py` with a temporary-directory demonstration of original checkpoint contamination and checks for candidate isolation across repeated save boundaries, in-memory observer behaviour, seeded metric parity and normal persistence.
- Added the `.github/workflows/probe-regression.yml` standard-library CI job.
- Expanded the project overview and added [developer decisions, staged release goals and future continuation notes](./DEV_NOTES.md).

### Reason and trade-offs
The old probe could overwrite the user's latest checkpoint during automatic saves and append its private events to the live-world event log. Per-instance disk isolation was chosen over global save-directory switching to prevent accidental crossover without disrupting normal checkpoint behaviour. See [Engineering decision 001](./DEV_NOTES.md#engineering-decision-001--per-instance-disk-isolation).

### Validation and known limits
The expanded suite passed **6/6 tests** in [GitHub Actions run 42174740503](https://github.com/levelinglucy/Worldheart/actions/runs/42174740503), checking a 12-step probe across repeated save boundaries and seeded metric parity with v0.2. [PR #1](https://github.com/levelinglucy/Worldheart/pull/1) merged the candidate on 2026-11-06 (squash commit [8c626b2](https://github.com/levelinglucy/Worldheart/commit/8c626b2edd1dfb2424aff9ea60623a1b1cec945b)). The candidate remains **not promoted to stable**; the suite proves only the specific cases exercised. The pickle checkpoint format remains unsafe for untrusted files and is outside this patch.

### Release next actions
Check real historical checkpoint recovery, document migration/rollback and assess promotion criteria before calling v0.2.1 stable. Historical baseline is recoverable via Git history and its unchanged file. No stable version or GitHub Release has been published by this entry.

## Earlier history

- `v0.2-primordial`: Historical source `Worldheart simulator`, original filename and content preserved. Its design includes deterministic seeded graph simulation, observer metrics, anomalies and filesystem snapshots. Historical motivation beyond the code is not inferred.
