# Changelog

All notable changes to this repository are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Nothing has been
tagged or published yet; the package version is 0.1.0.

## [Unreleased]

### Added

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

- `baseline-lock.json` names the current mains of the runner and the three
  workers, which add README references to experiment-craft; the workers'
  optimization-jobs pin is unchanged.
- The baseline documents record that the backend gate (actual user manager,
  logout, reboot and allocation evidence) is still open.
