# Named artifacts and verification report evidence

This evidence records the [artifact and verification report interface](../../docs/verification-reports.md)
over the merged native baseline. It preserves native command state and the
application's recorded verdict separately. Reporting runs no checker and
submits no work.

| Check | Result |
| --- | --- |
| Unit tests, including retained offline views | 167 passed |
| Real-runner campaign tests | 72 passed |
| Upstream CAP collector contracts | 32 passed |
| Pinned native build and smoke jobs | Passed for the runner and all three workers |
| Real scalar and PDE certificate campaigns | Three jobs each; 9/9 reported accepted per problem |
| Fresh Julia verification/replay | 36 processes across the two campaigns |
| Separate exact rational checks | All 18 certificates passed |
| Continuation | No duplicate attempt |
| Existing examples | Local mixed campaign, scientific comparison and operations rehearsal passed |

The source snapshot identifies the checked GitHub bases, pinned native builds,
Python/Julia/Rust versions and scope. The scalar and Cahn–Hilliard examples run
the real search, all-arm audit and acceptance as three foreground command jobs
per problem. Every accepted final candidate is verified and replayed in fresh
Julia processes, with separate exact rational checks by the example.

Each case retains its report, CSV, catalogue/summary and a read-only input
snapshot for rebuilding the report offline. The snapshot has no campaign
database and is not a workspace to continue or restore. It contains the saved
state, native metadata and acceptance input/cache bytes needed by the reader.
The test suite compares the rebuilt report with the recorded bytes while
refusing all runtime calls.

Synthetic test receipts exercise rejection, inconsistent native exits,
corruption and unavailable observations. They are reporting fixtures, not new
proof executions. The real examples and their exact checks are recorded
separately. Censoring is descriptive; no timing ranking, survival estimate,
optimizer advantage, global theorem or region coverage is inferred.

All work used one Linux environment and local foreground node roots, each with
capacity one. The dashboard and native worker/runtime source are unchanged.
Multi-host/systemd/logout/reboot and physical-phone commissioning remain
outside this evidence. GitHub CI is configured for these checks; this delivery
does not claim a remote CI run.

Input snapshots include pinned fcmaes-rust validated-numerics source. The
upstream mathematical examples are credited in that tutorial; the
[RadiiPolynomial license](RADII_POLYNOMIAL_LICENSE.txt) is retained here with
the snapshots.
