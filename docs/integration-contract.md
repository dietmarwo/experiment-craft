# experiment-craft integration contract

Status: P3 explicit remote contracts are implemented at the revisions in `baseline-lock.json`. Production backend commissioning remains a separate gate. Automatic allocation and campaign sections remain proposals. These interfaces need runtime source after published 0.3.0.

## 1. Existing local optimization interface

Use the Rust CLI as a subprocess with an argument array and JSON output. Do not parse human documentation as a capability API. This checkpoint tests `optimization-run` 0.3.0 with job envelope `optimization.job/0.1`, worker protocol `optimization.worker/0.2`, and result manifest `optimization.result/0.2`. The runtime also contains legacy compatibility paths; P0 does not redesign them.

Always pass `--root`: without it the runner uses `$OPTIMIZATION_RUN_ROOT`, then `$FCMAES_RUN_ROOT`, then `./.optimization-jobs` in the current directory. Output is JSON whether or not `--json` is given.

| Operation | Existing CLI after `optimization-run --json --root NODE_ROOT` | Client interpretation |
|---|---|---|
| Configure local capacity | `node init --capacity N` | Administrative setup; not a per-campaign operation |
| Register worker | `workers add --id ID --executable ABS_PATH` | Administrative trusted-code choice; registration records executable identity |
| Discover | `node doctor`, `workers list`, `problems list`, `problems describe ID` | Read worker protocol, build, profiles, schemas, examples and thread support |
| Validate | `validate --spec FILE` | Expect `valid: true` and `resolved`; this does not reserve resources, check node initialization or capacity, or prove numerical solvability. A valid job can still fail with `capacity_exceeded` at `run` or `submit` |
| Run foreground | `run --spec FILE` | Executes/waits on a newly prepared attempt; an existing key may return its current observation immediately |
| Launch detached | `submit --spec FILE` | Requires working user-systemd support; acknowledgement may be uncertain |
| Observe | `jobs get ID`, `jobs list`, `jobs wait ID --timeout SECONDS`, `jobs events ID` | Persist and use the handle. `jobs wait` returns the current state with exit 0 when the timeout expires; check `state`, and do not treat a timeout as permission to rerun work |
| Stop | `jobs cancel ID` or `jobs cancel ID --now` | Cooperative finish of active work or immediate stop; observe the resulting state. Cancelling a finished job returns the error `already_terminal` |
| Collect locally | `result DIRECTORY`, `jobs artifact ID NAME [--offset N --limit N]` | Read native result/declared JSON or records; directory is a local path, not a remote locator |
| Compare | `compare DIRECTORY_OR_MANIFEST DIRECTORY_OR_MANIFEST...` | Compares two or more native result manifests; it reads result schema 0.1 and 0.2 |
| Recover | `jobs reconcile`, `jobs repair ID` | Runtime-owned reconciliation and journal repair; not solver resume |

Successful commands emit JSON on stdout. Every runner failure exits with status 2 and writes one JSON error to stderr with `code`, `message`, and `retryable`; errors without a specific code are `runner_error`, argument errors are `invalid_command`, and only `attempt_active` is retryable. Two cases print plain text instead: clap's help when a subcommand is missing, and the refusal to run on a non-Linux system. Retain stderr either way, and do not classify errors by message text. This checkpoint confirms `request_key_conflict` for changed work under an existing key and `invalid_job` for corrupted input bytes.

Do not equate CLI exit 0 with scientific success. Inspect job `state`, manifest `status`, completed task counts, per-task `termination`, `claim`, `feasible`, and `evidence`. `best_found`, `numerical_optimum`, and `first_order` have different meanings. A first-order SQP point is not a global optimality proof. Preserve unknown accounting and evidence as unknown, rather than zero or verified.

The client should generate and durably retain a stable request key for each resolved campaign step. Keep the same key for observation/reconciliation; a deliberate new attempt gets a separately recorded key and reason. The existing local runtime derives the node-local job ID from the request key and hashes the worker-normalized specification together with the registered worker digest as the identity. Input SHA-256 values therefore participate in resolved identity. Because staging and validation precede the key lookup, a repeated request fails when its inputs are missing or changed (`invalid_job`), when the worker executable changed without re-registration (`worker_changed`), or when re-registration changed the identity (`request_key_conflict`). Observe an accepted job with `jobs get ID` rather than by repeating the request.

