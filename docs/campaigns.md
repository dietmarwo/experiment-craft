# Local campaigns

`experiment-craft` 0.1.0 implements the local P5 campaign layer. The native runtime remains the merged P3 set in [baseline-lock.json](../baseline-lock.json). RT-07 is [blocked in this environment](backend-gate.md); fleet placement and automatic scheduling are outside this client.

## Install and try the real example

On Linux with Python 3.12 or newer:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m pip install -r requirements-baseline.txt
.venv/bin/python scripts/baseline.py fetch build --workspace .baseline --jobs 2
.venv/bin/python examples/campaigns/local-mixed/run.py --bin-dir .baseline/bin --output /absolute/new/demo
```

The demo initializes its own one-slot node, explicitly enables trusted commands, and registers the three binaries. It prepares an LP model through a command output, runs a three-seed fcmaes sweep, solves the LP and an SQP problem, and checks the two native numerical results. Its seven jobs produce `report/report.json`, `report/results.csv` and `report/report.md`. The generated manifest and source inputs are under `source/`; the accepted campaign is under `campaign/`. Repeating advancement and reporting submits no new execution and changes no native job journal.

For an existing node, administration stays outside the campaign client. Configure capacity, workers and command policy with optimization-jobs. The client never enables commands, registers a worker, initializes a node, or chooses another host on your behalf.

## Manifest

The [versioned schema](../experiment_craft/schemas/campaign-0.1.schema.json) defines `experiment.campaign/0.1`. A manifest contains a name, explicit budgets and a nonempty list of steps. Commands additionally require `allow_commands: true`.

```json
{
  "schema_version": "experiment.campaign/0.1",
  "name": "Small trusted command",
  "allow_commands": true,
  "budget": {
    "max_jobs": 2,
    "max_wall_seconds": 60,
    "max_reserved_slot_seconds": 30
  },
  "steps": [{
    "id": "check",
    "job": {
      "schema_version": "execution.command/0.1",
      "argv": ["/bin/true"],
      "env": {},
      "resources": {"cpu_slots": 1},
      "limits": {"wall_seconds": 5, "grace_seconds": 1},
      "replay": "never",
      "inputs": [],
      "outputs": []
    },
    "matrix": {"/limits/wall_seconds": [5, 6]}
  }]
}
```

Optimization jobs use the existing `optimization.job/0.1` envelope, with `worker`, `payload_schema`, `payload`, `resources`, `limits` and inputs. The compiler assigns every `request_key`; specifying one yourself is an error. Native payload validation stays in the registered Rust worker. A ready step is validated through the runtime before its dispatch intent is written. Dry-run checks campaign structure and source references; it does not invoke a worker validator or promise that a scientific payload will be accepted.

Matrix keys are JSON pointers to existing fields under `/payload/`, `/resources/` or `/limits/`. Expansion sorts pointers and variant identities deterministically; duplicate values fail. A `needs` entry names another template and joins all its variants. Cycles and missing/self dependencies fail. There are at most 4,096 expanded jobs, 16 axes, 128 inputs per command and 16 per optimization job. The expanded plan and manifest each fit in 4 MiB. Input files are at most 64 MiB, with at most 256 MiB of unique static snapshots per campaign and resolved input bytes per job.

Static input `file` paths are relative to the manifest. The compiler hashes them; an optional declared hash/size must match. Paths must be contained and cannot include dot-prefixed components or source symlinks. Initialization retains verified copies, so continuation needs neither the original manifest nor its input files. Command executable/interpreter identity is also recorded; the submitted argv[0] is preserved. Host libraries and undeclared file reads are not snapshotted.

A dependent input can select a sealed command output:

```json
{"name":"model","from":{"step":"prepare","kind":"output","output":"model"}}
```

A command input uses `path` in place of `name`. `kind: "native"` selects the producer's checked native manifest and omits `output`. The producer must have exactly one variant; ambiguous sweep output binding fails. References automatically add dependencies. Binary output collection goes through `jobs collect`; the client does not add a transfer service. Native manifests are read locally using the runtime-provided terminal record, exact length and digest. The campaign stores the original bytes and retains the neutral record separately.

Optimization `accept` can specify `require_feasible: true` and a list of accepted native `claims`. Without extra rules, readiness means completed native tasks with complete accounting, not an optimality or feasibility claim. An infeasible result can be a legitimate completed experiment; declare stricter prerequisites when needed. Commands use exit status and declared-output completeness and cannot take optimization acceptance rules. Reports preserve all native claims, terminations, work and evidence.

## CLI and continuation

```bash
experiment-craft dry-run campaign.json
experiment-craft init campaign.json --workspace /absolute/new/campaign --runner /absolute/optimization-run --node-root /absolute/node --mode foreground
experiment-craft continue --workspace /absolute/new/campaign
experiment-craft status --workspace /absolute/new/campaign
experiment-craft stop --workspace /absolute/new/campaign
experiment-craft collect --workspace /absolute/new/campaign
experiment-craft report --workspace /absolute/new/campaign --destination /absolute/reports
experiment-craft events --workspace /absolute/new/campaign --after 0 --limit 1000
experiment-craft provenance-diff before/plan.json after/plan.json
```

`run MANIFEST` combines initialization and continuation with the same configuration flags as `init`. `run` and `continue` accept `--once` for one advancement/observation. Expected errors emit a JSON error with a stable code and exit 2. A full run returns exit 0 only when every step is accepted; an incomplete, stopped or uncertain run returns 1. Status/report/collect and `--once` return structured observations; exit 0 alone is not scientific success.

The default mode is `systemd`: the client delegates to native `submit`. It requires the runtime's user-manager preflight; actual logout survival also needs the node's commissioned linger/service configuration. Roots/helper paths containing `$` are refused in this mode because systemd expands them. The explicit `foreground` mode calls native `run`, waits and requests cancellation through native `jobs cancel`. It adds no detached service, process-group supervisor or SSH implementation. A killed Python client can reconnect to the same native job in a surviving session; this is not evidence for terminal logout or machine reboot survival.

State and decisions commit together in SQLite transactions with WAL and FULL synchronous mode. A separate advisory advancement lock prevents competing dispatch decisions while allowing a second client to stop the campaign. Runtime/root/node ID, worker and runner identities, mode, scientific plan and request keys bind the workspace. Changed inputs change plan identity; a changed plan/runtime cannot silently replace an existing workspace. No reset/retry flag overwrites accepted facts.

Dispatch intent, validated resolution/command identity and declared budget reservation precede the CLI call. Observations check the persistent node ID and the native job resolution/provenance against that evidence. A conflicting key or different resolved request cannot be adopted as the campaign result. This local verification is tested against the exact runtime revision in the lock, including its returned job directory and resolution/provenance files. Definitely unsent process-spawn failures return the step to pending. A lost answer, killed client or ambiguous start retains its predicted native handle; continuation observes it and does not submit again. A crash between the persisted intent and process creation can leave an unobserved uncertain step. Missing evidence is not proof that replay is safe: inspect/repair through the runtime before deciding on new work. The client never performs automatic repair or mathematical resume.

Stop commits before cancellation. Pending steps become stopped; cancellation of active handles is retried if it races native preparation. A failed prerequisite blocks transitive dependents. An uncertain attempt holds campaign admission reservations and blocks further sequential dispatch. An unconfirmed cancellation remains observable; neither a requested stop nor a deadline is presented as verified termination.

## Budget and report semantics

The campaign dispatches ready steps sequentially. `max_jobs` caps issued intents. The declared slot-second cost of a step is `cpu_slots * (wall + grace)`; its admission reservation is never refunded after an issued/uncertain call. This is a declared-work budget, not measured CPU time or enforced aggregate slot-hours. Native overhead and queueing are separate. It is not another host capacity ledger: Rust owns admission for this and every other client.

The absolute campaign deadline includes waiting and time between client sessions. While advancing, expiry persists stop and requests native cancellation. This is client policy, not an always-running backend group deadline: if the client is absent, only the native job's own limits are enforced. RT-07/RT-08 remain the gate for stronger backend/group policies. Disconnected or unconfirmed work stays visible and reserved.

Reporting reads retained evidence only and can run offline. Every expanded step appears, including failures, blocked prerequisites, unknown work and budget exhaustion. JSON retains native outcomes; CSV is a convenience scalar projection and Markdown is a first overview. There is no pooled objective across profiles, ranking, statistical inference or conversion of `best_found` into stronger evidence. P6 adds scientific comparison protocols.

Retain the whole campaign workspace. Initialization interrupted before publication leaves only a private temporary directory for inspection; an existing workspace is never replaced. Use SQLite's backup facilities with clients paused when backing up an active WAL database; copying only its main file is insufficient. Backup/restore and power-loss commissioning remain P7 work.

## Verification

```bash
python3 -m unittest discover -s tests -v
EXPERIMENT_CRAFT_TEST_BIN_DIR=/absolute/baseline/bin python3 tests/integration_campaign.py
```

The live suite requires the actual reviewed runner and all three workers; missing binaries fail. It checks interrupted clients, stop races, queued waiting deadlines, immutable snapshots, no replay after an uncertain intent, failed dependencies, budgets, native evidence and offline/tamper-checked reports. Two test-only commands under `tests/fixtures/` simulate a user manager to exercise the systemd delegation/unknown-start branch; they do not validate an actual user service.
