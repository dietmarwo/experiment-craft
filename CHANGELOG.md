# Changelog

All notable changes to this repository are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Nothing has been
tagged or published yet; the package version is 0.3.0.

## [Unreleased]

### Added

- Local operations: dispatch pause and checked reconciliation before unpausing,
  SQLite campaign snapshots and checked paused restores, a versioned inventory
  with one local default and six disabled planned workers, native CLI plan
  export, operating/January guides and a complete local recovery rehearsal.

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
- A seven-job campaign example and a 17-job comparison example with all three
  native workers, unit tests and a live suite against the real runner and
  workers, run in CI.
- [AGENTS.md](AGENTS.md) for coding agents working in this repository.

### Changed

- `baseline-lock.json` names the current mains of the runner and the three
  workers, which add README references to experiment-craft; the workers'
  optimization-jobs pin is unchanged.
- The baseline documents record that the backend gate (actual user manager,
  logout, reboot and allocation evidence) is still open.