The current contract supports explicit placement on registered SSH nodes. Generic commands and binary files are now available through the CLI, with explicit capability/policy discovery; worker discovery remains solver-specific.

## 2. Execution discovery and record

`optimization-run node capabilities` returns `execution.capabilities/0.3`
without creating a node root; doctor and MCP expose the same object. Supported
kinds are optimization and command; enabled kinds reflect node command opt-in.
It advertises binary file transfer through the CLI, schemas and byte limits;
fleet is explicit and CLI-only. The existing optimization and execution-record schemas
are unchanged.

`optimization-run --root NODE jobs execution ID` reads the atomic terminal
`.execution.json` sidecar. It records identity, kind, terminal state, declared
slots, timestamps, observed exit code or signal, stop reason, containment,
stdout/stderr references, and a native result attachment (filename, schema,
bytes, SHA-256). The hidden path cannot collide with named worker artifacts.
It is separate from native `run.json`: objectives, feasibility, evidence and
work counters stay native. A zero process exit without a valid optimization
manifest remains failed. The old fcmaes native schema remains integer `1`.

The launcher publishes native result, execution record and terminal state in
that order. A record does not replace the state/locks or authorize a retry.
`source: launcher` uses measured duration. `source: repair` has no observed
exit status; duration is zero for a never-admitted attempt, the validated
worker duration when recovered, or null. Missing old content identity is null,
not synthesized. Unknown containment retains reservations.

A record is served only when `job.json` is terminal with the same state and
`finished_at`. An attempt that has not finished returns `attempt_active`
(exit 2, retryable true): wait with `jobs wait` and ask again, or repair the
attempt if its launcher was lost. A finished attempt without a matching record
(finished by an older runner) returns `execution_unavailable` (retryable
false); native inspection still works. Records are not backfilled. A
malformed sidecar is `runner_error`. Repair records `not_started` containment
for attempts that never reached `running`.
There is no new MCP tool or Rust plugin API. MCP submission/result summaries
remain optimization-only: `validate_job` and `submit_job` refuse command
requests with `unsupported_job_kind`, and so does every runner the MCP server
starts. Commands and binary file operations use the CLI.
The adapter, admission and supervision modules remain private.

## 2a. Local command and binary-file contract (P2)

