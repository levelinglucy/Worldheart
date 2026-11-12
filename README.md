# Worldheart 🧫

A self-contained, deterministic computational ecology for Python and Pythonista. Byte-string structures interact with a mutable graph substrate; the observer measures outcomes without assigning built-in goals or semantics.

## Development

The `v0.2.1-rc1` source candidate is integrated work, **not a published stable release**. Current roadmap, integration/validation/release distinctions and exact checks are in [developer notes](./DEV_NOTES.md) and [PR #4](https://github.com/levelinglucy/Worldheart/pull/4). The original `Worldheart simulator` remains unchanged.

## Run

Download [`worldheart_v02_1.py`](./worldheart_v02_1.py) and run with Python 3 or Pythonista (standard library only):

```bash
python3 worldheart_v02_1.py
```

Use Enter to advance, `s` to save, `c` to run a private counterfactual probe, `n` to make a named snapshot, and `q` to save and quit. Data is stored in `WORLDHEART_V02_DATA/` relative to the working directory. Keep backups before switching versions; this is a release **candidate**, not an assurance of flawless persistence. If you answer **n** to the resume prompt, a subsequent save may replace the existing world: start in a separate working directory to preserve it. An existing **dangling symlink** at the latest checkpoint path is also treated as recovery evidence: it cannot silently start a new Genesis and be replaced. If an attempted resume **fails**, the candidate stops rather than silently starting Genesis; preserve the complete data directory and investigate a disposable copy. If a previous interrupted save left a `*.wh.tmp` file, **preserve both the `.tmp` and primary checkpoint**; this candidate refuses further saves to that target until the evidence is reviewed. Never delete or overwrite an unfamiliar `.tmp` merely to make saving work. **Named snapshots never replace an existing same-label/same-tick snapshot**; choose another label or advance the simulation on a collision. Named publication requires same-filesystem hard-link support and refuses without it (Pythonista compatibility unverified); normal rolling saves retain their existing replace behaviour. Observational fossils are staged as temporary JSON before exclusive hard-link publication to the first free `fossil_<tick>.json` or `fossil_<tick>_NNN.json`; existing fossils and symlinks are never overwritten, and incomplete new JSON is not published under a final fossil name. Unsupported hard-link filesystems refuse disk fossil publication (in-memory observations remain); an interrupted process may leave a `*.json.tmp` staging file. Observer JSONL events are best-effort: a symlink or special-file journal path is refused; if the OS lacks safe no-follow/nonblocking open flags, disk journaling is skipped while in-memory observations continue. Check the journal before relying on it as durable evidence. This does not establish power-loss durability or journal/fossil atomicity.

## Read-only envelope inspection

Before deciding whether to resume a **trusted** checkpoint, you can inspect its outer JSON envelope without decompressing or unpickling it:

```bash
python3 inspect_checkpoint.py WORLDHEART_V02_DATA/worldheart_v02_latest.wh
```

The utility returns JSON metadata (version, seed, tick, payload length and BLAKE2b checksum comparison), with exit codes 0 = checksum matches, 1 = mismatch, 2 = refused/invalid input. It makes no writes, refuses symlinks, multiply linked files, nonregular inputs and files above 16 MiB, and requires no-follow/nonblocking OS flags. A checksum match **does not authenticate the sender or establish safe pickle loading, semantic validity or recoverability**. Parent-directory path substitution and concurrent mutations are not fully defended; inspect copies in a controlled private directory. Pythonista flag support remains unverified. See [recovery guidance](./docs/RECOVERY.md).

For cautious review of **two** preserved checkpoint candidates (for example, a
rolling primary and an interrupted-save temporary file), use:

```bash
python3 inspect_checkpoint.py WORLDHEART_V02_DATA/worldheart_v02_latest.wh --against WORLDHEART_V02_DATA/worldheart_v02_latest.wh.tmp
```

This reads each envelope independently and does not change either file. If both
checksums match and the saved version and seed agree, it reports the signed tick
difference and which **recorded tick** is higher. Otherwise it declines to rank
them. A mismatch yields exit code 1; malformed/unreadable input yields 2 with
no partial JSON report. **Neither a higher tick nor matching seed/version proves
a newer or recoverable world**; never promote, delete or load a candidate on
this report alone. Keep both originals and inspect copies in a trusted directory.
The single-file JSON output and exit codes remain unchanged.

## What a probe actually measures

A probe forks the same seeded state into a control world and one with its oldest persistent structure removed; both advance for a bounded horizon. Differences in counts or diversity describe **model behaviour**, not a claim about consciousness, intent or life.

## Validation

```bash
python3 -m unittest discover -s tests -v
```

Tests exercise disposable worlds, saved-file noninterference, genuine historical CLI checkpoint compatibility, and failed-resume refusal. Exact revision-specific outcomes are in [PR #4](https://github.com/levelinglucy/Worldheart/pull/4); successful tests do not establish power-loss durability, safe untrusted pickle, or iPhone/Pythonista support.
