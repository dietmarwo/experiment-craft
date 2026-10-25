# Scientific comparisons

The P6 client adds a predeclared comparison protocol and descriptive reports on
top of [local campaigns](campaigns.md). It never launches a job while declaring
or reporting. Execution, capacity, file transfer and recovery still belong to
optimization-jobs. The [backend gate](backend-gate.md) is unchanged.

## Run the representative suites

```bash
python3 -m pip install -e .
python3 examples/campaigns/scientific/run.py --bin-dir .baseline/bin --output /absolute/new/scientific-demo
```

The example explicitly initializes a private one-slot foreground node. Its
17 real jobs include:

| Suite | Protocol and observations |
|---|---|
| fcmaes sphere | Two BiteOpt populations, three common seeds, a hard 100-evaluation cap, objective and endpoint target attainment, explicitly paired differences |
| LP/IP binary choice | Presolve on/off, two deterministic timing repeats each, the same 30-second cap, objective, native bound/gap and integrality violation; the known answer is checked separately |
| SQP simplex | Three distinct starts, a common 100-iteration cap, objective, primal residual and native KKT stationarity; no global-optimality claim |
| Numerical command | Checks the known LP/IP and SQP answers from verified native manifests and seals its checks artifact |
| Failure probes | A missing required output and a native timeout; both remain in all campaign totals |
| Preparation | Seals the shared LP model; explicitly excluded from solver comparisons, still visible in the report |

The example succeeds when **15 jobs succeed and the two deliberate probes
fail**. Its campaign status is therefore `incomplete`, not `completed`.
Three seeds and small models check the pipeline; they do not establish a
performance ranking or a confirmation sample. Repeated reporting changes no
native journal and creates no new execution.

Outputs are `comparison/comparison.json`, `observations.csv` and
`comparison.md`, plus the original P5 report under `report/`. The source
manifest and protocol are retained under `source/`. The example's comparison
reports keep every raw native result, including the details of bounds,
integrality, residuals, KKT, claims, evidence and work accounting.

## Declare before executing

For your own campaign:

```bash
experiment-craft dry-run campaign.json > expanded-plan.json
experiment-craft init campaign.json --workspace /absolute/new/campaign --runner /absolute/optimization-run --node-root /absolute/node --mode foreground
experiment-craft declare-comparison comparison.json --workspace /absolute/new/campaign
experiment-craft continue --workspace /absolute/new/campaign
experiment-craft compare --workspace /absolute/new/campaign --destination /absolute/reports
```

Use `plan_id` from the dry-run in the protocol. Initialization and declaration
are separate operations: `init` still performs the existing runtime validation,
and declaration makes no runtime call. The campaign deadline starts at the end
of initialization, including time spent declaring or waiting before `continue`.
Choose a sufficient deadline rather than expecting declaration to reset it.

This example protocol assumes templates `a` and `b` are single-retry BiteOpt
jobs on the same model, with a hard cap of 100 evaluations and seed sweeps.
Replace the plan ID with the actual 64-character hash:

```json
{
  "schema_version": "experiment.comparison/0.1",
  "name": "BiteOpt population comparison",
  "plan_id": "REPLACE_WITH_THE_DRY_RUN_PLAN_ID",
  "groups": [{
    "id": "sphere",
    "description": "Same sphere and limits; two populations over common seeds",
    "kind": "optimization",
    "arms": [
      {"id": "default", "templates": ["a"]},
      {"id": "larger", "templates": ["b"]}
    ],
    "vary": ["/payload/optimizer"],
    "replication": {"kind": "seed", "pointer": "/payload/seed"},
    "design": "paired",
    "budget": {
      "kind": "fixed_work",
      "pointer": "/payload/evaluations_per_retry",
      "counter": "evaluations",
      "limit": 100
    },
    "metrics": [{
      "id": "objective",
      "pointer": "/outcome/objective",
      "unit": "sum of squared coordinates",
      "direction": "minimize",
      "target": 0.01
    }]
  }],
  "exclude": []
}
```

Every template must be in exactly one arm or in `exclude` with a reason.
Exclusions remain visible with their statuses and full raw native results;
they are not silently dropped from the campaign totals. An arm is one fixed
configuration with its declared seeds, starts or deterministic repeats.

Declaration takes the advancement lock and atomically stores its protocol,
resolved units, campaign/plan identity, content hashes and audit event in
SQLite. The binding ID is also recorded in the campaign state and in the event,
and reports refuse a binding that differs from both. It requires no issued/reserved execution and all steps still pending.
A certainly unsent, refunded attempt does not count as executed work. A stop,
failed preparation or possibly issued attempt prevents a new declaration.
An identical declaration is idempotent, including after completion; a changed
protocol is refused. There is no post-hoc override. Use a deliberately new
campaign workspace to run a changed study. Keep the whole SQLite workspace,
including its WAL while active; the new declaration table shares that database.

## Compatibility and supported adapters

Groups do not pool different worker/profile identities, models, hashed inputs,
tolerances, resource configurations, acceptance policies or undeclared choices.
Only these variation and replication fields are supported initially:

| Native profile | Allowed solver variation | Seed/start field | Work cap and native counter |
|---|---|---|---|
| `fcmaes.retry/1` | `/payload/optimizer` | `/payload/seed` (`seed`) | `evaluations_per_retry` / `evaluations` |
| `lp-ip.solve/1` | `/payload/presolve` | `/payload/starts/0` (`start`), or deterministic repeats | `node_limit` / `nodes`, or `iteration_limit` / `simplex_iterations` |
| `sqp.solve/1` | `/payload/backend` | `/payload/starts/0` (`start`) | `max_iterations` / `iterations` |

