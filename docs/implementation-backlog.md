# Prioritized implementation backlog

P0 to P3 are merged: RT-01 to RT-06 are done, with local and real SSH transport tests; the real-host service, logout and reboot acceptance of P3 remains open. Local P5 (EC-01/EC-02) is implemented; RT-07/RT-08 remain blocked here. Later items are planned. Follow the phase gates of the [plan](implementation-plan.md) rather than implementing all items in parallel.

The IDs are local to this backlog: RT for the optimization-jobs runtime, EC for experiment-craft, REL for both repositories and BL for baseline maintenance in the solver repositories. They are unrelated to the review IDs used inside the upstream repositories, such as OJ-01, FC-01, LP-01 or SQP-01.

| Order / ID | Repository / phase | Concrete change | Acceptance and dependency |
|---|---|---|---|
| 1 — RT-01 | optimization-jobs / P1 | **Done** ([optimization-jobs#21](https://github.com/dietmarwo/optimization-jobs/pull/21)): extract neutral execution lifecycle, supervision and admission interfaces behind the existing CLI | Existing review, MCP, integration and Rust tests pass; old job/result fixtures unchanged; local execution needs no fleet service. Starts from this baseline. |
| 2 — RT-02 | optimization-jobs / P1 | **Done** ([optimization-jobs#21](https://github.com/dietmarwo/optimization-jobs/pull/21)): versioned neutral record and capability discovery; native optimization attachment. Public command request schema deferred to RT-03 | A neutral fixture completes without an objective or feasibility claim; unsupported kinds reject explicitly; embedded schemas/guide stay synchronized. Requires RT-01. |
| 3 — RT-03 | optimization-jobs / P2 | **Done** ([optimization-jobs#22](https://github.com/dietmarwo/optimization-jobs/pull/22)): separately enabled command adapter: argv, explicit script input, environment and exit/signal outcome | Literal shell metacharacters stay literal; command and optimization jobs share admission; deadline/cancel covers descendants under the chosen containment policy. Requires RT-02. |
| 4 — RT-04 | optimization-jobs / P2 | **Done** ([optimization-jobs#22](https://github.com/dietmarwo/optimization-jobs/pull/22)): checked binary staging and command-output collection | Safe paths, reserved names, size/digest checks, atomic publication, bounded transfer and cleanup; interrupted copy never looks complete. Input/script changes alter identity. Requires RT-02; combine with RT-03 demo. |
| 5 — RT-05 | optimization-jobs / P3 | **Done** ([optimization-jobs#23](https://github.com/dietmarwo/optimization-jobs/pull/23)): explicit node placement and fixed-helper SSH transport | Versioned node identity/capabilities, bounded control requests, verified staging, durable node launch and retrieval. Separate simulated transport tests from real SSH. Requires P2 acceptance. |
| 6 — RT-06 | optimization-jobs / P3 | **Done** ([optimization-jobs#23](https://github.com/dietmarwo/optimization-jobs/pull/23)): dispatch intent, immutable resolution and global/local/backend handle mapping | Lost launch response reconciles the same node/key to one execution; coordinator restart retains uncertainty/reservation; collection retry cannot rerun computation. Requires RT-05; account for today's validation-before-key-lookup behavior. |
| 7 — RT-07 | optimization-jobs / P4 gate | **Blocked:** native/systemd versus Slurm investigation; see [environment gate](backend-gate.md) | One authoritative capacity owner, evidence for daemon/user-manager durability and enforcement. If a suitable environment is unavailable, keep explicit placement and mark automatic fleet scheduling blocked. |
| 8 — RT-08 | optimization-jobs / P4 | Add automatic placement, drain, concurrency and durable group budgets using the selected authority | Simultaneous clients cannot double-reserve; uncertain jobs retain reservations; oversized requests reject early; drained/main-desktop hosts excluded. Requires RT-06 and RT-07 decision. |
| 9 — EC-01 | experiment-craft / P5 | **Implemented locally:** Python 3.12 package, strict manifest, deterministic expansion and thin CLI/JSON client | Local optimization campaign compiles to existing validated jobs; unsupported command/fleet steps fail before submission. Do not add SSH/process supervision. Depends on the stable runtime contract; local development can proceed after P1. |
| 10 — EC-02 | experiment-craft / P5 | **Implemented locally:** transactional intent, stable keys, native handles, dependencies, budgets and stop/continuation | Restart observes/reconciles existing attempts; no duplicate starts; failed dependencies block downstream steps; waiting has a campaign deadline. Requires EC-01. |
| 11 — EC-03 | experiment-craft / P6 | Add comparison/report rules and representative scientific suites | Reports retain feasibility, claim/evidence level, incomplete/unknown work and failed jobs; unsupported cross-profile comparisons reject. Requires EC-02. |
| 12 — REL-01 | both repositories / P7 | Rehearse installation, agent use, backup/restore and candidate packaging | Reviewable per-repository changes, pinned sources, test logs, capability matrix and explicit blocked checks. No tag/publication without the separately authorized release workflow. |

Every RT item that changes a shared path in optimization-jobs (`crates`, `ai-context.md`, `docs/job-api.md`, `docs/job-api`, `scripts/job-api` or `Cargo.lock`) also needs the worker pin moved in fcmaes-rust, LP-IP-craft and SQP-craft, and the commits in `baseline-lock.json` moved, before its package is accepted ([plan, section 4](implementation-plan.md#4-existing-foundation-and-compatibility-constraints)).

## Baseline maintenance

Clippy 1.88, the job layer's minimum Rust, reported diagnostics in the three solver workspaces at their P0 commits. The repositories' CI lints with the latest stable Clippy, which accepts these patterns, so their own gate was green. The fixes keep results unchanged and make Clippy clean on both toolchains; a full-workspace `cargo +1.88.0 clippy --workspace --all-targets --locked --keep-going -- -D warnings` run on each fix branch passed.

| ID | Repository | Diagnostics at the P0 commit | Change |
|---|---|---|---|
| BL-01 | fcmaes-rust | `needless_range_loop` in `crates/fcmaes-core/src/da.rs:491` and `:506`; with `--keep-going` also `uninlined_format_args` in `crates/fcmaes-core/src/cmaes.rs:768` (a test) and `crates/fcmaes-native-worker/src/main.rs:200` and `:213` | Iterate the L-BFGS two-loop updates with `zip` (same operations, same order); inline the three format arguments. [fcmaes-rust#31](https://github.com/dietmarwo/fcmaes-rust/pull/31) |
| BL-02 | LP-IP-craft | `collapsible_else_if` in `crates/native/src/lu.rs:1182` | Collapse to `else if`; branches and order unchanged. [LP-IP-craft#33](https://github.com/dietmarwo/LP-IP-craft/pull/33) |
| BL-03 | SQP-craft | `uninlined_format_args` in `crates/sqp-job-worker/src/lib.rs:134` | Inline `MAX_INNER_THREADS`; message text unchanged. [SQP-craft#35](https://github.com/dietmarwo/SQP-craft/pull/35) |

All three fixes are merged at the GitHub heads recorded in the P1 log. The refreshed pre-refactor baseline passed all 22 steps with Rust 1.88 builds/tests and stable lints.

## Next implementation package

RT-07 is the actual-backend investigation gate. Use the [plan brief](implementation-plan.md#12-next-increment-and-revision-record). The P3 transport and dispatch are merged, but real systemd, logout/reboot and enforcement evidence is still required. Keep RT-08 automatic placement blocked if no suitable environment is available; local P5 is implemented under that dependency rule. The next independent package is P6/EC-03 scientific comparison protocols; see [campaign behavior](campaigns.md).

## January commissioning remains separate

Verify actual host inventory, SMT/topology, storage paths, SSH keys, lingering/reboot behavior, drivers, resource enforcement and full-load limits on the user's machines. Then exercise two real nodes under lost acknowledgements/disconnects and validate backup/restore before production use. The main desktop remains excluded from the worker pool unless the user changes that decision.

