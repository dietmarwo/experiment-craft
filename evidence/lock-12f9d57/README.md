# Lock move to optimization-jobs 12f9d57

The baseline and the campaign suites after `baseline-lock.json` moved to
optimization-jobs `main` and to the workers' pin moves. This is recorded in
the [implementation log](../../implementation-log.md#lock-move-to-optimization-jobs-12f9d57).

| Repository | Commit | What it is |
| --- | --- | --- |
| optimization-jobs | `12f9d57` | The merge of [optimization-jobs#33](https://github.com/dietmarwo/optimization-jobs/pull/33). Since the 0.4.0 release `602d31a`, the changes are documentation only: doc comments on every public item, and a simulator section and corrections in the guide and job API docs |
| fcmaes-rust | `f764a75` | The merge of [fcmaes-rust#50](https://github.com/dietmarwo/fcmaes-rust/pull/50): documentation fixes and the optimization-jobs pin move to `12f9d57` |
| LP-IP-craft | `426ba00` | The merge of [LP-IP-craft#44](https://github.com/dietmarwo/LP-IP-craft/pull/44): the same pin move |
| SQP-craft | `3b053ec` | The merge of [SQP-craft#47](https://github.com/dietmarwo/SQP-craft/pull/47): the same pin move |

Relative to `602d31a`, the shared paths that the workers' `shared-pin.yml`
compares change only in documentation:
- doc comments;
- the `contract!` macro, which now forwards doc attributes;
- a hand-written `ValueEnum` for `Launch`, which keeps `--help` unchanged;
- the guide and `docs/job-api.md`.

`Cargo.lock` of optimization-jobs, the crate versions (0.4.0), the schema
files in the lock and the workers' own code and published packages are
unchanged.

**Baseline.** `scripts/baseline.py all --build-toolchain stable --lint-toolchain stable --jobs 2`
ran in a fresh workspace on 8 November 2026 (UTC), fetching every repository
from GitHub. It used Rust 1.97.0 for builds and lints; CI builds with Rust
1.88.0. All 26 steps passed:
- the four builds and the smoke jobs;
- fmt, Clippy and the release tests in each of the four workspaces. The only
  ignored test is SQP-craft's documentation `census`;
- the runner's rustdoc and the fcmaes documentation consistency check;
- the six job-API harnesses: review, MCP, integration, commands, remote and remote SSH;
- the command example.

The staged `optimization-run` reports `optimization-runner 0.4.0`. The files at
the top level and in `checks/`, `smoke/` and `command-example/` were written by
the tool. The smoke node root, with the native journals and the copied worker
executables, is not kept.

**Suites**, against the binaries of this baseline:

- `campaign/unit.log`: the 199 unit tests, including the link and heading checks.
  The first full run after the documents were written (`campaign/unit-run-1-flaky.log`)
  failed `test_a_stalled_download_is_cut_off_without_a_second_response`. The
  whole 16 MiB arrived before the patched 0.5 s socket timeout, so nothing was
  cut off. Run alone, the test failed once in three runs; the next two full runs
  passed. The test depends on timing, and the lock move changes no Python code.
- `campaign/integration_campaign.log`: the 79 live campaign tests with the real runner and all three workers.
- `campaign/local-mixed.log`, `campaign/scientific.log`, `campaign/rehearsal.log`: the seven-job campaign example, the 17-job comparison example (its `timeout` step fails by design) and the recovery rehearsal.

The dashboard page tests (jsdom and rendered Chromium) were not rerun locally;
the lock move changes no page code. A `full_checks` CI run on the branch
([run 42478352424](https://github.com/dietmarwo/experiment-craft/actions/runs/42478352424))
built the set with Rust 1.88.0 and passed. It ran these tests, the live suite,
the examples and the `check` action.

Absolute paths refer to the review container.
