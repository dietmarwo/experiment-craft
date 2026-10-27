# Named artifacts and recorded verification

Command jobs can seal arbitrary named files. `experiment-craft artifacts`
lists their saved metadata, `collect-artifact` retains a checked local copy,
and `verification-report` gives an offline view of a supported application's
acceptance receipt. Execution, staging, transfer and recovery remain in
optimization-jobs.

The built-in `cap.audit/0.1` adapter reads the validated-numerics all-arm audit
from fcmaes-rust. It displays the application's recorded verdict, every arm's
verification/replay outcomes and its final-candidate timing observations.
It does not execute a checker, upgrade a native claim or perform a statistical
comparison. The [campaign report](campaigns.md) and
[predeclared comparisons](scientific-comparisons.md) keep their existing formats.

## List and collect named outputs

```bash
experiment-craft artifacts --workspace /absolute/campaign
experiment-craft artifacts --workspace /absolute/campaign --step audit --after 0 --limit 100
experiment-craft collect-artifact --workspace /absolute/campaign --step accept --output acceptance
```

Use the expanded step ID from the plan, rather than a matrix template with
multiple variants. Output names are the command's declared `name` values.
For a name beginning with a dash, use `--output=--name`; the runtime call also
uses the argument separator so the name remains literal.

The catalogue is offline and pages at most 1,000 declarations at a time. Pass
`next_offset` as `--after` for the next page. Order follows the immutable plan
and output declarations. Each entry keeps the step/native state separately
from artifact availability:

| Availability | Meaning |
| --- | --- |
| `pending` | No retained terminal native result yet. Observe the existing handle with `collect`; no output is invented. |
| `unavailable` | No sealed file is recorded, including an absent optional output or an unissued/failed step. Byte count and digest stay unknown. |
| `sealed` | A checked native result names this output's length and SHA-256; it has not been retained by this client operation. |
| `retained` | The local copy matches that native length and digest. |

`collect-artifact` takes the campaign advancement lock. For a missing local
copy it checks the bound runner and node identity, the saved native handle,
execution identity and native result, then calls the runtime's `jobs collect`.
The returned bytes must match the already retained native metadata. It
publishes the cache file without replacing an existing one. It never dispatches,
resubmits, cancels, repairs or administers a job/node.

The checked file is retained under `results/STEP/outputs/NAME` in the campaign
workspace. The CLI returns that relative path and its provenance. A repeated
collection checks the cache and makes no runtime call. Changed bytes or a
symlink are refused; they are not silently replaced. Collection can retain
outputs from failed jobs as well as successful ones. A collected file is not
evidence that the command succeeded scientifically.

Collection changes neither campaign decisions/events nor job budgets. It is
allowed while dispatch is paused. Checked caches are included in campaign
backups, audited against the native manifest and available to offline reports
after a paused restore. Keep one writable campaign authority.

A transfer is staged in `results/STEP/`, beside the cache, so an interrupted
collection leaves nothing under `outputs/`; the next collection removes its
leftover. A cached copy that no longer matches its native digest blocks
`backup` and `restore`, which must carry intact copies; remove it and collect
it again. It does not block `unpause-dispatch`, since dispatch never reads it.

The formats are
[`experiment.artifacts/0.1` and `experiment.artifact.collection/0.1`](../experiment_craft/schemas/artifacts-0.1.schema.json).
Individual files retain the native 64 MiB limit; no binary data is embedded in
the catalogue's JSON output. There is no aggregate cache quota; backups keep
their existing `--max-bytes` bound. This client path supports local command outputs;
worker-specific artifacts and remote campaign routing remain separate APIs.

## Read a CAP audit receipt

After a generated search → audit → acceptance campaign:

```bash
experiment-craft collect-artifact --workspace /absolute/campaign --step accept --output acceptance
experiment-craft verification-report --workspace /absolute/campaign --step accept \
  --output acceptance --adapter cap.audit/0.1 --destination /absolute/verification-report
```

The acceptance step must use the input paths of fcmaes-rust's
`make_audit_campaign.py`: `problem.json`, `study.json`, `candidates.json`,
`evaluations.jsonl`, `protocol.json`, `audit.json`, `events.jsonl`,
`audit-protocol.json` and the checker source/schema inputs under `app/`.
The adapter reads their retained admitted snapshots, not the source manifest,
mutable node working files or arbitrary paths supplied by a receipt.

