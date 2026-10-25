# Compatibility matrix

## P7 local operations (current client)

The unpublished Python 0.3.0 client adds [operations](operations.md) and
[deployment configuration](deployment.md) over the unchanged native set below.
The seven P5/P6 public schemas are byte-identical to the accepted P6 merge.

| Surface | P7 behavior |
|---|---|
| Dispatch maintenance | Separate versioned table/event; no new intent after an accepted pause; no cancellation of current work |
| Campaign archive | SQLite online snapshot plus checked authoritative inputs/requests/results; bounded/no-clobber publication |
| Restore | New paused workspace, original identities/keys/reservations/deadline and declaration anchors |
| Unpause | Read-only native identity/resolution/result checks and stale never-issued-handle detection; no replay/repair |
| Inventory | One local default, six disabled planned workers; native argv export without node contact |
| Native recovery rehearsal | Sole-client quiescent copy at the original root, Rust reconciliation and unchanged journals |
| Still gated | Independent hosts, remote campaign routing, real services/cgroups, automatic placement, live native snapshots and power loss |

## P6 local comparisons (merged baseline)

The unpublished Python 0.2.0 client adds [scientific comparisons](scientific-comparisons.md)
over the same merged native commits listed below. The fresh [P6 run](../evidence/p6/README.md)
rebuilds and checks those exact public sources, and the [P6 review](../implementation-log.md#p6-review-and-merge)
records the fixes and the suites run against those builds. The four P5 schemas are unchanged.

| Surface | P6 behavior |
|---|---|
| Protocol | `experiment.comparison/0.1`, sealed before dispatch with full template coverage/exclusions |
| Binding | `experiment.comparison.binding/0.1`, one immutable SQLite declaration plus event, bound to campaign and plan |
| Report | `experiment.comparison.report/0.1`, original P5 report/raw results plus every observation and reconstructible descriptive summaries |
| Adapters | One task per `fcmaes.retry/1`, `lp-ip.solve/1` or `sqp.solve/1`; command exit/output checks |
| Compatibility | Same profile, model/input identities, tolerances and resources except explicit supported solver variation and sample fields |
| Design | Work/time caps, explicit seed/start pairing, deterministic timing repeats, complete/available feasible cohorts and missing-data accounting |
| Unchanged gates | Real manager/logout/reboot/cgroups, fleet integration and automatic placement remain RT-07/RT-08 |

## P5 local campaigns (native baseline)

The native runtime is unchanged since P3. [baseline-lock.json](../baseline-lock.json) names the current mains below; since the P3 merges they add only README references to experiment-craft, and all three workers still pin optimization-jobs at `8b4489d5df1340d0b991b11715eb07fbbe45274c`. P5 introduced the Python 0.1.0 package over that CLI contract; the current 0.2.0 client adds P6 without changing it. The [campaign guide](campaigns.md), the [P5 evidence](../evidence/p5/README.md) and the [P5 review](../implementation-log.md#p5-review-and-merge) define the local scope.

| Repository | Locked commit | Pull request |
|---|---|---|
| optimization-jobs | `27c4731a8ab3324793015267f9648e8bf818f9a3` | [#24](https://github.com/dietmarwo/optimization-jobs/pull/24) |
| fcmaes-rust | `ed70f303b7ca7c568af786c6c814b1d13b7c06ef` | [#35](https://github.com/dietmarwo/fcmaes-rust/pull/35) |
| LP-IP-craft | `e5cf5d04322a0ddecfb364b392ef92288bd27ee2` | [#37](https://github.com/dietmarwo/LP-IP-craft/pull/37) |
| SQP-craft | `687b78e22d41e3843226398191c8c62c0246a998` | [#39](https://github.com/dietmarwo/SQP-craft/pull/39) |

| Surface | Implemented local behavior |
|---|---|
| Campaign input | `experiment.campaign/0.1`, strict JSON and deterministic bounded matrix/DAG expansion; static steps validated through the runtime at initialization |
| Resolved plan | `experiment.campaign.plan/0.1`, content/executable identity and immutable source snapshots |
| Decisions | `experiment.campaign.state/0.1`, SQLite transactions/events, stable keys of their own per workspace and predicted native handles |
| Execution | Literal CLI/JSON calls; foreground explicit, systemd delegates native submit with no fallback |
| Continuation/stop | Issued work is observed without replay; missing acknowledgement retains uncertainty/reservations; errors before dispatch leave the step pending; cancelled work is reported as cancelled; failed or cancelled dependencies block downstream work |
| Budgets | Sequential scientific admission limits and absolute client deadline; no second host ledger or claimed backend group enforcement |
| Evidence/report | Native bytes checked against the neutral record; sealed output collection through Rust; `experiment.campaign.report/0.1`, CSV and Markdown generated offline |
| Not enabled | Fleet integration, automatic placement, statistical inference, actual service/logout/reboot or home commissioning |

The live campaign tests use the actual reviewed runner and all three native workers. A seven-job prepare–sweep–solve–check demonstration completes and repeating advancement/reporting changes no native journal. Systemd client-branch tests use explicitly simulated manager commands; the [backend gate](backend-gate.md) remains open.

## P3 (native runtime)

The merged P3 commits below define the native runtime. [baseline-lock.json](../baseline-lock.json) now names the later mains listed under P5, which change only READMEs. All three workers pin optimization-jobs at `8b4489d5df1340d0b991b11715eb07fbbe45274c`, the head of [optimization-jobs#23](https://github.com/dietmarwo/optimization-jobs/pull/23). The [implementation log](../implementation-log.md#p3--explicit-ssh-placement-and-reconciliation) records the implementation and its checks before merge, and the [evidence](../evidence/p3/README.md) separates real transport tests from the simulated service manager; the [P3 review](../implementation-log.md#p3-review-and-merge) records the changes made in review and the baseline run at these commits.

| Repository | Merged commit | Pull request |
|---|---|---|
| optimization-jobs | `717f6a691cf29548ae2807c9cc069ce831daa350` | [#23](https://github.com/dietmarwo/optimization-jobs/pull/23) |
| fcmaes-rust | `c3b0a39848b4e0b3614999cf4e9885e82b97f5c7` | [#34](https://github.com/dietmarwo/fcmaes-rust/pull/34) |
| LP-IP-craft | `1fd856d091246ec44a767bf956ce0e16f0629afc` | [#36](https://github.com/dietmarwo/LP-IP-craft/pull/36) |
| SQP-craft | `e0a75569ef9ca49a838c130a9679d94879c882c0` | [#38](https://github.com/dietmarwo/SQP-craft/pull/38) |

| Interface | P3 behavior |
|---|---|
| Optimization SDK, envelopes, native results | Unchanged; mathematical claims, evidence and accounting stay native |
| Commands and binary files | P2 opt-in/literal-argv and verified no-clobber publication rules preserved |
| Discovery | `execution.capabilities/0.3`; fleet CLI, explicit placement and required systemd user/linger launcher; historical capability schemas retained |
| Node identity | `execution.node/0.1`; persistent ID plus root, boot, capacity, worker/build/profile and launcher observations |
| Remote helper | `execution.remote/0.1`; fixed absolute helper over strict pinned-host-key SSH, bounded JSON on stdin and checked binary bodies |
| Fleet handle | `execution.fleet.job/0.1`; coordinator/global key, fixed endpoint/node identity, snapshots and native job/unit/provenance mapping |
| Recovery | Staging can resume from retained snapshots before dispatch, also by repeating the request; issued or uncertain work is observed on the same node and never automatically relaunched or moved; a node's refusal is final and keeps its code |
| Collection | Native manifest, neutral record, sealed command output or native artifact; independent checksum-verified retry without execution |
| MCP | Optimization-only submission preserved; command refusal and runner environment guard remain in force |
| Placement/resources | Explicit node selection only; local admission shared by both job kinds; no automatic placement, group budget or new kernel enforcement |

Before the pins moved, the implementation passed 26 baseline steps, 819 Rust tests (one existing SQP census test ignored) and 27 review, 38 MCP, 16 mixed integration, 19 command/file, 13 remote fixture and 4 real SSH tests, with both the pinned and the checkout SDK ([evidence](../evidence/p3/README.md)). The baseline at the merged commits passed all 26 steps against GitHub, including 18 remote fixture and 4 real SSH tests. The objectives are unchanged: 0.011643188766312476 (sphere), 7.0 (binary LP/IP) and 0.25 (simplex SQP), with their distinct claims and evidence.

Real SSH authentication, host-key refusal, a 1 MiB binary round trip, a deliberate disconnect after launch and all three real Rust workers are exercised through a disposable AsyncSSH endpoint. The user-service manager in those tests is simulated. Actual systemd service persistence, logout/reboot, cgroup enforcement and home hardware remain unvalidated; [RT-07](implementation-backlog.md) is the next backend gate, and automatic placement remains blocked on that evidence.

Stable lints and Rust 1.88 builds and tests remain separate; see [limits](known-limitations.md).

## P2 (historical)

The merged P2 commits below are historical; [baseline-lock.json](../baseline-lock.json) now describes P3. All three workers pinned optimization-jobs at `2351e40842d228d98880282a7788eb195c74d718`, the head of [optimization-jobs#22](https://github.com/dietmarwo/optimization-jobs/pull/22). The [implementation log](../implementation-log.md#p2--trusted-local-commands-and-binary-files) records the implementation and its checks before merge; the [P2 review](../implementation-log.md#p2-review-and-merge) records the changes made in review and the baseline run at these commits.

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

The merged P1 commits are below; the current [baseline-lock.json](../baseline-lock.json) describes P3. All three workers pinned optimization-jobs at `70e210fbf562900c1be8f278e2ab2852ef5934e3`, the head of [optimization-jobs#21](https://github.com/dietmarwo/optimization-jobs/pull/21). The [implementation log](../implementation-log.md#p1--execution-boundary-and-observations) records the implementation and its checks before merge; the [P1 review](../implementation-log.md#p1-review-and-merge) records the changes made in review and the baseline run at these commits.

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

Recorded 2026-10-24 on Linux x86_64, Rust 1.88.0 and CPython 3.12.14; the [P0 review](../implementation-log.md#p0-review) repeated the build and smoke jobs. The P0 commits are listed below; the current [baseline-lock.json](../baseline-lock.json) describes P3. The project started at `bcd74e9e2ba2c04088601bde5a786013f2053a1d`, containing only its MIT license.

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
