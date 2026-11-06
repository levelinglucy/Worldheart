# Worldheart changelog

Changes are listed newest first. A version number in this document does not by itself indicate a published stable release.

## 2026-11-06 — v0.2.1-rc1 (release candidate; validation pending final revision)

### Fixed — candidate
- Created `worldheart_v02_1.py` from the exact historical `Worldheart simulator` source. The original file is preserved unchanged.
- Isolated counterfactual fork disk output with `disk_writes_enabled=False` on both probe branches. Automatic checkpoints, event journaling and anomaly-fossil writes remain in memory for private forks.
- Refused explicit save attempts from disk-disabled forks; ordinary simulations and ordinary forks retain existing save functionality.
- Kept old pickled World instances readable through a backwards-compatible default when the new field is absent.

### Tests and documentation
- Added `tests/test_probe_isolation.py` with a temporary-directory demonstration of original checkpoint contamination and checks for candidate isolation, in-memory observer behaviour and normal persistence.
- Added the `.github/workflows/probe-regression.yml` standard-library CI job.
- Expanded the project overview and added [developer decisions, staged release goals and future continuation notes](./DEV_NOTES.md).

### Reason and trade-offs
The old probe could overwrite the user's latest checkpoint during automatic saves and append its private events to the live-world event log. Per-instance disk isolation was chosen over global save-directory switching to prevent accidental crossover without disrupting normal checkpoint behaviour. See [Engineering decision 001](./DEV_NOTES.md#engineering-decision-001--per-instance-disk-isolation).

### Validation and known limits
Initial regression job on the source/test/workflow candidate commit passed: [GitHub Actions run 42174478089](https://github.com/levelinglucy/Worldheart/actions/runs/42174478089). **Final candidate revision is not yet certified**; re-run/confirm after all documentation changes. The suite proves only the specific cases exercised. The pickle checkpoint format remains unsafe for untrusted files and is outside this patch.

### Release next actions
Confirm checks on the final candidate, review branch diff and assess promotion criteria before calling v0.2.1 stable. Historical baseline is recoverable via Git history and its unchanged file. No stable version or GitHub Release has been published by this entry.

## Earlier history

- `v0.2-primordial`: Historical source `Worldheart simulator`, original filename and content preserved. Its design includes deterministic seeded graph simulation, observer metrics, anomalies and filesystem snapshots. Historical motivation beyond the code is not inferred.
