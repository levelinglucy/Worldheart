# Worldheart — developer notes

## Development summary

**Goal:** Preserve live-world checkpoints and recoverable observational evidence without misleading or unsafe filesystem side effects. **Candidate:** `v0.2.1-rc1` source work; historical `Worldheart simulator` unchanged.
**Integration:** Observer journal safety [PR #9](https://github.com/levelinglucy/Worldheart/pull/9) is merged on main at `8bc08db3`. Checkpoint-path refusal is **proposed, not merged**, on [PR #10](https://github.com/levelinglucy/Worldheart/pull/10); its aliases/special-file compatibility decision remains reviewable.
**Validation:** [PR #9 exact-main CI](https://github.com/levelinglucy/Worldheart/actions/runs/42761973300) passed 27/27 on hosted Ubuntu. Four new checkpoint-path tests failed on [predecessor red CI](https://github.com/levelinglucy/Worldheart/actions/runs/42775492665) and passed with 31/31 tests at [source/test candidate `7b3672be`](https://github.com/levelinglucy/Worldheart/actions/runs/42775679340); final documentation-head checks remain revision-specific.
**Release:** Untagged and unpublished. Device-specific alias/regular-file semantics, concurrent path swaps, journal durability, multiwriter coordination, power loss and safe handling of untrusted pickle remain unverified.
**Next:** Dylan requested safe preservation of deliberate checkpoint aliases on 2026-11-13. PR #10's refusal-only implementation is not approved for merging as-is. See investigation 011 and the disposable filesystem spike; implement and validate any narrower safe policy on a reviewable branch before reconsidering integration.

[Changelog](./CHANGELOG.md) · [README](./README.md) · [Trusted recovery/rollback guide](./docs/RECOVERY.md) · [Journal path regressions](./tests/test_journal_path_safety.py).

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

## Engineering decision 005 — protect named snapshot history

**Confirmed defect:** Named snapshot filenames include only a cleaned label and tick. Two different universes at the same tick can use the same label, and the existing `os.replace` silently overwrote the older named snapshot; an existing symlink could also be replaced. Disposable test-first fixtures reproduced both failures. This is independent of the previously repaired failed-resume path.

**Decision:** Keep replace semantics for the rolling `latest.wh` checkpoint, but publish named snapshots with an atomic exclusive hard link from a completely written temp file. An already occupied destination (including a symlink) refuses without changing its bytes; a failed link removes only the staging temp created by this attempt. If hard links are unsupported, refuse rather than risk replacing evidence. The CLI reports refusal without exiting unexpectedly. The historical source remains unchanged.

**Trade-offs and limits:** This requires same-filesystem hard-link support; iPhone/Pythonista and specific filesystems remain unverified. It does not make the rolling checkpoint immutable, authenticate `pickle`, establish power-loss durability, or coordinate independent writers beyond exclusive final-name creation. New safety evidence added this gate after the earlier recovery candidate was integrated; no earlier tests or release claims are retroactively reclassified.

## Engineering decision 006 — treat a dangling latest checkpoint link as existing evidence

**Confirmed failure:** The candidate's boot choice tested the rolling checkpoint path with `os.path.exists`, which follows links. A dangling `latest.wh` symlink therefore appeared absent. The CLI offered Genesis, and saving the new world replaced the symlink. A disposable, synthetic subprocess fixture reproduced this at baseline main `158aadef`: [test-first CI 42644786690](https://github.com/levelinglucy/Worldheart/actions/runs/42644786690) failed the new preservation assertion while the previous 16 tests passed.

**Decision:** Use `os.path.lexists` only for detecting whether the latest path is occupied. An existing-but-broken link proceeds through the normal attempted recovery path, which fails closed with a clear message and nonzero exit. No new Genesis is offered and neither the link nor journal is modified. Genuine missing paths still permit Genesis; healthy existing checkpoint and symlink targets kept their previous load behaviour **at the time of PR #6**. [Proposed decision 010](#engineering-decision-010--refuse-checkpoint-aliases-and-blocking-special-files) supersedes symlink loading on its own branch. Historical v0.2 source remains untouched.

**Trade-offs:** A link pointing to a currently unavailable location prevents starting a new world in that directory until the user consciously preserves/moves that evidence, rather than risking automatic erasure. This is not symlink authentication, directory traversal hardening, safe untrusted pickle handling, or power-loss certification. Revisit if deliberate link-based storage needs a separate recovery UI.

## Engineering decision 007 — preserve colliding observational fossils

**Confirmed predecessor behaviour:** `preserve_fossil()` wrote `fossil_<tick>.json` using truncating text mode. Different seeded worlds and multiple anomalies at the same tick silently replaced earlier fossil records; an existing dangling symlink could be followed and its target created. Three disposable test-first cases failed on [red CI 42654009805](https://github.com/levelinglucy/Worldheart/actions/runs/42654009805), while the prior 17 tests remained green.

**Decision:** Use exclusive `x` creation for the existing tick name, followed by `_001`, `_002` and so on for occupied names, up to 999 alternatives. The operation never truncates an occupied destination, including symlinks. Normal first-fossil naming and observational JSON contents are unchanged; in-memory fossil retention and private-fork disk isolation remain. The unchanged historical simulator is not modified.

**Alternatives and trade-offs:** Refusing every collision would preserve older data but discard a new fossil; random filenames would avoid deterministic, phone-readable chronology; exclusive suffix allocation makes both histories inspectable. Filesystem failures and exhaustion still leave the in-memory fossil but may fail to publish on disk, as fossil I/O is best-effort. Direct exclusive writes can leave a partial *new* fossil after interrupted I/O and are not crash-atomic or `fsync` guaranteed. Independent writers can race to *different* suffixes without replacing each other's records, but other observer operations, including the event journal, are not transactionally coordinated. Reconsider a complete-only artifact writer alongside a versioned storage redesign.

## Engineering decision 008 — complete-only observational fossil publication

**Confirmed predecessor failure:** The collision-safe writer opened the final fossil filename with exclusive `x` and then streamed `json.dump` into it. An interrupted serialization left syntactically incomplete JSON at a filename that appears to be a real fossil. Two disposable injected-failure cases in [test-first CI 42664345362](https://github.com/levelinglucy/Worldheart/actions/runs/42664345362) failed on the previous source while the earlier 20 tests passed. No real user files or historical source were modified.

**Decision:** Write the fossil to a unique, private `*.json.tmp` staging file in the same data directory, close it successfully, then publish by `os.link(stage, final)`. The hard-link operation creates a complete final name exclusively, preserving earlier fossils and occupied symlinks and allowing bounded suffix allocation. Always try to remove the staging path created by this attempt, including on serialization or publication failure. Retain in-memory observer history when disk persistence fails.

**Alternatives:** Direct exclusive final-name writes can expose partial JSON. `os.replace` is atomic for visibility but can overwrite an earlier fossil. A second contents-copy step after serialization is not atomic. The existing named-checkpoint pattern already uses exclusive hard-link publication, so reusing it avoids another unfamiliar mechanism.

**Trade-offs and limits:** Hard links must work on the target filesystem; failure means no final fossil publication, rather than silent unsafe fallback. A crash may leave a separate `*.json.tmp` file, never an incomplete *new* final fossil from that interrupted serialization. This does not promise `fsync`, real power-loss durability, cross-file journal/fossil atomicity, coordinated independent writers or iPhone/Pythonista support. The original `Worldheart simulator` remains unchanged. Exact candidate and merged-main checks belong in [PR #8](https://github.com/levelinglucy/Worldheart/pull/8). Revisit hard-link portability only with device evidence or a similarly exclusive complete-only alternative.


## Engineering decision 009 — make observer journal append nonblocking and no-follow

**Confirmed predecessor:** `World.event()` used plain `open(path, "a")` for the JSONL observer journal. In disposable fixtures, a final-component symlink redirected both GENESIS and ordinary events into an unrelated existing file, while a FIFO in the journal slot blocked world startup waiting for a reader. [PR #9 test-first CI](https://github.com/levelinglucy/Worldheart/actions/runs/42761417590) failed those two cases (23 of 25 checks passed) on the predecessor.

**Decision:** Keep the event in the world's bounded in-memory history first. Serialize the record and open the final journal component using `O_NOFOLLOW | O_NONBLOCK | O_APPEND | O_CREAT`, then require `fstat()` to report a regular file before appending. The descriptor is closed on every path. A new journal is owner-only (mode `0600`, subject to the umask); existing regular-file permissions are unchanged. On unsupported OS guards, unsafe paths or other I/O errors, skip this **best-effort disk journal** rather than follow/block on it. Ordinary regular-file event append and the checkpoint/fossil formats remain unchanged.

**Alternatives:** Check `is_symlink()` before normal `open()` (race between check and open); apply `O_NOFOLLOW` without `O_NONBLOCK` (FIFO can still hang); or require a writable journal for all simulation steps (would turn optional observer I/O into a crash path). Descriptor-level checks are a narrow, conservative repair without a new storage subsystem.

**Limits:** This does not defend against symlinks or changes in **parent directories**, existing hard-link aliases, network or adversarial filesystems, concurrent append interleaving, crash/power-loss loss, cross-file journaling transactions or untrusted pickle. A journal failure is still silent and its event is retained only in memory, as before. Revisit a checked, versioned journal and path policy with a substantive persistence redesign or verified target-device evidence. Exact post-fix validation and integration belong in [PR #9](https://github.com/levelinglucy/Worldheart/pull/9).

## Engineering decision 010 — refuse checkpoint aliases and blocking special files

**Confirmed predecessor behaviour:** At main `8bc08db3`, `World.load()` followed final-component symlinks or multi-linked aliases and could wait indefinitely for a FIFO writer. The rolling `World.save()` replaced an occupied final symlink, FIFO or one hard-link directory entry; for hard links this silently separated two names that had previously referred to one history. All four disposable synthetic regressions failed on [test-first CI 42775492665](https://github.com/levelinglucy/Worldheart/actions/runs/42775492665), with the 27 earlier tests passing.

**Proposed choice:** [PR #10](https://github.com/levelinglucy/Worldheart/pull/10) requires a directly named regular checkpoint file with exactly one hard link. It refuses unsafe occupied paths before loading; rolling saves check before staging and again before `os.replace`. Ordinary missing checkpoints can be created, direct-file load/save stays compatible, and format/VM/seed evolution are unchanged. This is a **compatibility change**: deliberate final-component symlink and hard-link checkpoint aliases can no longer be loaded or overwritten by this candidate. Preserve the original and use a separate direct, single-linked copy in a private working directory.

**Alternatives and trade-offs:** Following aliases during load but refusing them on save lets a user start a session that cannot checkpoint; automatically following aliases on save risks destroying unintended history or blocking on special files; replacing an alias breaks the relationship between names. Explicit refusal is conservative and auditable, with the cost of deliberately unsupported alias workflows. `lstat()` checks are not descriptor-pinned transactions: a concurrent path swap after inspection may still defeat them. No `fsync`, multiwriter, parent-directory containment, untrusted `pickle`, platform-specific Pythonista or power-loss claim is made. A robust storage backend with file-descriptor and locking semantics would need separate design and tests.

**Evidence and decision gate:** Four tests passed at exact source/test candidate `7b3672be` ([31/31 hosted Ubuntu CI](https://github.com/levelinglucy/Worldheart/actions/runs/42775679340)). Documentation is in the same PR, and any later exact-head validation belongs there. The candidate remains **unmerged** pending acceptance of the alias-compatibility trade-off; reconsider if a supported use case genuinely requires aliases or trusted device evidence changes the proposed policy.

## Engineering investigation 011 — preserve aliases where demonstrably safe (2026-11-13; spike, no integration)

**User preference and gate:** Dylan chose to preserve deliberate checkpoint aliases *if a safe design exists* and requested investigation **without merging PR #10**. This supersedes decision 010's pending acceptance request, not the hazards it describes. PR #10's current source still refuses final symlinks, hard links and special files. Do not merge it as-is.

**Concrete mechanism:** The old rolling os.replace(stage, latest.wh) changes only its named directory entry. For latest.wh pointing by symlink to other_world.wh, it destroys the symlink rather than advancing other_world.wh. For a hard link it separates one name from other names sharing the old inode. Reading a trusted regular-file alias is different from replacing it. FIFO loading is a separate blocking hazard.

**Disposable Linux spike (not Worldheart source validation):** [experiments/checkpoint_alias_semantics_spike.py](./experiments/checkpoint_alias_semantics_spike.py) exercises seven synthetic filesystem cases in independent temporary directories. CPython 3.13.5/Linux: **7/7 passed** locally on 2026-11-13. A final symlink to a direct single-linked file within the same trusted directory survived staged replacement of its resolved target, and both names observed the new bytes. Hard-linked paths, symlinks to multiply-linked targets or outside the checkpoint directory, FIFOs, dangling links and loops were refused without modifying the occupied objects. This prototype uses realpath/lstat with no descriptor pinning: it illustrates stable-path mechanics, **not a production-safe concurrent transaction**. It is not a test of Worldheart source and not a Pythonista result.

**Design direction pending proof:** (1) Separate load/read eligibility from rolling-write eligibility; validate actual opened file descriptors without blocking on special files or unpickling untrusted data. (2) For a trusted final-component symlink, consider publishing to a checked **direct target path**, preserving the symbolic reference; restrict targets to the trusted checkpoint directory and single-linked regular files. (3) Hard links should allow an explicit read/recovery and migration to a new direct single-linked private checkpoint **only if the CLI cannot silently run a world it cannot save**. Do not replace one hard-link name or rewrite a shared inode in place: neither preserves current atomic checkpoint and crash behavior. (4) Keep named snapshot exclusivity and temp-file evidence refusal. (5) Require integrated red-to-green regressions and exact-revision local/hosted tests before any compatibility claim. The source branch remains unmerged and no save-format change is proposed.

**Unresolved risk and reconsideration:** realpath, lstat and os.replace are not a transaction. Concurrent path swaps, symlinked parents, escape checks, inode reuse, multiwriter coordination, fsync/power-loss durability, target-iPhone/Pythonista behavior and untrusted pickle remain unverified. It may be impossible to preserve hard-link *write-through* semantics while retaining safe replace-on-save with unknown additional hard-link names; preserve existing evidence and offer explicit migration instead of pretending all aliases are safe. If robust symlink publication cannot be established, default to the same explicit migration path rather than silently altering history.

## Engineering investigation 012 — real-checkpoint alias recovery probe (2026-11-13; test-only)

**Goal:** Test whether Worldheart's real save/load functions can be used safely *behind* a narrowly checked alias-to-direct-target migration, rather than extrapolating from the filesystem-only seven-case spike. This is an integration feasibility experiment, not an alias-enabled release candidate.

**Scope:** [tests/test_alias_compatibility_probe.py](./tests/test_alias_compatibility_probe.py) creates exclusively disposable, locally generated worlds and uses a **test-only** resolver for a same-directory, relative final-component symlink. It then passes the checked direct target to actual `World.load()` and `World.save()`. It checks preservation of the symlink during resumed saves, stale target-temp refusal, external alias refusal, hard-link target refusal, and explicit copy-out recovery from a stationary hard-linked history without splitting the originals. The current default `World.load(latest.wh)` still rejects symlinks, and no production path logic is modified. Evidence is only a controlled synthetic integration; never copy a concurrently written checkpoint.

**Evidence gate:** Added tests to the unmerged draft PR #10 branch. Await exact-head CI or an isolated full-suite result before claiming a passed integrated test; existing 31/31 hosted results certify the older refusal candidate only. This is not a production race, lock, directory-containment, Pythonista, power-loss, untrusted-pickle or multiwriter proof.

**Next:** If integration evidence is green, consider a design that safely pins the alias resolution and target descriptor, checks the same trusted directory, and has a CLI-safe migration/refusal path for multiply-linked checkpoints. Keep the draft PR open; do not merge the refusal-only source or claim alias support is currently shipping.

## Roadmap and release gates

| Stage | Intended result | Acceptance | Status |
| --- | --- | --- | --- |
| v0.2 historical baseline | Preserve existing deterministic simulator | Original source remains unchanged | Preserved |
| v0.2.1-rc1 candidate | Disk-isolated counterfactual probe | Baseline issue reproduced; fork leaves disk and live state unchanged across 12 steps; failed CLI resume refuses fallback genesis; named snapshots refuse existing final names while ordinary rolling saves and seeded dynamics pass | Merged on main, CI-validated candidate, not stable |
| v0.2.1 stable (proposed) | Safe recommended entry point | Exact candidate tests pass; authentic old-CLI recovery and rollback are documented; check a trusted user save/Pythonista if available; assess compatibility limits | Planned, not released |
| Future (optional) | Better portable checkpoints | Threat model, migration and replay equivalence tests | Idea only |

## Continuation checklist

1. **Completed in an isolated CI fixture:** run the unchanged v0.2 program as `__main__`, create a real-format checkpoint, then resume/re-save it through the candidate CLI; compare control with `c` probe. Both compatibility tests and all six existing tests passed.
2. **Pending:** check a trusted save from actual use (and Pythonista, if available) in a disposable directory, without ever loading untrusted pickle. Follow [the recovery and rollback guide](./docs/RECOVERY.md).
3. Recheck the precise candidate revision, review release limitations and decide whether to promote v0.2.1; preserve the old script and a recoverable backup.

**Design questions:** Should a dedicated persistence backend replace scattered file calls in a later feature version? Should saved games move from pickle to a versioned, validated structured format? Neither is required to make this specific probe fix.

**How to resume:** Start from the latest Worldheart branch/PR and check its exact head. Compare the candidate script with historical source, read the regression workflow, then update the roadmap and changelog only with verified outcomes.
