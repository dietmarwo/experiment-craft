# Lock move to optimization-jobs 41d5f00

The baseline and the campaign suites after `baseline-lock.json` moved to
optimization-jobs `41d5f00` and to the worker merges that pin it. This is
recorded in the
[implementation log](../../implementation-log.md#lock-move-to-optimization-jobs-41d5f00).

| Repository | Commit | What it is |
| --- | --- | --- |
| optimization-jobs | `41d5f00` | The merge of [optimization-jobs#46](https://github.com/dietmarwo/optimization-jobs/pull/46): command jobs may declare a progress file, read with `jobs progress`. The crates are still 0.4.1 |
| fcmaes-rust | `e996062` | The merge of [fcmaes-rust#60](https://github.com/dietmarwo/fcmaes-rust/pull/60), the pin move. Since `64e11b3` (0.3.0) it also contains the experimental surrogate `/2` profile and its budget-aware BiteOpt handoff (#57, #58) and tutorial record fields (#59); the crates are still 0.3.0 |
| LP-IP-craft | `e388aed` | The merge of [LP-IP-craft#49](https://github.com/dietmarwo/LP-IP-craft/pull/49): the pin move only, on 0.30.0 |
| SQP-craft | `daedde5` | The merge of [SQP-craft#56](https://github.com/dietmarwo/SQP-craft/pull/56): the pin move only, on 0.20.0 |

Relative to `78970a2`, the shared paths that the workers' `shared-pin.yml`
compares change in three ways:
- `execution.command/0.1` gains an optional `progress` object (both schema
  copies). Specs without it serialize and hash as before, and the runner at
  `78970a2` refuses it as an unknown field.
- A new schema `execution.command.progress/0.1` (both copies), the CLI
  command `jobs progress` and the error code `no_progress`.
- The guide (`ai-context.md` and the copy that `get_guide` serves) gains the
  BO-craft entry and corrected LP-IP-craft and crate-version lines.

The job envelope `optimization.job/0.1`, the worker protocol and the result
contract `optimization.result/0.2` are unchanged, and so are the crate and
worker versions. The lock hashes the new progress schema and names the
contract `command_progress`.

**Baseline.** `scripts/baseline.py all --build-toolchain stable --lint-toolchain stable --jobs 2`
ran on 17 November 2026 (UTC) with Rust 1.97.0 for builds and lints; CI builds
with Rust 1.88.0. The first run, in a fresh workspace, passed 25 of the 26
steps. `remote_ssh` timed out in its setup because the container's Python
lacked `asyncssh`, which `requirements-baseline.txt` lists
([`run-1/remote_ssh.log`](run-1/remote_ssh.log)). After installing those
requirements, the run recorded here used the same workspace. Its fetch action
verified the existing checkouts against the lock, and the builds reused the
build directories. All 26 steps passed:
- the four builds and the smoke jobs;
- fmt, Clippy and the release tests in each of the four workspaces. The only
  ignored test is SQP-craft's documentation `census`, as before;
- the runner's rustdoc and the fcmaes documentation consistency check;
- the six job-API harnesses: review, MCP, integration, commands, remote and
  remote SSH;
- the command example.

The staged `optimization-run` reports `optimization-runner 0.4.1`. The workers'
`describe` output reports engine versions 0.3.0, 0.30.0 and 0.20.0, each with
job API 0.4.1. fcmaes also lists the experimental `fcmaes.surrogate/2` profile
next to `/1`. The three smoke jobs end as in
[`lock-78970a2`](../lock-78970a2/README.md), with the same claims,
terminations and objectives. The files at the top level and in `checks/`,
`smoke/` and `command-example/` were written by the tool. The smoke node root,
with the native journals and the copied worker executables, is not kept.

**Suites**, against the binaries of this baseline:
- `campaign/unit.log`: the 214 unit tests, including the link and heading
  checks and the new pruning tests.
- `campaign/integration_campaign.log`: the 79 live campaign tests with the
  real runner and all three workers.
- `campaign/local-mixed.log`, `campaign/scientific.log` and
  `campaign/rehearsal.log`: the seven-job campaign example, the 17-job
  comparison example (its `invalid-output` and `timeout` steps fail by design)
  and the recovery rehearsal. Their job counts, outcomes, recovery checks and
  the comparison's protocol ID equal the previous record. The ids and hashes
  differ, because the manifests contain this run's absolute paths and each
  campaign binds a random instance.
- `campaign/adaptive-summary.json`: `tests/integration_adaptive.py` with this
  runner and BO-craft at the tree of its merge `9382519` (checked out from
  the branch before the merge). It includes the pruning
  campaign: one trial was pruned, and the runtime records its job as
  cancelled. The Python environment has no Torch, so the model answer is
  skipped, as in CI.

The dashboard page tests (jsdom and rendered Chromium) were not rerun locally;
the lock move changes no page code. A `full_checks` CI run on the branch
([run 44091206900](https://github.com/dietmarwo/experiment-craft/actions/runs/44091206900))
built the set with Rust 1.88.0 and passed. It ran these tests, the live suite,
the examples, the adaptive campaigns with pruning, the certificate reports and
the `check` action.

Absolute paths refer to the review container.
