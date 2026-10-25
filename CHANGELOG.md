# Changelog

All notable changes to this repository are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Nothing has been
tagged or published yet; the package version is 0.2.0.

## [Unreleased]

### Added

- Predeclared `experiment.comparison/0.1` protocols, an immutable transactional
  binding and additive report schemas; `declare-comparison` and offline `compare`.
- Scientific profile/input/resource compatibility, explicit seed/start designs,
  work/time caps, complete/available feasible cohorts, target denominators,
  accounting with unknown runs and raw paired differences only when declared.
- A 17-job representative scientific example using all three native workers,
  sealed input preparation, numerical checks and deliberate output/timeout
  failures; comparison unit and real-runtime regression tests.

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
- A seven-job example with all three native workers, unit tests and a live
  suite against the real runner and workers, run in CI.
- [AGENTS.md](AGENTS.md) for coding agents working in this repository.

### Changed

- The unpublished Python package version is 0.2.0. The four P5 schemas and all
  native source commits, SDK pins and mathematical behavior are unchanged.
- The plan is 2.7: local P6 is implemented, next independent work is P7
  installation/recovery preparation; the actual RT-07/RT-08 backend gates stay open.

- `baseline-lock.json` names the current mains of the runner and the three
  workers, which add README references to experiment-craft; the workers'
  optimization-jobs pin is unchanged.
- The baseline documents record that the backend gate (actual user manager,
  logout, reboot and allocation evidence) is still open.
