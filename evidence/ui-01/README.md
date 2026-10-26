# UI-01 acceptance evidence

Fresh local dashboard checks on merged P7 at `1d17218`. The source/native pins
remain unchanged. See the [implementation log](../../implementation-log.md#ui-01--local-experiment-controls-and-per-node-progress)
and [dashboard guide](../../docs/dashboard.md).

- `unit-complete`: 131 unit/schema/documentation tests.
- `live-delivery`: 61 real campaign tests, including four dashboard cases.
- `dom-uninterrupted`: actual page interactions using jsdom, real HTTP and real
  Rust jobs. Ten completed jobs and one separately cancelled job. No visual
  browser or real-phone validation is claimed.
- `ui-*.json`: observations and exported history from that run, including
  immutable main-database and ordinary client reads after server shutdown.
- `installed-final` and `wheel-proof`: the final installed wheel, all package
  files identical to source, actual HTTP/static/history access, no new jobs or
  native journal changes.
- `source-verification`, `native-smoke`, `native-*.json`: fresh locked-source,
  binary-manifest and three-worker smoke verification. The full old Rust
  baseline was not rerun.
- `github-heads.json`: current public heads matched the recorded base/pins.
- `failures/`: prototype build and cold-open failures, not accepted results.
  After early-yielding execution commands, retained SQLite artifacts were inconsistent;
  an uninterrupted final run and separate installed-client read passed. See the
  failure ledger for the distinction and the remaining uncertainty.
- `browser-limit.json`: actual browser launch was blocked by the environment.
- `sqlite-*-probe.json`: bounded independent filesystem/SQLite probes.

All times/paths/IDs are observations of this execution workspace. There is no
session access token, private SSH key, native executable or live database in
this directory. Retained snapshots are JSON records, not replay instructions.
Actual independent hosts, service/logout/reboot, cgroups, physical resources and
power-loss behavior remain uncommissioned. No remote CI run is inferred.
