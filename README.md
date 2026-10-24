# experiment-craft

Experiment campaigns for the [optimization-jobs](https://github.com/dietmarwo/optimization-jobs) execution layer.

This checkpoint implements **P0: audit and pin the foundation** from implementation plan v2.1. It contains working baseline verification/build tooling, three real optimization smoke jobs, test evidence, and the integration design. Campaign execution, generic commands, file transfer, and fleet scheduling are later work packages.

Rust `optimization-jobs` owns execution, resource admission, staging, supervision, and recovery. Python `experiment-craft` will own campaign composition, scientific choices, and reports. The scripts here are development checks; they do not create a second execution service.

## Start here

- [Implementation log](implementation-log.md): scope, changes, commands, results, and limitations.
- [Pinned baseline](baseline-lock.json) and [compatibility matrix](docs/compatibility-matrix.md).
- [Reuse audit](docs/reuse-audit.md): existing code and proposed internal boundaries.
- [Integration contract](docs/integration-contract.md): current CLI/JSON behavior and future interfaces.
- [Prioritized backlog](docs/implementation-backlog.md) and [validation limits](docs/known-limitations.md).
- [Accepted plan v2.1](docs/implementation-plan-v2.1.md), preserved as the planning input. Its earlier documentation-version concern is resolved by this audit.

## Reproduce on Linux

Requirements: Git, a C/C++ toolchain, Python 3.12 with venv support, Rustup, network access to GitHub/crates.io/PyPI, and enough disk for native build artifacts. The recorded environment had an 8-CPU quota and 8 GiB RAM; builds used two parallel Cargo jobs. Full native checks take substantially longer than the three smoke jobs.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-baseline.txt
rustup toolchain install 1.88.0 --profile minimal --component rustfmt --component clippy
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/baseline.py all --workspace .baseline --jobs 2
```

`all` fetches exact commits into a new workspace, verifies clean checkouts and file hashes, builds the workers and current runner, runs the named upstream checks, and saves the real-job evidence. Existing checkouts are verified, never reset. Each run creates a fresh evidence directory. A failed initial fetch leaves its checkout for inspection; use a new workspace to retry without changing it.

The three pinned solver workspaces have strict Clippy failures under Rust 1.88: indexed loops in fcmaes, a nested branch in LP-IP, and a format argument in SQP. Consequently `check`/`all` report those failures while preserving the other results. The reproduction tool does not suppress warnings or silently modify upstream code. See the implementation log for the complete observed status.

Individual actions are also available:

```bash
.venv/bin/python scripts/baseline.py fetch
.venv/bin/python scripts/baseline.py verify
.venv/bin/python scripts/baseline.py build
.venv/bin/python scripts/baseline.py check
.venv/bin/python scripts/baseline.py smoke
```

The `check` action requires the built binaries and schema dependencies. Inspect logs for failures and skipped tests, not just the process status. The upstream integration harness initializes an eight-slot node; use an environment suitable for those tests. For a smaller environment, `smoke` runs one job at a time with a one-slot budget. New binary hashes are observations: source reproducibility does not promise bit-identical binaries across build paths and environments.

The package includes the new project source and evidence, not upstream source trees, Rust caches, or compiled binaries. `baseline-lock.json` is the recipe for fetching them. No release or PyPI publication is made by these commands.

## License and attribution

The repository's original MIT [LICENSE](LICENSE) is unchanged. The smoke payloads are adapted from the MIT-licensed `optimization-jobs/scripts/job-api/test_review.py` at the pinned commit, with one-slot resources and stable request keys. Worker discovery and numerical outputs in `evidence/p0/` were produced by the pinned upstream tools.

