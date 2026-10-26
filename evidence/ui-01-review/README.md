# UI-01 review evidence

The baseline at the moved lock and the suites after the UI-01 review, recorded in the [implementation log](../../implementation-log.md#ui-01-review-and-merge). The lock now names optimization-jobs `051435c` (its comparison document's update, [optimization-jobs#25](https://github.com/dietmarwo/optimization-jobs/pull/25)); the three workers are unchanged and still pin optimization-jobs `8b4489d`.

**Baseline.** `scripts/baseline.py all --build-toolchain stable --jobs 2` ran in a fresh workspace on 26 October 2026 (UTC), fetching every repository from GitHub, with Rust 1.97.0 for builds and lints. All 26 steps passed. The files at the top level and in `checks/`, `smoke/` and `command-example/` were written by the tool.

- `summary.json`: actions, toolchains and each step's status, exit code and duration.
- `sources.json`, `environment.json`, `toolchains.json`, `binaries.json`: verified commits and shared tree IDs, the container, the exact Rust versions, and the staged executables with their manifest.
- `checks/`: the record and unedited log of every step.
- `smoke/`: every runner call's stdout, stderr and JSON and the smoke summary. The node root with the native journals and the copied worker executables is not kept.
- `command-example/`: the example's build and run records, its calls and its summary. The compiled program, its source, the collected answer bytes and the node root are not kept.

**Suites after the review**, against the binaries of this baseline, on 26 October 2026 (UTC):

- `campaign/unit.log`: the 140 unit tests, including the link and heading checks.
- `campaign/integration_campaign.log`: the 63 live campaign tests with the real runner and all three workers, including Ctrl-C sent to the dashboard's process group and SIGTERM.
- `campaign/local-mixed.log`, `campaign/scientific.log`, `campaign/rehearsal.log`: the seven-job campaign example, the 17-job comparison example and the recovery rehearsal.
- `campaign/dashboard-dom.log` and `dashboard-dom/`: the jsdom interaction test against the real server and workers. It keeps the summary, the snapshots before and after the server's exit for the completed and the stopped tour, and the exported history. The demo node roots and campaign workspaces are not kept.
- `dashboard-browser/`: the rendered check in Chromium (Playwright 1.63.0) at a 390 × 844 touch viewport and at 1366 × 900, with `report.json` (18 checks, ten completed native jobs, clean shutdown) and the three screenshots. It is not a physical phone.

Absolute paths refer to the review container.
