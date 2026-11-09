# Worldheart 🧫

A self-contained, deterministic computational ecology for Python and Pythonista. Byte-string structures interact with a mutable graph substrate; the observer measures outcomes without assigning built-in goals or semantics.

## Development

The `v0.2.1-rc1` source candidate is integrated work, **not a published stable release**. Current roadmap, integration/validation/release distinctions and exact checks are in [developer notes](./DEV_NOTES.md) and [PR #4](https://github.com/levelinglucy/Worldheart/pull/4). The original `Worldheart simulator` remains unchanged.

## Run

Download [`worldheart_v02_1.py`](./worldheart_v02_1.py) and run with Python 3 or Pythonista (standard library only):

```bash
python3 worldheart_v02_1.py
```

Use Enter to advance, `s` to save, `c` to run a private counterfactual probe, `n` to make a named snapshot, and `q` to save and quit. Data is stored in `WORLDHEART_V02_DATA/` relative to the working directory. Keep backups before switching versions; this is a release **candidate**, not an assurance of flawless persistence. If you answer **n** to the resume prompt, a subsequent save may replace the existing world: start in a separate working directory to preserve it. If an attempted resume **fails**, the candidate stops rather than silently starting Genesis; preserve the complete data directory and investigate a disposable copy. If a previous interrupted save left a `*.wh.tmp` file, **preserve both the `.tmp` and primary checkpoint**; this candidate refuses further saves to that target until the evidence is reviewed. Never delete or overwrite an unfamiliar `.tmp` merely to make saving work.

## What a probe actually measures

A probe forks the same seeded state into a control world and one with its oldest persistent structure removed; both advance for a bounded horizon. Differences in counts or diversity describe **model behaviour**, not a claim about consciousness, intent or life.

## Validation

```bash
python3 -m unittest discover -s tests -v
```

Tests exercise disposable worlds, saved-file noninterference, genuine historical CLI checkpoint compatibility, and failed-resume refusal. Exact revision-specific outcomes are in [PR #4](https://github.com/levelinglucy/Worldheart/pull/4); successful tests do not establish power-loss durability, safe untrusted pickle, or iPhone/Pythonista support.
