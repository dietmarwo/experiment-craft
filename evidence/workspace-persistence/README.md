# Workspace persistence

28 October 2026 (UTC). These runs reproduce the ways a campaign workspace can
reopen at an earlier state. They were run at experiment-craft `4cd7b31` (before
the fix) and `3035cfd` (with it). Native pins are unchanged. The environment
is one Linux machine with one-slot local foreground nodes, Python 3.12.3 and
SQLite 3.45.1, using the runner built from the locked commits.

[`reproduce.py`](reproduce.py) runs real campaigns of short sequential command
steps. In each scenario, a separate SQLite connection records the highest
committed event seq, and the script compares it with what a reopened workspace
or copy holds. [`before-fix/`](before-fix/) and [`after-fix/`](after-fix/) hold
its printed output and `results.json`.

| Scenario | Result |
| --- | --- |
| SIGKILL of a CLI client, 12 trials | No committed decision lost; the main file alone held decision 1 in all 12; no step ran twice. In one trial before the fix the kill fell between a dispatch intent and its launch, and `continue` left that step uncertain rather than launching it again |
| SIGKILL of an advancing dashboard while CLI clients read and pause, 6 trials | No committed decision lost |
| Copy while a client advances | Main file alone: decision 1 of 12 committed; main, WAL and SHM: 12 |
| `TRUNCATE` checkpoint while a client advances, then a main-file copy | Busy 0; the copy held decision 12 of the final 17 |
| Checkpoint with another connection holding an older snapshot | `PASSIVE` busy 0 with 0 of 9 frames copied; `TRUNCATE` busy 1; the copy missed the pause |
| Every client closed | WAL removed; a main-file copy was complete |
| Kill, then one `status` | The WAL stayed after the kill and was folded in when `status` closed |
| Main file and WAL copied one after the other while a client advanced, 30 tries | All complete |
| Backup and restore | Complete, and the restored workspace is paused |
| Continue a copy without its WAL that missed launches | Before: `recovery_diverged` at the first launched step, no job repeated. After: `state_regressed` |
| Continue a copy without its WAL that missed a stop | Before: launched the 4 stopped steps. After: `state_regressed`, nothing launched |
| Continue an earlier copy of the whole directory, taken before a stop | Before and after: launched the 4 stopped steps; this copy is not detected |
| `workspace-check` and dashboard start with a copy without its WAL | After only: `database_behind_head` and `results_without_decision`; the dashboard does not start (`state_regressed`) |

`regression-tests-before-fix.txt` holds the new tests run against `4cd7b31`,
the tests for the first review's findings against `18939b8` and those for the
second review's against `5a0a939`; each fails there. `unit-tests.txt` (190
tests) and `integration-tests.txt` (79 live tests) are the suites at `3035cfd`,
and `environment.json` names the commits, interpreter, SQLite and runner hash.

The campaign that reported the problem kept its own databases; they were not
available for these runs. A run on one machine does not establish power-loss or
filesystem behavior. See the
[implementation log](../../implementation-log.md#workspace-persistence) and
[copying and checking a workspace](../../docs/operations.md#copy-and-check-a-workspace).
