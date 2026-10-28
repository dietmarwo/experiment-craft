# Installed upgrade and rollback rehearsal, 0.3.0 to 0.4.0

28 October 2026 (UTC). Reviewed 0.3.0 (the P7 merge `1d17218`) and the 0.4.0
candidate (`a11de4e`) were built as wheels and installed in separate Python
3.12.3 venvs, with the pinned requirements and SQLite 3.45.1. Each ran from
outside any checkout, against the runner built from the locked commits
(`optimization-run` SHA-256 `13d5a019…ffef`) and a one-slot local foreground
node. The two versions never ran at the same time. Native pins are unchanged.

[`rehearse_upgrade.py`](rehearse_upgrade.py) follows
[upgrade and rollback](../../docs/operations.md#upgrade-and-rollback) with a
campaign of six sequential command steps. Every call, with its version, argv,
exit code and output, is in [`calls.json`](calls.json). The checks are in
[`summary.json`](summary.json), and [`wheels.json`](wheels.json) has the wheel
hashes. Each wheel's 23 or 37 package files equal its source commit's bytes,
and the 0.4.0 wheel holds 18 schemas.

| Step | Versions | Result |
| --- | --- | --- |
| Two steps, then pause while the third runs | 0.3.0 | The driver stops with `dispatch_paused` after the step in flight, which completes |
| Backup and offline report | 0.3.0 | Archive written |
| Status, report and `workspace-check` before unpausing | 0.4.0 | Opens paused; the report equals 0.3.0's byte for byte; no finding and no `head.json` yet |
| Unpause and one step | 0.4.0 | `head.json` records the last decision; no native journal of earlier jobs changed |
| Roll back: pause, then status, events and report | 0.3.0 | Reads the workspace with `head.json`; no native journal changes |
| Unpause, one step, pause | 0.3.0 | Decisions leave `head.json` at decision 12 while the database reaches 16 |
| Return: check, unpause and finish | 0.4.0 | The older record is accepted; the campaign completes, each step ran once, six jobs in all, and `head.json` is current again |
| Restore the 0.3.0 archive | 0.4.0 | Restored paused with its backup id; unpausing it is refused with `recovery_diverged`, because the original launched steps after the backup, and nothing is launched |
| Dashboard start and SIGTERM | 0.4.0 | Attaches the workspace and stops with no checkpoint error |

0.3.0 enforces the dispatch pause, so unlike the 0.2.0 rollback in the
[P7 rehearsal](../p7/README.md), the older client may also decide here. This is
a local package rehearsal, not a native-service upgrade or a power-loss test.
