# Worldheart — trusted checkpoint recovery

## Status

`v0.2.1-rc1` remains a source candidate, not a verified stable release. Current goal, precise integration/validation state and decision history live in [DEV_NOTES.md](../DEV_NOTES.md) and [PR #4](https://github.com/levelinglucy/Worldheart/pull/4). Valid historical CLI saves were tested in disposable copies; no real-use checkpoint or iPhone/Pythonista save has been verified.

## Preserve first

1. **Do not open a checkpoint received from someone else.** Both versions use Python `pickle`; loading untrusted data can execute code. The envelope hash checks accidental alteration, not authenticity.
2. With Worldheart stopped, copy the complete `WORLDHEART_V02_DATA/` directory (not just `worldheart_v02_latest.wh`) into a separate, trusted backup location. Keep the original file and folder untouched.
3. In an empty **test working directory**, place a copy of the saved data folder. Run `python3 worldheart_v02_1.py` from there and select `Y` to resume. Confirm the displayed seed, transition count and observer metrics against known prior values.
4. If desired, run `c` for a private probe. It should not alter the checkpoint or event/fossil files; use file comparisons or hashes if you are checking this rigorously. Save and exit only **within the test copy**.
5. Continue actual play only after you have verified recovery. Keep the original backup in case a later regression appears. Never commit personal checkpoints or their pickle payloads to a public repository.

The automated tests use an authentic *generated* old CLI checkpoint, including the `__main__.World` pickle class reference. They do **not** prove that every historical Python/Pythonista version or a real individual's save can be recovered. They also do not make `pickle` safe for untrusted files.

## Optional safe metadata check (no unpickling)

To examine a checkpoint envelope without trying to start the world, run `python3 inspect_checkpoint.py WORLDHEART_V02_DATA/worldheart_v02_latest.wh` on a **copy** in a controlled directory. This reads and checks the outer JSON envelope and its BLAKE2b-64 checksum, but neither decompresses the payload nor calls `pickle.loads`. Exit status 0 means the checksum matches, 1 means it does not, and 2 means the file is malformed, an unsafe path type, over 16 MiB, or cannot be inspected safely. The original file is not changed. A checksum match proves neither authenticity nor safe recovery. It also does not establish that the compressed inner pickle can be restored. The inspector requires OS no-follow/nonblocking flags and direct single-linked regular files; on unsupported devices it refuses rather than relaxing this gate. Do not use a checksum match as permission to load an untrusted checkpoint.

## If resuming fails

A dangling symlink occupying the latest-checkpoint filename counts as existing evidence rather than an empty slot: preserve it and investigate its target on a disposable copy. The candidate now stops with a nonzero exit status after a failed attempted resume; it does **not** offer a new Genesis that could overwrite the checkpoint during an ordinary save. Preserve the entire data folder, including `*.tmp`, journal and fossil files, even if the primary looks corrupt. Test recovery only on a trusted copy in a separate working directory. An explicit **n** at the resume prompt still starts anew; saving that new world may replace the prior checkpoint. Choose a **clean working directory** if you want to keep both histories.

Do not open untrusted checkpoints: the existing pickle format can execute code on load.

## Rollback

Keep the unmodified historical [`Worldheart simulator`](../Worldheart%20simulator) and the untouched backed-up `WORLDHEART_V02_DATA/` copy. To return to historical behaviour, stop the candidate, restore **your own trusted backup** into a separate working directory and run the historical script there. Do not assume an already re-saved candidate checkpoint is backwards compatible without separately verifying it. Keep the candidate data files and baseline files apart.

## Verification notes

The CI scenario runs the original file as a separate program to produce its real CLI format, then launches the candidate in separate programs with and without `c`. It checks recovery, metadata, absence of unexpected artifacts, an expected quit-checkpoint event, and **identical final disk artifacts between control and counterfactual branches**. Pickle byte streams need not be identical after a simple load/resave across versions, so those are compared against a matched control rather than incorrectly assuming canonical serialization.

No in-the-wild checkpoint or device-specific Pythonista save has been loaded by this project test. If a trusted saved world fails in the test copy, preserve the failed copy and diagnostic message, leave the original backup untouched, and do not promote this candidate to stable until the cause is understood.
