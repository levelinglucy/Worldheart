# Worldheart 🧫

A self-contained, deterministic computational ecology for Python and Pythonista. Byte-string structures interact with a mutable graph substrate; the observer measures outcomes without assigning built-in goals or semantics.

## Development

The `v0.2.1-rc1` source candidate is integrated work, **not a published stable release**. Current roadmap, integration/validation/release distinctions and exact checks are in [developer notes](./DEV_NOTES.md) and [PR #4](https://github.com/levelinglucy/Worldheart/pull/4). The original `Worldheart simulator` remains unchanged.

## Run

Download [`worldheart_v02_1.py`](./worldheart_v02_1.py) and run with Python 3 or Pythonista (standard library only):

```bash
python3 worldheart_v02_1.py
```

Use Enter to advance, `s` to save, `c` to run a private counterfactual probe, `n` to make a named snapshot, and `q` to save and quit. **On the unmerged [PR #10 draft](https://github.com/levelinglucy/Worldheart/pull/10), a trusted same-directory relative symlink can name a direct, single-linked regular checkpoint:** loading and rolling saving follow its checked direct target while keeping the symlink itself intact. Absolute, chained, dangling or escaping symlinks, multiply-linked files, symlinked immediate parent directories and special checkpoint files are refused. An explicit new Genesis cannot overwrite a symlinked checkpoint: use a separate working directory. Keep the checkpoint folder private and quiescent while saving: this is not safe against adversarial concurrent changes, crash/power loss or untrusted pickle, and is not an integrated stable-main capability. For hard-link aliases, first preserve the original directory and explicitly copy the stopped world's trusted checkpoint into a new private, single-linked location. Data is stored in `WORLDHEART_V02_DATA/` relative to the working directory. Keep backups before switching versions; this is a release **candidate**, not an assurance of flawless persistence. If you answer **n** to the resume prompt, a subsequent save may replace the existing world: start in a separate working directory to preserve it. An existing **dangling symlink** at the latest checkpoint path is also treated as recovery evidence: it cannot silently start a new Genesis and be replaced. If an attempted resume **fails**, the candidate stops rather than silently starting Genesis; preserve the complete data directory and investigate a disposable copy. If a previous interrupted save left a `*.wh.tmp` file, **preserve both the `.tmp` and primary checkpoint**; this candidate refuses further saves to that target until the evidence is reviewed. Never delete or overwrite an unfamiliar `.tmp` merely to make saving work. **Named snapshots never replace an existing same-label/same-tick snapshot**; choose another label or advance the simulation on a collision. Named publication requires same-filesystem hard-link support and refuses without it (Pythonista compatibility unverified); normal rolling saves retain their existing replace behaviour. Observational fossils are staged as temporary JSON before exclusive hard-link publication to the first free `fossil_<tick>.json` or `fossil_<tick>_NNN.json`; existing fossils and symlinks are never overwritten, and incomplete new JSON is not published under a final fossil name. Unsupported hard-link filesystems refuse disk fossil publication (in-memory observations remain); an interrupted process may leave a `*.json.tmp` staging file. Observer JSONL events are best-effort: a symlink or special-file journal path is refused; if the OS lacks safe no-follow/nonblocking open flags, disk journaling is skipped while in-memory observations continue. Check the journal before relying on it as durable evidence. This does not establish power-loss durability or journal/fossil atomicity.

## What a probe actually measures

A probe forks the same seeded state into a control world and one with its oldest persistent structure removed; both advance for a bounded horizon. Differences in counts or diversity describe **model behaviour**, not a claim about consciousness, intent or life.

## Validation

```bash
python3 -m unittest discover -s tests -v
```

Tests exercise disposable worlds, saved-file noninterference, genuine historical CLI checkpoint compatibility, and failed-resume refusal. Exact revision-specific outcomes are in [PR #4](https://github.com/levelinglucy/Worldheart/pull/4); successful tests do not establish power-loss durability, safe untrusted pickle, or iPhone/Pythonista support.
