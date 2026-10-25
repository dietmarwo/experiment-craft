# AGENTS.md

This repository is **experiment-craft**: reproducible experiment campaigns
(parameter sweeps, comparisons and dependent steps) on top of the
[optimization-jobs](https://github.com/dietmarwo/optimization-jobs) execution
layer. It contains:

- the Python package `experiment_craft` with the `experiment-craft` command:
  the manifest compiler, the campaign state in SQLite, a thin client of
  `optimization-run` and the reports, with their JSON Schemas in
  [`experiment_craft/schemas/`](experiment_craft/schemas/);
- the pinned baseline of the runner and the three solver workers
  ([`baseline-lock.json`](baseline-lock.json)), the tooling that rebuilds and
  checks it ([`scripts/baseline.py`](scripts/baseline.py),
  [`scripts/smoke.py`](scripts/smoke.py)) and the records of past runs in
  [`evidence/`](evidence/);
- the implementation plan, the integration contract and the implementation
  log.

## Read first

- [`README.md`](README.md): the status and how to reproduce the baseline.
- [`docs/dashboard.md`](docs/dashboard.md): the local UI, control semantics and observation-only history.
- [`docs/campaigns.md`](docs/campaigns.md): manifests, the CLI,
  continuation, budgets and reports.
- [`docs/scientific-comparisons.md`](docs/scientific-comparisons.md): predeclared comparison designs, compatible cohorts, reporting and limits.
- [`docs/operations.md`](docs/operations.md) and [`docs/deployment.md`](docs/deployment.md): pause, backup/restore, local configuration and planned workers.
- [`docs/integration-contract.md`](docs/integration-contract.md): what this
  repository uses from optimization-jobs, and what it must not reimplement.
- [`docs/implementation-plan.md`](docs/implementation-plan.md), section 12:
  the brief for the next work package; [`implementation-log.md`](implementation-log.md):
  what each package changed and how it was checked.
- For choosing a solver and for the job API itself, optimization-jobs'
  [`ai-context.md`](https://github.com/dietmarwo/optimization-jobs/blob/main/ai-context.md)
  and [`docs/job-api.md`](https://github.com/dietmarwo/optimization-jobs/blob/main/docs/job-api.md).

## Build and test

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-baseline.txt
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v       # unit tests, links and headings
.venv/bin/python scripts/baseline.py fetch build smoke --workspace .baseline --jobs 2
EXPERIMENT_CRAFT_TEST_BIN_DIR=$PWD/.baseline/bin \
  .venv/bin/python tests/integration_campaign.py         # campaigns with the real runner and workers
.venv/bin/python examples/campaigns/local-mixed/run.py \
  --bin-dir .baseline/bin --output /absolute/new/demo
.venv/bin/python examples/campaigns/scientific/run.py \
  --bin-dir .baseline/bin --output /absolute/new/scientific-demo
.venv/bin/python examples/operations/rehearse.py \
  --bin-dir .baseline/bin --output /absolute/new/operations-demo
.venv/bin/python scripts/baseline.py check --workspace .baseline   # all upstream checks; slow
```

The native build needs Rust 1.88.0 for builds and tests and the latest stable
Rust for lints, and the remote suites of `check` need the OpenSSH client; the
[README](README.md#reproduce-on-linux) lists the requirements.

## Conventions

- Execution, admission, staging, supervision and recovery belong to
  optimization-jobs. Do not add SSH code, a launcher, a process supervisor or
  a capacity ledger here; call `optimization-run` with literal argv.
- Never resubmit or repair uncertain work automatically: observe its recorded
  native handle. A campaign workspace is never reset or rebound to another
  plan or node.
- Maintenance pause is cooperative; restore stays paused and observes existing handles before unpausing. Do not bypass it, reset a deadline, rebind a node or use two writable copies of a recovered campaign. Deployment export is offline and the default stays one local test node.
- Native results stay as they are. Claims, evidence and accounting come from
  the native manifest; a report never strengthens a claim.
- The CLI prints JSON. Expected errors exit 2 with
  `{"error": {"code": …, "message": …}}` and a stable code; keep that contract
  for every new failure path.
- Each fix comes with a regression test. Behavior that involves the runner
  goes into `tests/integration_campaign.py`, which uses the real binaries;
  missing binaries fail the suite rather than skipping it.
- Once a manifest, plan, status or report format is on `main`, a change to it
  gets a new schema version in `experiment_craft/schemas/` and updated
  documentation.
- `baseline-lock.json` names merged commits only. When an upstream `main`
  moves, move the lock ([Moving the baseline](README.md#moving-the-baseline))
  and rerun `scripts/baseline.py all` in a new workspace.
- `evidence/` records past runs. Add a new directory for a new run; do not edit
  or relabel earlier ones.
- A change to optimization-jobs or a worker lands there first, by pull
  request. Upstream documents describe it as after 0.3.0 and do not use this
  plan's package names (P0, RT-05, …).
- Record changes in [`CHANGELOG.md`](CHANGELOG.md) under `[Unreleased]`
  (Added, Changed, Fixed). Do not tag or publish.
- `tests/test_docs.py` checks every relative Markdown link and heading anchor.
