# Installation, upgrades and campaign recovery

The 0.4.0 client includes the P7 operations for the completed local
subset, which 0.3.0 added, and the workspace check.
Read the [deployment guide](deployment.md) for the local default and planned
workers, and the [January checklist](january-commissioning.md) for actual hosts.
The four P5 and three P6 public schemas are unchanged. Maintenance controls,
backup archives and the workspace head record have their own additive versions.

## Install and retain versions

Use Linux with Python 3.12+, Git, a C/C++ toolchain and rustup; full native checks
also need the OpenSSH client/keygen. Install the exact wheel/source being reviewed
and its declared dependency in a dedicated environment:

```bash
python3 -m venv /absolute/releases/client-0.4.0/venv
/absolute/releases/client-0.4.0/venv/bin/python -m pip install /absolute/experiment_craft-0.4.0-py3-none-any.whl
/absolute/releases/client-0.4.0/venv/bin/experiment-craft --version
```

The repository's [lock](../baseline-lock.json) names exact public native sources.
Build with `scripts/baseline.py fetch build smoke --workspace NEW --jobs 2`, or
reuse a previously checked set only after `verify` and binary-manifest checks.
Native builds/tests use Rust 1.88.0, lints use the recorded stable toolchain.
Preserve the staged runner/workers and their `manifest.json` under a versioned
absolute install path. Configure capacity, command policy and worker registrations
with the native CLI. The normal campaign client never administers the node.

An existing workspace binds runner bytes/path, node root/ID, worker identity and
mode. Retain the exact old native artifacts and registration while its jobs are
active or uncertain; keep them available for later observation as well. Replacing
files or retargeting a `current` symlink under an accepted binding can cause a
refusal. Do not change a runtime root, worker registration or campaign identity
to make a pending request pass an upgrade.

## Upgrade and rollback

1. Stop advancing clients, including the dashboard, and pause dispatch with the
   installed client. Wait for the advancement lock to become free; use
   status/native observation for in-flight work. A pause does not cancel the
   current job.
2. Create and verify a campaign backup. Preserve the original workspace and
   existing native artifacts. Install the new version in another versioned venv.
3. Check version, offline reports and identity before `unpause-dispatch`. Reconcile
   before continuing; an unknown handle is not permission to start another attempt.
4. For rollback, stop all advancing clients and keep dispatch paused. Use the
   retained previous venv for offline inspection/reporting first. 0.3.0 enforces
   the pause and ignores `head.json`; decisions it makes leave the record behind
   the database, which 0.4.0 accepts. The 0.2.0 reader can read the unchanged
   P5/P6 formats and ignores the SQLite control table, but **its driver does not
   enforce the pause**, so do not run that driver against a workspace being
   maintained. Return to the current client and reconcile before dispatching
   again.

The installed-package rehearsals never run two client versions at once and
create no extra native job. The P7 one, recorded in the
[implementation log](../implementation-log.md), installs reviewed 0.2.0, upgrades
to 0.3.0, backs up/restores, rolls back for offline reports and returns to 0.3.0.
The [0.4.0 one](../evidence/release-0.4.0-rehearsal/README.md) upgrades a paused
0.3.0 campaign to 0.4.0, rolls back to 0.3.0, which also decides, returns to
0.4.0, finishes the campaign and restores the 0.3.0 archive. They are local
package rehearsals, not native-service upgrades or power-loss guarantees.

## Pause and inspect

```bash
experiment-craft pause-dispatch --workspace /absolute/campaign --reason "backup"
experiment-craft maintenance-status --workspace /absolute/campaign
experiment-craft status --workspace /absolute/campaign
```

The [maintenance record](../experiment_craft/schemas/campaign-maintenance-0.1.schema.json)
is `experiment.campaign.maintenance/0.1`, stored separately in SQLite. Its update
and event commit together. A pause can commit while an advancing client holds
the advancement lock. The loop stops before further dispatch; the dispatch
transaction checks it again after validation. A launch whose intent committed
before the pause may still start or finish. The pause neither cancels it nor
rewrites its outcome. `stop` remains the explicit cancellation policy.

Pause is cooperative client policy, not a native admission drain. Older clients
and independent native CLI callers do not honor it. Keep only one writable
campaign workspace/client authority. The absolute campaign deadline is not
extended by a pause, backup, restore or time offline. While dispatch is paused
the client does not cancel overdue work; native per-job limits continue to
apply, as they do while Python is absent, and `stop` cancels explicitly.

## Copy and check a workspace

A campaign's committed decisions are in `campaign.sqlite3` together with its
write-ahead log, `campaign.sqlite3-wal`. While any client has the database open,
and after a client was killed, recent decisions are only in the WAL. SQLite
copies them into the main file when the WAL reaches 1,000 pages (about 4 MB),
and when the last client closes, which also removes the WAL. A small campaign
stays below that, so its main file alone can reopen at the state right after
initialization. To keep or move a workspace, pause it and use `backup`. For a plain
file copy, stop every client first (CLI commands, the dashboard and any
script that opens the database), check that no `campaign.sqlite3-wal` remains,
and copy the whole directory.

