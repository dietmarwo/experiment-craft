# P5 review evidence

The baseline at the commits in `baseline-lock.json` after the P5 review, recorded in the [implementation log](../../implementation-log.md#p5-review-and-merge): `scripts/baseline.py all --build-toolchain stable --jobs 2` in a fresh workspace on 25 October 2026, fetching every repository from GitHub. The files at the top level and in `checks/`, `smoke/` and `command-example/` were written by the tool.

- `summary.json`: actions, toolchains and each step's status, exit code and duration.
- `sources.json`, `environment.json`, `toolchains.json`, `binaries.json`: verified commits and shared tree IDs, the container, the exact Rust versions, and the staged executables with their manifest.
- `checks/`: the record and unedited log of every step, including the command/file harness (`commands`), the remote fixture suite (`remote`), the real-OpenSSH suite (`remote_ssh`, whose service manager is simulated) and the build–run–collect example (`command-example`).
- `smoke/`: every runner call's stdout, stderr and JSON, including `capabilities` and each job's `*-execution` record, and the smoke summary. The node root with the native journals and the copied worker executables is not kept.
- `command-example/`: the example's build and run records, its calls and its summary with the checked answer `002aff`. The compiled program, its source, the collected answer bytes and the example's node root are not kept.
- `campaign/`: the live campaign suite (`integration_campaign.log`, 38 tests) and the seven-job example (`local-mixed.log`, and in `local-mixed/` its summary and its JSON, CSV and Markdown report), both run against the binaries of this baseline. The example's node root and campaign workspace are not kept.

Absolute paths refer to the review container.
