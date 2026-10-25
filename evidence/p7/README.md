# P7 operations and planned deployment evidence

Recorded 25 October 2026 from experiment-craft base
14aa6524aa63789451a44feee54f98b6336482b0 (the merged P6 review). Only the
Python client, tests, configuration and documentation change.

- [Current checks](checks/): source/pin verification, unit/link tests, required
  live tests, the local recovery example and installed upgrade/rollback checks.
- [Fresh native smoke](native-smoke/summary.json): the three real solver jobs
  after checking all staged executable/source hashes against the lock.
- [Reused native baseline](reused-native-baseline/summary.json): the actual P6
  run at these identical native commits passed 26 steps and 819 Rust tests,
  with the recorded single SQP census ignore. It was not rerun for this Python
  change; the distinction is explicit in [native-reuse-proof.json](native-reuse-proof.json).
- [Rehearsal](rehearsal/summary.json): seven configured nodes, one tested local
  node, six disabled remote entries, 17 real jobs, expected 15/2 outcome, paused
  campaign restore and a controlled quiescent native-root copy at its original
  path, native reconciliation, identical reports and zero new jobs after restore.
- [Installed wheels](wheel-proof.json): reviewed 0.2.0 -> 0.3.0 -> 0.2.0 -> 0.3.0,
  outside the checkout. Older software is used for offline reporting only;
  maintenance remains paused and native journals stay unchanged.

The [P7 implementation log](../../implementation-log.md#p7--operations-and-planned-worker-configuration)
records scope, inspection fixes and limits. Archive/native-root copies, SQLite
binary databases, staged executables and dependency caches are not included in
this evidence directory; the checked archive manifest and JSON facts are.
Remote structure/argv exports are offline preparation, not actual host tests.
No real multi-node, service/logout/reboot, cgroup, live native snapshot or power
loss acceptance is claimed. GitHub publication and branch cleanup were not done.
