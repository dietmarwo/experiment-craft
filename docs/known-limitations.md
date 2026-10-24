# Validation limits

This P0 checkpoint establishes a local Linux source/build/worker baseline. It is not a fleet release.

| Area | What was established | What remains unvalidated or unimplemented |
|---|---|---|
| Native local execution | Current runner built with all three independently pinned workers; real numerical jobs and shared black-box harnesses | Other operating systems/architectures and host-specific installations |
| Resource accounting | Existing slot admission/recovery exercised by upstream tests; smoke uses capacity 1 | Physical-core mapping, affinity, memory limits, hard CPU enforcement and mixed generic-command admission |
| Detached execution | `node doctor` reported `systemd_user_manager: false`; MCP suite exercises the unavailable-manager error branch | Successful detached user service, logout survival, lingering, reboot recovery and cgroup containment on a suitable host |
| Multi-node behavior | Contract and acceptance criteria documented | SSH transport, transfers, fleet coordinator, lost-acknowledgement recovery across hosts, scheduling, group budgets |
| Generic commands/files | Reuse seams and additive design documented; current hashed model input staging verified | Generic shell/argv jobs, binary file upload/download and interrupted network copy |
| Python layer | Baseline scripts and source-drift tests run on Python 3.12.14 (P0) and 3.13 (review) | Campaign package, UI, PyPI distribution, wheel publication and a supported interpreter matrix |
| Solver validation | Rust workspace checks and relevant native worker/runtime tests, with detailed logs | Full Python-binding wheel/test matrices, long benchmarks, complete scientific tutorial suites and external solver comparisons |
| Recovery | Existing harness exercises journal corruption/repair, cancellation, launcher loss and conservative reservations | Power-loss/filesystem crash testing and long-running home workloads |
| Reproducibility | Full source commits, Cargo/manifest/schema hashes, dependency versions, commands and observed binary hashes | Offline dependency vendoring or bit-identical binaries across build directories and platforms |

The SQP workspace intentionally ignores one `census` test used to generate documentation. Its test log records that reason. This checkpoint did not override the ignored-test setting.

No home machine was accessed. Home-machine commissioning is deferred until January 2027 as stated in the plan. No simulated test is labeled hardware validation. No runtime source, worker dependency pin, public API, remote branch, tag or release was changed by P0.

Clippy 1.88 is not clean for the three pinned solver workspaces; the stable Clippy of their CI gate is. These diagnostics do not prevent the release worker builds or real-job checks, and no warning policy was relaxed. The P0 run stopped at the first failing crate of each workspace; with `--keep-going`, fcmaes-rust shows three more. The baseline now lints with stable Rust, as the repositories do. The fixes, which make Clippy 1.88 clean as well, are [backlog items BL-01 to BL-03](implementation-backlog.md#baseline-maintenance); until they merge and the lock moves, `--lint-toolchain 1.88.0` reproduces these failures.

| Repository | Diagnostic | Location |
|---|---|---|
| fcmaes-rust | `clippy::needless_range_loop` (two) | `crates/fcmaes-core/src/da.rs:491` and `:506` |
| fcmaes-rust | `clippy::uninlined_format_args` (three, found with `--keep-going`) | `crates/fcmaes-core/src/cmaes.rs:768`, `crates/fcmaes-native-worker/src/main.rs:200` and `:213` |
| LP-IP-craft | `clippy::collapsible_else_if` | `crates/native/src/lu.rs:1182` |
| SQP-craft | `clippy::uninlined_format_args` | `crates/sqp-job-worker/src/lib.rs:134` |

The container's `systemctl --user is-system-running` command printed that systemd was unavailable while returning exit 0. The runner's actual doctor result and the MCP unavailable-manager branch are the relevant evidence; the shell exit code alone is not a successful service test.

The initial smoke-tool development run expected `invalid_spec` for a corrupted model input. The actual documented runtime code is `invalid_job`; the new checker was corrected and rerun successfully. Both records are retained. This was a client-test expectation error, not an upstream defect.
