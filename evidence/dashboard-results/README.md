# Artifact and recorded audit dashboard evidence

27 October 2026 (America/Lima). Base experiment-craft `7ac945d`; native pins
are unchanged. This is one Linux environment with one-slot local foreground
nodes. Emulated phone and desktop viewports do not establish physical-phone,
independent-host or service/reboot commissioning.

| Check | Result |
| --- | --- |
| Python unit suite | 176 passed |
| Real-runner integration | 77 passed |
| Pinned source/binary verification and smoke | Passed using the checked unchanged build |
| Existing jsdom dashboard interactions | Passed; ten completed jobs and one cancelled workflow job |
| Existing rendered Chromium dashboard | Passed at phone and desktop sizes |
| New result UI | 39 checks passed; nine fixture-copying command jobs, no added jobs from result actions |
| Retained real CAP report rendering | Scalar/PDE JSON, Markdown and CSV remain byte-identical |
| Package wheel | Builds; new assets and snapshot schema match source bytes |

The result workflow exercises explicit artifact loading and collection,
checked report/raw downloads, every recorded verdict, censoring, pending
unknowns, late responses, superseded operation recovery and corrupt-cache
refusal. UI fixture commands copy recorded documents with the application's
plan shape; they run no scientific checker and produce no new proof evidence.
The existing real certificate snapshots are in
[verification-reports](../verification-reports/README.md).

Playwright 1.63.0 used packaged Chromium 153.0.8010.0 locally: the default
browser-download endpoint returned an HTML error page. The test executable
and argv overrides selected that binary; CI retains the default browser.
No production dependency was added. Browser images were inspected locally;
these evidence files contain test results and hashes, not screenshots.

The new CI workflow was not run remotely for this patch. The full upstream
Rust matrix and fresh Julia campaigns were not rerun. RT-07/RT-08 and the
previous unidentified Rust flake remain open. Source, environment and binary
hashes are recorded in `source-snapshot.json`; file hashes are in
`files-sha256.json`. See the [implementation log](../../implementation-log.md#ui-02--artifacts-and-recorded-certificate-audits).
