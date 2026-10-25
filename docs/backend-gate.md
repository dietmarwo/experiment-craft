# RT-07 backend gate

Decision recorded with P5 (local campaigns): **production allocation authority remains undecided; RT-07 and RT-08 remain blocked**. The P3 runtime and review fixes stay in use for explicit placement. The P5 dependency rule permits local campaign work independently of this gate.

The recorded [environment probe](../evidence/p5/available-backend.json) found a Docker container with `supervisord` as PID 1, no user bus and no `/dev/kvm`. Its `systemctl` command exits 0 while printing that systemd is unavailable; this is not a responding user manager. `loginctl` fails to connect to the bus. No real systemd host, Slurm allocation or home-machine endpoint was provided or accessed. No manager/linger setting was changed, and no reboot was attempted.

| Candidate | Existing implementation/evidence | Required before a production decision |
|---|---|---|
| Native user-systemd | Runtime launch, identity, conservative repair and real SSH transport; simulated-manager branch tests | Actual user service and linger, disconnect/logout/reboot observations, cancellation and cgroup/resource behavior on a suitable host |
| Slurm | No new integration or tested allocation here | A suitable actual controller/worker environment, one authoritative capacity owner, job/identity/accounting mapping and the same failure tests |

An actual-host investigation must retain the runtime handles and records before and after an SSH disconnect, session logout and reboot; verify actual resource/containment behavior; test cancellation and unknown-start recovery; and decide which backend is the allocation authority. P3's open acceptance is specifically that a real SSH disconnect leaves a durably launched job running. A loopback SSH session plus a simulated manager does not close it.

Until that evidence is available, keep placement explicit and do not enable automatic failover, placement or group-budget scheduling. Local campaigns use the existing native node admission policy. The phone-only preparation period can still produce campaign manifests, snapshots, tests and reports, then validate the real backend in January.
