# Experiment orchestration: implementation before January 2027

**Date:** 25 October 2026

**Version:** 2.7 — local P6 comparisons and suites; backend gate remains open

**Preparation window:** now until the return home in January 2027; mid-January remains a planning assumption.  
**Basis:** experiment orchestration plan v2 (not kept in this repository) and the agreed boundary between optimization-jobs and experiment-craft.  
**Status:** implementation plan. P0 is complete; its evidence is in [`evidence/p0/`](../evidence/p0/) and the [implementation log](../implementation-log.md). P1 (RT-01/RT-02) is merged in all four repositories, and the baseline at the merged commits passed; see the [P1 log](../implementation-log.md#p1--execution-boundary-and-observations) and the [P1 review](../implementation-log.md#p1-review-and-merge). P2 (RT-03/RT-04) is merged as well, and the baseline at the merged commits passed; see the [P2 log](../implementation-log.md#p2--trusted-local-commands-and-binary-files) and the [P2 review](../implementation-log.md#p2-review-and-merge). P3 (RT-05/RT-06) is merged too, and the baseline at the merged commits passed; see the [P3 log](../implementation-log.md#p3--explicit-ssh-placement-and-reconciliation) and the [P3 review](../implementation-log.md#p3-review-and-merge). P3's real-host acceptance (a durably launched job surviving an actual SSH disconnect, logout and reboot) remains open; P5 local EC-01/EC-02 is merged; see the [campaign guide](campaigns.md), the [P5 evidence](../evidence/p5/README.md) and the [P5 review](../implementation-log.md#p5-review-and-merge). Local P6/EC-03 is implemented; see the [comparison guide](scientific-comparisons.md) and [P6 evidence](../evidence/p6/README.md). RT-07/RT-08 remain blocked on actual backend evidence; P7 remains future work.

## 1. Decision and preparation target

Extend **optimization-jobs** into the shared execution layer for local and remote optimization jobs, generic commands, scripts, and file staging. Build **[experiment-craft](https://github.com/dietmarwo/experiment-craft)** above that execution layer to define, run, compare, and continue scientific campaigns.

The execution layer answers: *where does this job run, with which resources and inputs, and what happened to it?* The orchestrator answers: *which experiments should run, what constitutes a useful result, and what should happen next?*

This replaces version 1's proposed Python fleet controller. Rust continues to own execution, including remote dispatch and reconciliation. Python owns campaign composition, scientific analysis, and reporting.

Before January, aim to deliver:

1. Existing single-node optimization behavior preserved and covered by regression tests.
2. Generic command jobs using the same execution machinery and resource admission as optimization jobs.
3. Verified file staging and collection, explicit-host remote execution, and conservative recovery after lost connections.
4. A small orchestrator that expands reproducible campaigns, submits jobs, collects results, and produces comparison reports.
5. Local and disposable-environment evidence, installation instructions, and a separate home-fleet commissioning checklist.

The useful minimum is a local mixed-workload runtime plus a real campaign and report. Fleet automation is an additional milestone, not a prerequisite for useful preparation.

Actual Mint compatibility, physical-core isolation, memory enforcement, GPU compatibility, LAN throughput, and six-machine performance remain January gates. Simulating six node identities on one machine does not demonstrate 96-core execution.

Keep optimizer internals and objective evaluation together on one host initially. Distribute complete jobs or explicitly constructed independent batches, transfer inputs once, and collect results afterward. MPI, cross-machine optimizer internals, automatic controller failover, GPU scheduling, and a dashboard are outside the critical path.

## 2. Repository ownership and dependency direction

The orchestrator repository is **[dietmarwo/experiment-craft](https://github.com/dietmarwo/experiment-craft)**, created by the user and confirmed for this plan on 24 October 2026.

| Responsibility | optimization-jobs: Rust execution layer | experiment-craft: Python campaign layer |
| --- | --- | --- |
| Local process execution | Launch, supervise, stop, time out, and recover attempts | Submit a declared campaign step |
| Optimization execution | Existing worker SDK, discovery, validation, and result contracts | Choose profiles, parameters, seeds, starts, and comparisons |
| Generic command/script execution | New execution kind with logs, exit status, artifacts, and limits | Define build, simulation, validation, and analysis steps |
| Host inventory and placement | Probe hosts, select eligible nodes, queue work, drain nodes | Declare requirements, preferences, and comparison constraints |
| Resource management | Own reservations and enforce configured job/group limits | Set campaign budgets and stopping rules |
| File movement | Stage, transfer, checksum, cache, publish, and collect bytes | Decide which source, inputs, and outputs belong to an experiment |
| Provenance | Record actual executable, environment, host, allocation, and execution facts | Record hypothesis, source selection, treatment, baseline, and metric definitions |
| Durability | Dispatch intents, placement, execution handles, journals, reconciliation | Campaign definition, step intent, accepted handles, scientific decisions |
| Retry behavior | Perform only permitted execution retries; preserve uncertain attempts | Decide whether another scientific attempt is justified |
| Workflows | Execute submitted work and expose stable handles | Decide dependencies, expand sweeps, select follow-up experiments |
| Results | Preserve raw execution records and native optimization evidence | Compare, plot, summarize, and interpret results |
| Interfaces | Execution CLI/MCP, local and fleet capabilities | Campaign CLI/schema and canonical agent guide |
| Installation | Runtime/helper/backend configuration and runtime recovery | Orchestrator environment, campaign examples, report tools |

**Dependency direction:** the orchestrator uses the versioned runtime CLI/JSON interface, with MCP optional. optimization-jobs has no dependency on the orchestrator. Solver workers continue to depend on their shared API and remain in their existing repositories.

Keep two repositories. Begin with internal execution, fleet, and optimization modules in optimization-jobs; extract an internal crate only when the code audit demonstrates a useful dependency boundary. A third generic-runtime repository or a public rename is not required for this roadmap.

Preserve standalone use: an existing single-node installation must not require a fleet daemon, SSH configuration, Python orchestrator, or cluster database. Keep remote-control dependencies out of the solver-facing worker SDK where practical.

**One owner per fact:** the orchestrator may cache execution observations for reporting, but the runtime remains authoritative for job status, reservations, cancellation, and artifact verification. It must not edit the runtime's database, journals, worker directories, or remote processes directly.

## 3. Confirmed repository and naming

The user has created **[dietmarwo/experiment-craft](https://github.com/dietmarwo/experiment-craft)**. Use this existing repository for the Python campaign orchestrator and its documentation. The earlier naming alternatives are superseded.

| Item | Name or location | Status |
| --- | --- | --- |
| Orchestrator repository | [dietmarwo/experiment-craft](https://github.com/dietmarwo/experiment-craft) | Created by the user; canonical repository |
| Project name | `experiment-craft` | Confirmed |
| Python distribution | `experiment-craft` | Intended package name; publication remains future work |
| Python import package | `experiment_craft` | Intended import name |
| Execution-layer repository | [dietmarwo/optimization-jobs](https://github.com/dietmarwo/optimization-jobs) | Existing shared execution project |

Suggested repository description:

> Reproducible experiment campaigns, parameter sweeps, comparisons, and agent workflows on top of optimization-jobs.

P0 found experiment-craft at commit `bcd74e9` with only its MIT license, recorded that commit in [`baseline-lock.json`](../baseline-lock.json) and kept the license unchanged. Use this repository for campaign implementation; no second orchestrator repository is needed.

Keep optimization-jobs and its existing package/binary names during this work. A neutral runtime alias can be considered later if generic workloads become a substantial independent audience.

## 4. Existing foundation and compatibility constraints

P0 audited the merged commits recorded in [`baseline-lock.json`](../baseline-lock.json) (optimization-jobs `f65e664`, fcmaes-rust `bdd01e8`, LP-IP-craft `3645d2d`, SQP-craft `3f155f9`), built them and ran their checks; see the [reuse audit](reuse-audit.md) and the [compatibility matrix](compatibility-matrix.md).

The runner already provides worker registration, staging, idempotency, admission, supervision, cancellation, deadlines, recovery, and CLI/MCP access. Reuse these facilities while separating generic machinery from optimizer-specific interpretation. [R1, R3]

Preserve the existing optimization envelope and result contracts, including their distinctions between process completion, mathematical claims, and evidence. The current interface restricts execution to registered workers; generic commands therefore introduce a new explicit capability rather than merely another description field. [R3]

CPU slots provide admission accounting, not physical-core pinning or memory enforcement. The existing idempotency scope is local to a node; fleet placement and global dispatch reconciliation must be added. [R2]

The suspected 0.2.0/0.3.0 documentation drift does not exist: both crate manifests, the lockfile, the README, the job guide and `ai-context.md` say 0.3.0, and the 0.2.0 mentions in `ai-context.md` refer to `fcmaes-core` 0.2.0. Do not infer compatibility from a version mentioned in prose; the baseline lock pins commits and file hashes. [R1–R3]

P0 findings that later packages must respect:

- **Validation precedes the request-key lookup.** `prepare` stages inputs and runs the worker's validator before it looks up an existing job, so repeating a request fails (`worker_changed`, `request_key_conflict` or `invalid_job`) when the registered worker or an input changed. Clients keep the returned handle and observe with `jobs get`; P3 designs immutable resolution and the global lookup explicitly.
- **`validate` does not check node capacity.** A job that validates can still fail with `capacity_exceeded` at `run` or `submit`.
- **Shared-pin coordination.** The three workers pin optimization-jobs at one revision, and each worker repository's `shared-pin.yml` fails once optimization-jobs `main` changes `crates`, `ai-context.md`, `docs/job-api.md`, `docs/job-api`, `scripts/job-api` or `Cargo.lock`. P1–P4 change `crates` and the job API documents and schemas, so every merged runtime change needs a pin move in all three worker repositories and in the baseline lock. optimization-jobs CI already builds the workers against the checkout SDK before they are repinned. Batch runtime changes so that a pin moves once per accepted package, not once per commit.
- **Toolchains.** The job layer's minimum Rust is 1.88; the repositories' lint gate is the latest stable Clippy. P0 first ran Clippy 1.88, which reports patterns that newer Clippy accepts; fixes are proposed in [fcmaes-rust#31](https://github.com/dietmarwo/fcmaes-rust/pull/31), [LP-IP-craft#33](https://github.com/dietmarwo/LP-IP-craft/pull/33) and [SQP-craft#35](https://github.com/dietmarwo/SQP-craft/pull/35), and the baseline now lints with stable Rust and builds and tests with 1.88.
- **Executables under test.** Workspace-wide checks rebuild worker binaries with other feature sets. The baseline copies the built executables before running checks, so smoke jobs and harnesses test the same files.
- **No systemd user manager in the test container.** The runner's `node doctor` reported none, and the MCP suite passed only its unavailable-manager branch. Detached durability remains a disposable-VM or January test.

Compatibility rules:

- Existing optimization job files, result artifacts, CLI behavior, local roots, and worker integrations continue to work.
- New generic execution schemas have explicit versions and separate names. P1 defines `execution.record/0.1` and `execution.capabilities/0.1`. P2 adds `execution.command/0.1`, `execution.command.result/0.1` and discovery `execution.capabilities/0.2`; the internal adapter is not a plugin API.
- Preserve strict validation. Do not insert command, host, or memory fields into an old envelope that rejects them.
- Keep the existing scientific result artifact intact; a generic execution record can reference it.
- All additions remain additive unless a demonstrated incompatibility requires an explicit migration.
- Use repository instructions, synchronization tests, and changelog conventions. Package publication and public release tags are outside this implementation plan.

## 5. Execution architecture inside optimization-jobs

### 5.1 Local core, fleet coordinator, and optimization integration

Separate responsibilities internally:

| Module boundary | Responsibility |
| --- | --- |
| Local execution core | Attempt identity, process supervision, deadlines, cancellation, resource admission, journals, logs, artifact publication |
| Optimization integration | Worker discovery and validation, native task/results handling, scientific claims and evidence |
| Command integration | Argument-array execution, explicit scripts, exit status, stdout/stderr, declared outputs |
| Artifact transport | Verified staging, transfer, local cache, collection, and immutable artifact references |
| Fleet coordinator | Node identities, placement, global request keys, reservations, dispatch intents, reconciliation, and group limits |
| Backend adapter | Selected SSH/systemd or Slurm execution integration |

Refactor working code behind these boundaries; do not implement replacement lifecycle machinery alongside the existing runner. Keep the existing local storage model unless the audit finds a concrete reason to change it.

The optional fleet service has one active writer and durable state. SQLite is a reasonable candidate for fleet mappings and reservations; it does not require replacing local job journals or sharing a database over the network. Local-only execution needs no fleet service.

### 5.2 Generic commands and explicit scripts

Provide a generic execution kind with an argument array, controlled working directory, declared environment, input artifacts, output declarations, and limits. A script is an explicit interpreter invocation of a versioned script artifact; ordinary arguments never pass implicitly through a shell.

Examples include compiling a Rust application, running a Python simulation, executing a test suite, checking a mathematical candidate, and generating a report. These are durable jobs with the same supervision and cancellation behavior as optimization jobs.

Generic results contain execution state, exit code or signal, timestamps/durations, resource facts, logs, and artifacts. They do not need an objective value or an optimality claim. An optimization execution additionally references the native scientific result.

Use separate capabilities for optimization-only clients and command-enabled clients. Preserve existing optimization-only access by default. Worker registration and execution-policy changes remain administrative operations. This is trusted research execution, not a hostile-code sandbox.

A command may have side effects. Automatic retry is disabled unless its policy explicitly permits replay; a transport retry reconciles the original attempt rather than launching the command again.

### 5.3 Artifact movement and reproducibility

The orchestrator selects source snapshots, datasets, environment descriptions, and expected outputs. The runtime moves and verifies them.

Implement:

- Immutable artifact manifests with content digests, sizes, and declared relative paths.
- Verified staging to controlled roots; reject traversal, conflicting destinations, and escaping symlinks.
- Transfer retry and resumable collection where worthwhile; publish completion only after verification.
- Separate mutable work directories from immutable inputs and published outputs.
- Bounded logs, projected storage reservations, and explicit retention policies.
- A clear distinction between disposable caches and authoritative, uncollected results.
- Recorded source, input, executable, toolchain, environment, and actual host identities.

Start with small files and simple bundles. General transfer should have its own declared limits rather than inherit optimization-input size limits accidentally. Keep old optimization limits intact until an explicit compatible extension is justified.

Build cache identity includes source, lockfiles, toolchain, target architecture, and compiler flags. Do not distribute host-specific native binaries without compatibility checks. Build/staging time remains separate from solver timing.

### 5.4 One resource system for mixed workloads

Command jobs and optimization jobs use the same resource admission path. A compilation and an optimizer cannot each reserve all 16 cores independently.

The runtime owns node and fleet reservations; the orchestrator supplies requirements and a campaign/group budget. The runtime enforces that budget across every associated build, command, solver run, and execution retry. The campaign layer separately enforces scientific limits such as the number of configurations to investigate.

Distinguish:

- CPU slots used for admission.
- Physical cores and allowed logical CPU IDs, established from actual topology.
- Memory/storage reservations.
- Kernel-enforced resource limits, enabled only where verified.

Before the topology mapping is verified, report slot-hours rather than core-hours. Reserve conservative capacity before dispatch, settle known usage after completion, and retain reservations while execution is uncertain. Include a deadline that bounds campaign waiting as well as per-job execution limits.

For the first fleet release, use whole-host placement where appropriate. Add smaller allocations only after the selected backend passes actual CPU and memory tests. Local multi-node tests must also obey the real test host's aggregate capacity.

### 5.5 Durable dispatch and two-level identity

The orchestrator persists campaign/step intent before submission and assigns a stable request key. The runtime persists execution intent before contacting a worker.

| Identity | Owner and purpose |
| --- | --- |
| Campaign, experiment, and step IDs | Orchestrator: scientific and workflow identity |
| Global execution request and attempt IDs | Runtime: one accepted execution and explicit retries |
| Node identity and local runner root | Runtime: scope of local idempotency |
| Local job key/ID and backend ID | Runtime: correlate node records and systemd/Slurm execution |
| Artifact digest | Runtime: immutable bytes; referenced by both projects |

The runtime resolves binaries, environment, and inputs once; atomically records placement and reservations; stages; dispatches; and saves the returned handle. If the acknowledgement is lost, it reconciles the same node and key.

It must not submit the uncertain attempt on a different node. Reassignment requires proof that the original did not start, or verified termination and an explicit new attempt. No exactly-once computation guarantee is claimed across arbitrary failures.

The orchestrator also reuses its original request key after a restart. It follows runtime uncertainty rather than interpreting a lost response as permission to create new work.

Track execution state, connection uncertainty, and artifact collection separately. Repair or collection retry must not become an accidental computation retry.

### 5.6 Backend ownership and decision gate

The first remote increment uses explicit-host execution through SSH and the existing durable launcher where supported. Before implementing production automatic fleet dispatch, compare this route with Slurm using a timeboxed investigation.

| Selected backend | Resource authority |
| --- | --- |
| SSH/systemd | Runtime fleet reservations and local admission form one hierarchy; the verified service/cgroup configuration enforces host limits |
| Slurm | Slurm owns physical allocation; the runtime submits within it, accounts for campaign limits, and bounds local work to the granted allocation |

On the Slurm path, do not create a competing host scheduler. Use an allocation-scoped execution context where necessary, with preserved job journals and terminal receipts. Do not launch a nested service that escapes the allocation. Generic and optimization jobs follow the same backend policy.

Implement one production allocation path. The orchestrator sees the same execution interface in either case and does not contain Slurm or systemd control logic.

An initial VM investigation has a one-day timebox. If unavailable, leave automatic fleet dispatch gated and continue local campaigns, transfers, explicit placement, and reporting. The final selection may require January hardware evidence. Upstream cgroup documentation is a design reference, not proof of installed Mint behavior. [R5, R6]

## 6. Campaign architecture in experiment-craft

Use Python for manifest expansion, experiment design, analysis, and reports. Start with Python 3.12-compatible code; pin the actual supported interpreter and dependencies in P0.

The orchestrator stores:

- Hypothesis, baseline, variants, seeds or initial points, metric definitions, and success criteria.
- Immutable expanded experiment specifications and selected source/environment identities.
- Campaign limits, stop decisions, step dependencies, and confirmation protocols.
- Runtime request keys and returned execution handles.
- References to verified artifacts and generated scientific reports.

It does not own SSH transport, host queues, CPU reservations, process groups, worker repair, or transfer recovery. A campaign journal or optional query database contains campaign facts and rebuildable runtime observations.

Begin with explicit sequences and bounded fan-out/fan-in:

1. Prepare source and input artifact references.
2. Submit a build or preparation job when needed.
3. Submit independent experiment jobs with stable identifiers.
4. Wait for verified results, preserving failures and partial outcomes.
5. Run declared checks and produce a comparison.
6. Submit a bounded follow-up only when the campaign policy permits it.

A failed prerequisite blocks dependent steps; it does not silently produce incomplete inputs. Persist the decision to submit follow-up work before doing so. No arbitrary workflow language or autonomous research agent is needed for the first release.

For multi-node optimization, expand explicit independent job batches while preserving seeds, task identities, and total budgets. Do not silently split a single LP/SQP solve or change an optimizer's feedback order. The runtime chooses placement; the orchestrator defines the scientific decomposition.

The external coding/analysis agent can propose experiments through this interface. Neither repository needs its own model-hosting or provider-key service.

## 7. Work packages and acceptance gates

Effort estimates are focused developer-days including verification, not calendar promises or model-speed predictions. Each package produces a useful checkpoint and an evidence log. P5 can begin against the local runtime while remote capabilities remain under development.

### P0 — Audit and pin the foundation

**Owner:** optimization-jobs, with an orchestrator integration specification.  
**Window:** late October. **Effort:** 1–2 days. **Dependencies:** none.  
**Status:** complete on 24 October 2026, in one day. All four repositories built at their recorded commits, the existing checks ran, and one real job per worker passed; the [implementation log](../implementation-log.md) lists every command and result.

Fetch recent merged source for optimization-jobs and the three solver repositories. Inspect the existing experiment-craft repository and preserve its files and instructions. Record full commits where present, lockfiles, schemas, and worker discovery; record an empty repository explicitly if it has no commit yet. Read repository instructions and run the relevant existing checks before changing behavior.

Audit which code is generic, which assumes optimization semantics, and which durability/resource contracts a command or fleet adapter must preserve. Resolve the documentation-version mismatch. Specify the local/fleet/command capability boundary and orchestrator interface.

**Deliver:** baseline lock, reuse audit, compatibility matrix, proposed module boundaries, and prioritized integration backlog.

**Acceptance:** a reproducible pinned runner/worker build and one small real job per available worker. Record unavailable workers or environmental tests explicitly. No claim that new execution kinds or remote behavior already exist.

### P1 — Separate execution mechanics from optimization semantics

**Status:** merged on 24 October 2026 (optimization-jobs#21, then the three worker pin moves, then experiment-craft), in about one day (estimated: 2–4 days). Pinned-SDK and checkout-SDK compatibility passed before the pins moved, and the baseline at the merged commits passed. See the [integration contract](integration-contract.md#2-execution-discovery-and-record).

**Owner:** optimization-jobs.  
**Window:** early November. **Effort:** 2–4 days. **Dependency:** P0.

Refactor behind internal boundaries while preserving existing optimization interfaces. Define the neutral execution record and its relationship to the native optimization result. Reuse lifecycle, logging, supervision, cancellation, and artifact code.

Keep modules internal initially; extract crates only to improve a demonstrated dependency boundary. Define capability/version discovery for clients and maintain synchronized schemas/docs where the repository requires them.

**Deliver:** internal execution interfaces, compatibility fixtures, and documented additive schema decisions.

**Acceptance:** existing optimization regression and relevant real-worker tests pass; old job/result fixtures retain their semantics; local execution requires no fleet service. A small neutral fixture can exercise the execution path without inventing mathematical output. Before the worker pins move, the three workers pass optimization-jobs' mixed-node checks against the checkout SDK. After the pin moves merge, the baseline lock moves to the new commits ([moving the baseline](../README.md#moving-the-baseline)) and `scripts/baseline.py all` passes in a new workspace.

### P2 — Add command jobs and generic artifact staging

**Status:** merged on 24 October 2026 (optimization-jobs#22, then the three worker pin moves, then experiment-craft), in about one day (estimated: 3–5 days). experiment-craft's baseline validates the new capability schema and runs the command/file harness and the build–run–collect example. The review fixed an MCP path that ran command jobs and a launcher that waited indefinitely for output held by a process outside its group; see the [P2 review](../implementation-log.md#p2-review-and-merge). Commands are opt-in trusted same-user programs; process-group cancellation is tested; escaped descendants and kernel resource enforcement are not promised.

**Owner:** optimization-jobs.  
**Window:** first half of November. **Effort:** 3–5 days. **Dependency:** P1.

Implement argument-array commands, explicit script artifacts, exit/signal results, bounded logs, output declarations, and staging/collection. Add separately configurable command capability and explicit replay policy.

Route command and optimization jobs through the same local admission, deadline, and cancellation machinery. Implement file hashing, safe paths, interrupted-copy handling, and storage policy checks.

**Deliver:** local mixed-workload runtime and one useful build–run–collect demonstration.

**Acceptance:** a command and an optimizer cannot exceed their shared admission budget; cancellation reaches workload descendants; shell metacharacters remain literal in ordinary arguments. Changed input/script bytes change request identity. A truncated transfer cannot be published as verified. A failed command reports failure without fabricating an optimization result.

Kernel-enforced CPU/memory isolation remains unproven until the environment-specific checks actually pass.

### P3 — Add explicit remote execution and reconciliation

**Status:** merged on 25 October 2026 (optimization-jobs#23, then the three worker pin moves, then experiment-craft), in about a day (estimated: 4–6 days). Explicit node/endpoint binding, persistent coordinator/global/local/backend handles, a fixed JSON/binary SSH helper, checked snapshots and collection, launch barriers, guarded repair and conservative reconciliation are in optimization-jobs. Real OpenSSH authentication, host-key refusal, binary transfer and a forced disconnect run against a disposable AsyncSSH endpoint with real Rust workers; its service manager is simulated. The review made node refusals final with their own codes, kept unsent requests staging and settled dispatches interrupted before their launch barrier; see the [P3 review](../implementation-log.md#p3-review-and-merge). The acceptance item that an actual SSH disconnect leaves a durably launched job running, and real logout/reboot and cgroup behavior, remain a commissioning gate; no automatic failover or placement is enabled by these tests.

**Owner:** optimization-jobs.  
**Window:** second half of November. **Effort:** 4–6 days. **Dependency:** P2.

Implement node identities and capability discovery, fixed-helper SSH requests using JSON over stdin, verified remote staging, explicit placement, bounded connectivity checks, and artifact retrieval.

Persist fleet dispatch intent and node selection before launch. Correlate global keys, local keys, runner handles, and backend handles. Add conservative reconciliation and transfer recovery. Use existing durable local launch support; add only demonstrated gaps.

Build fault-injecting fixtures and several isolated real node roots. Use actual disposable SSH endpoints when available.

**Deliver:** explicit-host command and optimization execution with a failure ledger.

**Acceptance:** lose the response after a real launch and reconcile to one start on the selected node. A retry cannot move the uncertain attempt elsewhere. Restart the fleet coordinator during dispatch/collection. Collection retry does not rerun computation. An actual SSH disconnect leaves a durably launched job running; a simulated transport test is recorded separately.

### P4 — Add automatic fleet placement and group budgets

**Owner:** optimization-jobs.  
**Window:** late November–early December. **Effort:** 3–6 days, excluding the initial one-day backend investigation.  
**Dependencies:** P3 and the backend decision gate for production scheduling.

Select the allocation path before adding a custom scheduler. Implement or expose queueing, eligible-node placement, drain, concurrency limits, and durable group budgets for mixed workloads. Coordinate fleet reservations with the selected local/backend authority.

Extend inventory and request validation for memory, storage, topology, and supported capabilities. Handle simultaneous clients and unknown jobs conservatively. Keep whole-host scheduling as the first operating mode.

**Deliver:** one production allocation path, budget policy, and automatic placement tests.

**Acceptance:** mixed jobs queue when capacity is exhausted; simultaneous clients do not double-reserve resources; unknown running work retains reservations; oversized requests fail before dispatch. Drain affects subsequent dispatch. The main desktop stays excluded. Separate simulated accounting tests from actual enforcement evidence.

If the backend decision lacks an adequate environment, retain P3 explicit placement and mark P4 blocked rather than inventing hardware validation.

### P5 — Implement the campaign orchestrator

**Implementation:** local EC-01/EC-02 is merged: strict manifests, deterministic matrix/DAG expansion, input and executable identity, SQLite decisions/events, stable native keys, declared budgets, continuation/stop, checked native/command output binding and offline reports. A seven-job example runs all three native workers. Positive systemd client-branch tests use a named simulated manager; actual backend acceptance remains RT-07. Fleet integration is deferred to the commissioned runtime path. See the [campaign guide](campaigns.md).

**Owner:** [experiment-craft](https://github.com/dietmarwo/experiment-craft).  
**Window:** November–December. **Effort:** 3–5 days.  
**Dependencies:** P0 and a stable local execution interface; generic-command steps use P2. Fleet integration uses P3/P4.

Implement campaign validation, deterministic expansion, immutable source/input references, stable step request keys, budgets, dependency checks, and continuation after restart. Use existing optimization job profiles and the new generic command interface.

Submit through the runtime's CLI/JSON surface. Store campaign decisions and returned handles. Add a concise CLI with dry-run, run/continue, status, stop, collect/report, and provenance-diff operations; exact command names are implementation choices.

**Deliver:** a reproducible campaign that builds or prepares inputs, runs a small sweep, checks results, and creates a first report.

**Acceptance:** dry-run launches nothing; repeated expansion is stable; changed scientific inputs change identity. Restart after submission and retrieve the same executions. A failed prerequisite blocks its dependents. Campaign stop prevents new steps and requests cancellation through the runtime. The project contains no independent SSH launcher or host scheduler.

### P6 — Add scientific workload suites and reports

**Implementation:** local EC-03 is present: predeclared immutable comparison protocols, compatible model/profile/input/resource partitions, explicit seeded/start or deterministic designs, fixed-work/fixed-time caps, complete-feasible and available-feasible cohorts, target denominators, missing work accounting and paired raw differences only when declared. The 17-job example covers all three workers, numerical checks and deliberate timeout/invalid-output failures. All original native outcomes remain in the offline report. Multi-task, multi-objective, external-solver and cross-workspace comparisons are outside this first adapter set. See the [comparison guide](scientific-comparisons.md) and [P6 evidence](../evidence/p6/README.md).

**Owner:** experiment-craft for comparisons; solver repositories only for missing model/validation capabilities.  
**Window:** December. **Effort:** 2–4 days. **Dependency:** P5.

Start with existing small models:

| Suite | Example | Report requirements |
| --- | --- | --- |
| fcmaes scalar | Two configurations over declared seeds | Actual work, objective, feasibility definition, timeout, target attainment |
| LP/IP | Small model set with known feasible points | Feasibility, integrality, bounds/gap where available, termination |
| SQP | Distinct starts for a constrained model | Feasibility, stationarity/KKT evidence where available, failed starts |
| Generic scientific command | A small simulation or numerical checker | Input/code identity, checks, exit status, and verified output artifacts |
| Optional surrogate/trajectory | Existing compatible application | Evaluation accounting, provenance, and application validity |

Retain termination, claim, and evidence separately. Repeated deterministic solves may measure timing but are not independent quality discoveries. Keep surrogate integration optional; the current fcmaes documentation describes it as experimental. [R4]

Produce CSV/JSON exports and Markdown reports. Separate fixed-work and fixed-time protocols; show all failures and partial results. Pair experiments only when the design justifies it. Use small seed sets for pipeline validation and predeclare larger confirmation samples later.

**Acceptance:** reconstruct summary arithmetic from raw results; inject invalid output and a timeout; preserve both in totals. Partition incompatible metric definitions. Regenerating a report submits no jobs. CI timings are not presented as home-fleet performance.

### P7 — Package, rehearse, and freeze a preparation candidate

**Owner:** both repositories, each owning its deployment and state.  
**Window:** late December–early January. **Effort:** 2–3 days. **Dependencies:** the chosen completed subset of P0–P6.

Prepare runtime installation/upgrade/rollback, inventory templates, and backup/restore; prepare orchestrator installation, examples, and operating guide. Keep active worker versions and artifacts available across upgrades.

Rehearse service/logout/reboot/resource behavior in a suitable disposable VM if available. Restore runtime state with dispatch paused; reconcile before resuming. Restore campaign state and reuse existing request keys.

Run a clean end-to-end demonstration through an available agent or scripted client. Package per-repository source with exact bases, checksums, compatibility versions, test evidence, limitations, and January checks.

**Acceptance:** the advertised demonstration works from a clean supported Linux environment. Each capability has linked evidence. Existing optimization-only behavior remains usable. Blocked fleet, agent-client, or privileged tests are explicit. Follow repository instructions on tags and publication.

## 8. Calendar, scope cuts, and environments

| Period | Main outcome | Reduced scope if necessary |
| --- | --- | --- |
| 24–31 October | P0 baseline and boundary specification (done 24 October) | One verified worker first |
| Early November | P1–P2 local runtime and generic commands/files (both done 24 October) | Small bundles and a narrow command schema |
| Late November | P3 remote execution (merged 25 October; real-host acceptance open); P5 campaign work against local runtime | Local campaigns plus blocked SSH tests |
| Early December | Backend decision and P4 placement when testable | Explicit-host execution |
| December | P5–P6 real campaigns and scientific reports | fcmaes and a generic simulation first; retain LP/IP and SQP smoke cases |
| Late December–early January | P7 installation and release candidate | Freeze completed capabilities |
| Return home | One worker, then two, then six | Use the last verified configuration |

The eight packages total approximately **20–35 focused developer-days**, plus the one-day initial backend investigation and **4–7 days of integration contingency**. This is a larger scope than version 1 because it adds generic execution and moves shared runtime responsibilities into optimization-jobs. P0 took one day, inside its estimate, so the estimates stand; re-estimate after P2. Add a pin move in the three worker repositories to each package that changes the shared crates (see section 4).

Priority order:

1. **Required:** compatibility, one local execution system, command jobs, verified artifacts, local campaigns, and honest reports.
2. **Next:** real SSH, lost-acknowledgement recovery, installation/restore rehearsal.
3. **Then:** automatic fleet placement and group quotas, where evidence supports the backend.
4. **Optional:** surrogate/trajectory integrations, longer soak, richer plots.
5. **Deferred:** GPUs, dashboard, new fleet MCP surface, arbitrary workflow DAGs, cross-host optimizer internals, automatic failover.

Available-environment tiers:

| Environment | What it can establish | What it cannot establish |
| --- | --- | --- |
| Ordinary Linux environment | Builds, real small jobs, schemas, journals, campaigns, reports | Home boot/driver/resource behavior |
| Multiple local node roots and fake transport | Identity, reconciliation, scheduling logic | Independent physical capacity or real network behavior |
| Disposable SSH endpoints | Transport, framing, connection loss, actual transfer recovery | Mint service/cgroup configuration |
| Disposable systemd VM | Installation, logout/reboot, selected resource-control tests | Home-fleet performance and GPU compatibility |
| Home machines in January | Real inventory, enforcement, compatibility, throughput | Results beyond the tested configurations |

Use environments already available. A previously used remote server is optional only if it remains accessible and supports isolated testing. Do not reconfigure its existing services or make the roadmap depend on renting new machines.

## 9. Test evidence and failure matrix

Each acceptance record contains exact commits, environment, command, expected result, observed result, and evidence path. Use `passed`, `failed`, `blocked_environment`, and `not_run`; a skipped test is not a pass.

| Test | Required outcome | Owner |
| --- | --- | --- |
| Legacy optimization fixtures and worker suites | Existing behavior preserved | optimization-jobs |
| Generic command plus optimizer at capacity | One shared admission budget | optimization-jobs |
| Ordinary arguments contain spaces/metacharacters | Literal argument handling | optimization-jobs |
| Input/script changes under reused key | Conflict; no silent rebinding | optimization-jobs |
| Lost response after remote launch | Reconcile original placement; no duplicate start | optimization-jobs |
| Concurrent clients, drained host, disconnected running job | Atomic accounting; conservative reservations | optimization-jobs |
| Coordinator dies during staging/dispatch/collection | Durable recovery without blind relaunch | optimization-jobs |
| Cancellation with child processes | Workload termination verified | optimization-jobs |
| Corrupt or truncated transfer; disk pressure | Incomplete data never published as verified | optimization-jobs |
| Actual memory violation or CPU placement | Enforcement demonstrated on the tested backend | optimization-jobs |
| Campaign dies after submitting a step | Same runtime handle recovered using stable key | Orchestrator |
| Prerequisite fails or budget is exhausted | Dependent/new scientific work does not launch | Orchestrator plus runtime budget enforcement |
| Invalid scientific results and incompatible metrics | Visible failures or separated comparisons | Orchestrator and relevant worker |
| Restore runtime and campaign backups | Runtime starts paused; campaign reuses accepted identities | Both |
| Six-worker throughput and GPU ownership | Measured evidence on actual devices | January commissioning |

Keep CI bounded. Run cheap checks on routine changes, relevant real-worker integration when affected, and privileged tests only where supported. A short soak precedes one 24–48-hour rehearsal if an available environment and a concrete longevity risk justify it.

Keep a failure ledger. If the same acceptance condition fails twice after attempted fixes, diagnose the cause before introducing another abstraction or service.

## 10. January commissioning

Preparation tests reduce integration work but do not satisfy home-fleet gates.

| Gate | Work | Pass condition |
| --- | --- | --- |
| J0 — inventory | Measure all seven hosts, disks, topology, usable memory, clocks, Mint/systemd versions, and GPU identities | Bounded partial report; controller excluded by default |
| J1 — one worker | Install runtime and run mixed command/optimization work | Accurate records and collection after disconnect, logout, and coordinator restart |
| J2 — resource backend | Complete any unresolved SSH/systemd versus Slurm decision | CPU placement, memory limits, cancellation, restart, and durable terminal evidence |
| J3 — two workers | Reproduce jobs; interrupt transfer and launch acknowledgement | Verified artifacts and no duplicate dispatch |
| J4 — six workers | Enable whole-host allocation and over-capacity mixed campaigns | Correct queueing, budgets, drain, and uncertainty handling |
| J5 — scientific calibration | Measure process/thread packing for representative workloads | Choose allocation from actual throughput and memory data |
| J6 — stable operation | Bounded operational campaign and backup/restore | Sufficient evidence for regular use |

Treat six nominal 16-core workers as separate machines with local memory. Reserve headroom for services. Smaller allocations follow enforcement tests. The desktop stays outside the execution pool unless explicitly enabled.

Record the two RTX 3090s and the controller GPU, but keep GPU execution behind its own compatibility and exclusivity gate.

Retain the original **1 March 2027 scope freeze**. If reliable fleet operation is not demonstrated, use the last proven local or explicit-host configuration for research. Preserve March for applications and competition preparation. The original April–June competition window was user-supplied and was not reverified for this revision.

## 11. Deliverables and repository-local files

Each increment produces exact source bases, a demonstration, actual test results, blocked checks, known limitations, and one reviewable change per repository against an exact base revision.

| Repository | Proposed files or areas |
| --- | --- |
| optimization-jobs | Runtime execution/fleet modules; generic schemas; shared acceptance tests; transport fixtures; installation/backend templates; runtime operations and recovery documentation |
| experiment-craft | Campaign schema/compiler; runtime client; campaign journal; comparison/report modules; sample campaigns; scientific fixtures; agent guide |
| Solver repositories | Only necessary worker/model/checking improvements, each with its own tests |

Cross-repository handoff artifacts:

- [`baseline-lock.json`](../baseline-lock.json): exact repositories, toolchains, schemas, and the shared pin (P0).
- [`docs/reuse-audit.md`](reuse-audit.md): existing facilities, generic boundaries, and demonstrated gaps (P0).
- [`docs/integration-contract.md`](integration-contract.md): supported CLI/JSON versions, capabilities, IDs, budgets, and artifacts (P0; extended by P1–P5).
- [`implementation-log.md`](../implementation-log.md): repository-labelled changes and evidence, one section per package.
- [`docs/known-limitations.md`](known-limitations.md): unimplemented, blocked, and unverified behavior.
- `docs/january-commissioning.md`: actual-machine acceptance checklist (P7; the [backlog](implementation-backlog.md) lists its scope).

Model subscriptions or API credits are independent of execution. Worker machines need neither an AI agent nor provider credentials. Long jobs must not depend on a phone SSH session or an ongoing conversation.

## 12. Next increment and revision record

Each increment brief names one package, the accepted baseline, the owner repository, the prior evidence, and the failure ledger. The next one:

> Accepted native baseline: the merged revisions in `baseline-lock.json`, with the unchanged P3 runtime/SDK and all P5 review fixes from experiment-craft `1577721`. Local P6/EC-03 and its evidence are in `evidence/p6/`. Inspect GitHub and the next review before changing source; rerun the baseline in a new workspace when upstream moves. The next independent package is P7/REL-01: clean installation, upgrade/rollback and backup/restore rehearsal for the completed local subset, operating guidance, inventory templates and an explicit January checklist. Retain worker versions and stable keys; restore with dispatch paused and reconcile before advancing. Do not silently rebind a campaign or introduce automatic replay. Preserve immutable comparison declarations, explicit compatibility, raw native evidence, all failure/unknown denominators and no-submission reporting. P6 uses common declared caps and descriptive statistics, not proof of equal consumed work, statistical significance or home-fleet performance. RT-07 remains blocked without an actual manager/host; keep RT-08 automatic placement and backend group enforcement blocked until real disconnect/logout/reboot, cancellation/containment and allocation evidence selects one authority. Carry the P3/P5 review findings and the P6 failure ledger forward. No tag/publication.

**Version 2.7 revision:** recorded local P6 comparisons and representative suites, additive schemas over unchanged P5 formats, unchanged native pins, continued RT-07/RT-08 gates and the next P7 preparation package.

**Version 2.6 revision:** recorded local P5, its review fixes and merge, its example, declared-budget/foreground boundaries, unchanged native P3 pins, blocked RT-07 environment and the next P6 work.

**Version 2.5 revision:** recorded the merged explicit SSH placement and recovery, the protocol, node and fleet-record schemas, the remote transfer and launch requirements, the review fixes, real-versus-simulated evidence and the remaining backend commissioning gate; the next brief is RT-07, with P3's failure ledger.

**Version 2.4 revision:** recorded the merged command and file contracts (opt-in trusted local commands, verified binary transfer, capabilities 0.2), the review fixes, the compatibility checks and the coordinated pin moves; the next brief is P3, with P2's failure ledger. January commissioning and resource-enforcement claims remain separate.

**Version 2.3 revision:** recorded the merged P1 adapter, record and discovery contract, its compatibility evidence and the coordinated pin moves; the next brief is P2, with P1's failure ledger.

**Version 2.2 revision:** marked P0 complete with its evidence; replaced the documentation-level assessment in section 4 with the commit-pinned audit and its findings (validation before key lookup, capacity not checked by `validate`, shared-pin coordination, build and lint toolchains, staged executables, no systemd user manager in the test container); added the baseline rerun and checkout-SDK checks to P1 acceptance; replaced the P0 brief with the P1 brief; linked the handoff files that now exist.

**Version 2.1 revision:** confirmed experiment-craft, replaced provisional repository references, updated P0/P5 ownership and the first implementation brief, and retained the agreed Rust execution / Python campaign boundary.

| Version 1 decision | Current plan |
| --- | --- |
| Python project owns fleet dispatch, SSH, and execution recovery | optimization-jobs owns the Rust execution and fleet layers |
| Optimization-only first-class execution | Add explicit generic command/script execution with neutral results |
| Separate new coordinator owns resource reservations | Shared runtime owns resource admission and group enforcement |
| New project handles transfer implementation | Runtime stages/transfers/verifies; orchestrator selects artifacts |
| Campaign and execution state share a proposed controller | Each project owns its own facts and communicates through stable handles |
| Seven packages estimated at 14–25 days | Eight packages estimated at 20–35 days, with explicit added scope |
| Provisional orchestrator repository | User-created dietmarwo/experiment-craft is the confirmed campaign repository |

## 13. References and verification boundary

The architecture, package boundaries, priorities, and estimates are implementation proposals. The orchestrator repository is confirmed as dietmarwo/experiment-craft. Version 2.1 described existing capabilities from public documentation; P0 replaced those observations with the commit-pinned [reuse audit](reuse-audit.md), which links the audited source.

- **R1:** [optimization-jobs repository and README](https://github.com/dietmarwo/optimization-jobs) — existing components and integration.
- **R2:** [optimization-jobs AI guide](https://github.com/dietmarwo/optimization-jobs/blob/main/ai-context.md) — node scope, resource limitations, and documented behavior.
- **R3:** [Shared job API guide](https://github.com/dietmarwo/optimization-jobs/blob/main/docs/job-api.md) — execution, result, capability, and compatibility boundaries.
- **R4:** [fcmaes-rust repository](https://github.com/dietmarwo/fcmaes-rust) — solver workers and experimental surrogate support.
- **R5:** [Slurm cgroup v2 documentation](https://slurm.schedmd.com/cgroup_v2.html) — resource-control integration.
- **R6:** [systemd resource-control documentation](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html) — configuration capabilities; installed support must be verified.
- **R7:** [optimization-jobs repository instructions](https://github.com/dietmarwo/optimization-jobs/blob/main/AGENTS.md) — checks, synchronized files, and contribution conventions.
- **R8:** [experiment-craft repository](https://github.com/dietmarwo/experiment-craft) — canonical orchestrator repository created by the user and confirmed on 24 October 2026.

The home machines were not used for P0. Acceptance tests of later packages are recorded in the implementation log as they run.
