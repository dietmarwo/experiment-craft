# P0 review evidence

The independent re-run recorded in the [implementation log](../../implementation-log.md#independent-re-run): `scripts/baseline.py all --build-toolchain stable --jobs 2` in a fresh workspace on 24 October 2026. Every file was written by the tool.

- `summary.json`: actions, toolchains and each step's status, exit code and duration.
- `sources.json`, `environment.json`, `toolchains.json`, `binaries.json`: verified commits and shared tree IDs, the container, the exact Rust versions, and the staged executables.
- `checks/`: the record and unedited log of every step.
- `smoke/`: every runner call's stdout, stderr and JSON, and the smoke summary. The node root with the native journals and the copied worker executables is not kept; [`../p0/smoke/attempts/`](../p0/smoke/attempts/) has the P0 journals for the same jobs.

Absolute paths refer to the review container. This run was made before the build step wrote a `manifest.json` next to the staged executables, so `binaries.json` here has the earlier form (toolchain, directory, files).
