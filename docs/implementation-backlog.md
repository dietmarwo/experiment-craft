# Prioritized implementation backlog

P0 establishes a compatible foundation. These are proposed work items; none is an assertion that a future runtime or campaign feature already exists. Follow the phase gates of the accepted plan rather than implementing all items in parallel.

| Order / ID | Repository / phase | Concrete change | Acceptance and dependency |
|---|---|---|---|
| 1 — OJ-01 | optimization-jobs / P1 | Extract neutral execution lifecycle, supervision and admission interfaces behind the existing CLI | Existing review, MCP, integration and Rust tests pass; old job/result fixtures unchanged; local execution needs no fleet service. Starts from this baseline. |
| 2 — OJ-02 | optimization-jobs / P1 | Define versioned neutral request/record and capability discovery; keep native optimization attachment | A neutral fixture completes without an objective or feasibility claim; unsupported kinds reject explicitly; embedded schemas/guide stay synchronized. Requires OJ-01. |
| 3 — OJ-03 | optimization-jobs / P2 | Add separately enabled command adapter: argv, explicit script input, environment and exit/signal outcome | Literal shell metacharacters stay literal; command and optimization jobs share admission; deadline/cancel covers descendants under the chosen containment policy. Requires OJ-02. |
| 4 — OJ-04 | optimization-jobs / P2 | Generalize checked staging and artifact collection to arbitrary files | Safe paths, reserved names, size/digest checks, atomic publication, bounded transfer and cleanup; interrupted copy never looks complete. Input/script changes alter identity. Requires OJ-02; combine with OJ-03 demo. |
| 5 — OJ-05 | optimization-jobs / P3 | Add explicit node placement and fixed-helper SSH transport | Versioned node identity/capabilities, bounded control requests, verified staging, durable node launch and retrieval. Separate simulated transport tests from real SSH. Requires P2 acceptance. |
| 6 — OJ-06 | optimization-jobs / P3 | Persist dispatch intent, immutable resolution and global/local/backend handle mapping | Lost launch response reconciles the same node/key to one execution; coordinator restart retains uncertainty/reservation; collection retry cannot rerun computation. Requires OJ-05; account for today's validation-before-key-lookup behavior. |
| 7 — OJ-07 | optimization-jobs / P4 gate | Timebox native/systemd versus Slurm allocation investigation | One authoritative capacity owner, evidence for daemon/user-manager durability and enforcement. If a suitable environment is unavailable, keep explicit placement and mark automatic fleet scheduling blocked. |
| 8 — OJ-08 | optimization-jobs / P4 | Add automatic placement, drain, concurrency and durable group budgets using the selected authority | Simultaneous clients cannot double-reserve; uncertain jobs retain reservations; oversized requests reject early; drained/main-desktop hosts excluded. Requires OJ-06 and OJ-07 decision. |
| 9 — EC-01 | experiment-craft / P5 | Create Python 3.12 package, campaign manifest/schema, deterministic expansion and thin CLI/JSON client | Local optimization campaign compiles to existing validated jobs; unsupported command/fleet steps fail before submission. Do not add SSH/process supervision. Depends on the stable runtime contract; local development can proceed after P1. |
| 10 — EC-02 | experiment-craft / P5 | Persist campaign step intent, stable keys, accepted handles and scientific decisions | Restart observes/reconciles existing attempts; no duplicate starts; failed dependencies block downstream steps; waiting has a campaign deadline. Requires EC-01. |
| 11 — EC-03 | experiment-craft / P6 | Add comparison/report rules and representative scientific suites | Reports retain feasibility, claim/evidence level, incomplete/unknown work and failed jobs; unsupported cross-profile comparisons reject. Requires EC-02. |
| 12 — BOTH-01 | both repositories / P7 | Rehearse installation, agent use, backup/restore and candidate packaging | Reviewable per-repository patches, pinned sources, test logs, capability matrix and explicit blocked checks. No tag/publication without the separately authorized release workflow. |

## First P1 change to implement

**Baseline maintenance, FC-01 — fcmaes-rust:** resolve or explain the two `needless_range_loop` diagnostics in `crates/fcmaes-core/src/da.rs` under Rust 1.88, preserving numerical update order and existing tests. This is a strict-lint gate, not a runner/worker incompatibility. Do not suppress all warnings to make the baseline appear green.

**Baseline maintenance, LP-01 — LP-IP-craft:** resolve `collapsible_else_if` at `crates/native/src/lu.rs:1182` while preserving the sparse LU branch behavior and numerical tests.

**Baseline maintenance, SQP-01 — SQP-craft:** resolve `uninlined_format_args` at `crates/sqp-job-worker/src/lib.rs:134` without changing the validation message or accepted thread range. Recheck each workspace after its focused lint fix; diagnostics may stop before later warnings.

Start with OJ-01 in `optimization-jobs`: extract the lifecycle around `launch`, `execute_worker`, and `finish` without changing the public optimization envelope. Keep `worker_outcome` and native manifest construction in an optimization adapter. Preserve the current locked admission path and conservative release conditions. Add one focused neutral-fixture regression when the new boundary exists, then rerun the pinned real-worker suite. Do not combine that refactor with SSH or campaign scheduling.

## January commissioning remains separate

Verify actual host inventory, SMT/topology, storage paths, SSH keys, lingering/reboot behavior, drivers, resource enforcement and full-load limits on the user's machines. Then exercise two real nodes under lost acknowledgements/disconnects and validate backup/restore before production use. The main desktop remains excluded from the worker pool unless the user changes that decision.

