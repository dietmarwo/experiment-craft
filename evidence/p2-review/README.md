# P2 review evidence

The baseline at the merged P2 commits, recorded in the [implementation log](../../implementation-log.md#baseline-at-the-merged-commits-1): `scripts/baseline.py all --build-toolchain stable --jobs 2` in a fresh workspace on 24 October 2026, fetching every repository from GitHub. Every file was written by the tool.

- `summary.json`: actions, toolchains and each step's status, exit code and duration.
- `sources.json`, `environment.json`, `toolchains.json`, `binaries.json`: verified commits and shared tree IDs, the container, the exact Rust versions, and the staged executables with their manifest.
- `checks/`: the record and unedited log of every step, including the command/file harness (`commands`) and the build–run–collect example (`command-example`).
- `smoke/`: every runner call's stdout, stderr and JSON, including `capabilities` and each job's `*-execution` record, and the smoke summary. The node root with the native journals and the copied worker executables is not kept.
- `command-example/`: the example's build and run records, its calls and its summary with the checked answer `002aff`. The compiled program, the collected answer bytes and the example's node root are not kept.

Absolute paths refer to the review container.
