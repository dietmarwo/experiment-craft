# P5 local campaign evidence

The native baseline remains the merged P3 revisions in [baseline-lock.json](../../baseline-lock.json). No runtime, worker or mathematical source changed. GitHub heads matched that lock. The [backend probe](available-backend.json) records why RT-07/RT-08 remain blocked; the [gate decision](../../docs/backend-gate.md) carries the open acceptance.

`native-baseline/` records source verification, release builds, real smoke jobs and the upstream checks with Rust 1.88.0 builds/tests and stable lints. Compiled dependency caches are reused; native binaries and repetitive call dumps are omitted. `campaign/` records unit/live acceptance, wheel installation and the seven-job demonstration. The demo uses actual foreground Rust jobs, verified native manifests and command outputs. Its reports preserve all three optimizers' claim/evidence levels.

Two test-only commands in `tests/fixtures/` simulate a user manager for the Python systemd-delegation and lost-acknowledgement branches. They do not establish actual systemd, SSH disconnect/logout/reboot persistence, cgroup enforcement, physical hosts or home hardware. The native SSH suite has the same explicit simulated-manager boundary as P3. No tag, publication or remote change was made.

Logs retain original absolute scratch paths and durations. They are observations, not portable paths or home-fleet timing claims. Initial failures, if any, remain separate from accepted runs.