Optimization observations must have exactly one native task: one fcmaes retry
or one LP/IP/SQP start. A start point is part of the problem instance, not a
random draw like a seed, so in every design all arms of a start-replicated group
use the same starts; arms started elsewhere are refused as incompatible. A fixed-work fcmaes study requires a hard evaluation
limit. Soft-limit algorithms may use the fixed-time protocol when all other
unvaried definitions agree; overshooting a soft cap is not relabelled equal work.
The current example compares two hard-cap BiteOpt configurations.

A fixed-time budget specifies `{"kind":"fixed_time","seconds":30}` and must
match each job's wall limit. A fixed-work budget must match the adapter's
request field and counter. Both are **common declared caps**: early termination
can consume less, other native stopping conditions still apply, and a timed
protocol is not proof of identical CPU consumption. Native counters and their
missingness remain visible. Campaign admission reservations are separate from
these per-job scientific limits. For a fixed-time group, each observation
records `within_time_limit`, `time_limit_reached` or `time_unknown` from the
native job state.

Input source locations are not scientific identity. Static digests and the
preparation dependency's code/input identity participate in compatibility.
Reporting additionally checks the actual staged input hashes from each saved
dispatch: identical preparation code alone does not establish identical model
bytes. A mismatch refuses the scientific comparison; the P5 report remains
available for inspection.

Commands support deterministic exit/output checks and native elapsed timing,
with fixed-time caps. They cannot declare optimization metrics or inferred
seeds. Their argv, environment, input hashes and executable identity must agree
within a group. Different scientific command programs need separate groups.
The client does not interpret arbitrary output files as objectives.

## Arithmetic, failures and pairing

Each metric declares a native task JSON pointer, unit and direction. Native
missing fields, null, booleans and nonnumeric values are not measurements and
are never turned into zero. A pointer that is absent in an outcome, or whose
name meets an array there, marks that observation's metric as missing. The
declared direction is not checked against the native objective sense. No new feasibility, bound, gap or stationarity
value is computed from an unsupported profile. The native manifest is retained
unchanged next to the derived summaries.

- **Complete feasible** summaries need a succeeded step, a completed single
  task, complete native accounting, `feasible: true` and a numeric metric. For a
  fixed-work protocol the known actual counter must also be within its cap.
- **Available feasible** summaries may include a checked point from a partial,
  failed or over-cap run. They are labelled separately and never silently enter
  the complete cohort.
- Every planned observation has its status, native state, error, termination,
  claim, evidence, work, lower bounds, time and command exit/output details.
  Failed, cancelled, blocked, budget-exhausted and uncertain jobs remain visible.
- Work totals show known runs and unknown runs for each counter. Zero known
  total with zero known runs means no measured total, not zero consumed work.
  Known lower bounds remain separate from complete accounting.
- Target counts show attained, known non-attained and unresolved observations
  against **all planned runs**. Unresolved includes observations ineligible for
  the complete feasible cohort; failures cannot improve the denominator.
- Means and medians are descriptive. Arithmetic, including paired
  differences and their summaries, uses exact decimal values represented as
  fractions; only the emitted numbers are rounded, and a result beyond the
  finite double range is refused with `comparison_overflow`. The raw values
  reconstruct every summary. No ranking, p-value, confidence interval or
  optimality certification is produced.

`design: "paired"` must be explicitly declared, with two or more arms and the
same unique seed/start schedule. Numerically equal start coordinates such as
`1` and `1.0` are the same sample. Each pair lists both steps and values; a
difference is computed as **left minus right** only when both are complete and
feasible. Other pairs stay listed as excluded. Common seeds encode the declared
design; they do not by themselves prove useful statistical correlation.
`unpaired` never invents matches. Deterministic repeats cannot request paired
quality inference; repeated deterministic solves measure timing reproducibility.

## Formats, errors and limits

Three additive schemas ship with the package:
[protocol](../experiment_craft/schemas/comparison-0.1.schema.json),
[binding](../experiment_craft/schemas/comparison-binding-0.1.schema.json) and
[report](../experiment_craft/schemas/comparison-report-0.1.schema.json).
The four published P5 formats are unchanged. The private binding is stored in
the `comparison_protocol` SQLite table; no source protocol file is needed to
regenerate a report. `compare` uses retained, digest-checked native bytes and a
single campaign state snapshot. It neither polls nor submits to a node and
does not change campaign decisions/events. While work is active it produces an
explicitly incomplete snapshot, not an assertion that all runs have finished.

Expected errors use the existing JSON/exit-2 contract. Relevant codes are
`invalid_protocol`, `protocol_plan_mismatch`, `unsupported_comparison`,
`incompatible_comparison`, `comparison_too_late`, `comparison_conflict`,
`comparison_not_declared`, `comparison_changed`, `campaign_busy`,
`comparison_overflow`, `invalid_destination` and the existing cached-byte `result_changed`/`invalid_json`.
Report exit 0 means the requested files were produced; inspect campaign statuses
and counts for scientific success. The Markdown report opens with the campaign
status. New output is created only after the full retained snapshot has passed
the integrity and compatibility checks. The three files are then published
together: the destination is a new directory, or a directory holding only an
earlier comparison report, which one atomic rename replaces as a whole. A
destination holding other files is refused with `invalid_destination`.

The protocol has the existing 4 MiB input bound, at most 128 groups, 8 arms and
8 metrics per group, over at most 4,096 expanded steps. The new layer supports
one predeclared protocol per campaign. It does not yet compare separate campaign
workspaces, support multi-objective/quality-diversity or multi-task profiles,
infer independent quality samples from timing repeats, compute trajectories or
time-to-target, or integrate external solver baselines. Larger confirmation
samples, long performance studies and home-fleet calibration remain future work.
CI/container times are not measurements of the home machines.
