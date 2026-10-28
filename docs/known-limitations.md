# Validation limits

P5 implements local campaigns, P6 adds predeclared scientific comparisons and P7 adds local operations/configuration preparation through the unchanged merged P3 runtime. See [campaign limits](campaigns.md) and the [blocked backend gate](backend-gate.md).

P3 implements explicit SSH placement and persisted recovery. Real transport is tested; the service manager in those tests is simulated. Actual backend/hardware commissioning remains open.

P2 introduced trusted local commands and verified local files. P3 extends those paths to explicit SSH nodes; automatic allocation remains gated.

| Area | What was established | What remains unvalidated or unimplemented |
|---|---|---|
| Native local execution | Current runner built with all three independently pinned workers; real numerical jobs and shared black-box harnesses | Other operating systems/architectures and host-specific installations |
| Resource accounting | Shared command/optimization admission and queue cancellation tested; smoke uses capacity 1 | Physical-core mapping, affinity, memory limits, hard CPU enforcement |
| Detached execution | Manager/linger prerequisite and existing service launch; simulated manager tests plus actual SSH connection abort | Positive real systemd user service, logout survival, reboot/linger and cgroup enforcement on a suitable host |
| Multi-node behavior | Explicit node selection, SSH host-key/authentication checks, binary staging/collection, lost acknowledgements, coordinator restart and same-node reconciliation | Actual independent hosts, successful real systemd services/logout/reboot and automatic fleet/group-budget scheduling |
| Generic commands/files | Literal argv and the submitted argv[0], explicit environment, hashed scripts/executables, sealed outputs, interrupted stdin uploads, no-clobber downloads and size/digest/path checks tested; dedicated retained-byte blob-quota test; MCP refuses command requests; a process that leaves the group no longer holds the launcher | Filesystem sandbox; undeclared working-data quota; hostile same-UID races; containment of descendants that escape the process group |
| Python layer | Local campaign compiler/client, snapshots, transactional decisions, dependencies, declared budgets, stop/restart, offline campaign/comparison reports, predeclared protocols and representative native suites; Python 3.12 wheel/console checks | Fleet integration, browser manifest/protocol editing, multi-user/public hosting, published distribution and a supported interpreter/platform matrix |
| Verification views | Checked local named command outputs and an offline CAP audit receipt adapter, bound to admitted input snapshots; native state and reported scientific verdict are separate | Independent theorem checking during reporting, proof-aware dashboard, predeclared certificate cohorts, anytime certification and semantic cross-environment replay |
| Solver validation | Rust workspace checks and relevant native worker/runtime tests, with detailed logs | Full Python-binding wheel/test matrices, long benchmarks, complete scientific tutorial suites and external solver comparisons |
| Recovery | Existing harness exercises journal corruption/repair, cancellation, launcher loss and conservative reservations | Power-loss/filesystem crash testing and long-running home workloads |
| Reproducibility | Full source commits, Cargo/manifest/schema hashes, dependency versions, commands and observed binary hashes | Offline dependency vendoring or bit-identical binaries across build directories and platforms |

The SQP workspace intentionally ignores one `census` test used to generate documentation. Its test log records that reason. This checkpoint did not override the ignored-test setting.

No home machine was accessed. Home-machine commissioning is deferred until January 2027 as stated in the plan. No simulated test is labeled hardware validation. P1 changed runtime source and moved all three worker pins. Existing optimization contracts remain; discovery and observation APIs are additive. No tag or release was made.

