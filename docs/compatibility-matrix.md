# P1 compatibility matrix

The exact P1 candidates below extend the merged P0/review baseline.
The [implementation log](../implementation-log.md#p1--execution-boundary-and-observations)
records the original GitHub heads, build environment, checks and remaining
merge gates. These commits are supplied in the patch ZIP's Git bundles;
they have not been published by this iteration.

| Repository | Candidate source revision |
|---|---|
| optimization-jobs | `4f93d75ba9dc0ca40d6de455261b7a753f130976` |
| fcmaes-rust | `505ea687e0cc2ff5253edb13fb1d0943bd42017e` |
| LP-IP-craft | `b490a1389e57b064e9ab0c9a952bc72dd0f66f1f` |
| SQP-craft | `6979501181080ec743fe02122cc1921abbf9a344` |

| Interface | P1 behavior |
|---|---|
| Optimization envelope / worker / result | Unchanged: job 0.1, worker 0.1/0.2 compatibility, native result 0.2 with compare also reading 0.1 |
| Legacy fcmaes envelope/result | Still `fcmaes.job/0.1` and native schema integer `1`; real legacy execution checked |
| Discovery | `execution.capabilities/0.1`; CLI `node capabilities`, doctor and MCP `describe_node` |
| Neutral record | `execution.record/0.1`; CLI `jobs execution ID`; no mathematical claims |
| Old terminal directories | Native tools still work; absent sidecar returns `execution_unavailable`; no backfill |
| Command / file transfer / fleet | Explicitly unsupported; neutral fixture exists only in tests |

The pre-refactor refreshed GitHub baseline passed all 22 steps. The new runner
also passed 27 review, 36 MCP and 16 mixed integration tests, plus six per-worker
MCP checks, in **both** pinned-SDK and checkout-SDK modes before pin changes.
The final baseline result is recorded in the implementation log; its smoke jobs
validate each native/neutral schema and the attachment digest/size. Expected
objectives remain 0.011643188766312476 (sphere), 7.0 (binary LP/IP) and 0.25
(simplex SQP), with their existing distinct claims/evidence.

Stable lints and Rust 1.88 builds/tests remain separate. Positive detached
systemd and home-machine/fleet behavior remain unvalidated. Shared-pin ancestry
on public `main` and a post-merge GitHub baseline must pass before P1 is accepted
as merged. See [limits](known-limitations.md).

---

# P0 compatibility matrix (historical)

Recorded 2026-10-24 on Linux x86_64, Rust 1.88.0 and CPython 3.12.14; the [P0 review](../implementation-log.md#p0-review) repeated the build and smoke jobs. The P0 commits are listed below; the current [baseline-lock.json](../baseline-lock.json) now describes P1. The project started at `bcd74e9e2ba2c04088601bde5a786013f2053a1d`, containing only its MIT license.

## Source and executable pairing

| Repository | Full source revision | Executable/version | Result |
|---|---|---|---|
| optimization-jobs | `f65e664f12cfa68c3e23a070147ea2a6fed87944` | `optimization-run` and `optimization-mcp` 0.3.0 | Release build and shared runtime suites pass |
| fcmaes-rust | `bdd01e846226544e76cd1c9267e3c78719212041` | `fcmaes-job-worker` 0.2.1 | Release build and native runtime integration pass; Clippy 1.88 reported diagnostics (BL-01) |
| LP-IP-craft | `3645d2d6962f30d4962cb5700a3d0b1e392345d5` | `lp-ip-job-worker` 0.29.0 | Release build and native runtime integration pass; Clippy 1.88 reported one diagnostic (BL-02) |
| SQP-craft | `3f155f9aa6acc680f9e6d4a0c8b80d26468e619d` | `sqp-job-worker` 0.17.0 | Release build and native runtime integration pass; Clippy 1.88 reported one diagnostic (BL-03) |

All three workers use shared `optimization-job-api`/`optimization-runner` 0.3.0 pinned at `37b30e428c5fdd017975e0093cc261243148257f`. The runner executable was built from current optimization-jobs, while worker builds selected only each worker package. The relevant Rust crate and job-schema Git trees at the two shared revisions are identical; see [tree comparison](../evidence/p0/runtime-tree-comparison.json). None of the paths that the workers' `shared-pin.yml` compares (`crates`, `ai-context.md`, `docs/job-api.md`, `docs/job-api`, `scripts/job-api`, `Cargo.lock`) changed, and `scripts/baseline.py verify` checks this. No worker pin was changed.

| Contract | Produced/tested baseline | Compatibility boundary |
|---|---|---|
| Optimization job envelope | `optimization.job/0.1` | Strict existing envelope; future command fields do not belong here |
| Worker discovery/execution | `optimization.worker/0.2` | Runtime also accepts 0.1; three workers here advertise 0.2 |
| Native result manifest | `optimization.result/0.2` | New manifests are written as 0.2; `compare` also reads 0.1. Retain the evidence and claim distinctions |
| Local runner provenance | `optimization.runner/0.1` | This is not a fleet handle or generic execution record |
| Shared schema validator | jsonschema 4.26.0 | Required, not silently skipped in the recorded harness runs |

## Retained real jobs

All jobs ran through the actual native binaries in foreground mode on one node root with capacity 1. Each used one task and passed schema validation, key-reuse/journal-stability and changed-key-identity rejection checks.

| Worker/profile | Small problem | Recorded objective | Claim / evidence |
|---|---|---:|---|
| fcmaes / `fcmaes.retry/1` | 2D sphere, BiteOpt, seed 1, 100 evaluations | 0.011643188766312476 | `best_found`; objective/bounds rechecked |
| lp-ip / `lp-ip.solve/1` | Two binary variables, choose one, offset 5 | 7.0 | `numerical_optimum`; objective, bounds, constraints, integrality rechecked; numerical bound 7 |
| sqp / `sqp.solve/1` | Four-variable simplex quadratic | 0.25 | `first_order`; objective, bounds, constraints and KKT rechecked |

The smoke suite also changed model bytes while retaining the original digest and confirmed `invalid_job`. [Summary](../evidence/p0/smoke/summary.json), [fixtures](../examples/smoke/), and retained manifests/journals provide the evidence. This is a correctness check, not a performance benchmark or a mathematical proof of global optimality.

The broader shared integration suite exercises all three workers, runnable discovery examples, threaded/serial agreement, cancellation/timeouts, admission and recovery. The review suite selected the SQP real worker; the integration suite supplies the multi-worker coverage. The MCP suite includes both protocol fixtures and real-worker calls. Its systemd test passed the unavailable-manager branch; positive detached operation was not validated.

## Interpretation

This exact set is a compatible local execution baseline. It is not a full-repository CI certificate: every check outcome, including the Clippy 1.88 diagnostics that the repositories' stable lint gate does not report ([backlog BL-01 to BL-03](implementation-backlog.md#baseline-maintenance)), is listed without suppression in the [implementation log](../implementation-log.md). Generic commands, binary transfers, fleet placement and campaigns remain planned. See [validation limits](known-limitations.md) before commissioning hardware.
