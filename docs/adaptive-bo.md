# Experimental adaptive BO campaigns

The optional BO-craft integration extends local campaigns with dynamic accepted trials, multiple evaluation jobs and one proposal job in flight. Existing static formats remain unchanged. The new manifest is experiment.adaptive/0.1, with a separate state/status schema. A saved plan adds its deterministic plan_id; it is an internal resolved plan, not a user manifest to edit in place.

BO-craft owns numerical proposals. This module owns trial/seed decisions and scientific reservations. optimization-jobs remains the execution/capacity authority. Install BO-craft from the paired source delivery; no new hosted service or MCP tool is required.

Start with BO-craft/examples/adaptive_campaign.py and its generated manifest. The local CLI commands are adaptive-init, adaptive-continue, adaptive-status and adaptive-stop. Proposal computation runs as a trusted command with a slot/wall reservation. Evaluation is either a trusted command producing observation.json from trial.json or the existing one-point fcmaes.evaluate/1 scalar simulation bridge. Native evaluation currently supports one unconstrained objective, with one evaluation thread and a distinct run_seed per trial.

Each dispatch intent, request key, validated resolution, accepted candidate and ingestion receipt is transactional. A lost launch answer is observed under the saved native handle. An intent that committed but never launched remains unknown; absence of a native job does not authorize automatic resubmission. Unknown work retains reservations and blocks new scientific decisions. A terminal result is checked against its resolved request and output/native digests before ingestion.

The workspace binds node/runner/worker identity, Python executable, BO-craft source files and relevant package versions. Inputs are retained as immutable snapshots. Changes require a deliberate new campaign or the original environment. Independent trial seeds are deterministic within a scientific plan but workspace request keys differ, so separate workspaces do not share native jobs.

Scientific evaluation count, job count and declared slot-seconds are separate. Accepted candidates count against the evaluation allowance; failures/cancellations still consumed work. Reservations are not a second host CPU ledger. Per-job process limits enforce work while the client is absent; a campaign deadline is client policy, not a new backend group limit.

Pause-dispatch, backup, restore, unpause-dispatch and workspace-check reuse the existing maintenance API. Adaptive audit checks resolved-plan identity, input/output digests and SQLite integrity. Restore stays paused; unpause re-observes native handles and terminal receipts. Keep one writable copy of a recovered workspace.

The new status is an observation-only CLI artifact; the existing browser dashboard remains a static-campaign surface. Do not point it at an adaptive workspace as though an adaptive UI were implemented. Live metric/pruning streams, automatic external-study synchronization, production fleet scheduling and real reboot acceptance are not claimed.

Run tests/integration_adaptive.py with real runner, Python, BO source and a new output directory. The test exercises a lost submission answer, six unique evaluations, repeated continuation, paused backup/restore and a never-launched uncertain intent. Existing integration_campaign.py retains static campaign acceptance.
