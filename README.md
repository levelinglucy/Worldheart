# Worldheart 🧫

A self-contained, deterministic computational ecology for Python and Pythonista. Byte-string structures interact with a mutable graph substrate; the observer measures outcomes without assigning built-in goals or semantics.

## Development summary

**Current release stage:** `v0.2.1-rc1` — **candidate, not a verified stable release**.  
**Stable historical source:** [Worldheart simulator](./Worldheart%20simulator) (`v0.2-primordial`, unchanged).  
**Current goal:** Preserve the original universe and its disk artifacts during counterfactual experiments.

**Latest candidate changes:** [worldheart_v02_1.py](./worldheart_v02_1.py) isolates probe forks from automatic checkpoint, event-log and anomaly-fossil writes; adds explicit refusal of manual saves from private forks. It includes regression tests and an automated test workflow. No original simulation source was overwritten.

**Next steps:** (1) confirm the legacy failure and candidate fix in CI; (2) independently check longer probe horizons and checkpoint restoration; (3) decide whether to promote the candidate as the preferred release.  
**Known limitation:** Old checkpoint files use Python pickle and **must only be loaded from trusted sources**. This candidate does not change the save format.

[Full changelog](./CHANGELOG.md) · [Developer notes, decisions and roadmap](./DEV_NOTES.md) · [Regression tests](./tests/test_probe_isolation.py)

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

The suite uses temporary directories, demonstrates the original checkpoint contamination, and checks that the new probe leaves checkpoint bytes, event logs and the live world's in-memory state unchanged. The GitHub Actions job is defined in [`probe-regression.yml`](./.github/workflows/probe-regression.yml). See the changelog for what has actually passed; source changes alone are not proof of a successful run.
