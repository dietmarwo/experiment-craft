# experiment-craft

Reproducible experiment campaigns, parameter sweeps and comparisons on top of the [optimization-jobs](https://github.com/dietmarwo/optimization-jobs) execution layer.

Rust `optimization-jobs` owns execution, resource admission, staging, supervision and recovery. Python `experiment-craft` will own campaign composition, scientific choices and reports. The [implementation plan](docs/implementation-plan.md) describes the split and the work packages.

**Status:** work package P0 (audit and pin the foundation) is complete. This repository holds the pinned baseline, the tooling that rebuilds and checks it, three real smoke jobs, the audit and the integration design. Campaign execution, generic commands, file transfer and fleet scheduling are later work packages. The scripts here are development checks; they are not a second execution service.

## Start here

- [Implementation log](implementation-log.md): what each work package changed, the commands run and their results.
- [Pinned baseline](baseline-lock.json) and [compatibility matrix](docs/compatibility-matrix.md).
- [Reuse audit](docs/reuse-audit.md): existing runner code and the proposed internal boundaries.
- [Integration contract](docs/integration-contract.md): the current CLI/JSON interface and the proposed additions.
- [Prioritized backlog](docs/implementation-backlog.md) and [validation limits](docs/known-limitations.md).
- [Implementation plan](docs/implementation-plan.md), version 2.2.

## Reproduce on Linux

Requirements: Git, a C/C++ toolchain, Python 3.12 or later with venv support, rustup, network access to GitHub, crates.io and PyPI, and a few GB of disk for the native builds. Two toolchains are used:

- **Build toolchain**, Rust 1.88.0: the minimum supported Rust of the job layer. It builds the runner and the three workers and runs their tests.
- **Lint toolchain**, the latest stable Rust: `cargo fmt`, `clippy` and rustdoc warnings, as in the repositories' own CI. Clippy's lints change between releases, so linting with 1.88 reports diagnostics that the repositories' gate does not check.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-baseline.txt
rustup toolchain install 1.88.0 --profile minimal
rustup toolchain install stable --profile minimal --component rustfmt --component clippy
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/baseline.py fetch build smoke --workspace .baseline --jobs 2
.venv/bin/python scripts/baseline.py check --workspace .baseline     # the full upstream checks; slow
```

The actions always run in the order fetch, verify, build, smoke, check; `all` runs all of them.

| Action | What it does |
|---|---|
| `fetch` | Clones each repository at its exact commit into `WORKSPACE/repos/`, or verifies an existing checkout. Also fetches the workers' pinned optimization-jobs commit as an object, without changing the checkout. |
| `verify` | Implied by every action. Checks HEAD, a clean working tree and the recorded file hashes; that every worker's `Cargo.toml` and `Cargo.lock` pin optimization-jobs at the recorded revision; and that the files the workers share with optimization-jobs (the paths of their `shared-pin.yml` check) are unchanged between that pin and the runner commit. |
| `build` | Builds each worker package, then the current runner, with the build toolchain, and copies the five executables to `WORKSPACE/bin/`. Later checks rebuild `target/` with other feature sets; the copies keep what smoke and the harnesses test fixed. |
| `smoke` | Runs one real job per worker with `scripts/smoke.py` on a one-slot node (see below). |
| `check` | fmt, clippy (`--keep-going`, so every crate's diagnostics are listed) and rustdoc with the lint toolchain; release tests with the build toolchain; fcmaes-rust's documentation consistency check; and the shared review, MCP and integration harnesses against `WORKSPACE/bin/`. The integration harness initializes an eight-slot node. |

Existing checkouts are verified, never reset. A failed first fetch leaves its checkout for inspection; use a new workspace to retry. `--build-toolchain` and `--lint-toolchain` override the lock, for example `--lint-toolchain 1.88.0` to repeat the lint run recorded in the P0 evidence.

Every action after verify writes a new evidence directory (`--output`, by default `WORKSPACE/evidence-<UTC time>`):

| File | Content |
|---|---|
| `summary.json` | Actions, toolchains and the status, exit code and duration of every step |
| `sources.json` | Verified commits, file hashes and the Git tree IDs of the shared paths at both revisions |
| `environment.json`, `toolchains.json` | Platform, CPU and memory limits, systemd user manager output, and the exact `rustc`, `cargo`, `clippy` and `rustfmt` versions |
| `binaries.json` | SHA-256 and size of the staged executables |
| `checks/NAME.json`, `checks/NAME.log` | argv, working directory, timing and exit code; the unedited output |
| `smoke/` | Every runner call's stdout, stderr and JSON, worker discovery, the node root with the native journals, and `summary.json` |

Read the logs for skipped tests, not only exit codes. Binary hashes are observations: the pinned sources do not promise bit-identical binaries across build paths and environments.

## Smoke jobs

[`examples/smoke/`](examples/smoke/) holds one small job per worker: a 2-D sphere with BiteOpt (fcmaes), a binary choice with an objective offset (LP-IP) and a simplex quadratic (SQP). [`scripts/smoke.py`](scripts/smoke.py) registers the three workers, validates each job against the job schema and the worker's payload schema, runs it in the foreground and checks the result manifest against the result schema. It then rechecks the numbers (bounds and the sphere objective, the LP/IP solution and bound, the SQP point and stationarity), repeats the request to confirm that the same key returns the same job without a journal append, changes the work under the same key to get `request_key_conflict`, and changes a model byte under its old hash to get `invalid_job`. It is an executable example of the current local interface, not the future campaign client.

## Continuous integration

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs the unit tests and the fetch/verify step on every push and pull request, then builds the pinned set with Rust 1.88.0 and runs the smoke jobs. The evidence directory is uploaded as a workflow artifact. A manual run (`workflow_dispatch` with `full_checks`) adds the `check` action.

## License and attribution

The repository's MIT [LICENSE](LICENSE) is unchanged. The smoke payloads are adapted from the MIT-licensed `optimization-jobs/scripts/job-api/test_review.py` at the pinned commit, with one-slot resources and stable request keys. Worker discovery and numerical outputs in `evidence/` were produced by the pinned upstream tools.
