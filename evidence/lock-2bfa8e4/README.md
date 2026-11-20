# Lock move to optimization-jobs 0.5.0 (2bfa8e4)

The baseline and the campaign suites after `baseline-lock.json` moved to
the merge of the optimization-jobs 0.5.0 release and to the worker merges
that pin it. This is recorded in the
[implementation log](../../implementation-log.md#lock-move-to-optimization-jobs-050).

| Repository | Commit | What it is |
| --- | --- | --- |
| optimization-jobs | `2bfa8e4` | The merge of [optimization-jobs#47](https://github.com/dietmarwo/optimization-jobs/pull/47), release 0.5.0. The tag `v0.5.0` is on the later `df7c55d` (#48: tutorial pins and registry records), whose shared files are the same |
| fcmaes-rust | `eba5f46` | The merge of [fcmaes-rust#80](https://github.com/dietmarwo/fcmaes-rust/pull/80), the pin move, on release 0.4.0 (jSO, the CR-FM-NES → BiteOpt retry kind `crfmnes_bite`, `repair_z`) |
| LP-IP-craft | `5a2e9d4` | The merge of [LP-IP-craft#50](https://github.com/dietmarwo/LP-IP-craft/pull/50): the pin move only, on 0.30.0 |
| SQP-craft | `4106a5e` | The merge of [SQP-craft#58](https://github.com/dietmarwo/SQP-craft/pull/58): the pin move only, on 0.20.0 |

Relative to `41d5f00`, the shared paths that the workers' `shared-pin.yml`
compares change in two ways:
- the crate versions (0.5.0) in the crate manifests and `Cargo.lock`;
- the guide (`ai-context.md` and the copy that `get_guide` serves), which names
  fcmaes 2.2.0, fcmaes-rust 0.4.0 and CFD-craft's wind-direction model.

The schemas, the job envelope `optimization.job/0.1`, the worker protocol and
the result contract `optimization.result/0.2` are unchanged.

**Baseline.** `scripts/baseline.py all --build-toolchain stable --lint-toolchain stable --jobs 2`
ran on 20 November 2026 (UTC) in a fresh workspace with Rust 1.97.0 for builds
and lints; CI builds with Rust 1.88.0. All 26 steps passed:
- the four builds and the smoke jobs;
- fmt, Clippy and the release tests in each of the four workspaces;
- the runner's rustdoc and the fcmaes documentation consistency check;
- the six job-API harnesses: review, MCP, integration, commands, remote and
  remote SSH (OpenSSH installed in the container for the loopback);
- the command example.

The staged `optimization-run` reports runner 0.5.0. The workers' `describe`
output reports engine versions 0.4.0, 0.30.0 and 0.20.0, each with job API
0.5.0; fcmaes lists `fcmaes.surrogate/2` next to `/1`. The smoke summary equals
the `41d5f00` record except for the binary, journal and execution hashes and
the time: the three smoke jobs end with the same claims, terminations and
objectives. The files at the top level and in `checks/`, `smoke/` and
`command-example/` were written by the tool. The smoke node root, with the
native journals and the copied worker executables, is not kept.

**Suites**, against the binaries of this baseline:
- `campaign/unit.log`: the 214 unit tests, including the link and heading
  checks.
- `campaign/integration_campaign.log`: the 79 live campaign tests with the
  real runner and all three workers.
- `campaign/local-mixed.log`, `campaign/scientific.log` and
  `campaign/rehearsal.log`: the seven-job campaign example, the 17-job
  comparison example (its `invalid-output` and `timeout` steps fail by design)
  and the recovery rehearsal. Their job counts and step outcomes equal the
  previous record; ids and hashes differ, because the manifests contain this
  run's absolute paths and each campaign binds a random instance.
- `campaign/adaptive-summary.json`: `tests/integration_adaptive.py` with this
  runner and BO-craft at `9382519`. Its checks equal the previous record,
  including the pruning campaign with one pruned trial. The Python environment
  has no Torch, so the model answer is skipped, as in CI.

The dashboard page tests (jsdom and rendered Chromium) were not rerun locally;
the lock move changes no page code.

Absolute paths refer to the review container.
