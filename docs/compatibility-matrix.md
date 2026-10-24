# Compatibility matrix

## P2 (current baseline)

The merged commits below are the ones in [baseline-lock.json](../baseline-lock.json). All three workers pin optimization-jobs at `2351e40842d228d98880282a7788eb195c74d718`, the head of [optimization-jobs#22](https://github.com/dietmarwo/optimization-jobs/pull/22). The [implementation log](../implementation-log.md#p2--trusted-local-commands-and-binary-files) records the implementation and its checks before merge; the [P2 review](../implementation-log.md#p2-review-and-merge) records the changes made in review and the baseline run at these commits.

| Repository | Merged commit | Pull request |
|---|---|---|
| optimization-jobs | `d9827d107cd201332664db3c120f150b928579fa` | [#22](https://github.com/dietmarwo/optimization-jobs/pull/22) |
| fcmaes-rust | `cca34c2d0dfe2e40d44c8f346fdc7b6afecdca7d` | [#33](https://github.com/dietmarwo/fcmaes-rust/pull/33) |
| LP-IP-craft | `1162df71daecb1d8307fcdc848e8529c6939d3bb` | [#35](https://github.com/dietmarwo/LP-IP-craft/pull/35) |
| SQP-craft | `b1d719c1aaba8b879e352a564f56c581edd382da` | [#37](https://github.com/dietmarwo/SQP-craft/pull/37) |

| Interface | P2 behavior |
|---|---|
| Optimization SDK / envelopes / results | Unchanged; mathematical claims remain native |
| Commands | Opt-in CLI `execution.command/0.1`: literal argv run under the submitted argv[0], explicit environment, verified inputs, declared outputs, replay=never |
| Command outcome | `execution.command.result/0.1`; no objective, feasibility or optimization claim |
| Neutral observation | Existing terminal `execution.record/0.1` with the native attachment's size and digest |
| Discovery | `execution.capabilities/0.2`: supported versus enabled kinds, CLI file/command interfaces and limits |
| Binary files | `files put/get/cleanup` and sealed command outputs through `jobs collect`; bounded, verified, atomic no-clobber publication |
| MCP | Optimization submission and tools as before; `validate_job` and `submit_job` refuse command requests, as does every runner the server starts; result summaries reject command jobs |
| Fleet / isolation | No fleet; trusted same-user process groups, no kernel CPU/memory/disk enforcement |

Before the pins moved, the implementation passed 24 baseline steps, 815 Rust tests (one existing SQP census test ignored) and 27 review, 36 MCP, 16 mixed integration and 15 command/file tests, with both the pinned and the checkout SDK ([evidence](../evidence/p2/README.md)). The baseline at the merged commits passed all 24 steps against GitHub, including 19 command/file tests and the build–run–collect example. Its smoke jobs validate capability schema 0.2. The objectives are unchanged: 0.011643188766312476 (sphere), 7.0 (binary LP/IP) and 0.25 (simplex SQP), with their distinct claims and evidence.

Stable lints and Rust 1.88 builds and tests remain separate. Positive detached systemd and home-machine or fleet behavior remain unvalidated; see [limits](known-limitations.md).

## P1 (historical)

The merged P1 commits are below; the current [baseline-lock.json](../baseline-lock.json) describes P2. All three workers pinned optimization-jobs at `70e210fbf562900c1be8f278e2ab2852ef5934e3`, the head of [optimization-jobs#21](https://github.com/dietmarwo/optimization-jobs/pull/21). The [implementation log](../implementation-log.md#p1--execution-boundary-and-observations) records the implementation and its checks before merge; the [P1 review](../implementation-log.md#p1-review-and-merge) records the changes made in review and the baseline run at these commits.

| Repository | Merged commit | Pull request |
|---|---|---|
| optimization-jobs | `a61379821e667847105f5bf4c3d8cd893cbe861c` | [#21](https://github.com/dietmarwo/optimization-jobs/pull/21) |
| fcmaes-rust | `8dd061add421457c3c6beee54b58e12af8cda06b` | [#32](https://github.com/dietmarwo/fcmaes-rust/pull/32) |
| LP-IP-craft | `d25f874eee4b8674281dd8120f9b86886444e4fd` | [#34](https://github.com/dietmarwo/LP-IP-craft/pull/34) |
| SQP-craft | `ec348c1ca327a04938261cffeada8eaed2d5f599` | [#36](https://github.com/dietmarwo/SQP-craft/pull/36) |

| Interface | P1 behavior |
|---|---|
| Optimization envelope / worker / result | Unchanged: job 0.1, worker 0.1/0.2 compatibility, native result 0.2 with compare also reading 0.1 |
| Legacy fcmaes envelope/result | Still `fcmaes.job/0.1` and native schema integer `1`; real legacy execution checked |
| Discovery | `execution.capabilities/0.1`; CLI `node capabilities`, doctor and MCP `describe_node` |
| Neutral record | `execution.record/0.1`; CLI `jobs execution ID`; no mathematical claims |
| Unfinished attempts | `jobs execution` returns the retryable `attempt_active` until `job.json` is terminal; a record is served only if it matches that state |
| Old terminal directories | Native tools still work; a missing or non-matching record returns `execution_unavailable`; no backfill |
| Command / file transfer / fleet | Explicitly unsupported; neutral fixture exists only in tests |

The pre-refactor baseline passed all 22 steps. Before the pins moved, the new runner passed 27 review, 36 MCP and 16 mixed integration tests, plus six per-worker MCP checks, with both the pinned and the checkout SDK. The baseline at the merged commits passed all 22 steps against GitHub. Its smoke jobs validate the native result and execution record schemas and the attachment size and digest. The objectives are unchanged: 0.011643188766312476 (sphere), 7.0 (binary LP/IP) and 0.25 (simplex SQP), with their distinct claims and evidence.

Stable lints and Rust 1.88 builds and tests remain separate. Positive detached systemd and home-machine or fleet behavior remain unvalidated; see [limits](known-limitations.md).

## P0 (historical)

Recorded 2026-10-24 on Linux x86_64, Rust 1.88.0 and CPython 3.12.14; the [P0 review](../implementation-log.md#p0-review) repeated the build and smoke jobs. The P0 commits are listed below; the current [baseline-lock.json](../baseline-lock.json) describes P2. The project started at `bcd74e9e2ba2c04088601bde5a786013f2053a1d`, containing only its MIT license.

### Source and executable pairing

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

### Retained real jobs

All jobs ran through the actual native binaries in foreground mode on one node root with capacity 1. Each used one task and passed schema validation, key-reuse/journal-stability and changed-key-identity rejection checks.

| Worker/profile | Small problem | Recorded objective | Claim / evidence |
|---|---|---:|---|
| fcmaes / `fcmaes.retry/1` | 2D sphere, BiteOpt, seed 1, 100 evaluations | 0.011643188766312476 | `best_found`; objective/bounds rechecked |
| lp-ip / `lp-ip.solve/1` | Two binary variables, choose one, offset 5 | 7.0 | `numerical_optimum`; objective, bounds, constraints, integrality rechecked; numerical bound 7 |
| sqp / `sqp.solve/1` | Four-variable simplex quadratic | 0.25 | `first_order`; objective, bounds, constraints and KKT rechecked |

The smoke suite also changed model bytes while retaining the original digest and confirmed `invalid_job`. [Summary](../evidence/p0/smoke/summary.json), [fixtures](../examples/smoke/), and retained manifests/journals provide the evidence. This is a correctness check, not a performance benchmark or a mathematical proof of global optimality.

The broader shared integration suite exercises all three workers, runnable discovery examples, threaded/serial agreement, cancellation/timeouts, admission and recovery. The review suite selected the SQP real worker; the integration suite supplies the multi-worker coverage. The MCP suite includes both protocol fixtures and real-worker calls. Its systemd test passed the unavailable-manager branch; positive detached operation was not validated.

### Interpretation

This exact set is a compatible local execution baseline. It is not a full-repository CI certificate: every check outcome, including the Clippy 1.88 diagnostics that the repositories' stable lint gate does not report ([backlog BL-01 to BL-03](implementation-backlog.md#baseline-maintenance)), is listed without suppression in the [implementation log](../implementation-log.md). Generic commands, binary transfers, fleet placement and campaigns remain planned. See [validation limits](known-limitations.md) before commissioning hardware.