An explicit `PRAGMA wal_checkpoint` is no substitute. It copies the WAL as of
one moment; decisions made after it go to the WAL again. A reader that holds an
older snapshot stops it at that snapshot: a `PASSIVE` checkpoint then copies only
the older frames and still reports busy 0, and a `TRUNCATE` checkpoint reports
busy 1. Only a `TRUNCATE`
checkpoint that reports busy 0 while no client runs leaves a complete main file.

Every committed decision is also recorded in `head.json`, an
[`experiment.campaign.head/0.1`](../experiment_craft/schemas/campaign-head-0.1.schema.json)
record written after the commit. It holds no secret and is readable by every
account that can reach the workspace, with the database's group and, when root
writes it, its owner. A failed write leaves the previous record and does not
fail the decision. A
workspace whose database lacks that
decision, or holds a different one, fails to open with `state_regressed`: the
database is an earlier copy, for example one taken without its WAL, and nothing
is decided from it. Keep that copy unchanged and continue from the complete
workspace or a backup. A record of another campaign gives `campaign_conflict`,
and an unreadable or symlinked record `invalid_head`. A client stopped between
a commit and its record leaves the record behind the database, which is
accepted. A workspace created before this record has none until its next
decision, and a copy that leaves out `head.json` is not checked.

```bash
experiment-craft workspace-check --workspace /absolute/campaign
```

`workspace-check` compares a workspace's database with what the workspace
recorded outside it. It copies the database files to a private temporary
directory and reads them there, so the workspace and its WAL stay unchanged,
and it makes no runtime call. It opens the files only in a child process, so it
does not disturb SQLite's locks of a client in the calling process. The result
lists `findings`:

| Finding | Meaning |
| --- | --- |
| `wal_required` | The main file alone ends at an earlier decision (`main_file_alone`) than with its WAL (`last_decision`). Copy them together. |
| `database_behind_head` | The database lacks the decision that `head.json` records (`head.seq` above `last_decision`): it lost decisions, for example in a copy without its WAL. |
| `head_differs` | The database holds a different decision at `head.seq`, or the record is of another campaign: the database or the record comes from another copy. |
| `results_without_decision` | A step has a saved native result, but the database never issued it: the database lost decisions. This check also covers workspaces without `head.json`. |
| `unrecorded_results` | An issued step has a saved result that the database does not record: a client stopped between saving and recording it, or the decision that recorded it was lost. `collect` records it from the native job. |
| `client_advancing` | A client holds the advancement lock, as `/proc/locks` shows, so the files can change while they are read. `advancing` is `null` when that cannot be told, for example on overlayfs or btrfs, whose device numbers can differ from the lock table's; a client in another PID namespace is not listed at all. |
| `invalid_head` | `head.json` cannot be read, or is not a head record. |

The command exits 1 when a finding means that the database lost or does not
hold the workspace's decisions, or that the workspace cannot be opened
(`invalid_head`, `database_behind_head`, `head_differs`,
`results_without_decision`), so that a loop over many workspaces can tell them
apart; otherwise it exits 0. No finding means that the database agrees with the
workspace's own records. Its
`status` and `steps` are the last observed state: a native job that finished
after its client left still shows as running until `collect` or `continue`
observes it. Files that cannot be copied give `copy_failed`, `invalid_input` or
`size_limit`. `restored_from` names the backup a workspace was restored from,
whose state is that backup's by design. The command reads the files one after
another, so check a workspace whose clients are stopped. The dashboard does not
start with a workspace that fails to open; check it and attach the complete
workspace instead.

## Back up a campaign

```bash
experiment-craft backup --workspace /absolute/campaign --destination /absolute/new/campaign-backup.zip
```

