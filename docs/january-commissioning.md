# January 2027 commissioning

Local P7 preparation does not establish home-fleet acceptance. Use the
[deployment inventory](deployment.md), [operating guide](operations.md) and
[backend decision gate](backend-gate.md). Keep the main desktop outside the
worker pool; the local test target is one explicit small allocation.

| Gate | Observe on the actual machines | Required evidence |
|---|---|---|
| J0 — inventory | Seven hosts: physical/logical cores, SMT, usable RAM, storage, clocks, Mint/kernel/systemd versions and GPUs | Measured inventory; proposed capacities reduced for service headroom; stable host labels and paths |
| J1 — one worker | Pinned runner/workers, SSH authentication and strict known-hosts, node ID and registered profiles | Mixed command/optimization jobs; verified inputs, records and collected bytes |
| J2 — backend | Actual user manager and lingering, disconnect/logout/reboot, cancellation, descendants, CPU/memory behavior | Decide native/systemd versus Slurm authority from observations; unknown work remains reserved |
| J3 — two workers | Independent nodes, interrupted staging/transfer and lost launch acknowledgements | One execution per accepted handle, conservative recovery, checksum-verified collection |
| J4 — six workers | Whole-host allocation, concurrency, over-capacity work, drain and budgets through the chosen authority | No double reservations; desktop excluded; automatic placement remains off until its implementation and tests pass |
| J5 — scientific calibration | Process/thread packing and memory for representative fcmaes, LP/IP and SQP workloads | Measured throughput and work accounting; do not use container timings as a substitute |
| J6 — stable operation | Bounded campaigns, retained artifacts, paused backup/restore and upgrade/rollback | Same native IDs/keys, no replay, checked reports and a documented recovery path |

For each gate record exact source/toolchain/binary versions, host, commands,
expected versus observed behavior and evidence. Use passed, failed,
blocked_environment or not_run; no skipped or simulated test counts as actual
host acceptance. Configure and probe one worker at a time before enabling more.

Preserve active and uncertain jobs' exact binaries and state across upgrades.
Keep only one writable campaign authority after a restore. Do not relocate an
uncertain attempt or infer non-execution from a missing old snapshot entry.

Record the two RTX 3090s and other GPU identities, but keep GPU execution behind
its own compatibility and exclusivity gate. Smaller CPU allocations follow
actual enforcement tests. Retain the plan's 1 March 2027 scope freeze and use the
last proven local/explicit-host configuration if fleet gates remain open.
