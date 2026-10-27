# experiment-craft

Reproducible experiment campaigns, parameter sweeps and comparisons on top of the [optimization-jobs](https://github.com/dietmarwo/optimization-jobs) execution layer.

Rust `optimization-jobs` owns execution, resource admission, staging, supervision and recovery. Python `experiment-craft` owns campaign composition, scientific choices and reports. The [implementation plan](docs/implementation-plan.md) describes the split and the work packages.

**Status:** P0–P3, P5 (local campaigns), P6 (scientific comparisons), the local subset of P7 (operations and planned workers) and the local browser dashboard (UI-01) are merged. The Python campaign package compiles deterministic sweeps and dependent steps into native jobs and validates them at initialization. It keeps immutable input snapshots, transactional decisions and stable native handles, applies dependencies, declared budgets, a deadline, stop and continuation, and writes offline reports. Local acceptance uses the real runner and three real Rust workers. The [RT-07 backend gate](docs/backend-gate.md) remains blocked: no actual systemd/logout/reboot or cgroup commissioning is claimed. Automatic placement remains gated. This repository delegates execution to optimization-jobs.

## Browser dashboard

The local dashboard (0.4.0, unpublished) controls initialized experiments and
plots sampled progress per native node. It uses the existing continuation,
pause, reconciliation, stop and collection operations and retains bounded
history across restarts. Start with the [illustrated UI user manual](docs/ui-user-manual.md)
for setup, controls, chart reading and troubleshooting, or read the
[dashboard reference](docs/dashboard.md).

```bash
experiment-craft dashboard --workspace /absolute/campaign --state-dir /absolute/dashboard-history
python3 examples/dashboard/prepare.py --bin-dir .baseline/bin --output /absolute/new/dashboard-demo --serve
```

The **Artifacts & recorded audits** panel lists command outputs, collects and
downloads checked files, and displays CAP acceptance receipts with every arm's
verification/replay outcome. Native execution and reported scientific verdicts
remain separate. JSON, Markdown and CSV downloads use the same offline report
as the CLI; no checker is run by viewing a report.

No remote host is commissioned by displaying its inventory entry. Charts show
campaign step counts and declared slots, not measured machine utilization.

## Local campaigns

```bash
python3 -m pip install -e .
experiment-craft dry-run campaign.json
```

Read the [campaign guide](docs/campaigns.md) for initialization, continuation, budgets and report semantics. The [seven-job example](examples/campaigns/local-mixed/run.py) prepares data, runs a seeded sweep and LP/IP/SQP jobs, checks native outcomes and creates a report. It uses an isolated local foreground node; actual service commissioning stays separate.

## Scientific comparisons

The P6 layer adds a comparison protocol sealed before execution, compatible model/profile groups, declared work/time caps, seeded or start-based designs, and offline descriptive reports. It retains all failures and partial/unknown outcomes and preserves native claims and evidence. The existing P5 formats remain unchanged; the current package version is 0.4.0, unpublished.

```bash
python3 examples/campaigns/scientific/run.py --bin-dir .baseline/bin --output /absolute/new/scientific-demo
```

The [comparison guide](docs/scientific-comparisons.md) explains the protocol, cohorts, pairing, limits and CLI. Its 17-job example checks all three workers, numerical results and two deliberate failures. Small seed sets validate the pipeline, not solver performance. Local P7 installation/recovery preparation is implemented; RT-07/RT-08 and real-host commissioning remain gated.

## Named artifacts and verification reports

`artifacts` lists saved command outputs, `collect-artifact` retains a file
through the native transfer API, and `verification-report` reads an application
acceptance receipt offline. The built-in CAP audit adapter keeps native command
state separate from reported scientific acceptance and retains per-arm failures
and censored observations. Read the [artifact and verification guide](docs/verification-reports.md)
for the CLI, trust scope and real scalar/PDE example. It does not run a checker
or add proof semantics to the dashboard or predeclared comparison layer.

## Operations and planned workers

The local P7 subset (0.3.0, unpublished) adds dispatch pause/reconciliation,
checked SQLite campaign backups, paused restores and installation/rollback
rehearsal. A validated inventory includes one local default and six disabled
planned workers; it exports literal native fleet commands without contacting
hosts or adding automatic placement. Read the [deployment guide](docs/deployment.md),
[operating guide](docs/operations.md) and [January checklist](docs/january-commissioning.md).

```bash
experiment-craft deployment-check examples/deployment/home-lab.json
python3 examples/operations/rehearse.py --bin-dir .baseline/bin --output /absolute/new/operations-demo
```

## Start here

- [AGENTS.md](AGENTS.md): orientation and conventions for coding agents working in this repository.
- [Campaign guide](docs/campaigns.md): manifests, the CLI, continuation, budgets and reports.
- [Artifacts and verification reports](docs/verification-reports.md): checked named outputs and offline application-reported certificate results.
- [A mathematician's guide](docs/mathematicians-guide.md) ([PDF](docs/mathematicians/mathematicians-guide.pdf)): which repository serves which mathematical task, the worked scalar and PDE certificates, a finite-check design, agent prompts and what each result does and does not establish.
- [UI user manual](docs/ui-user-manual.md): the first local tour, screenshots, daily controls and troubleshooting.
- [Implementation log](implementation-log.md): what each work package changed, the commands run and their results.
- [Pinned baseline](baseline-lock.json) and [compatibility matrix](docs/compatibility-matrix.md).
- [Reuse audit](docs/reuse-audit.md): existing runner code and the proposed internal boundaries.
- [Integration contract](docs/integration-contract.md): the current CLI/JSON interface and the proposed additions.
- [Prioritized backlog](docs/implementation-backlog.md) and [validation limits](docs/known-limitations.md).
- [Implementation plan](docs/implementation-plan.md), version 2.11.

## Reproduce on Linux

Requirements: Git, the OpenSSH client (`ssh` and `ssh-keygen`), a C/C++ toolchain, Python 3.12 or later with venv support, rustup, network access to GitHub, crates.io and PyPI, and a few GB of disk for the native builds. Two toolchains are used:

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

The actions always run in the order fetch, verify, build, smoke, check; `all` runs fetch (which verifies), build, smoke and check.

| Action | What it does |
|---|---|
| `fetch` | Clones each repository at its exact commit into `WORKSPACE/repos/`, or verifies an existing checkout. Also fetches the workers' pinned optimization-jobs commit as an object, without changing the checkout. |
| `verify` | Implied by every action. Checks HEAD, a clean working tree and the recorded file hashes; that every tracked `Cargo.toml` and `Cargo.lock` of each worker pins optimization-jobs at the recorded revision; and that the files the workers share with optimization-jobs (the paths of their `shared-pin.yml` check) are unchanged between that pin and the runner commit. |
| `build` | Builds each worker package, then the current runner, with the build toolchain, and copies the five executables to `WORKSPACE/bin/` with a `manifest.json` (toolchain, source commits, SHA-256). Later checks rebuild `target/` with other feature sets; the copies keep what smoke and the harnesses test fixed. |
| `smoke` | Runs one real job per worker with `scripts/smoke.py` on a one-slot node (see below). Like `check`, it first confirms that `WORKSPACE/bin/` is executable and still matches its manifest and the lock's commits. |
| `check` | fmt, clippy (`--keep-going`, so every crate's diagnostics are listed) and rustdoc with the lint toolchain; release tests with the build toolchain; fcmaes-rust's documentation consistency check; and the shared review, MCP, integration, command/file and remote/SSH harnesses, plus the build–run–collect example against `WORKSPACE/bin/`. The integration harness initializes an eight-slot node. |

Existing checkouts are verified, never reset. A failed first fetch leaves its checkout for inspection; use a new workspace to retry. `--build-toolchain` and `--lint-toolchain` override the lock, for example `--lint-toolchain 1.88.0` to repeat the lint run recorded in the P0 evidence.

Every action after verify writes a new evidence directory (`--output`, by default `WORKSPACE/evidence-<UTC time>`):

| File | Content |
|---|---|
| `summary.json` | Actions, toolchains and the status, exit code and duration of every step |
| `sources.json` | Verified commits, file hashes and the Git tree IDs of the shared paths at both revisions |
| `environment.json`, `toolchains.json` | Platform, CPU and memory limits, systemd user manager output, and the exact `rustc`, `cargo`, `clippy` and `rustfmt` versions |
| `binaries.json` | The staged executables that smoke and check used: toolchain, source commits, SHA-256 and size |
| `checks/NAME.json`, `checks/NAME.log` | argv, working directory, timing and exit code; the unedited output |
| `smoke/` | Every runner call's stdout, stderr and JSON, worker discovery, the node root with the native journals, and `summary.json` |

Read the logs for skipped tests, not only exit codes. Binary hashes are observations: the pinned sources do not promise bit-identical binaries across build paths and environments.

## Moving the baseline

When a repository's `main` moves (for example after a pin move or a merged fix), update its entry in `baseline-lock.json`: `commit`, and every `files_sha256` value (`git show COMMIT:Cargo.lock | sha256sum`, likewise for the other files). If the workers' pin moved, update `contracts.worker_job_api_revision` and each worker's `job_api_revision`. Then run `scripts/baseline.py all` in a **new** workspace: fetch never changes an existing checkout, so an old workspace fails with "HEAD differs". `verify` rejects a lock whose optimization-jobs commit changed a shared path since the workers' pin, which means the pin has to move first. Record the run in the implementation log and keep its evidence under `evidence/`.

## Smoke jobs

[`examples/smoke/`](examples/smoke/) holds one small job per worker: a 2-D sphere with BiteOpt (fcmaes), a binary choice with an objective offset (LP-IP) and a simplex quadratic (SQP). [`scripts/smoke.py`](scripts/smoke.py) registers the three workers, validates each job against the job schema and the worker's payload schema, runs it in the foreground and checks the result manifest against the result schema. It also validates the runner's capabilities (`node capabilities`, which must agree with `node doctor`) and each job's execution record (`jobs execution`) against their schemas, checks that the record's native-result size and SHA-256 match `run.json`, and that a repeated request leaves the record unchanged. It then rechecks the numbers (bounds and the sphere objective, the LP/IP solution and bound, the SQP point and stationarity), repeats the request to confirm that the same key returns the same job without a journal append, changes the work under the same key to get `request_key_conflict`, and changes a model byte under its old hash to get `invalid_job`. It is an executable example of the native local interface; campaigns use the `experiment-craft` client above.

## Continuous integration

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs the unit tests and the fetch/verify step on pull requests and pushes to `main`, then builds the pinned set with Rust 1.88.0 and runs the smoke jobs. The evidence directory is uploaded as a workflow artifact. A manual run (`workflow_dispatch` with `full_checks`) adds the `check` action.

## License and attribution

The repository's MIT [LICENSE](LICENSE) is unchanged. The smoke payloads are adapted from the MIT-licensed `optimization-jobs/scripts/job-api/test_review.py` at the pinned commit, with one-slot resources and stable request keys. Worker discovery and numerical outputs in `evidence/` were produced by the pinned upstream tools.
