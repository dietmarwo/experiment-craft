# Lock move to optimization-jobs 78970a2

The baseline and the campaign suites after `baseline-lock.json` moved to the
optimization-jobs 0.4.1 release and to the worker releases that pin it. This
is recorded in the
[implementation log](../../implementation-log.md#lock-move-to-optimization-jobs-78970a2).

| Repository | Commit | What it is |
| --- | --- | --- |
| optimization-jobs | `78970a2` | The merge of [optimization-jobs#38](https://github.com/dietmarwo/optimization-jobs/pull/38): the 0.4.1 release (tag `v0.4.1`). Since `12f9d57` (#34 to #38), the shared paths change only in the crate versions (0.4.0 to 0.4.1) and in the guide |
| fcmaes-rust | `64e11b3` | The merge of [fcmaes-rust#56](https://github.com/dietmarwo/fcmaes-rust/pull/56): the 0.3.0 release (tag `v0.3.0`) with cooperative stopping of retries, and the optimization-jobs pin move to `78970a2` |
| LP-IP-craft | `e5d2481` | The merge of [LP-IP-craft#48](https://github.com/dietmarwo/LP-IP-craft/pull/48): the 0.30.0 release (tag `v0.30.0`) with MIP gap limits, and the same pin move |
| SQP-craft | `fa0611d` | The merge of [SQP-craft#55](https://github.com/dietmarwo/SQP-craft/pull/55): the 0.20.0 release (tag `v0.20.0`) with numerical failure statuses and two experimental step safeguards, and the same pin move. Since `3b053ec` it also contains 0.18.0 (experimental structured SQP) and 0.19.0 (automatic QP backend selection) |

Relative to `12f9d57`, the shared paths that the workers' `shared-pin.yml`
compares change in two ways:
- the versions in both crate manifests and `Cargo.lock` (0.4.0 to 0.4.1);
- the guide (`ai-context.md` and the copy that `get_guide` serves) and one
  version line of `docs/job-api.md`.

The job envelope `optimization.job/0.1`, the worker protocol, the result
contract `optimization.result/0.2` and the locked schema files are unchanged.
Unlike the previous lock moves, the workers' versions change: fcmaes-rust 0.2.1
to 0.3.0, LP-IP-craft 0.29.0 to 0.30.0 and SQP-craft 0.17.0 to 0.20.0.

**Baseline.** `scripts/baseline.py all --build-toolchain stable --lint-toolchain stable --jobs 2`
ran on 16 November 2026 (UTC) with Rust 1.97.0 for builds and lints; CI builds
with Rust 1.88.0. The first run fetched every repository from GitHub into a
fresh workspace. A restart of the review container stopped it during
LP-IP-craft's Clippy step, after the builds, the smoke jobs and seven checks had
passed; its output is not kept. The run recorded here used the same workspace:
its fetch action verified the existing checkouts against the lock (commits,
`files_sha256` and every worker's optimization-jobs pin), and the builds reused
the build directories. All 26 steps passed:
- the four builds and the smoke jobs;
- fmt, Clippy and the release tests in each of the four workspaces. The only
  ignored test is SQP-craft's documentation `census`, as before;
- the runner's rustdoc and the fcmaes documentation consistency check;
- the six job-API harnesses: review, MCP, integration, commands, remote and
  remote SSH (after installing the OpenSSH client and server in the container);
- the command example.

The staged `optimization-run` reports `optimization-runner 0.4.1`, and the
workers' `describe` output reports engine versions 0.3.0, 0.30.0 and 0.20.0,
each with job API 0.4.1. The three smoke jobs end as in
[`lock-12f9d57`](../lock-12f9d57/README.md): the same claims (`best_found`,
`numerical_optimum`, `first_order`), terminations and objectives (the fcmaes
objective is bit-identical). The files at the top level and in `checks/`,
`smoke/` and `command-example/` were written by the tool. The smoke node root,
with the native journals and the copied worker executables, is not kept.

**Suites**, against the binaries of this baseline:

- `campaign/unit.log`: the 199 unit tests, including the link and heading
  checks. The first full run (`campaign/unit-run-1-flaky.log`) failed
  `test_a_stalled_download_is_cut_off_without_a_second_response` in the same
  way as during the previous lock move: the whole 16 MiB arrived before the
  patched 0.5 s socket timeout, so nothing was cut off. Run alone, the test
  passed six times in six runs, and the next full run passed. The test
  depends on timing, and the lock move changes no Python code.
- `campaign/integration_campaign.log`: the 79 live campaign tests with the
  real runner and all three workers.
- `campaign/local-mixed.log`, `campaign/scientific.log`,
  `campaign/rehearsal.log`: the seven-job campaign example, the 17-job
  comparison example (its `invalid-output` and `timeout` steps fail by design)
  and the recovery rehearsal. Their job counts, outcomes and recovery checks
  equal the previous record; the ids and hashes differ because the manifests
  contain this run's absolute paths and each campaign binds a random instance.

The dashboard page tests (jsdom and rendered Chromium) were not rerun locally;
the lock move changes no page code. A `full_checks` CI run on the branch
([run 43945803873](https://github.com/dietmarwo/experiment-craft/actions/runs/43945803873))
built the set with Rust 1.88.0 and passed. It ran these tests, the live suite,
the examples and the `check` action.

Absolute paths refer to the review container.
