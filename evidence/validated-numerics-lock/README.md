# Lock move to the fcmaes-rust validated-numerics tutorial

The baseline and the campaign suites after `baseline-lock.json` moved to the fcmaes-rust main `46a6a48`, the merge of [fcmaes-rust#36](https://github.com/dietmarwo/fcmaes-rust/pull/36), recorded in the [implementation log](../../implementation-log.md#lock-move-to-the-fcmaes-rust-validated-numerics-tutorial). That pull request adds a Julia tutorial, `tutorials/validated-numerics/`, outside the Rust workspace, plus documentation and a workflow; no Rust source, dependency or shared pin changed. The other three mains are unchanged, and the workers still pin optimization-jobs `8b4489d`.

**Baseline.** `scripts/baseline.py all --build-toolchain stable --jobs 2` ran in a fresh workspace on 26 October 2026 (UTC), fetching every repository from GitHub, with Rust 1.97.0 for builds and lints. All 26 steps passed. The files at the top level and in `checks/`, `smoke/` and `command-example/` were written by the tool.

- `summary.json`: actions, toolchains and each step's status, exit code and duration.
- `sources.json`, `environment.json`, `toolchains.json`, `binaries.json`: verified commits and shared tree IDs, the container, the exact Rust versions, and the staged executables with their manifest.
- `checks/`: the record and unedited log of every step.
- `smoke/`: every runner call's stdout, stderr and JSON and the smoke summary. The node root with the native journals and the copied worker executables is not kept.
- `command-example/`: the example's build and run records, its calls and its summary. The compiled program, its source, the collected answer bytes and the node root are not kept.

**Suites**, against the binaries of this baseline:

- `campaign/unit.log`: the 144 unit tests, including the link, heading and manual option checks.
- `campaign/integration_campaign.log`: the 64 live campaign tests with the real runner and all three workers.
- `campaign/local-mixed.log`, `campaign/scientific.log`, `campaign/rehearsal.log`: the seven-job campaign example, the 17-job comparison example and the recovery rehearsal.
- `campaign/dashboard-dom.log` and `dashboard/dom-summary.json`: the jsdom interaction test, with ten completed jobs and a stopped tour.
- `dashboard/browser-report.json`: the rendered Chromium check, 22 checks passed with ten completed native jobs.

Absolute paths refer to the review container.
