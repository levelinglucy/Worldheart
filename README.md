# Worldheart 🧫

A self-contained, deterministic computational ecology for Python and Pythonista. Byte-string structures interact with a mutable graph substrate; the observer measures outcomes without assigning built-in goals or semantics.

## Development summary

**Current release stage:** `v0.2.1-rc1` — **CI-validated candidate integrated on main, not a stable release**.  
**Stable historical source:** [Worldheart simulator](./Worldheart%20simulator) (`v0.2-primordial`, unchanged).  
**Current goal:** Preserve the original universe and its disk artifacts during counterfactual experiments.

**Latest candidate changes:** [worldheart_v02_1.py](./worldheart_v02_1.py) isolates probe forks from automatic checkpoint, event-log and anomaly-fossil writes; adds explicit refusal of manual saves from private forks. It includes regression tests and an automated test workflow. No original simulation source was overwritten.

**Latest compatibility evidence:** the historical v0.2 script generated an authentic CLI checkpoint, which the candidate successfully resumed, re-saved and probed in two separate-process tests; the full suite passed **8/8**. This is not a check of an in-the-wild saved game. [CI run](https://github.com/levelinglucy/Worldheart/actions/runs/42181165055).  
**Next steps:** (1) verify a separate, trusted checkpoint from ordinary use and Pythonista when available; (2) check recovery and rollback using the [guide](./docs/RECOVERY.md); (3) assess stable v0.2.1 only when evidence supports the release gate. [Candidate PR #1 was merged](https://github.com/levelinglucy/Worldheart/pull/1).  
**Known limitation:** Old checkpoint files use Python pickle and **must only be loaded from trusted sources**. This candidate does not change the save format.

[Full changelog](./CHANGELOG.md) · [Developer notes and roadmap](./DEV_NOTES.md) · [Trusted recovery/rollback guide](./docs/RECOVERY.md) · [Probe tests](./tests/test_probe_isolation.py) · [CLI compatibility tests](./tests/test_legacy_cli_recovery.py)

## Run

Download [`worldheart_v02_1.py`](./worldheart_v02_1.py) and run with Python 3 or Pythonista (standard library only):

```bash
python3 worldheart_v02_1.py
```

Use Enter to advance, `s` to save, `c` to run a private counterfactual probe, `n` to make a named snapshot, and `q` to save and quit. Data is stored in `WORLDHEART_V02_DATA/` relative to the working directory. Keep backups before switching versions; this is a release **candidate**, not an assurance of flawless persistence.

## What a probe actually measures

A probe forks the same seeded state into a control world and one with its oldest persistent structure removed; both advance for a bounded horizon. Differences in counts or diversity describe **model behaviour**, not a claim about consciousness, intent or life.

## Validation

```bash
python3 -m unittest discover -s tests -v
```

The original six-test probe suite uses temporary directories, reproduces checkpoint contamination and checks fork isolation and deterministic metrics. The new two-test CLI recovery suite creates an authentic historical checkpoint from the unchanged v0.2 program and checks candidate resume and counterfactual noninterference against a matched control. **8/8 passed** on [candidate branch CI](https://github.com/levelinglucy/Worldheart/actions/runs/42181165055). The workflow is defined in [`probe-regression.yml`](./.github/workflows/probe-regression.yml). See the changelog for what has actually passed; source changes alone are not proof of a successful run.