Backup requires paused dispatch and the exclusive advancement lock. A busy
client gives `campaign_busy`; do not copy a live WAL database by copying only
`campaign.sqlite3` (see [Copy and check a workspace](#copy-and-check-a-workspace)).
Backup uses SQLite's online backup API and then verifies
the scientific plan, retained inputs/results, SQLite integrity and all three
P6 declaration anchors. It preserves state, events, comparison, maintenance and
existing handles/keys. Normal file hashing is bounded and does not block on FIFOs.

The [archive schema](../experiment_craft/schemas/campaign-backup-0.1.schema.json)
defines `experiment.campaign.backup/0.1`. `BACKUP.json` records campaign/plan/runtime
identities, package version, sizes, SHA-256 and file modes. Archive entries under
`data/` contain a consistent SQLite database, `plan.json`, and authoritative
`files/`, `requests/` and `results/`. Live `runner.stdout`/`runner.stderr`, locks,
SQLite WAL/SHM, `head.json` and derived report directories are omitted; restore
records its own decision in a new `head.json`. The corresponding
native output/result evidence lives in the runtime or retained result cache.

The default total source-byte limit is 1 GiB, adjustable with `--max-bytes` up to
16 GiB; at most 20,000 files and a 4 MiB manifest are allowed. The database limit
is 256 MiB and other files 64 MiB each. `total_bytes` describes uncompressed data;
the returned `bytes` and SHA identify the finished ZIP. The archive must be
outside the campaign workspace and is published without replacing an existing
file. A changing, oversized, corrupt, symlink or non-regular input fails safely.
Hashes detect corruption; they do not authenticate an archive from another owner.
The SQLite snapshot holds the database write lock briefly; a pause or stop issued
meanwhile waits for it up to five seconds. Pause and stop stay usable while the
archive is written, but a decision committed after the snapshot is not in it:
such a backup is refused with `backup_changed` and nothing is published.
Archives include declared campaign data/environments and input snapshots.

## Restore and reconcile

```bash
experiment-craft restore /absolute/campaign-backup.zip --workspace /absolute/new/restored
experiment-craft maintenance-status --workspace /absolute/new/restored
experiment-craft compare --workspace /absolute/new/restored --destination /absolute/new/offline-report
experiment-craft unpause-dispatch --workspace /absolute/new/restored
experiment-craft continue --workspace /absolute/new/restored
```

Restore makes no runtime call. It requires a new workspace, checks all declared
paths, sizes, hashes, file types, database integrity, scientific identity and
declaration anchors in a private directory, then atomically publishes a **paused**
workspace. Existing destinations, path traversal, duplicate/unlisted entries,
symlinks, encrypted entries and byte-limit violations are refused. Files and
directories are synced, but actual power-loss behavior remains a commissioning
test. Restore never resets the deadline, reservations, request keys or node binding.

Keep the original workspace retired/paused and all its clients stopped. A
restored workspace is recovery of the same campaign, not a new independent run.
Do not unpause multiple copies. Preserve the authoritative native root at its
original absolute location and node identity. A new node/root is not a substitute
for missing execution facts.

`unpause-dispatch` first verifies the exact runtime/worker binding. For each
issued handle it checks native resolution/provenance, then observes active work
or compares terminal identity/result bytes with the retained facts. Unknown or
unverifiable work keeps the campaign paused; use the runtime's guarded recovery
tools explicitly. It also queries every **never-issued** predicted handle: if
one now exists, the snapshot is stale and gives `recovery_diverged`, rather than
adopting newer or foreign work. A newer pause requested during reconciliation
wins through a generation check. No submission, replay, repair, re-registration
or failover occurs during unpausing. A verified job that is still running passes,
even if its launch acknowledgement was lost. A step that failed because the
client refused a foreign job under its key has nothing of its own to reconcile.

The check on never-issued handles is repeated before every later dispatch. If
another copy of the campaign launched the step in the meantime, the predicted
handle exists with this step's request: dispatch pauses the campaign and fails
with `recovery_diverged` instead of adopting that job.

After successful reconciliation, `continue` follows existing native handles.
If the archived deadline has passed it applies the existing stop/cancel policy;
it does not extend the study. Reports can be regenerated offline while paused.

## Runtime-owned state

The campaign ZIP is **not a backup of the Rust node root or worker installations**.
Coordinate all native clients before backing up runtime state. Without a
commissioned native drain/snapshot service, the preparation procedure is an
operator-owned quiescent copy: stop every submitter, establish that every job
is terminal and none is uncertain, retain exact external runner/worker artifacts,
and copy the complete runtime root with permissions. Restore to its original
absolute path with all submitters still stopped. Ask the Rust runtime to
`jobs reconcile`, then verify node identity, native records and collection before
unpausing a campaign. Never use a possibly stale native copy as proof that an
uncertain job did not run.

The example below controls a private one-slot root with no other clients,
copies it only after all 17 jobs are terminal, retains the original, restores a
copy at the same absolute path, and delegates reconciliation to Rust. Live or
concurrent native-root snapshots, cross-host restore, service/logout/reboot and
power-loss recovery remain unvalidated. No second runtime recovery API was added.

## Run the preparation rehearsal

```bash
python3 examples/operations/rehearse.py --bin-dir /absolute/native/bin --output /absolute/new/operations-demo
```

The script exports a seven-node plan without contacting remote hosts, explicitly
administers only its new local node, and runs the P6 scientific example. Its
17 actual jobs give 15 successes and two deliberate failures. It pauses, backs
up and restores campaign state, rehearses the controlled quiescent native copy,
reconciles, and verifies the same handles, unchanged native journals, identical
comparison files and **zero new jobs after restore**. Source, configuration,
calls, reports, archive and summary stay under the new output directory. The
private native copies contain staged executables and are not kept in the repository.

The [backend gate](backend-gate.md) remains open. This preparation package does
not commission real independent hosts, lingering, cgroups, failover, automatic
placement or production group budgets.
