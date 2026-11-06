# Worldheart — trusted checkpoint recovery

## Development summary

**Stage:** `v0.2.1-rc1`, candidate; stable promotion remains pending.  
**Goal:** resume a historical `v0.2-primordial` world without losing its saved state or allowing a counterfactual experiment to change its files.  
**Latest check:** two isolated, end-to-end CLI tests generated checkpoints by executing the *unchanged* historical script as `__main__`, then resumed them with the candidate. The full suite passed 8/8 in [GitHub Actions](https://github.com/levelinglucy/Worldheart/actions/runs/42181165055).  
**Next:** validate a separately backed-up, trusted save from normal use and, where available, Pythonista before designating a stable release.

[README](../README.md) · [Developer notes](../DEV_NOTES.md) · [Changelog](../CHANGELOG.md)

## Preserve first

1. **Do not open a checkpoint received from someone else.** Both versions use Python `pickle`; loading untrusted data can execute code. The envelope hash checks accidental alteration, not authenticity.
2. With Worldheart stopped, copy the complete `WORLDHEART_V02_DATA/` directory (not just `worldheart_v02_latest.wh`) into a separate, trusted backup location. Keep the original file and folder untouched.
3. In an empty **test working directory**, place a copy of the saved data folder. Run `python3 worldheart_v02_1.py` from there and select `Y` to resume. Confirm the displayed seed, transition count and observer metrics against known prior values.
4. If desired, run `c` for a private probe. It should not alter the checkpoint or event/fossil files; use file comparisons or hashes if you are checking this rigorously. Save and exit only **within the test copy**.
5. Continue actual play only after you have verified recovery. Keep the original backup in case a later regression appears. Never commit personal checkpoints or their pickle payloads to a public repository.

The automated tests use an authentic *generated* old CLI checkpoint, including the `__main__.World` pickle class reference. They do **not** prove that every historical Python/Pythonista version or a real individual's save can be recovered. They also do not make `pickle` safe for untrusted files.

## Rollback

Keep the unmodified historical [`Worldheart simulator`](../Worldheart%20simulator) and the untouched backed-up `WORLDHEART_V02_DATA/` copy. To return to historical behaviour, stop the candidate, restore **your own trusted backup** into a separate working directory and run the historical script there. Do not assume an already re-saved candidate checkpoint is backwards compatible without separately verifying it. Keep the candidate data files and baseline files apart.

## Verification notes

The CI scenario runs the original file as a separate program to produce its real CLI format, then launches the candidate in separate programs with and without `c`. It checks recovery, metadata, absence of unexpected artifacts, an expected quit-checkpoint event, and **identical final disk artifacts between control and counterfactual branches**. Pickle byte streams need not be identical after a simple load/resave across versions, so those are compared against a matched control rather than incorrectly assuming canonical serialization.

No in-the-wild checkpoint or device-specific Pythonista save has been loaded by this project test. If a trusted saved world fails in the test copy, preserve the failed copy and diagnostic message, leave the original backup untouched, and do not promote this candidate to stable until the cause is understood.
