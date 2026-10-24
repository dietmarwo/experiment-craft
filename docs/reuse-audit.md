# P0 reuse audit

## Finding

Keep execution in Rust `optimization-jobs`. Most persistence and process helpers already support the intended direction. The significant coupling is the runner's request/worker lifecycle and optimization-specific result interpretation. Refactor those seams before adding command jobs. No upstream source change or dependency-pin change is necessary to establish the tested P0 baseline.

This audit uses `optimization-jobs` commit `f65e664f12cfa68c3e23a070147ea2a6fed87944`. The three workers pin its shared crates to `37b30e428c5fdd017975e0093cc261243148257f`. Git tree comparisons show that `crates/` and `docs/job-api/` are identical between these revisions. The later commits add tutorials, discovery material, a tutorial CI workflow, and documentation/site changes; none touches the paths that the workers' `shared-pin.yml` compares. Compatibility is supported by both this comparison and the recorded real-worker tests.

The plan's suspected 0.2.0/0.3.0 documentation mismatch is not present in this checkout. Both crate manifests and the current `ai-context.md` identify 0.3.0. The 0.2.0 mentions in `ai-context.md` refer to `fcmaes-core` 0.2.0, and `docs/job-api.md` mentions 0.2.0 only as history. Treat the earlier observation as stale retrieval, not a reason to change source or claim an extra release.

## Existing components

Paths below are relative to the pinned optimization-jobs checkout. Names refer to existing code, not proposed APIs.

