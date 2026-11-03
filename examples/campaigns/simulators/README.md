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
with the patched sibling repositories. From experiment-craft:

```bash
python examples/campaigns/simulators/run.py --cpu-slots 8 --tasks 8 --output /tmp/x1-smoke
python examples/campaigns/simulators/run.py --preset study --cpu-slots 8 --tasks 8 --extend --output /tmp/x1-study
```

Use `--sources /absolute/sibling-parent` and the documented binary overrides
for other locations. A smaller functional check can use `--cpu-slots 2 --tasks 2`;
that is not an eight-CPU measurement. Only 1, 2, 4 or 8 CPU slots are supported.
Each command has a fixed 1,800-second wall limit; a large study that exhausts it
stays failed rather than silently resetting a deadline.

The script creates a new node, compiles a campaign manifest, initializes the
existing campaign store and calls `drive`. It retains all statuses and writes
the normal campaign report before judging success. It observes a completed
campaign again and requires the terminal state to remain unchanged. This
checks repeat-safe observation, not reboot or logout persistence.

## Follow the evidence

`source/campaign.json` contains the concrete plan. Each staged `source.json`
hashes trusted tutorial sources and used binaries, records repository heads,
and checks installed package versions at launch. Source files and packages
must stay unchanged throughout execution. Static command inputs are snapshotted
by the existing runtime; imported host dependencies are not a hermetic snapshot.

The campaign retains native jobs and their `summary` and `evidence` outputs.
A dependent `numerical-and-work-checks` command consumes **sealed summaries**,
checks every application passed its declared tests, and compares C1 fitted
rates, losses, actual calls and paths/events across layouts. It refuses an
oversubscribed layout or mismatched work. See [check.py](check.py).

The layout wall time includes subprocess startup, imports, every search, final
SSA rechecks and output writing. Per-fit preparation/search/validation timing
remains in the nested summaries. The top-level `summary.json` records campaign
setup and total elapsed time. `cold_build_seconds` is explicitly null: time
installation/build separately before making a complete deployment-cost claim.
Native runner overhead and scientific work remain distinguishable.

The campaign's `max_reserved_slot_seconds` is an admission reservation derived
from declared limits. It is not measured CPU consumption. Report the measured
wall times descriptively; a single smoke run is not a scaling benchmark and
fixed layout order can include warm-cache effects. For a study, predeclare
repetitions, alternate order in separate manifests, retain failures, and compare
quality as well as complete cost.

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
