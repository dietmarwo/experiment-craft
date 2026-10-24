# Baseline evidence after the lock move

The run recorded in the [implementation log](../../implementation-log.md#baseline-lock-moved-to-the-solver-clippy-fixes): `scripts/baseline.py all --build-toolchain stable --jobs 2` in a fresh workspace on 24 October 2026, with `baseline-lock.json` naming the merged Clippy fixes of the three solver repositories. Every file was written by the tool.

- `summary.json`: actions, toolchains and each step's status, exit code and duration.
- `sources.json`, `environment.json`, `toolchains.json`, `binaries.json`: verified commits and shared tree IDs, the container, the exact Rust versions, and the staged executables with their manifest.
- `checks/`: the record and unedited log of every step.
- `smoke/`: every runner call's stdout, stderr and JSON, and the smoke summary. The node root with the native journals and the copied worker executables is not kept.

Absolute paths refer to the review container.
