# Lock move to optimization-jobs 0.4.0

The baseline and the campaign suites after `baseline-lock.json` moved to the
0.4.0 release of optimization-jobs and to the workers' pin moves. This is
recorded in the
[implementation log](../../implementation-log.md#release-040-lock-move-and-baseline).

| Repository | Commit | What it is |
| --- | --- | --- |
| optimization-jobs | `602d31a` | The merge of [optimization-jobs#26](https://github.com/dietmarwo/optimization-jobs/pull/26): both crates at 0.4.0, changelog and docs. To be tagged `v0.4.0` |
| fcmaes-rust | `b63d7b7` | The merge of [fcmaes-rust#39](https://github.com/dietmarwo/fcmaes-rust/pull/39): the optimization-jobs pin moves to `602d31a` in the workspace and four tutorials |
| LP-IP-craft | `822bd81` | The merge of [LP-IP-craft#38](https://github.com/dietmarwo/LP-IP-craft/pull/38): the same pin move |
| SQP-craft | `2b9b1d8` | The merge of [SQP-craft#40](https://github.com/dietmarwo/SQP-craft/pull/40): the same pin move |

Relative to the previous pin `8b4489d`, the shared paths change only in the
release commit's version lines and wording. The workers' own versions and
published packages are unchanged.

**Baseline.** `scripts/baseline.py all --build-toolchain stable --lint-toolchain stable --jobs 2`
ran in a fresh workspace on 29 October 2026 (UTC), fetching every repository
from GitHub. It used Rust 1.97.0 for builds and lints; Rust 1.88.0 could not
be installed in this environment, and CI builds with it. All 26 steps passed:
- the four builds and the smoke jobs;
- fmt, Clippy and the release tests in each of the four workspaces;
- the runner's rustdoc and the fcmaes documentation consistency check;
- the six job-API harnesses: review, MCP, integration, commands, remote and remote SSH;
- the command example.

The staged `optimization-run` reports `optimization-runner 0.4.0`. The files at
the top level and in `checks/`, `smoke/` and `command-example/` were written by
the tool:

- `summary.json`: actions, toolchains and each step's status, exit code and duration.
- `sources.json`, `environment.json`, `toolchains.json`, `binaries.json`: verified commits and shared tree IDs, the container, the exact Rust versions, and the staged executables with their manifest.
- `checks/`: the record and unedited log of every step.
- `smoke/`: every runner call's stdout, stderr and JSON and the smoke summary. The node root with the native journals and the copied worker executables is not kept.
- `command-example/`: the example's build and run records, its calls and its summary.

**Suites**, against the binaries of this baseline:

- `campaign/unit.log`: the 192 unit tests, including the link, heading and manual option checks.
- `campaign/integration_campaign.log`: the 79 live campaign tests with the real runner and all three workers.
- `campaign/local-mixed.log`, `campaign/scientific.log`, `campaign/rehearsal.log`: the seven-job campaign example, the 17-job comparison example and the recovery rehearsal.
- `campaign/dashboard-dom.log` and `dashboard/dom-summary.json`: the jsdom interaction test, with ten completed jobs and a stopped tour.
- `campaign/dashboard-browser.log` and `dashboard/browser-report.json`: the rendered check in Chrome for Testing 153.0.8010.12, with ten completed native jobs. All 22 checks passed. In the first run, two checks failed because this browser requests `/favicon.ico` without the token and logs the server's 401. CI's headless browser requests no icon. The page now declares an inline icon, and this is the run after that change.
- `campaign/dashboard-results-browser.log` and `dashboard/results-browser.json`: the rendered result workflow in the same browser, 42 checks with nine jobs.

The page tests and the unit tests ran with the icon change. The other suites
ran before that change, which touches only the page markup.

Absolute paths refer to the review container.
