# P1 validation evidence

`before/` is the refreshed public-GitHub baseline before refactoring.
`superseded/` is an earlier candidate before the neutral schema slot-cap
correction; its SQP test process could not start due to execute permissions.
Its run records, step records, smoke summary and the failing `sqp-tests` log
are kept; the passing step logs and per-call smoke output, which duplicated
`final/`, were dropped in review.
`final/` is the full accepted run on the exact candidate commits in
`baseline-final-lock.json`, using process-scoped local Git mirrors.
`initial-final/` retains the first candidate run, whose smoke failed because
of a non-executable worker artifact; `permission-retry/` records the first
unsuccessful permission-only retry, and `permission-retry2/` records the
successful smoke after atomic byte-identical rematerialization (its records
and smoke summary are kept). The cause of the permission behavior was not
established. No failed log is relabeled.

`checks/` contains targeted runtime tests, both mixed-SDK compatibility modes,
legacy compatibility, SDK/binary identities, project tests and permission
repair records. `p1-review-pinned` is the earlier discovery-side-effect test
failure; the compatibility suites and final baseline pass after its fix.

Build/test records use Rust 1.88.0, lints/docs use stable 1.99.1, and all
Python schema checks require jsonschema. The final baseline summary has
22 steps. Read individual logs for the one intentionally ignored SQP census
test and for systemd's unavailable-manager branch.

Executable bytes and process lock files are omitted. The five executable
hashes and source/toolchain IDs are in each baseline's `binaries.json`.
Retained attempt JSON, journals and logs are under `smoke/attempts/`; paths
inside those files remain the original execution paths. Evidence is for
local candidate commits, not publication or hardware commissioning.
