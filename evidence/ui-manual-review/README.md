# UI user manual review evidence

The suites after the review of the [UI user manual](../../docs/ui-user-manual.md), recorded in the [implementation log](../../implementation-log.md#ui-user-manual-review-and-merge). They ran on 26 October 2026 (UTC) against the binaries built from the commits in `baseline-lock.json`, the build of [`evidence/ui-01-review/`](../ui-01-review/README.md). No native source has moved since then, so the native baseline was not run again.

- `campaign/unit.log`: the 144 unit tests, including the link, heading and manual option checks.
- `campaign/integration_campaign.log`: the 64 live campaign tests with the real runner and all three workers.
- `campaign/local-mixed.log`, `campaign/scientific.log`, `campaign/rehearsal.log`: the seven-job campaign example, the 17-job comparison example and the recovery rehearsal.
- `campaign/dashboard-dom.log` and `dashboard-dom/`: the jsdom interaction test against the real server and workers, with the summary, the snapshots before and after the server's exit for the completed and the stopped tour, and the exported history. The demo node roots and campaign workspaces are not kept.
- `dashboard-browser/`: the rendered check in Chromium (Playwright 1.63.0) at a 390 × 844 touch viewport and at 1366 × 900, with `report.json` (22 checks, ten completed native jobs, clean shutdown) and its three screenshots of the page as changed by the review.
- `manual-commands.log`: the manual's commands on a fresh demo, with their output and exit status: shell syntax of its nine bash blocks, `--version`, `dashboard --help`, a second preparation into the same directory, `dry-run`, `continue`, `report`, `backup` before and after `pause-dispatch`, `maintenance-status`, and the reopen command with `--port 0` stopped by SIGTERM.

Absolute paths refer to the review container.
