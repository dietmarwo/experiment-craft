# X1 — Measure complete CRN and CFD optimization campaigns

Run simulator lessons through the existing command-job and campaign interfaces,
then compare complete CRN fits at a fixed CPU allowance. The example preserves
native handles, sealed summaries and detailed evidence; it does not add a new
execution lifecycle or modify the pinned three-worker baseline.

## Scientific question and layout

A faster SSA call need not make an entire optimization faster. Preparation,
Python/process startup, candidate search and final validation all contribute.
For an eight-CPU allowance, run the same independent C1 fits under:

| Layout | Independent fit processes | Simulator threads per process | Maximum concurrent allowance |
|---|---:|---:|---:|
| 1×8 | 1 | 8 | 8 |
| 2×4 | 2 | 4 | 8 |
| 8×1 | 8 | 1 | 8 |

Each layout completes eight tasks by default. Task `i` offsets the optimizer
seeds by `100*i`; the same tasks and simulation seeds are used in every layout.
Each task includes both C1 models and both fresh/reusable routes, including
held-out validation. All declared layout arms run sequentially at campaign
level. Parallel work occurs only inside the admitted command. BLAS/OpenMP
threads are fixed to one to avoid accidental nested parallelism.

The CFD F1 comparison runs as a separate serial step. Its prescribed transport
has no inner threading speedup to measure; do not interpret an idle allowance
as eight-way CFD work. `--extend` adds C2 sensitivity fitting and F3 coupled-flow
validation, also as explicit serial steps.

## Set up and run

Follow the shared [simulator setup](https://github.com/dietmarwo/optimization-jobs/blob/main/tutorials/simulators/README.md)
with sibling checkouts of the eight repositories. From experiment-craft:

```bash
python examples/campaigns/simulators/run.py --cpu-slots 8 --tasks 8 --output /tmp/x1-smoke
python examples/campaigns/simulators/run.py --preset study --cpu-slots 8 --tasks 8 --extend --output /tmp/x1-study
```

Use `--sources /absolute/sibling-parent` and the documented binary overrides
for other locations. A smaller functional check can use `--cpu-slots 2 --tasks 2`;
that is not an eight-CPU measurement. Only 1, 2, 4 or 8 CPU slots are supported.
Each tutorial command has a fixed 1,800-second wall limit and each C1 task inside
a layout 300 seconds; the dependent check step has 30 seconds. A large study
that exhausts a limit stays failed rather than silently resetting a deadline.

The summary records the node's usable CPUs (`usable_cpus`, from `node doctor`)
and its warnings. When `--cpu-slots` exceeds the usable CPUs, the runtime admits
the layouts but they share fewer cores; `timing_comparison_valid` is then false
and the layout wall times must not be compared. Equal work and results are still
checked.

The script creates a new node, compiles a campaign manifest, initializes the
existing campaign store and calls `drive`. It retains all statuses and writes
the normal campaign report before judging success. It then calls `drive` on the
completed campaign once more and requires the same terminal state and the same
number of native jobs on the node: a terminal campaign submits nothing. This is
a small idempotence check, not a test of reboot or logout persistence.

## Follow the evidence

`source/campaign.json` contains the concrete plan. Each staged `source.json`
hashes trusted tutorial sources and used binaries, records repository heads
and whether each checkout differs from its head, and checks installed package
versions at launch. Source files and packages
must stay unchanged throughout execution. Static command inputs are snapshotted
by the existing runtime; imported host dependencies are not a hermetic snapshot.

The campaign retains native jobs and their `summary` and `evidence` outputs.
A dependent `numerical-and-work-checks` command consumes **sealed summaries**,
checks every application passed its declared tests, and compares C1 fitted
rates, losses, actual calls and search and validation paths/events across
layouts. It refuses a layout whose tasks did not run with its inner thread
count, an oversubscribed layout or mismatched work, and names both layouts of
a mismatch. See [check.py](check.py) and its tests in
[tests/test_simulator_campaign.py](../../../tests/test_simulator_campaign.py).

The layout wall time includes subprocess startup, imports, every search, final
SSA rechecks and output writing. Per-fit preparation/search/validation timing
remains in the nested summaries. The top-level `summary.json` records campaign
setup and total elapsed time. `cold_build_seconds` is explicitly null: time
installation/build separately before making a complete deployment-cost claim.
Native runner overhead and scientific work remain distinguishable.

The campaign's `max_reserved_slot_seconds` is an admission reservation derived
from declared limits. It is not measured CPU consumption. Report the measured
wall times descriptively; a single smoke run is not a scaling benchmark. The
compiler orders steps by id, so the layouts always run 1x8, 2x4, 8x1 and the
later ones can benefit from warm caches. For a study, predeclare repetitions,
write separate manifests with the layouts in alternating order, retain
failures, and compare quality as well as complete cost.

## Prompt and follow-up

> Run the CRN and CFD lessons as local campaigns. Preserve input/source
> identities and native artifacts, compare complete C1 fits under one fixed CPU
> budget, and verify equal work and final quality before interpreting timings.
> Report missing cold setup cost and unsupported parallel layouts explicitly.

Use the normal [campaign CLI](../../../docs/campaigns.md) to observe the existing
workspace and inspect its reports. Keep the entire workspace, including the
node and SQLite state. Never start a new campaign as an automatic repair for
uncertain native work. These are descriptive application reports; no formal
cross-profile retry/GP/MODE/QD cohort is inferred. Fleet placement and actual
logout/reboot survival require separate backend commissioning.