At the historical P0 commits, Clippy 1.88 was not clean for the three solver workspaces; stable Clippy was. The three fixes are now merged and the refreshed pre-P1 baseline passed; the following diagnostics describe historical P0 evidence. These diagnostics do not prevent the release worker builds or real-job checks, and no warning policy was relaxed. The P0 run stopped at the first failing crate of each workspace; with `--keep-going`, fcmaes-rust shows three more. The baseline now lints with stable Rust, as the repositories do. The fixes, which make Clippy 1.88 clean as well, are [backlog items BL-01 to BL-03](implementation-backlog.md#baseline-maintenance); they are no longer open blockers for the current baseline. Reproducing those failures requires the historical P0 lock.

| Repository | Diagnostic | Location |
|---|---|---|
| fcmaes-rust | `clippy::needless_range_loop` (two) | `crates/fcmaes-core/src/da.rs:491` and `:506` |
| fcmaes-rust | `clippy::uninlined_format_args` (three, found with `--keep-going`) | `crates/fcmaes-core/src/cmaes.rs:768`, `crates/fcmaes-native-worker/src/main.rs:200` and `:213` |
| LP-IP-craft | `clippy::collapsible_else_if` | `crates/native/src/lu.rs:1182` |
| SQP-craft | `clippy::uninlined_format_args` | `crates/sqp-job-worker/src/lib.rs:134` |

The container's `systemctl --user is-system-running` command printed that systemd was unavailable while returning exit 0. The runner's actual doctor result and the MCP unavailable-manager branch are the relevant evidence; the shell exit code alone is not a successful service test.

The initial smoke-tool development run expected `invalid_spec` for a corrupted model input. The actual documented runtime code is `invalid_job`; the new checker was corrected and rerun successfully. Both records are retained. This was a client-test expectation error, not an upstream defect.

P5 advances sequentially on one explicitly configured local node. Persisted intent without an observed native job is uncertain, not permission to relaunch. Unknown work retains declared reservations. Client deadlines request cancellation while the client is present; they are not always-on backend group enforcement. Foreground continuation after killing only Python does not establish survival of terminal logout or reboot. Reports preserve outcomes and failures; [P6](scientific-comparisons.md) adds explicit compatible protocols, complete/available cohorts and descriptive summaries. Cross-workspace, multi-task, multi-objective, external-solver, long benchmark and inferential comparisons remain unsupported. Input snapshots are bounded; undeclared command reads/writes, host interpreter libraries, aggregate retained result storage and hostile same-UID races remain outside these guarantees. P7 exercises SQLite campaign backups and paused restores plus a controlled quiescent native-root copy. It does not establish power-loss, live/concurrent native snapshot, service or cross-host commissioning. A workspace records its last decision in `head.json` and refuses a database that is behind it. A copy without that record, or an earlier copy of the whole directory, is not detected: the check of never-issued handles still refuses a step that another copy launched, but a stop or pause that the copy lacks is not restored. Pause is cooperative for 0.3.0 clients; old clients/direct native submitters require operator coordination, and only one restored campaign copy may be writable. The campaign state is one JSON document that every decision rewrites. For 4,096 small fcmaes jobs it is about 4 MB at initialization and about 13 MB once every step has finished; unchanged observations write nothing, but very large campaigns with many short steps pay for each decision. Initialization validates the steps with one runtime call each, several minutes for 4,096 steps on a loaded two-CPU machine.


The [local dashboard](dashboard.md) adds a single-operator browser UI over
initialized local campaigns. Its per-node history is sampled saved state, starts
with first dashboard observation, and is not live machine telemetry or exact
execution timing. Startup never resumes work. Two local node roots on one host
validate grouping only; actual independent hosts remain uncommissioned. Remote
routing, probes, solver convergence, CPU/RAM/GPU telemetry, LAN/phone access and
multi-user hosting remain separate work. History is bounded by point count and
changing the attached campaign set removes inactive aggregate scopes. Ctrl-C
or SIGTERM stops the dashboard between steps and leaves the job in flight
running to completion; a hard kill leaves recovery to the native handles. The
rendered check uses Chromium at desktop and emulated phone sizes; a physical
phone has not been checked. Each refresh carries every step of every attached
campaign, so very large campaigns make refreshes large.

The dashboard collects and downloads command artifacts and displays recorded
CAP audit receipts; it runs no independent theorem checker, compares no
predeclared certificate cohorts and edits no protocols. The page gives each
read, including a download, eight seconds: a catalog page with many large
retained copies, or a large download over a slow connection, can exceed that
and shows an error; the CLI reads the same data without that limit. Collection
runs as an operation and is not bound by it. The server ends a download whose client
stays idle for five seconds.