| Component | Existing behavior | Reuse decision / remaining seam |
|---|---|---|
| `crates/optimization-job-api/src/storage.rs` | Atomic JSON replacement, directory/file syncing, locks, checked journal envelopes, resilient tail reading and repair | Reuse storage primitives. Keep journal record meaning with its domain. Do not claim that several individually durable files form one atomic transaction. |
| `…/process.rs` | Shell-free argv spawning, process groups, bounded output drainage, cancellation/deadlines, checking whether a group stopped | Reuse under one supervisor. Process groups are not hostile-code isolation; a descendant that changes session/group needs stronger containment. |
| `…/spec.rs` | Strict optimization envelope, resource validation, relative checked inputs, SHA-256 staging | Reuse path/hash checks. Introduce a separate command request; adding arbitrary fields to the existing deny-unknown-fields envelope would break its contract. |
| `…/artifact.rs` | Declarations, journal/JSON reading, digest sealing, bounded inline reads and record paging | Reuse metadata and sealing; add a versioned binary-file/transfer path. Declared formats are `records` and `json` (the runner reads older manifests' `file` entries), not arbitrary file downloads. |
| `…/worker.rs` | `Worker::prepare`, `Prepared::solve`, task concurrency, cooperative cancellation and result journals | Keep in the optimization adapter/SDK. A command has exit status and outputs, not optimizer tasks or fabricated objectives. |
| `…/result.rs` | Optimization outcomes, claims, evidence, feasibility, progress, repair, comparisons, manifests | Keep domain-specific. Introduce a neutral execution record that can refer to a native optimization manifest. |
| `crates/optimization-runner/src/lib.rs`: `staged`, `prepare` | Registered binary verification, validator execution, normalization, local key/identity lookup, durable attempt directory | Retain content identity and administrative worker registration. Separate neutral prepared-execution metadata from optimizer validation. |
| Same file: `reconcile_ledger`, `admit`, `release` | Locked slot ledger, boot/attempt checks, conservative reservations | Reuse the authority. Admission is cooperative CPU-slot accounting, not CPU pinning, memory enforcement, or a documented FIFO scheduler. |
| Same file: `launch`, `execute_worker`, `finish` | Worker process lifetime, log capture, stop requests, deadlines, group cleanup, terminal state | Extract lifecycle mechanics internally. Replace hard-coded `worker execute DIR` and `worker_outcome` calls with explicit adapter boundaries. |
| Same file: `submit`, `get`, and the `jobs reconcile`/`jobs repair` command handlers | User-systemd launch, handles, durable observations, conservative recovery | Preserve unknown-start behavior. Fleet support must reconcile the same chosen node and request key. |
| `crates/optimization-runner/src/mcp/` | CLI-backed tools, input handling, tasks, cancellation, artifacts, embedded guide | Retain existing optimization access. Add generic capabilities separately with versioned discovery and policy. |
| `crates/optimization-runner/src/host.rs` | Host/resource observations | Reuse discovery inputs, but do not infer enforced allocations from observations. |

### Limits that future interfaces must account for

- Current inputs: at most 16, each at most 64 MiB, relative paths contained beneath their base directory, and verified hashes.
- Current artifact declarations: at most 4,096; inline reading is bounded to 1 MiB; record pages are bounded to 10,000 records and 1 MiB of payload. Reserved runtime filenames remain protected.
- Shared resource rule: `1 <= outer_workers * inner_threads <= cpu_slots <= 1024`; node capacity is another admission constraint. Worker discovery can impose stricter thread limits.
- Worker validation runs separately with bounded time/output. The runner verifies that a worker does not change shared envelope fields.
- Worker execution stdout/stderr capture is bounded (1 MiB each); excess is drained rather than retained. Validator output is capped at 4 MiB, and exceeding it is an error.
- An attempt is not a solver checkpoint. Journal repair recovers committed evidence; it does not resume an optimizer or repeat an uncertain execution.

## Durability and identity

`prepare` derives a node-local job ID from the first 32 hex characters of SHA-256(request_key). A separate identity hashes the normalized request plus staged worker digest. Reusing a key with different resolved work yields `request_key_conflict`; reusing the same identity returns the existing attempt. The smoke evidence checks both behaviors without another journal append.

There is an important ordering constraint: the current implementation stages and validates, and checks node capacity, **before** looking up the existing request. A repeated call can therefore fail if registered worker bytes (`worker_changed`) or input bytes (`invalid_job`) have changed. A client should preserve its specification and registration, persist returned handles, and use `jobs get` for observation. P3 must explicitly design immutable resolution and a global lookup contract; it must not assume this local implementation already provides one.

`submit` creates a user-systemd service with control-group killing. If service-start acknowledgement is ambiguous, it records `start_unknown`; re-submitting that key does not blindly start another unit. Slot reconciliation uses boot IDs, launcher/worker locks, process/group observations, and unit state. An uncertain remaining process group keeps its reservation. Preserve these conservative decisions when introducing new kinds or remote dispatch.

Foreground tests exercise the native local runtime. They do not demonstrate detached logout survival, reboot behavior, or home-machine systemd/cgroup configuration. Positive service durability requires a suitable VM and later January commissioning.

## Proposed internal boundaries (P1 onward; not implemented)

| Internal boundary in optimization-jobs | Owns | Must not own |
|---|---|---|
| `execution` | Neutral request identity, attempt state, execution record, adapter interface | Mathematical validity or campaign decisions |
| `supervision` | Start, deadline, stop, logs, process/backend containment | Solver-specific success rules |
| `admission` | Local resource reservations, conservative reconciliation | Competing campaign-side reservations |
| `staging` / `artifacts` | Verified input/output materialization, sizes, digests, transfer completion | Scientific interpretation of bytes |
| `optimization` adapter | Existing envelope/worker protocol, validation, task journal, native manifest | Generic shell semantics |
| `command` adapter (P2) | argv or explicit script, working directory, bounded environment, exit/signal result | Invented feasible/optimal values |
| `fleet` / transport (P3+) | Selected node, durable dispatch intent, global/local handles, transport recovery | A second node-level resource authority |

Begin as internal modules. New crates are justified only by demonstrated dependency separation. Keep remote dependencies out of the solver-facing SDK where feasible. Existing local users retain their current CLI, schema, MCP, and library behavior without Python or a fleet daemon.

## Source anchors

- [Shared API at audited commit](https://github.com/dietmarwo/optimization-jobs/tree/f65e664f12cfa68c3e23a070147ea2a6fed87944/crates/optimization-job-api/src)
- [Runner lifecycle and CLI](https://github.com/dietmarwo/optimization-jobs/blob/f65e664f12cfa68c3e23a070147ea2a6fed87944/crates/optimization-runner/src/lib.rs)
- [Published contract and operational guide](https://github.com/dietmarwo/optimization-jobs/blob/f65e664f12cfa68c3e23a070147ea2a6fed87944/docs/job-api.md)
- [Black-box integration tests](https://github.com/dietmarwo/optimization-jobs/blob/f65e664f12cfa68c3e23a070147ea2a6fed87944/scripts/job-api/test_integration.py)

