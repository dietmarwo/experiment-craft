# P6 review evidence

The campaign suites after the P6 review, recorded in the [implementation log](../../implementation-log.md#p6-review-and-merge). They ran on 25 October 2026 against binaries built from the commits in `baseline-lock.json`, the same commits as [`evidence/p5-review/`](../p5-review/README.md), whose baseline also built these binaries. No native source moved since then, so the native baseline was not run again for this review.

- `campaign/unit.log`: the 92 unit tests, including the link and heading checks.
- `campaign/integration_campaign.log`: the 44 live campaign tests with the real runner and all three workers.
- `campaign/local-mixed.log`: the seven-job campaign example.
- `campaign/scientific.log` and `scientific/`: the 17-job comparison example, with its source manifest, protocol and checker (`source/`), the campaign report (`report/`), the comparison report (`comparison/`) and its summary. The node root and the campaign workspace are not kept.

Absolute paths refer to the review container.
