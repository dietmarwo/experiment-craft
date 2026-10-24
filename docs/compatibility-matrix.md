# P0 compatibility matrix

Recorded 2026-10-24 on Linux x86_64, Rust 1.88.0 and CPython 3.12.14. Full commits and file hashes are in [baseline-lock.json](../baseline-lock.json). The project started at `bcd74e9e2ba2c04088601bde5a786013f2053a1d`, containing only its MIT license.

## Source and executable pairing

| Repository | Full source revision | Executable/version | Result |
|---|---|---|---|
| optimization-jobs | `f65e664f12cfa68c3e23a070147ea2a6fed87944` | `optimization-run` and `optimization-mcp` 0.3.0 | Release build and shared runtime suites pass |
| fcmaes-rust | `bdd01e846226544e76cd1c9267e3c78719212041` | `fcmaes-job-worker` 0.2.1 | Release build and native runtime integration pass; strict workspace Clippy has recorded diagnostics |
| LP-IP-craft | `3645d2d6962f30d4962cb5700a3d0b1e392345d5` | `lp-ip-job-worker` 0.29.0 | Release build and native runtime integration pass; strict workspace Clippy has a recorded diagnostic |
| SQP-craft | `3f155f9aa6acc680f9e6d4a0c8b80d26468e619d` | `sqp-job-worker` 0.17.0 | Release build and native runtime integration pass; strict workspace Clippy has a recorded diagnostic |

All three workers use shared `optimization-job-api`/`optimization-runner` 0.3.0 pinned at `37b30e428c5fdd017975e0093cc261243148257f`. The runner executable was built from current optimization-jobs, while worker builds selected only each worker package. The relevant Rust crate and job-schema Git trees at the two shared revisions are identical; see [tree comparison](../evidence/runtime-tree-comparison.json). No worker pin was changed.

| Contract | Produced/tested baseline | Compatibility boundary |
|---|---|---|
| Optimization job envelope | `optimization.job/0.1` | Strict existing envelope; future command fields do not belong here |
| Worker discovery/execution | `optimization.worker/0.2` | Runtime also accepts 0.1; three workers here advertise 0.2 |
| Native result manifest | `optimization.result/0.2` | Schema also accepts 0.1; retain evidence/claim distinctions |
| Local runner provenance | `optimization.runner/0.1` | This is not a fleet handle or generic execution record |
| Shared schema validator | jsonschema 4.26.0 | Required, not silently skipped in the recorded harness runs |

## Retained real jobs

All jobs ran through the actual native binaries in foreground mode on one node root with capacity 1. Each used one task and passed schema validation, key-reuse/journal-stability and changed-key-identity rejection checks.

| Worker/profile | Small problem | Recorded objective | Claim / evidence |
|---|---|---:|---|
| fcmaes / `fcmaes.retry/1` | 2D sphere, BiteOpt, seed 1, 100 evaluations | 0.011643188766312476 | `best_found`; objective/bounds rechecked |
| lp-ip / `lp-ip.solve/1` | Two binary variables, choose one, offset 5 | 7.0 | `numerical_optimum`; objective, bounds, constraints, integrality rechecked; numerical bound 7 |
| sqp / `sqp.solve/1` | Four-variable simplex quadratic | 0.25 | `first_order`; objective, bounds, constraints and KKT rechecked |

The smoke suite also changed model bytes while retaining the original digest and confirmed `invalid_job`. [Summary](../evidence/smoke/summary.json), [fixtures](../examples/smoke/), and retained manifests/journals provide the evidence. This is a correctness check, not a performance benchmark or a mathematical proof of global optimality.

The broader shared integration suite exercises all three workers, runnable discovery examples, threaded/serial agreement, cancellation/timeouts, admission and recovery. The review suite selected the SQP real worker; the integration suite supplies the multi-worker coverage. The MCP suite includes both protocol fixtures and real-worker calls. Its systemd test passed the unavailable-manager branch; positive detached operation was not validated.

## Interpretation

This exact set is a compatible local execution baseline. It is not an all-green full-repository CI certificate: strict upstream lint failures and any other check outcomes are listed without suppression in the [implementation log](../implementation-log.md). Generic commands, binary transfers, fleet placement and campaigns remain planned. See [validation limits](known-limitations.md) before commissioning hardware.
