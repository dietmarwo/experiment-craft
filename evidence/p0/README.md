# P0 evidence index

- `checks/*.json`: exact command argv, working directory, start time, exit code, elapsed time and log filename. The recording wrapper used for P0 also recorded the selected runtime environment; `scripts/baseline.py` now writes `environment.json`, `toolchains.json`, `binaries.json`, `sources.json` and `summary.json` itself.
- `checks/*.log`: unedited stdout/stderr from that check. A failed initial smoke-tool run and upstream lint diagnostics remain visible.
- `smoke/summary.json`: three real numerical jobs, observed binary/journal hashes and assertion results.
- `smoke/*-describe.json`: complete worker discovery, including payload/input schemas and examples.
- `smoke/*-run.json`, `*-result.json`, `*-repeat.json`, `*-conflict.json`: actual CLI output.
- `smoke/attempts/`: native submitted/resolved specifications, provenance, results and journal evidence. Executable copies and lock files are omitted: this is a review record, not a restorable node image.
- `runtime-tree-comparison.json`: Git object IDs proving identical shared crate and job-schema trees between the current runner and the workers' dependency revision.
- `environment.json`, `*-version.txt`, `python-freeze.txt`, `binaries.json`: tested environment, exact installed tooling and observed executable fingerprints.
- `reproduction-build/`: commands and outputs from running the build action of `scripts/baseline.py` against the verified workspace.
- `binaries-initial.json`, `smoke-initial-summary.json`: initial observations retained separately. Full workspace checks changed two executable fingerprints; the final build/smoke and shared runtime suites were rerun against the final binary set.
- `check-summary.json`: compact machine-readable check outcomes and parsed test totals. Raw logs are authoritative.

Paths, timestamps and boot/process identifiers in raw evidence refer to the original test container. They are not portable execution handles. Use the reproduction scripts to create a new node root and new evidence. The source fixtures contain no machine-specific absolute paths.

No source trees, toolchain downloads, Cargo caches, compiled executables, or Python virtual environment are included. The source lock and dependency pins allow online reconstruction. Binary fingerprints identify the observed run; they are not an assertion of bit-identical builds elsewhere.
