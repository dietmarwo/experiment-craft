# Experimental adaptive BO campaigns

The optional BO-craft integration extends local campaigns with dynamic accepted trials, multiple evaluation jobs and one proposal job in flight. Existing static formats remain unchanged. The new manifest is experiment.adaptive/0.1, with a separate state/status schema. A saved plan adds its deterministic plan_id; it is an internal resolved plan, not a user manifest to edit in place.

BO-craft owns numerical proposals. This module owns trial/seed decisions and scientific reservations. optimization-jobs remains the execution/capacity authority. No new hosted service or MCP tool is required.

[BO-craft](https://github.com/dietmarwo/BO-craft) is not published to a package index. Install it into the environment of the `python` the manifest names, at the revision CI tests (`BO_CRAFT_REVISION` in `.github/workflows/ci.yml`, currently `9382519`):

```sh
python -m pip install "bo-craft[botorch,optuna] @ git+https://github.com/dietmarwo/BO-craft@93825196b3006531cc07a80a7cea7814fdc0985c"
```

The `random` backend needs no extra. Without BO-craft, every adaptive command fails with the error code `missing_dependency`.

Start with BO-craft/examples/adaptive_campaign.py and its generated manifest. The local CLI commands are adaptive-init, adaptive-continue, adaptive-status and adaptive-stop. Proposal computation runs as a trusted command with a slot/wall reservation. Evaluation is either a trusted command producing observation.json from trial.json or the existing one-point fcmaes.evaluate/1 scalar simulation bridge. Native evaluation currently supports one unconstrained objective, with one evaluation thread and a distinct run_seed per trial.

The manifest is checked before any job:
- its schema;
- the problem and the `config` against BO-craft's own request schema, so every setting the pinned BO-craft accepts is accepted here and nothing else;
- for the native bridge: the profile `fcmaes.evaluate/1`, one unconstrained objective, a noise mode other than `known` (native evaluations carry no variances), and no replicates of an unseeded evaluation.

## The campaign answer

When the optimization budget is spent and no job is active, the campaign answers in up to three steps. The answer is recorded in the state and written to `answer.json` in the workspace (`experiment.adaptive.answer/0.1`). `adaptive-status` reports its step as `answer`, and the campaign is `completed` only when the answer is done.

1. **Empirical:** BO-craft's empirical recommendation, the best observed point or the observed Pareto set, computed in the client.
2. **Model:** a `recommend --kind model` command job, which picks among the observed points by the fitted GP's posterior. It runs by default when the backend is `botorch`; set `answer.model` to choose explicitly. It reserves a job and the proposal job's slot-seconds, like a proposal. A failed job is recorded as an error, and the answer continues with the empirical choice.
3. **Validation:** `answer.validation_replicates: k` reserves k of the evaluations. After the optimization's `evaluations − k` trials, the campaign evaluates the chosen point k more times with fresh trial seeds. The chosen point is the empirical choice, or the model's with `answer.validate: model`. BO-craft's confirmation found the model's choice not reliably better (gate G1 in its [benchmarks of 17 November](https://github.com/dietmarwo/BO-craft/blob/main/docs/evidence/plan-2026-11-17/README.md)). It reports their mean and standard error. These observations are kept apart from the optimization's and do not change the recommendation. This is single-objective only.

The empirical and model answers are records of the observed history; only the validation replicates are fresh evidence. `answer.json` is derived from the state; after a restore, the next `adaptive-continue` writes it again.

## Declared replicates

With `config.replication: incumbent` (BO-craft's BoTorch backend), a proposal may name an observed point in `replicate_of`. The campaign accepts a repeated point only when it is declared that way, refers to a completed observation with the same coordinates, and replication is enabled. The replicate is a new trial with its own seed. Undeclared repeats and repeats of pending points are still `duplicate_candidate`.

## Proposal look-ahead

Without `proposal_lookahead`, the original rule applies: whenever no accepted candidate waits and no proposal job is active, the campaign proposes `min(remaining, concurrent)` candidates. With `proposal_lookahead: L`, it proposes `min(remaining, free slots + L)`. `0` proposes exactly for the free slots, so every candidate sees the latest observations, but a slot waits for each proposal job. Larger values hide the proposal job's start-up behind running evaluations. In BO-craft's simulation of 17 November (noisy Hartmann-6, 40 evaluations, 4 slots, lognormal evaluation times with median 10 s), `proposal_lookahead: 0` reached 0.42 [0.28, 0.64] times the original rule's regret over 30 fresh seeds, and took 1.23 times as long (gate G5 in its [look-ahead protocol](https://github.com/dietmarwo/BO-craft/blob/main/docs/evidence/plan-2026-11-17/async.md)). Use 0 when evaluations are scarcer than wall time.

## Pruning

`pruning: {"policy": "median"}` stops running evaluations whose learning curve is worse than the median of the completed trials' curves at the same step (Optuna's median rule, as `bo_craft.pruning.median_decision`). It needs:
- a command evaluator: a native `fcmaes.evaluate/1` evaluation has no curve, so the manifest is refused with `unsupported_profile`;
- one unconstrained objective (`invalid_manifest` otherwise);
- a runner whose command jobs accept a progress file: optimization-jobs 0.5.0 or later. `adaptive-init` checks this before any job and fails with `unsupported_runtime` on an older runner.

**Evaluator contract.** The evaluator appends one JSON object per line to `progress.jsonl` in its working directory: `{"step": k, "value": v}`, with an integer step ≥ 0 and a finite value of the objective, in the objective's own direction. Lines of another shape are ignored, and a later line for the same step replaces an earlier one. Write and flush each complete line; the runner reads only lines that end with a newline. The final value still goes to `observation.json` as before. `progress_max_bytes` (default 64 KiB, at most 16 MiB) bounds the file; lines past it are not read.

**Settings:**
- `startup_trials` (default 5): completed trials with curves before any pruning;
- `warmup_steps` (default 1): no pruning before this step;
- `check_seconds` (default 1): how often `adaptive-continue` reads the curves of running evaluations.

**What happens:**
1. The decision is recorded in the state first (`prune_requested`, event `adaptive_prune`), then the runtime is asked to cancel the job. A restart repeats only the cancel.
2. When the runtime reports the job cancelled, the trial becomes a `pruned` observation with its curve in `intermediate` and the step and median in its provenance. It has no values. A job that finished before the cancel reached it keeps its own outcome.
3. Completed evaluations keep their curve in `intermediate` too, and their trial keeps it for later decisions. Validation replicates are never pruned.

A pruned trial counts against the evaluation budget, like a failed one. BO-craft's BoTorch backend drops pruned trials unless `config.pruned` is `last`, which trains on each pruned trial's last reported value; without it, BoTorch proposes again where it just pruned. Optuna's TPE ranks pruned trials by their last value; the setting is BoTorch-only.

**Measured effect: none shown.** BO-craft's confirmation of 17 November simulated Hartmann-6 learning curves at equal total evaluation time (400 time units, 30 fresh seeds, gates G7a/G7b in its [evidence](https://github.com/dietmarwo/BO-craft/blob/main/docs/evidence/plan-2026-11-17/README.md)). Pruning with `pruned: last` ran 54 trials instead of 40 on average. The time to reach a regret of 0.1 had a paired ratio of 0.98 [0.91, 1.05], and the final regret 0.76 [0.43, 1.29]; neither gate passed. Pruning therefore stays opt-in; use it when evaluations are long and early values rank them reliably.

Each dispatch intent, request key, validated resolution, accepted candidate and ingestion receipt is transactional. A lost launch answer is observed under the saved native handle. An intent that committed but never launched remains unknown; absence of a native job does not authorize automatic resubmission. Unknown work retains reservations and blocks new scientific decisions. A terminal result is checked against its resolved request and output/native digests before ingestion.

The workspace binds node/runner/worker identity, Python executable, BO-craft source files and relevant package versions. Inputs are retained as immutable snapshots. Changes require a deliberate new campaign or the original environment. Independent trial seeds are deterministic within a scientific plan but workspace request keys differ, so separate workspaces do not share native jobs.

Scientific evaluation count, job count and declared slot-seconds are separate. Accepted candidates count against the evaluation allowance; failures/cancellations still consumed work. Reservations are not a second host CPU ledger. Per-job process limits enforce work while the client is absent; a campaign deadline is client policy, not a new backend group limit.

Pause-dispatch, backup, restore, unpause-dispatch and workspace-check reuse the existing maintenance API. Adaptive audit checks resolved-plan identity, input/output digests and SQLite integrity. Restore stays paused; unpause re-observes native handles and terminal receipts. Keep one writable copy of a recovered workspace.

The new status is an observation-only CLI artifact; the existing browser dashboard remains a static-campaign surface. Do not point it at an adaptive workspace as though an adaptive UI were implemented. Live metric dashboards, automatic external-study synchronization, production fleet scheduling and real reboot acceptance are not claimed. Pruning reads progress files on local nodes; `fleet` (SSH) placements have no progress command yet.

Stop is recorded once, and the runtime is asked once to cancel each active job; a cancel that finds no native job is asked again on the next pass, since a lost launch answer can still produce it. `adaptive-continue` checks the bound files and package versions when it starts and before each dispatch.

Run tests/integration_adaptive.py with the real runner, the Python that has BO-craft installed, a BO-craft checkout (`--bo-root`, for its example evaluator) and a new output directory. CI runs it with the baseline runner. The test exercises:
- a lost submission answer, six unique evaluations and repeated continuation;
- paused backup and restore, and a never-launched uncertain intent;
- a campaign with a look-ahead and two validation replicates;
- when the given Python has BoTorch, a campaign whose answer includes the model recommendation job;
- a pruning campaign whose evaluator writes a learning curve: at least one trial is pruned, its job is cancelled in the runtime's records, and every completed trial keeps its full curve. With a runner without progress files, this step expects `unsupported_runtime` instead. CI's environment has no Torch, so CI runs the rest. Existing integration_campaign.py retains static campaign acceptance.