The report binds the receipt's audit/protocol/input hashes to the actual
acceptance request. It checks the frozen problem, common exact target, arm
identities/order, candidate hashes, stage-document identities, certificate to
replay links, counts and displayed timing observations. A changed input,
receipt, cache, checker identity or inconsistent link fails reporting before
an existing report is replaced. It does not duplicate the application's
theorem implementation or its full acceptance algorithm.

| Report status | Meaning |
| --- | --- |
| `reported_accepted` | The application reports all arms accepted, and its native command completed with exit 0 and valid declared outputs. |
| `reported_rejected` | The application reports rejection and its native command failed with the documented exit 3; rejected/censored arms stay in the report. |
| `unconfirmed` | A receipt exists but its native execution/exit does not support it, for example an accepted receipt alongside exit 7 or cancellation. |
| `unavailable` | No terminal receipt is recorded. Arm counts and costs stay unknown rather than zero. |

A sealed receipt that has not been collected gives `artifact_not_collected`;
collect it explicitly first. Missing scientific evidence never becomes an
accepted observation. Execution consistency confirms the receipt's provenance
and exit convention, not its mathematics. The producer/checker remains a
trusted application. For untrusted external proof data, run the trusted
verifier/replay afresh before relying on its conclusion.

The adapter supports the frozen scalar cube-root and order-32 Cahn–Hilliard
problems at the exact physical target `1/10000000000`. It preserves their
declared equation, branch, norm and local theorem scope. It does not assert
global optimality, nonexistence, a parameter-family proof or region coverage.

Outputs are `verification.json`, `verification.md` and `observations.csv`.
The versioned format is
[`experiment.verification.report/0.1`](../experiment_craft/schemas/verification-report-0.1.schema.json),
with [the adapter's consumed fields](../experiment_craft/schemas/verification-cap-0.1.schema.json).
The destination must be outside campaign/node roots and may contain only a
previous report of the same kind. Repeated reports are stable and make no
runtime call. Existing reports survive invalid input or publication failure.

These are final-candidate costs: shared search startup, arm work and fresh
verification/replay, with the application's declared exclusions. Unsuccessful
arms remain in the denominator. Censoring can be informative; the report
provides no survival estimate, successful-only median, timing rank or optimizer
advantage claim. It is not time to the first certificate found during search.

## Expected failures

Expected failures use the CLI's existing JSON error/exit-2 contract:

| Code | Meaning |
| --- | --- |
| `unknown_step`, `unknown_artifact`, `unsupported_artifact` | Selection is absent or is not a named command output. |
| `output_unavailable` | No sealed native output is retained for collection. |
| `artifact_not_collected` | Collect the existing sealed receipt before offline reporting. |
| `artifact_changed`, `input_changed`, `result_changed` | Retained data or its identity no longer matches; nothing is replaced or rerun. |
| `node_identity_mismatch`, `runtime_changed` | The collection target no longer matches the campaign binding. |
| `unsupported_verification`, `invalid_verification`, `verification_mismatch` | Unsupported adapter/input layout, malformed data or inconsistent receipt/source links. |
| `invalid_destination`, `campaign_busy` | Choose a report-only destination, or wait for the other campaign operation. |

## Real scientific example

Build the pinned native baseline using the [README](../README.md), instantiate
the pinned Julia 1.10.10 environment under the baseline's fcmaes-rust checkout,
and build its nested search binary:

```bash
cargo +1.88.0 build --release --locked \
  --manifest-path .baseline/repos/fcmaes-rust/tutorials/validated-numerics/search/Cargo.toml \
  --target-dir /absolute/search-target
python3 examples/campaigns/certificates/run.py \
  --fcmaes-source .baseline/repos/fcmaes-rust \
  --binary /absolute/search-target/release/cap-search \
  --julia /absolute/julia-1.10.10/bin/julia --depot /absolute/instantiated-depot \
  --runner .baseline/bin/optimization-run --problem scalar-cuberoot \
  --output /absolute/new/certificate-demo
```

Use `--problem cahn-hilliard` and a new output directory for the PDE case.
Python must have jsonschema in the interpreter used to generate the campaign.
The example explicitly administers its own one-slot foreground test node;
that administration is not an automatic client action. Each problem uses
three real command jobs, verifies and replays nine final candidates in fresh
Julia processes, collects its receipt and reports it offline. A separate exact
rational recheck validates all nine certificates. Continuation submits no
duplicates. Small easy cases demonstrate integration, not optimizer superiority.

The [retained evidence](../evidence/verification-reports/README.md) records the
tests and their scope. The dashboard keeps its existing execution-step view;
proof-aware UI, predeclared certificate comparison cohorts, harder/held-out
cases, anytime certification and multi-node commissioning are separate work.
