# Experimental adaptive BO campaigns

The optional BO-craft integration extends local campaigns with dynamic accepted trials, multiple evaluation jobs and one proposal job in flight. Existing static formats remain unchanged. The new manifest is experiment.adaptive/0.1, with a separate state/status schema. A saved plan adds its deterministic plan_id; it is an internal resolved plan, not a user manifest to edit in place.

BO-craft owns numerical proposals. This module owns trial/seed decisions and scientific reservations. optimization-jobs remains the execution/capacity authority. No new hosted service or MCP tool is required.

[BO-craft](https://github.com/dietmarwo/BO-craft) is not published to a package index. Install it into the environment of the `python` the manifest names, at the revision CI tests (`BO_CRAFT_REVISION` in `.github/workflows/ci.yml`, currently `a480918`):

```sh
python -m pip install "bo-craft[botorch,optuna] @ git+https://github.com/dietmarwo/BO-craft@a4809189e2d5bbc185ab13cf532d1f6414605fde"
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

Each dispatch intent, request key, validated resolution, accepted candidate and ingestion receipt is transactional. A lost launch answer is observed under the saved native handle. An intent that committed but never launched remains unknown; absence of a native job does not authorize automatic resubmission. Unknown work retains reservations and blocks new scientific decisions. A terminal result is checked against its resolved request and output/native digests before ingestion.

The workspace binds node/runner/worker identity, Python executable, BO-craft source files and relevant package versions. Inputs are retained as immutable snapshots. Changes require a deliberate new campaign or the original environment. Independent trial seeds are deterministic within a scientific plan but workspace request keys differ, so separate workspaces do not share native jobs.

Scientific evaluation count, job count and declared slot-seconds are separate. Accepted candidates count against the evaluation allowance; failures/cancellations still consumed work. Reservations are not a second host CPU ledger. Per-job process limits enforce work while the client is absent; a campaign deadline is client policy, not a new backend group limit.

Pause-dispatch, backup, restore, unpause-dispatch and workspace-check reuse the existing maintenance API. Adaptive audit checks resolved-plan identity, input/output digests and SQLite integrity. Restore stays paused; unpause re-observes native handles and terminal receipts. Keep one writable copy of a recovered workspace.

The new status is an observation-only CLI artifact; the existing browser dashboard remains a static-campaign surface. Do not point it at an adaptive workspace as though an adaptive UI were implemented. Live metric/pruning streams, automatic external-study synchronization, production fleet scheduling and real reboot acceptance are not claimed.

Stop is recorded once, and the runtime is asked once to cancel each active job; a cancel that finds no native job is asked again on the next pass, since a lost launch answer can still produce it. `adaptive-continue` checks the bound files and package versions when it starts and before each dispatch.

Run tests/integration_adaptive.py with the real runner, the Python that has BO-craft installed, a BO-craft checkout (`--bo-root`, for its example evaluator) and a new output directory. CI runs it with the baseline runner. The test exercises:
- a lost submission answer, six unique evaluations and repeated continuation;
- paused backup and restore, and a never-launched uncertain intent;
- a campaign with a look-ahead and two validation replicates;
- when the given Python has BoTorch, a campaign whose answer includes the model recommendation job. CI's environment has no Torch, so CI runs the rest. Existing integration_campaign.py retains static campaign acceptance.