The authoritative schema and behavior live in the
[upstream command guide](https://github.com/dietmarwo/optimization-jobs/blob/main/docs/job-api.md#trusted-local-command-jobs-and-binary-files)
at the pinned runtime commit. Experiment-craft must call these operations,
not implement a second execution or transfer service.

| Surface | Implemented contract |
|---|---|
| Enable | `node init --allow-commands` or `node commands --enable`; default off |
| Request | `execution.command/0.1`: literal argv, explicit env, cpu_slots, wall/grace, replay=never, checked inputs and outputs; input `file` paths are relative to the request file's directory |
| Identity | Normalized request (with the submitted argv[0]) + resolved executable path and digest; input/script bytes and permissions enter identity; source file location is not identity |
| Workspace | Declared relative paths under work/; no symlinks, no empty or dot-prefixed segments, no path inside another declared path; runtime files live beside work/; trusted same-UID code is not sandboxed |
| Process | Same admission ledger and supervision as optimization; the verified executable (absolute, at most 1 GiB, or a declared `./` input) runs under the submitted argv[0]; TERM then KILL for command cancellation/deadline; logs capped at 1 MiB each, drained for at most two seconds after the group stopped |
| Result | `execution.command.result/0.1` attached by hash/size to `execution.record/0.1`; exit/signal and output completeness only |
| Recovery | No automatic replay. Lost launcher requires conservative repair, which reports interrupted and no invented process exit or elapsed time |
| Upload/download | `files put/get` stream at most 64 MiB, verify exact size/hash and publish without clobbering; 1 GiB blob store |
| Collection | `jobs collect ID NAME --destination NEW_FILE` copies a verified sealed output, independently retryable without execution |
| Job bounds | 128 declarations, 64 MiB each, 256 MiB combined input bytes and output limits; arbitrary working writes are not quota-enforced |
| Retention | `files cleanup` removes only upload partials under lock; verified blobs/attempts persist until explicitly removed; download/staging leftovers need inspected manual cleanup |

The baseline `check` action includes the upstream command/file suite and the
build–run–collect example. These exercise real local processes, not SSH or
systemd/cgroup durability. Process groups cannot contain deliberate session
escapes; no kernel CPU/memory/disk enforcement is claimed.

## 3. Explicit remote contract

The Rust runtime owns endpoint inventory, node identity, staging, durable dispatch intent and recovery. Python asks for execution and retains the returned handles; it does not add SSH or another capacity ledger. The
[authoritative SSH guide](https://github.com/dietmarwo/optimization-jobs/blob/main/docs/job-api.md#explicit-ssh-placement-and-recovery) and published schemas describe the full interface.

| Surface | Implemented behaviour |
|---|---|
| Discovery | `execution.node/0.1`, stable node ID, boot observation, capacity, compact worker identities and manager/linger observations |
| Transport | OpenSSH batch mode, pinned known-hosts file, explicit helper path, no TTY/forwarding; `execution.remote/0.1` JSON plus bounded raw bytes |
| Placement | `fleet nodes add/probe`, `fleet submit --node`; endpoint and node identity bind before any launch |
| Local intent | `execution.fleet.job/0.1` stores coordinator/global/dispatch identities, immutable normalized spec and input snapshots |
| Remote intent | Node records before preparation and a launch barrier before calling existing systemd-user launch; repeats only observe |
| Resolution | Native job identity, resolved-spec digest, local ID and backend unit are retained with the global handle |
| Uncertainty | `get` reads local state; `reconcile` observes the same node. An issued launch cannot move/relaunch. A never-issued staging intent may resume |
| Recovery | Explicit cancel/guarded repair use the existing node liveness and reservation rules; no automatic repair or fabricated exit |
| Collection | Inspect a verified terminal result/record/sealed artifact, then hash/length-check download before no-clobber publication. Collection retry never computes |
| Bounds | 4 MiB control frame, 64 MiB file, 256 MiB declared input total; existing 1 GiB node blob quota; client deadline1–300 s, helper I/O300 s |
| Backend | User manager plus `Linger=yes` required for new remote dispatch. Actual service/logout/reboot/cgroup evidence is still required |

Real OpenSSH loopback tests use real Rust workers and an explicitly simulated service manager. Protocol/fault tests use a named transport fixture. Actual user services, hardware and kernel enforcement are not inferred from those results. Automatic placement, global group budgets and Slurm integration remain gated by RT-07/RT-08.

## 4. Python campaign boundary (P5 proposal)

`experiment_craft` will contain manifest expansion, a thin CLI/JSON client, campaign state/journal, comparison rules and reports. Before submission it records the step's resolved inputs and stable key; after acknowledgement it records the opaque handle. On restart it observes/reconciles existing handles before advancing dependencies. It retains scientific decisions separately from runtime state.

Independent optimization runs can be composed without changing the SDK. A command or fleet step is rejected until the runtime advertises that capability. Campaign limits include waiting and aggregate budgets; the authoritative allocation remains in Rust/backend policy. Reports must distinguish objective values, claims and evidence, failed/partial jobs, unknown work, and verified versus estimated slot-hours.

### Compatibility gates

1. Reproduce this pinned baseline and old fixtures before P1 changes.
2. Preserve current output semantics and schema validation while extracting internal modules.
3. Add a neutral non-optimization fixture before the command adapter; it must not invent an optimization outcome.
4. Exercise mixed command/optimization admission, descendant cancellation, literal metacharacter arguments, changed input identity and interrupted transfers before P2 acceptance.
5. Fault-test lost launch acknowledgements and coordinator restarts before P3; record real SSH/systemd evidence separately from simulated transports.

The [backlog](implementation-backlog.md) assigns these gates to repositories and phases. The [smoke script](../scripts/smoke.py) is an executable example of the existing local interface, not the future campaign client.
