# P7 review evidence

The campaign suites after the P7 review, recorded in the [implementation log](../../implementation-log.md#p7-review-and-merge). They ran on 25 October 2026 against binaries built from the commits in `baseline-lock.json`, the same build as [`evidence/p5-review/`](../p5-review/README.md). No native source has moved since then, so the native baseline was not run again for this review.

- `campaign/unit.log`: the 118 unit tests, including the link and heading checks.
- `campaign/integration_campaign.log`: the 57 live campaign tests with the real runner and all three workers.
- `campaign/local-mixed.log` and `campaign/scientific.log`: the seven-job campaign example and the 17-job comparison example.
- `campaign/rehearsal.log` and `rehearsal/`: the recovery rehearsal. It contains the inventory (`deployment.json`) and its offline export (`deployment-plan/`), the source manifest and protocol (`source/`), every runner call (`calls.json`), the comparison reports before the pause, while paused and after restore and reconciliation, the archive's manifest (`BACKUP.json`) and the summary. The node root, its copies, the campaign workspaces and the archive itself are not kept.

Absolute paths refer to the review container.
