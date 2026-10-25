# Changelog

All notable changes to this repository are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Nothing has been
tagged or published yet; the package version is 0.4.0.

## [Unreleased]

### Added

- A loopback browser dashboard for explicitly attached local campaigns, with
  start/continue, dispatch pause, verified unpause, native stop/collection,
  step/error inspection and per-node progress charts. Pause/stop remain
  available while advancement is running. No automatic startup continuation.
- Bounded persisted observation history, JSON download, disabled planned-node
  views and separate `experiment.dashboard/0.1` and
  `experiment.dashboard.history/0.1` schemas. Counts and declared slots do not
  imply solver convergence, host reachability or measured utilization.
- A real ten-step dashboard example and HTTP/history/control regressions.

- The Python package `experiment_craft` with the `experiment-craft` command
  for local campaigns over `optimization-run`: strict
  `experiment.campaign/0.1` manifests with deterministic matrix and
  dependency expansion, retained input snapshots, validation of static steps
  at initialization, SQLite decisions and events, request keys of their own
  for each workspace, dependencies, declared job and slot-second budgets, a
  campaign deadline, stop and continuation without replay, and offline
  JSON, CSV and Markdown reports.
- JSON Schemas for the campaign manifest, the resolved plan, the status and
  the report.
- Predeclared scientific comparisons over a campaign: an
  `experiment.comparison/0.1` protocol that `declare-comparison` seals before
  the first dispatch, and offline `compare` reports
  (`experiment.comparison.binding/0.1`, `experiment.comparison.report/0.1`).
  Groups pool only compatible profiles, models, inputs, tolerances and
  resources, with explicit seed or start designs, work or time caps,
  complete and available feasible cohorts, targets over all planned runs,
  known and unknown work, and paired differences only when declared.
- Local operations: `pause-dispatch`, `unpause-dispatch` after checking every
  native handle, consistent campaign `backup` archives
  (`experiment.campaign.backup/0.1`) and `restore` into a new, paused
  workspace, with the maintenance record `experiment.campaign.maintenance/0.1`.
- A node inventory (`experiment.deployment/0.1`) with one local test node as
  the default and six disabled planned SSH workers, `deployment-check`,
  `deployment-export` of native CLI argument arrays
  (`experiment.deployment.plan/0.1`) and `init`/`run --deployment`.
- Operating, deployment and January commissioning guides.
- A seven-job campaign example, a 17-job comparison example and a recovery
  rehearsal with all three native workers, unit tests and a live suite
  against the real runner and workers, run in CI.
- [AGENTS.md](AGENTS.md) for coding agents working in this repository.

### Changed

- `baseline-lock.json` names the current mains of the runner and the three
  workers, which add README references to experiment-craft; the workers'
  optimization-jobs pin is unchanged.
- The baseline documents record that the backend gate (actual user manager,
  logout, reboot and allocation evidence) is still open.
