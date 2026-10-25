# Implementation log

One section per work package or review, oldest first. Each records the exact bases, the commands run, their results and what remained unvalidated.

- [P0 — audit and pin the foundation](#p0--audit-and-pin-the-foundation)
- [P0 review](#p0-review)
- [P1 — execution boundary and observations](#p1--execution-boundary-and-observations)
- [P1 review and merge](#p1-review-and-merge)

## P0 — audit and pin the foundation

Date: 2026-10-24 (UTC). Scope: **P0**, implementation plan v2.1. Home machines remain unavailable until January 2027.

### Outcome

The current Rust runner and all three real workers build and interoperate. The retained smoke jobs passed schema, numerical-evidence, request-identity and input-checksum checks. P0 adds reproducible baseline tooling and the agreed integration design to experiment-craft. It does not implement campaign execution, generic commands, transfers or a fleet.

This is a compatible execution baseline, not an all-green upstream CI certificate. The results below retain upstream failures and the corrected initial smoke-tool expectation.

### Source bases and changes

| Repository | Exact base commit | P0 change |
|---|---|---|
| experiment-craft | `bcd74e9e2ba2c04088601bde5a786013f2053a1d` | New tooling, fixtures, documentation and evidence; original LICENSE preserved |
| optimization-jobs | `f65e664f12cfa68c3e23a070147ea2a6fed87944` | No source or lockfile changes |
| fcmaes-rust | `bdd01e846226544e76cd1c9267e3c78719212041` | No source or lockfile changes |
| LP-IP-craft | `3645d2d6962f30d4962cb5700a3d0b1e392345d5` | No source or lockfile changes |
| SQP-craft | `3f155f9aa6acc680f9e6d4a0c8b80d26468e619d` | No source or lockfile changes |

All three worker workspaces pin the shared job crates to `37b30e428c5fdd017975e0093cc261243148257f`. Git object comparison confirms identical `crates/` and `docs/job-api/` trees at that revision and the current runner. Current crate manifests and ai-context.md agree on 0.3.0; the plan’s earlier documentation mismatch was stale. No dependency-pin change was needed.

### Implemented files

- `baseline-lock.json`: exact repository revisions and manifest/Cargo.lock/schema hashes, tested tools, protocol versions and evidence references.
- `scripts/baseline.py`: fetch exact revisions, reject source/lock drift, build the three workers and current runner, run existing checks, and retain evidence. Existing modified checkouts are never reset.
- `scripts/smoke.py` and `examples/smoke/`: one real job per worker, schema and numerical checks, same-key reuse, changed-identity conflict and changed-input-byte rejection.
- `tests/test_baseline.py`: six tests for clean-source verification, fresh detached fetching, revision/checksum drift and preservation of user edits/untracked source.
- `docs/reuse-audit.md`, `docs/integration-contract.md`, `docs/compatibility-matrix.md`, `docs/implementation-backlog.md`, `docs/known-limitations.md`: inspected code seams, current CLI/JSON contract, proposed additive interfaces, repository ownership and acceptance gates.
- `rust-toolchain.toml` (removed in the review; the lock names the toolchains), `requirements-baseline.txt`, README and the preserved plan v2.1: reproduction instructions and scope.
- `evidence/p0/`: actual command records/logs, worker discovery, native manifests/journals, binary fingerprints, environment and Git tree comparisons.

### Environment and method

Linux x86_64; Rust 1.88.0 installed in an isolated toolchain; CPython 3.12.14; jsonschema 4.26.0. The container exposes 9 CPUs by affinity with an 8-CPU cgroup quota and 8 GiB memory limit. Cargo compilation used 2 jobs. OMP/OpenBLAS/MKL thread environment variables were set to 1. No home host was used.

The repositories were fetched at their latest merged default-branch revisions during this run. A separate rehearsal used the fetch action of `scripts/baseline.py` to retrieve all four exact source pins into a fresh workspace and verify hashes. Its build action also passed against the verified original workspace using its existing Cargo cache. This was not a second cold rebuild of every dependency.

Recorded Rust commands used the isolated Rust 1.88.0 PATH, `CARGO_TARGET_DIR` pointing to a shared target directory, `CARGO_BUILD_JOBS=2`, and `--locked`. Worker release builds selected only each worker package, so the shared pinned runner was not selected as the runner executable. `scripts/baseline.py` builds the current runner last.

Python runtime suites used the recorded venv, `JOB_API_TARGET` pointing to those release binaries, `JOB_API_REQUIRE_SCHEMA=1`, `JOB_API_REQUIRE_WORKER=1`, and the fcmaes job-api tutorial directory. Rust docs used `RUSTDOCFLAGS="-D warnings"`.

### Actual command results

The compact commands below omit absolute workspace prefixes for readability. Each linked JSON record contains the full argv, working directory and timestamps; each log retains the actual output. Durations include compilation.

| Check | Result | Duration (s) | Test counts, where reported |
|---|---|---:|---|
| [build-runner](evidence/p0/checks/build-runner.json) | passed (exit 0) | 58.9 |  |
| [fetch-worker-pin](evidence/p0/checks/fetch-worker-pin.json) | passed (exit 0) | 4.7 |  |
| [build-fcmaes](evidence/p0/checks/build-fcmaes.json) | passed (exit 0) | 83.9 |  |
| [build-lp-ip](evidence/p0/checks/build-lp-ip.json) | passed (exit 0) | 64.6 |  |
| [build-sqp](evidence/p0/checks/build-sqp.json) | passed (exit 0) | 49.9 |  |
| [review](evidence/p0/checks/review.json) | passed (exit 0) | 20.4 | 24 tests; 0 skipped |
| [mcp](evidence/p0/checks/mcp.json) | passed (exit 0) | 65.2 | 36 tests; 0 skipped |
| [baseline-unit](evidence/p0/checks/baseline-unit.json) | passed (exit 0) | 0.3 | 5 tests; 0 skipped |
| [baseline-verify](evidence/p0/checks/baseline-verify.json) | passed (exit 0) | 1.3 |  |
| [smoke](evidence/p0/checks/smoke.json) | failed (exit 1) | 0.8 |  |
| [smoke-verified](evidence/p0/checks/smoke-verified.json) | passed (exit 0) | 1.1 |  |
| [integration](evidence/p0/checks/integration.json) | passed (exit 0) | 11.6 | 16 tests; 0 skipped |
| [runner-fmt](evidence/p0/checks/runner-fmt.json) | passed (exit 0) | 0.3 |  |
| [runner-clippy](evidence/p0/checks/runner-clippy.json) | passed (exit 0) | 15.8 |  |
| [runner-tests](evidence/p0/checks/runner-tests.json) | passed (exit 0) | 51.5 | 46 passed, 0 failed, 0 ignored |
| [fcmaes-fmt](evidence/p0/checks/fcmaes-fmt.json) | passed (exit 0) | 0.5 |  |
| [fcmaes-clippy](evidence/p0/checks/fcmaes-clippy.json) | failed (exit 101) | 32.0 |  |
| [fcmaes-tests](evidence/p0/checks/fcmaes-tests.json) | passed (exit 0) | 607.6 | 329 passed, 0 failed, 0 ignored |
| [baseline-fetch](evidence/p0/checks/baseline-fetch.json) | passed (exit 0) | 26.9 |  |
| [baseline-unit-final](evidence/p0/checks/baseline-unit-final.json) | passed (exit 0) | 0.4 | 6 tests; 0 skipped |
| [lp-ip-fmt](evidence/p0/checks/lp-ip-fmt.json) | passed (exit 0) | 0.5 |  |
| [lp-ip-clippy](evidence/p0/checks/lp-ip-clippy.json) | failed (exit 101) | 11.6 |  |
| [lp-ip-tests](evidence/p0/checks/lp-ip-tests.json) | passed (exit 0) | 69.3 | 213 passed, 0 failed, 0 ignored |
| [sqp-fmt](evidence/p0/checks/sqp-fmt.json) | passed (exit 0) | 0.5 |  |
| [sqp-clippy](evidence/p0/checks/sqp-clippy.json) | failed (exit 101) | 25.1 |  |
| [sqp-tests](evidence/p0/checks/sqp-tests.json) | passed (exit 0) | 49.1 | 217 passed, 0 failed, 1 ignored |
| [runner-docs](evidence/p0/checks/runner-docs.json) | passed (exit 0) | 2.4 |  |
| [fcmaes-doc-consistency](evidence/p0/checks/fcmaes-doc-consistency.json) | passed (exit 0) | 0.2 |  |
| [baseline-build](evidence/p0/checks/baseline-build.json) | passed (exit 0) | 1.2 |  |
| [smoke-final](evidence/p0/checks/smoke-final.json) | passed (exit 0) | 1.0 |  |
| [review-final](evidence/p0/checks/review-final.json) | passed (exit 0) | 19.0 | 24 tests; 0 skipped |
| [mcp-final](evidence/p0/checks/mcp-final.json) | passed (exit 0) | 60.7 | 36 tests; 0 skipped |
| [integration-final](evidence/p0/checks/integration-final.json) | passed (exit 0) | 11.1 | 16 tests; 0 skipped |

#### Commands executed

- **build-runner**, `optimization-jobs`: `cargo build --release --locked`; [raw log](evidence/p0/checks/build-runner.log).
- **fetch-worker-pin**, `optimization-jobs`: `git fetch --depth 1 origin 37b30e428c5fdd017975e0093cc261243148257f`; [raw log](evidence/p0/checks/fetch-worker-pin.log).
- **build-fcmaes**, `fcmaes-rust`: `cargo build --release --locked -p fcmaes-job-worker`; [raw log](evidence/p0/checks/build-fcmaes.log).
- **build-lp-ip**, `LP-IP-craft`: `cargo build --release --locked -p lp-ip-job-worker`; [raw log](evidence/p0/checks/build-lp-ip.log).
- **build-sqp**, `SQP-craft`: `cargo build --release --locked -p sqp-job-worker`; [raw log](evidence/p0/checks/build-sqp.log).
- **review**, `optimization-jobs`: `python scripts/job-api/test_review.py -v`; [raw log](evidence/p0/checks/review.log).
- **mcp**, `optimization-jobs`: `python scripts/job-api/test_mcp.py -v`; [raw log](evidence/p0/checks/mcp.log).
- **baseline-unit**, `experiment-craft`: `python -m unittest discover -s tests -v`; [raw log](evidence/p0/checks/baseline-unit.log).
- **baseline-verify**, `experiment-craft`: `python scripts/baseline.py verify --workspace $WORKSPACE`; [raw log](evidence/p0/checks/baseline-verify.log).
- **smoke**, `experiment-craft`: `python scripts/smoke.py --bin-dir $WORKSPACE/target/release --schemas $WORKSPACE/repos/optimization-jobs/docs/job-api/schemas --output $WORKSPACE/smoke-first`; [raw log](evidence/p0/checks/smoke.log).
- **smoke-verified**, `experiment-craft`: `python scripts/baseline.py smoke --workspace $WORKSPACE --output $WORKSPACE/baseline-smoke`; [raw log](evidence/p0/checks/smoke-verified.log).
- **integration**, `optimization-jobs`: `python scripts/job-api/test_integration.py -v`; [raw log](evidence/p0/checks/integration.log).
- **runner-fmt**, `optimization-jobs`: `cargo fmt --all -- --check`; [raw log](evidence/p0/checks/runner-fmt.log).
- **runner-clippy**, `optimization-jobs`: `cargo clippy --locked --workspace --all-targets -- -D warnings`; [raw log](evidence/p0/checks/runner-clippy.log).
- **runner-tests**, `optimization-jobs`: `cargo test --release --locked --workspace`; [raw log](evidence/p0/checks/runner-tests.log).
- **fcmaes-fmt**, `fcmaes-rust`: `cargo fmt --all -- --check`; [raw log](evidence/p0/checks/fcmaes-fmt.log).
- **fcmaes-clippy**, `fcmaes-rust`: `cargo clippy --locked --workspace --all-targets -- -D warnings`; [raw log](evidence/p0/checks/fcmaes-clippy.log).
- **fcmaes-tests**, `fcmaes-rust`: `cargo test --release --locked --workspace`; [raw log](evidence/p0/checks/fcmaes-tests.log).
- **baseline-fetch**, `experiment-craft`: `python scripts/baseline.py fetch --workspace $WORKSPACE/fetch-rehearsal`; [raw log](evidence/p0/checks/baseline-fetch.log).
- **baseline-unit-final**, `experiment-craft`: `python -m unittest discover -s tests -v`; [raw log](evidence/p0/checks/baseline-unit-final.log).
- **lp-ip-fmt**, `LP-IP-craft`: `cargo fmt --all -- --check`; [raw log](evidence/p0/checks/lp-ip-fmt.log).
- **lp-ip-clippy**, `LP-IP-craft`: `cargo clippy --locked --workspace --all-targets -- -D warnings`; [raw log](evidence/p0/checks/lp-ip-clippy.log).
- **lp-ip-tests**, `LP-IP-craft`: `cargo test --release --locked --workspace`; [raw log](evidence/p0/checks/lp-ip-tests.log).
- **sqp-fmt**, `SQP-craft`: `cargo fmt --all -- --check`; [raw log](evidence/p0/checks/sqp-fmt.log).
- **sqp-clippy**, `SQP-craft`: `cargo clippy --locked --workspace --all-targets -- -D warnings`; [raw log](evidence/p0/checks/sqp-clippy.log).
- **sqp-tests**, `SQP-craft`: `cargo test --release --locked --workspace`; [raw log](evidence/p0/checks/sqp-tests.log).
- **runner-docs**, `optimization-jobs`: `cargo doc --locked --no-deps`; [raw log](evidence/p0/checks/runner-docs.log).
- **fcmaes-doc-consistency**, `fcmaes-rust`: `python scripts/check_doc_consistency.py`; [raw log](evidence/p0/checks/fcmaes-doc-consistency.log).
- **baseline-build**, `experiment-craft`: `python scripts/baseline.py build --workspace $WORKSPACE --output $WORKSPACE/build-rehearsal`; [raw log](evidence/p0/checks/baseline-build.log).
- **smoke-final**, `experiment-craft`: `python scripts/baseline.py smoke --workspace $WORKSPACE --output $WORKSPACE/final-smoke`; [raw log](evidence/p0/checks/smoke-final.log).
- **review-final**, `optimization-jobs`: `python scripts/job-api/test_review.py -v`; [raw log](evidence/p0/checks/review-final.log).
- **mcp-final**, `optimization-jobs`: `python scripts/job-api/test_mcp.py -v`; [raw log](evidence/p0/checks/mcp-final.log).
- **integration-final**, `optimization-jobs`: `python scripts/job-api/test_integration.py -v`; [raw log](evidence/p0/checks/integration-final.log).

### Retained numerical smoke results

| Worker | Recorded objective | Required interpretation |
|---|---:|---|
| fcmaes: 2D sphere, seed 1, 100 evaluations | 0.011643188766312476 | best_found; objective and bounds rechecked |
| LP-IP: choose one binary variable, objective offset 5 | 7.0 | numerical_optimum; x=[1,0], numerical bound 7; integrality and feasibility rechecked |
| SQP: 4D simplex quadratic | 0.25 | first_order; x=[0.25,0.25,0.25,0.25], stationarity <= 1e-6 |

All three use a single node with capacity 1 and one task. Repeated identical requests return the same job ID without changing the result journal. Changed specifications under the same key produce request_key_conflict. Changed model bytes under the original hash produce invalid_job. These are native jobs, not mocked solver outputs. See evidence/p0/smoke/summary.json and the retained manifests.

### Findings and deviations

1. The agreed ownership split is supported by the code: Rust owns execution, staging, admission and recovery; Python will own campaigns and scientific reporting. The runner’s hard-coded worker invocation and optimization result processing are the main seams for P1.
2. The existing runtime stages/validates before request-key lookup. Client recovery should use persisted handles and preserve input/worker identity; future fleet design must make immutable resolution explicit.
3. All three pinned solver workspaces have strict Clippy diagnostics under Rust 1.88: fcmaes da.rs:491/:506 (needless_range_loop), LP-IP crates/native/src/lu.rs:1182 (collapsible_else_if), and SQP crates/sqp-job-worker/src/lib.rs:134 (uninlined_format_args). Worker builds and native integration succeed. No upstream code was changed or lint suppressed to hide these issues; backlog items BL-01 to BL-03 record the follow-ups. A failed check may stop before subsequent warnings. The [P0 review](#p0-review) found that the repositories' own lint gate, the latest stable Clippy, accepts these patterns.
4. The first development smoke run incorrectly expected invalid_spec for corrupt input. Actual runner behavior is invalid_job. The checker was corrected and its entire three-worker smoke rerun passed. The failed initial run remains in the evidence.
5. Full workspace checks changed the fcmaes and SQP executable fingerprints. The release-build action and the three-job smoke were rerun; final binaries are recorded separately from the initial observations. The shared review/MCP/integration suites were repeated against the final set. No bit-identical-build claim is made.
6. No runtime compatibility fix was necessary. The preserved project LICENSE is byte-identical to the initial commit.

### Unavailable and out-of-scope validation

- The runner reported no systemd user manager. The MCP systemd test passed the systemd_unavailable branch; it did not validate successful detached launch. The container’s systemctl command printed an unavailable message despite exit 0, so that exit code is not positive service evidence.
- No logout/reboot/power-loss, lingering or kernel-enforced resource/escaping-descendant containment checks on the home machines or a suitable systemd VM.
- No real SSH/fleet transfer, multi-node placement, Slurm comparison, GPU/driver, full-load thermal or physical-core/SMT commissioning.
- No full Python-binding wheel matrices, mdBook build, long benchmarks or complete application tutorial sweep. Native Rust/runtime checks are explicitly enumerated above. SQP intentionally ignores one documentation census test; its 217 passing Rust tests and one ignored test are reported separately.
- No generic command, transfer or fleet feature is claimed implemented. P0 published no package or release tag.

### Record and next step

The repository keeps the experiment-craft source and the evidence. Upstream source trees, compiled binaries, toolchain caches and virtual environments are not kept; the exact source pins and dependency locks reconstruct them online. Raw evidence paths belong to the original test container. The retained attempt files are review evidence, not a restorable node backup.

P0's acceptance requirement, a reproducible pinned build and one small real job per available worker, is met. The next implementation step is RT-01 in optimization-jobs: extract execution mechanics behind the existing optimization interface, preserve native semantics, and rerun this compatibility baseline before command and fleet additions.

## P0 review

Date: 2026-10-24 (UTC). Scope: a review of the P0 tooling, documents and plan, an independent re-run of the baseline, and fixes in the solver repositories. No runtime code in optimization-jobs changed.

### Changes

| Repository | Change |
|---|---|
| experiment-craft | Baseline tooling: build and lint toolchains from the lock; executables staged to `WORKSPACE/bin` with a manifest; worker pin and shared-path verification; composable actions; evidence records written by the tool; smoke failures recorded. CI. Contract and audit corrections from a source check, backlog IDs, plan 2.2, evidence moved to `evidence/p0/`, link and anchor test. |
| fcmaes-rust | [#31](https://github.com/dietmarwo/fcmaes-rust/pull/31): the five Clippy 1.88 diagnostics (BL-01) |
| LP-IP-craft | [#33](https://github.com/dietmarwo/LP-IP-craft/pull/33): the Clippy 1.88 diagnostic (BL-02) |
| SQP-craft | [#35](https://github.com/dietmarwo/SQP-craft/pull/35): the Clippy 1.88 diagnostic (BL-03) |
| optimization-jobs | None |

### Findings

1. **The Clippy failures were a toolchain mismatch, not an open upstream gate.** P0 linted with Clippy 1.88. The solver repositories lint with the latest stable Clippy in CI, and their `main` branches were green. A local stable 1.97 run at the pinned commits passed fmt and Clippy in all four workspaces (below). The baseline now builds and tests with 1.88.0 and lints with the lock's lint toolchain, `stable`. The upstream fixes make Clippy 1.88 clean too. P0's run stopped at the first failing crate; `--keep-going` showed three more format-argument diagnostics in fcmaes-rust.
2. **Smoke could test other executables than the build step produced.** `cargo test --release --workspace` rebuilds `target/release` with the workspace's feature unification. That explains the fingerprint change P0 observed (finding 5 above). `build` now copies the five executables with a manifest, and smoke and check refuse copies that no longer match it or the lock's commits.
3. **The pin claim was checked on fewer paths than the workers use.** P0 compared `crates` and `docs/job-api`. The workers' `shared-pin.yml` compares six paths and checks every manifest and lockfile. `verify` now does both, except the ancestry check, which needs more history than depth-1 fetches give.
4. **Evidence summaries came from a recording wrapper outside the repository.** Each run now writes `sources.json`, `environment.json`, `toolchains.json`, `binaries.json` and `summary.json` itself.
5. **The contract needed corrections.** A line-by-line check against optimization-jobs `f65e664` confirmed the audit's limits, identity derivation, ordering and CLI table. These corrections followed:
   - every runner error exits 2 with JSON;
   - `validate` does not check capacity;
   - `jobs wait` returns on timeout with exit 0;
   - cancelling a finished job is `already_terminal`;
   - `worker_changed` reports an unregistered executable change;
   - always pass `--root`;
   - result schema 0.1 is read only by `compare`.
6. **The backlog IDs collided with upstream review IDs.** OJ-01 and later, FC-01, LP-01 and SQP-01 already name other findings inside the upstream repositories. The items are now RT, EC, REL and BL.
7. **The plan underestimated pin coordination.** Every runtime package changes shared paths, so each needs pin moves in three repositories and a lock move. Plan 2.2 states this, and P1 acceptance includes it.

### Independent re-run

Environment: Linux x86_64 container, 2 CPUs, CPython 3.13.17, jsonschema 4.26.0 from `requirements-baseline.txt`. Rust 1.88.0 could not be downloaded in this environment, so the build toolchain was stable 1.97.0 (`--build-toolchain stable`), with stable 1.97.0 (Clippy 0.1.97) as the lint toolchain. The CI workflow builds with 1.88.0. The workspace was fresh, and the command was `scripts/baseline.py all --build-toolchain stable --jobs 2`. The tool's records and logs are in [`evidence/p0-review/`](evidence/p0-review/).

| Step | Result | Duration (s) | Tests |
|---|---|---:|---|
| build-fcmaes-rust, build-LP-IP-craft, build-SQP-craft, build-runner | passed | 78.0, 51.5, 31.6, 30.3 | |
| smoke | passed | 0.7 | |
| runner-fmt, runner-clippy | passed | 0.2, 14.4 | |
| runner-tests | passed | 57.4 | 46 passed |
| fcmaes-fmt, fcmaes-clippy | passed | 0.6, 81.6 | |
| fcmaes-tests | passed | 638.8 | 329 passed |
| lp-ip-fmt, lp-ip-clippy | passed | 0.5, 18.5 | |
| lp-ip-tests | passed | 69.7 | 213 passed |
| sqp-fmt, sqp-clippy | passed | 0.4, 18.8 | |
| sqp-tests | passed | 51.3 | 217 passed, 1 ignored (the documentation census) |
| runner-docs, fcmaes-doc-consistency | passed | 2.7, 0.2 | |
| review, mcp, integration | passed | 20.3, 56.8, 10.4 | 24, 36, 16; none skipped |

The test counts equal P0's. A second `build smoke` run with the revised tool staged byte-identical executables and passed again.

Smoke results compared with `evidence/p0/smoke`, with timing fields ignored:

- fcmaes: objective 0.011643188766312476 and `x = [0.09381334298071842, 0.053312713728477235]`, the same as P0. LP-IP: 7.0 with bound 7. SQP: 0.25.
- The job IDs, spec digests, claims, evidence levels, `request_key_conflict` and `invalid_job` all equal P0's.
- The only differences are elapsed times, the journal byte counts that include them, and LP-IP's remaining `time_limit_seconds` option.

Clippy 1.88 on the solver fix branches ran on GitHub-hosted runners in a temporary workflow: `cargo +1.88.0 clippy --workspace --all-targets --locked --keep-going -- -D warnings`. The first fcmaes-rust run reported the three additional format arguments. After those were fixed, all three workspaces passed.

### Not repeated

- A local build with Rust 1.88.0 (not downloadable here); the CI job covers it.
- Clippy 1.88 at the P0 commits: the P0 logs record it, and `--lint-toolchain 1.88.0` repeats it.
- The P0 environment limits remain: no systemd user manager (`systemctl --user` reported `offline`), no SSH, no home machines.

The solver PRs merged afterwards; P1 started from their merge commits.

## P1 — Execution boundary and observations

Iteration 02, 24 October 2026. Scope: RT-01 and RT-02 of plan 2.2.
The plan is now 2.3; P2 command/file work is next after P1 merge acceptance.

### Checkout and completed work found

Fresh GitHub checkouts confirmed that experiment-craft P0/review and all
three solver lint fixes had merged. experiment-craft started at
`f807f491c5b1672b82d962c8f66b589ad6f4ca8e`; optimization-jobs was unchanged
from the reviewed `f65e664` baseline. The P0 review's toolchain split, staged
binary manifests, six shared paths and coded-error semantics were preserved.
The refreshed baseline ran **before runner changes** and passed all 22 steps:
805 Rust tests, 24 review, 36 MCP and 16 integration tests, plus all native
builds, smoke jobs, stable formatting/lints/docs and documentation consistency.

### Implemented changes

- optimization-jobs now has private `admission`, `supervision`, `execution`
  and `optimization` modules. The generic lifecycle owns admission, process
  observations and finalization ordering; the adapter owns worker commands,
  native outcome validation, journals and mathematical manifest construction.
  Existing request identity, locks, conservative slot release, no implicit
  restart and native optimization formats are preserved.
- `node capabilities` returns `execution.capabilities/0.1` without creating a
  node. The same object appears in `node doctor` and MCP `describe_node`.
  Only optimization is advertised. There are no new MCP tool names.
- `jobs execution ID` reads `.execution.json`, version
  `execution.record/0.1`. The terminal record contains observed exit code or
  signal, stop reason, containment, log references and a hashed native-result
  attachment. Mathematical claims, work and feasibility stay in `run.json`.
  Old terminal attempts are not backfilled; active/missing records return
  `execution_unavailable`. Recovery does not invent exit codes, elapsed time
  or missing content identities. Legacy native schema integer `1` is retained.
- A neutral adapter exists only in Rust tests. It exercises success, failure,
  timeout, queued cancellation, spawn failure and process-record write failure
  without an optimization request, SDK journal or mathematical output.
- Every tracked worker manifest/lock pin moves to the runtime candidate below:
  ten files in fcmaes-rust (including four standalone tutorials), two in
  LP-IP-craft and two in SQP-craft. The other tracked subcrate manifests were
  checked and do not carry a Git pin. Solver algorithms/tolerances are untouched.
- experiment-craft updates the baseline lock, plan, contract, backlog, audit
  status and compatibility matrix. Smoke jobs additionally validate discovery,
  execution schemas, native result hash/size and unchanged records on key reuse.
  It remains development tooling; no campaign package was added.

| Repository | GitHub base | Exact candidate |
|---|---|---|
| optimization-jobs | `f65e664f12cfa68c3e23a070147ea2a6fed87944` | `4f93d75ba9dc0ca40d6de455261b7a753f130976` |
| fcmaes-rust | `e34dd20d0fa8bb38309ccb4bed3d5000bba7d11f` | `505ea687e0cc2ff5253edb13fb1d0943bd42017e` |
| LP-IP-craft | `a257f993e121fb328c1b00edd62a506d9bc468f9` | `b490a1389e57b064e9ab0c9a952bc72dd0f66f1f` |
| SQP-craft | `a053857c3e721e268ef4322171f1973744cbd838` | `6979501181080ec743fe02122cc1921abbf9a344` |

The experiment-craft commit of this package was `5dab9ad`; it is not
recorded in its own lock, which would make the source hash self-referential.

### Validation and reproducibility

**All 22 final candidate-baseline steps passed. Coordinated merge and public-GitHub acceptance are pending.**

| Gate | Recorded result |
|---|---|
| Refreshed GitHub baseline before refactor | All 22 steps passed; 805 Rust tests, 1 existing SQP census test ignored |
| Runtime after extraction | 52 Rust tests passed, including six neutral tests; stable fmt, Clippy with warnings denied, rustdoc with warnings denied |
| New runner with existing SDK pins | Review 27, MCP 36, mixed integration 16, plus two MCP real-worker tests for each of three workers: all passed |
| New runner with checkout SDK | All three workers rebuilt with explicit Cargo path patches; `sdk_source.py` checked resolution. The same 85 checks passed before pins moved |
| Legacy fcmaes runtime | Real `fcmaes.job/0.1` completed; neutral schema validated and native schema `1` / attachment digest preserved |
| Final pinned candidate baseline | All 22 steps passed; 811 Rust tests, 1 existing ignored test; review 27, MCP 36, integration 16; all three smoke jobs/schema and attachment checks passed |
| experiment-craft unit/documentation checks | 27 tests passed |

Builds and Rust tests use 1.88.0; fmt/Clippy/docs use stable rustc
1.99.1 (`58cf8f9c3`, 2026-10-13). Python is 3.12.14 with pinned
jsonschema 4.26.0. The container exposes an eight-CPU quota and an 8 GiB memory
limit; Cargo used four jobs. Every baseline stages five executables before
smoke/tests, retaining hashes and source IDs so later test builds cannot
silently replace the binaries under test.

The final baseline uses freshly fetched candidate checkouts (the full all run
was repeated after the artifact permission correction) and process-scoped Git URL
rewrites to exact local candidate mirrors. Canonical GitHub URLs stay in
manifests/locks. This validates the unpublished commits; it is not evidence
that GitHub served them; the [P1 review](#p1-review-and-merge) repeated the
baseline against the merged commits on GitHub.

Evidence is under `evidence/p1/`: before/final baseline records, command logs,
source and executable hashes, SDK resolution, schema/legacy checks and retained
native/neutral smoke output. Copied evidence omits executable worker bytes,
process lock files and the transient node root; the staged binary manifest
identifies them and the individual job's JSON/journals/logs are retained under
`smoke/attempts/`. Absolute paths/timestamps are historical observations.

### Findings corrected during implementation

1. A CLI regression caught that capability discovery inherited the CLI's
   root-directory creation. Discovery now returns before that code; the
   no-filesystem-side-effect assertion passes. The original failing log is kept.
2. A boot-ID lookup after process spawn could return before cleanup. It now
   shares the guarded process-record error path; the child is killed/reaped
   and unknown containment still retains slots.
3. The first neutral schema copied the modern envelope's 1,024-slot maximum.
   The legacy request has no such maximum, so the neutral schema now records
   any positive slot declaration. A regression accepts 2,048 and rejects zero.
   The final candidate baseline uses the corrected schemas and updated hashes.

4. The first corrected-candidate smoke failed because the freshly built
   fcmaes executable lacked execute permission (0644). The cause was not
   established; a superseded candidate run also hit a non-executable SQP
   test binary. A mode-only retry still failed, so the trusted worker copies
   were replaced atomically with identical bytes and executable mode. The next
   smoke passed. Staging/manifest verification now explicitly
   rejects non-executable files (two regressions). The original failed smoke
   and permission/hash record remain; the full baseline was rerun afterward.

No failing gate was waived and no numerical test expectation was weakened.

### Remaining gates and scope limits

- Merge optimization-jobs first, then the three worker pin changes, then
  experiment-craft. Preserve candidate commits through fast-forward/merge,
  or regenerate every downstream pin/lock after rebasing or squashing.
- The workers' shared-pin **ancestor of public main** check and a fresh
  baseline against published GitHub commits remain pending. No remote branch,
  pull request, tag or release was created by this iteration.
- The systemd user manager is unavailable here; MCP exercised that error path.
  Positive detached execution, logout/reboot behavior, nested-PID CI invocation,
  real SSH, cgroup containment and January home hardware were not validated.
- One existing SQP documentation census test stays ignored. Python-binding
  wheel matrices, all scientific tutorial workloads and performance benchmarks
  were not run for these runtime/pin-only changes.
- Command jobs, generic binary transfer, fleet allocation and Python campaign
  execution are not implemented. P1's generic adapter is private and test-only
  outside optimization; P2 must specify its public request and enablement policy.

## P1 review and merge

Date: 2026-10-24 (UTC). Scope: a review of the P1 changes in all four repositories, fixes in separate commits, the merges in dependency order and a baseline run against the merged commits on GitHub.

### How the work was integrated

The implementation commits keep their recorded hashes: optimization-jobs `4f93d75`, fcmaes-rust `505ea68`, LP-IP-craft `b490a13`, SQP-craft `6979501` and experiment-craft `5dab9ad`. Each one's parent is the recorded GitHub base. The review fixes are separate commits on top. The worker pins then moved from `4f93d75` to the reviewed optimization-jobs head `70e210f`.

| Repository | Pull request | Commits | Merged as |
|---|---|---|---|
| optimization-jobs | [#21](https://github.com/dietmarwo/optimization-jobs/pull/21) | `4f93d75`, `196991c`, `70e210f` | `a613798` |
| fcmaes-rust | [#32](https://github.com/dietmarwo/fcmaes-rust/pull/32) | `505ea68`, `c1300a3` | `8dd061a` |
| LP-IP-craft | [#34](https://github.com/dietmarwo/LP-IP-craft/pull/34) | `b490a13`, `06e1462` | `d25f874` |
| SQP-craft | [#36](https://github.com/dietmarwo/SQP-craft/pull/36) | `6979501`, `6639968` | `ec348c1` |
| experiment-craft | this pull request | `5dab9ad` and the review commits | this merge |

The merge order was optimization-jobs, then the three workers, then this repository. That way each worker's `shared-pin.yml` found its pin on optimization-jobs `main`, and the lock names merged commits only. The superseded lock move [#2](https://github.com/dietmarwo/experiment-craft/pull/2) was closed: P1's pre-refactor baseline had already run at those commits.

### Findings

1. **The runtime refactor preserves behavior.** I compared the old `launch`, `execute_worker`, `finish` and repair code with the new `admission`, `supervision`, `execution` and `optimization` modules. Slot release follows the same rules:
   - a spawn failure or a staged-digest mismatch releases the slots;
   - unverified group termination retains them;
   - a failed process record retains them unless the group is verifiably stopped.
   
   The terminal states, `exact` accounting, `elapsed_seconds: null` after launcher loss and the order of file writes are unchanged; the record is written between `run.json` and `job.json`. Worker statuses (`completed`, `cancelled`, `timed_out`) all parse into the new state type. `.execution.json` cannot collide with an artifact, because artifact files may not start with `.`.
2. **An independent review of the record handling found three defects, fixed in `70e210f`.**
   - **Stale or forged records.** `jobs execution` served whatever `.execution.json` held. The worker runs in the job directory and can write that file. A launcher lost between writing the record and writing `job.json` also left a record that repair later replaces. A record is now served only when `job.json` is terminal with the same state and `finished_at`.
   - **Non-retryable error for unfinished jobs.** A job that had not finished returned the non-retryable `execution_unavailable`, although the same call succeeds once it finishes. It now returns the retryable `attempt_active`. `execution_unavailable` remains for finished attempts without a matching record.
   - **Wrong repair containment.** Repair recorded `stopped` containment for admitted attempts that never reached `running`; those now get `not_started`.
   
   The tests changed too:
   - the neutral fixture has a per-test wall time, so only the deadline test can time out on a slow disk;
   - a Rust test covers the serving rule;
   - the review harness schema-checks repair records and keeps its behavioral assertions when `jsonschema` is missing.
3. **The boot-ID cleanup is a fix, not a change.** The old code evaluated `boot()?` inside the process-record write and returned before stopping the spawned worker. The changelog now lists it under Fixed.
4. **Plan names and temporary states leaked into upstream documents.** Before the fixes:
   - the changelogs began with "P1:" or a new "Shared runtime P1" heading outside Added, Changed and Fixed;
   - each `ai-context.md` opened with a dated "P1" notice;
   - the runner README and job guide spoke of "the P1 source iteration";
   - the workers called the pin a "P1 source candidate", and the LP-IP and SQP sentence attributed the 0.3.0 additions to the new pin.
   
   The upstream documents now say "after 0.3.0", put the entries under the Keep a Changelog categories, and place the new commands where the guides list commands.
5. **Two example manifests kept the old pin.** `docs/job-api/models.md` in fcmaes-rust and SQP-craft still showed `37b30e4`; they now show the pinned revision.
6. **Repository documents described a pre-merge package.** The experiment-craft documents described unpublished candidate commits and a local helper for reproducing them. They now describe the merged state. The P1 section keeps its record of the candidate validation, without the reproduction instructions.
7. **Evidence duplicated itself.** `evidence/p1/` held 761 files (4.3 MiB). The superseded candidate run and the second permission retry each repeated about 1 MiB of per-call smoke output and passing logs already in `final/`. Their summaries, step records, smoke summaries and the failing `sqp-tests` log are kept; the duplicates are gone, and the evidence README says so.

### Baseline at the merged commits

The commits are the ones in `baseline-lock.json`: optimization-jobs `a613798`, fcmaes-rust `8dd061a`, LP-IP-craft `d25f874` and SQP-craft `ec348c1`. All three workers pin `70e210f`. The run used a fresh workspace and fetched everything from GitHub, without local mirrors. The environment was a 2-CPU container with CPython 3.13.17 and stable Rust 1.97.0 (Clippy 0.1.97) for both building and linting, because 1.88.0 cannot be downloaded there. The command was `scripts/baseline.py all --build-toolchain stable --jobs 2`, and the records are in [`evidence/p1-review/`](evidence/p1-review/).

- All 22 steps passed: fetch and verify (pins and shared paths), 4 builds, smoke, fmt, Clippy and tests in all four workspaces, rustdoc, the fcmaes documentation consistency check, and the review, MCP and integration harnesses.
- Rust tests: 53 in optimization-jobs (52 delivered plus the new serving-rule test), 329 in fcmaes-rust, 213 in LP-IP-craft, and 217 in SQP-craft with 1 ignored (the documentation census). The harnesses ran 27 review, 36 MCP and 16 integration tests, with none skipped.
- Smoke results equal `evidence/p1/final`. The objectives are 0.011643188766312476 (fcmaes, same `x`), 7.0 (LP-IP) and 0.25 (SQP). The job IDs, claims, evidence levels, observations (exit 0, no stop reason, `stopped` containment), native-result sizes, `request_key_conflict`, `invalid_job` and the capabilities object are also unchanged.
- Only timing fields, the `run.json` digests that contain them, and the content identities differ. The identities hash the worker executable, which this run built with another toolchain and pin.

On GitHub, the optimization-jobs and worker pull requests and their post-merge `main` runs passed CI. That includes optimization-jobs' mixed-node checks with the pinned and checkout SDK, and each worker's `shared-pin.yml`. This repository's pull request CI builds the merged set with Rust 1.88.0 and runs the smoke jobs.

### Not repeated

- Rust 1.88.0 builds locally: the toolchain cannot be downloaded in the review environment. This repository's CI builds the merged set with 1.88.0 and runs the smoke jobs, and optimization-jobs' CI checks the declared Rust 1.88.
- Positive detached systemd, SSH, cgroup containment and home hardware, as before.

## P2 — Trusted local commands and binary files

Date: 24 October 2026. Scope: P2 / RT-03–RT-04, trusted local command jobs and checked binary staging/collection. This section records the implementation and its checks before merge; the [P2 review](#p2-review-and-merge) records the changes made in review and the baseline at the merged commits.

### GitHub checkout and what was already done

Fresh checkouts showed that P1 was merged across all five repositories. The repository plan was version 2.3 and explicitly selected P2 next. A later `ls-remote` check found all five main heads unchanged.

| Repository | GitHub base commit |
|---|---|
| SQP-craft | `ec348c1ca327a04938261cffeada8eaed2d5f599` |
| optimization-jobs | `a61379821e667847105f5bf4c3d8cd893cbe861c` |
| LP-IP-craft | `d25f874eee4b8674281dd8120f9b86886444e4fd` |
| experiment-craft | `abd9b5ea31e33ba059858ee19a9c620288607488` |
| fcmaes-rust | `8dd061add421457c3c6beee54b58e12af8cda06b` |

P1 already provided the private execution/admission/supervision split, optimization adapter, terminal `execution.record/0.1`, capability discovery, and coordinated worker pin `70e210fbf562900c1be8f278e2ab2852ef5934e3`. Review had tightened record/state/finish-time matching, active-attempt errors, recovery containment and executable staging. Those fixes were preserved. No solver algorithm, numerical tolerance, optimization envelope, worker protocol or optimization result contract was changed.

### Implementation and repository split

**optimization-jobs owns the implementation.** It adds:

- A separate strict `execution.command/0.1` request: literal argv, explicit environment, declared CPU slots and wall/grace limits, hashed inputs/scripts, declared outputs and `replay: "never"`. Absolute executables are resolved and hashed; staged executables must be explicitly declared executable inputs. Input bytes and executable identity are checked before launch. Reusing a key returns the same attempt; changed work conflicts, including command/optimizer key collisions.
- Node command opt-in via `node init --allow-commands` or `node commands --enable`; default off. Disable rejects new command validation/submission, while accepted attempts may finish. `run`, `submit`, `jobs get/wait/cancel/repair` and terminal observations use the existing lifecycle and admission ledger. Command stop requests signal the process group with TERM, then KILL at grace expiry. Optimizer cooperative cancellation is unchanged.
- Separate `execution.command.result/0.1` results attached to the existing neutral record by size and SHA-256. They describe observed exit/signal, output completeness and collection errors, with no invented objective, feasibility, work or optimization claim. Repair reports interruption with no invented successful exit or elapsed duration; it never replays the command.
- `files put/get/cleanup` for raw binary data and `jobs collect` for sealed command outputs. Transfers stream through private temporary files, enforce exact size/hash, sync, and publish without clobbering destinations. Inputs/outputs reject unsafe relative paths, symlinks and runtime filenames. File limits: 64 MiB each, 128 declarations and 256 MiB combined declared input/output budget per job; blob storage quota 1 GiB. Verified blobs and attempts are retained until explicit owner cleanup. Interrupted uploads cannot appear verified.
- Discovery `execution.capabilities/0.2`, distinguishing supported and enabled kinds and exposing CLI-only command/file interfaces and limits. `execution.record/0.1` is unchanged; the older capabilities schema is retained. MCP mathematical summaries reject command jobs; MCP submission was meant to stay optimization-only, which the review found it did not (finding 1 of the [P2 review](#p2-review-and-merge)).
- Published and embedded schemas, documentation, error codes, CI coverage, a 15-test process/transfer suite, and an executable C build–run–collect demonstration. The SDK crate is unchanged; the runner gains a direct dependency on the already-locked SHA-256 crate.

**Worker repositories only move the shared runtime pin and explain it.** All three root manifests/lockfiles were updated, as were all four fcmaes standalone tutorial manifests/lockfiles and the fcmaes/SQP example-manifest documentation. Their numerical and Python sources are unchanged.

**experiment-craft owns plan and integration evidence.** It updates the baseline lock, validates capability schema 0.2 in smoke, adds command/file regression and build–run–collect steps to the baseline, and revises the plan to version 2.4. The next brief is P3: explicit remote execution and reconciliation. No campaign engine, SSH transport or automatic fleet scheduler was added.

### Coordinated local revisions

All workers pin runtime `466a373ff81815493451063a9885db28c1946504`.

| Repository | Candidate commit |
|---|---|
| optimization-jobs | `466a373ff81815493451063a9885db28c1946504` |
| fcmaes-rust | `193e903d3038ad63a0c225360442f1b48d575a0d` |
| LP-IP-craft | `549a972eb2d3de6eb29bfe171a54248aa4af08c3` |
| SQP-craft | `3f13b7a32403ed1dcd3530721b1ceedcc49eb494` |

The experiment-craft commit of this package was `f311969`; it is not recorded in its own lock. The validation runs resolved the canonical GitHub URLs to local mirrors of these commits inside their child processes only, without changing the global Git configuration. The [P2 review](#p2-review-and-merge) repeated the baseline against the merged commits on GitHub.

### Verification

Environment: Linux x86-64, Python 3.12.14, Rust 1.88.0 builds/tests, stable Rust 1.99.1 for repository lints and standalone tutorial builds, GCC 13.3.0, an eight-CPU cgroup quota and 8 GiB memory. JSON Schema validation was required. Detailed versions and commands are in `evidence/p2/baseline/`.

| Check | Result |
|---|---|
| Accepted coordinated baseline | All 24 steps passed: source/pin verification, builds, smoke, formats, clippy, tests, rustdoc, documentation consistency and CLI suites/demo |
| Rust workspace tests | 815 passed: runtime 56, fcmaes 329, LP/IP 213, SQP 217; one pre-existing SQP documentation-census test ignored |
| Shared Python suites | 27 review, 36 MCP, 16 mixed-worker integration and 15 command/file tests passed, no skips |
| Before pin changes | Both existing pinned-SDK and checkout-SDK configurations passed all four suites, plus six per-worker MCP checks each |
| Local examples/tutorials | Four standalone tutorial worker builds; fcmaes custom/simulation examples and SQP custom example; all three job tutorials and the surrogate tutorial passed |
| Legacy compatibility | Real `fcmaes.job/0.1` execution passed with native integer schema 1 and a verified neutral attachment |
| Build–run–collect | Compiled a hashed C input, collected/uploaded the executable, staged it into a second command and verified answer bytes `00 2a ff` |

The new command/file tests cover literal metacharacters, environment non-inheritance, exit codes/signals, output absence/oversize/symlink/FIFO rejection, binary round trips, sealed-output tampering, no clobber, interrupted stdin uploads and cleanup, unsafe paths, changed input/executable identity, mixed admission in both directions, queue cancellation, timeout and descendant cancellation, and launcher loss/repair without replay. Exported optimizer result directories without job metadata remain readable/comparable.

The real numerical smoke results match the previous baseline: sphere objective `0.011643188766312476` (`best_found`), binary LP/IP objective `7.0` (`numerical_optimum`), and simplex SQP objective `0.25` (first-order result). The checked claims and evidence remain native.

The full run used fresh source checkouts and a reused compiled dependency cache. Final binary hashes, source commits, per-step exit codes and raw logs are retained. Native result/record evidence is kept without duplicating staged worker binaries or every discovery response. Initial failed logs are preserved; they are not relabeled as passes.

### Failures found and resolved

1. Command dispatch initially bypassed the existing invalid-job wrapper for malformed optimization JSON. The old regression suite caught `runner_error` instead of `invalid_job`; dispatch now preserves the original error code. The complete review suite passed afterward.
2. A legacy MCP handshake assertion still expected only optimization in *supported* kinds. It now checks both supported kinds, optimization-only enabled by default, command opt-in false and binary-transfer availability. Both complete SDK compatibility runs passed afterward.
3. The formatter caught a multiline dispatch guard after its error-handling fix; formatting was applied and checked again.
4. Four native-test invocations stopped before executing a compiled binary because this environment lost its execute bit: fcmaes/SQP in the initial GitHub baseline, LP/IP/SQP in the initial candidate baseline. Only compiled cache file modes were repaired, with byte-identical SHA-256 values recorded. The initial worker suites and then the entire candidate baseline were rerun successfully. No source fix or relaxed assertion was used to hide these environment failures.
5. Session tooling initially queried an optional tutorial dependency without its `job-worker` feature, omitted the already-built simulation example from a tutorial staging directory, and expected only one failed cache step when there were two. These setup checks were corrected; the missing checks were completed. Final tutorial step summaries were reconstructed from their JSON log records because the outer command logger reused their initial summary filenames. Raw failure/output records remain available.

### Limits and next work

Commands run as trusted programs under the runner user. Relative-path checks protect declared file materialization/collection; they do not isolate arbitrary program file access. Slot counts are admission accounting, not kernel CPU/memory/disk enforcement. Undeclared working-directory writes are not quota-limited. Host interpreter/compiler libraries are not snapshotted, and hostile same-UID races are not contained. Descendants in the original process group were tested; deliberate session/group escapes are outside this containment policy.

The test host has no usable systemd user manager. Successful detached services, logout/reboot survival, SSH/disconnect/lost-ack behavior and the user's home machines remain unvalidated. Full Python wheel matrices and long scientific benchmarks were outside this runtime/pin-only change. Nothing here claims fleet or hardware commissioning.

P3 implements explicit node placement, a fixed SSH helper, verified remote transfers and persistent dispatch/handle reconciliation. Automatic fleet allocation and Python campaigns remain later packages.

## P2 review and merge

Date: 2026-10-24 (UTC). Scope: a review of the P2 changes in all four repositories, fixes in separate commits, the merges in dependency order and a baseline run against the merged commits on GitHub.

### How the work was integrated

The implementation commits keep their recorded hashes: optimization-jobs `466a373`, fcmaes-rust `193e903`, LP-IP-craft `549a972`, SQP-craft `3f13b7a` and experiment-craft `f311969`. Each one's parent is the recorded GitHub base, and each tree equals its exported patch applied to that base. The review fixes are separate commits on top. The worker pins then moved from `466a373` to the reviewed optimization-jobs head `2351e40`.

| Repository | Pull request | Commits | Merged as |
|---|---|---|---|
| optimization-jobs | [#22](https://github.com/dietmarwo/optimization-jobs/pull/22) | `466a373`, `bbb17dc`, `a539f23`, `261292e`, `2351e40` | `d9827d1` |
| fcmaes-rust | [#33](https://github.com/dietmarwo/fcmaes-rust/pull/33) | `193e903`, `6fa64b8` | `cca34c2` |
| LP-IP-craft | [#35](https://github.com/dietmarwo/LP-IP-craft/pull/35) | `549a972`, `643af78` | `1162df7` |
| SQP-craft | [#37](https://github.com/dietmarwo/SQP-craft/pull/37) | `3f13b7a`, `8af98d1` | `b1d719c` |
| experiment-craft | this pull request | `f311969` and the review commits | this merge |

The merge order was optimization-jobs, then the three workers, then this repository. Each worker's `shared-pin.yml` thereby found its pin on optimization-jobs `main`, and the lock names merged commits only.

### Findings

Findings 1–6 come from this review and an independent review of the command and transfer code. Each was reproduced before the fix, and findings 1–5 have regression tests that fail at `466a373`.

1. **MCP ran command jobs.** `validate_job` and `submit_job` passed any request with `execution.command/0.1` to the runner. On a node with commands enabled, `submit_job` with `argv: ["/usr/bin/touch", MARKER]` completed and created the marker, although the guide and the capabilities (`command_interface: "cli"`) say commands are CLI-only. The server now refuses them with `unsupported_job_kind`. Because the runner reads a `spec_path` again after the server checked it, the server also sets `OPTIMIZATION_RUN_REFUSE_COMMANDS` for every runner it starts, and the runner refuses to stage a command while it is set (`bbb17dc`). An environment variable, unlike a new CLI flag, keeps `optimization-mcp --runner` working with older runners.
2. **A process that left the group held the launcher.** After the worker's process group was verified stopped, the launcher still joined its log readers until both pipes reached end of file. A program that started a helper with `setsid` (a build server, for example) kept them open: the attempt stayed `running` with its slots reserved, `jobs cancel --now` had no effect and `jobs repair` answered `attempt_active`. 0.3.0 had the same join for optimization workers. The launcher now stops reading two seconds after the group stopped (`261292e`, listed under Fixed).
3. **The executable ran under its resolved name.** Staging replaced `argv[0]` with the canonical path, so `/usr/bin/unxz` ran as `xz`, `clang++` as `clang`, and a virtual environment's `python` lost the environment. The verified file now runs under the submitted `argv[0]`; provenance keeps the resolved path, size and digest (`a539f23`).
4. **A bare request name broke inputs.** `validate --spec command.json`, as in the guide's own example, failed with `runner_error` for inputs with a `file`, because the parent of a bare name is empty. Inputs now resolve beside the request's canonical directory.
5. **The overlap check compared sorted neighbours only.** `.` sorts before `/`, so the outputs `a`, `a.txt` and `a/c` passed validation; an input `a` with an output `a/b` then failed late. Every directory prefix of every declared path is checked now.
6. **Smaller staging limits.**
   - Absolute executables were bound by the 64 MiB transfer limit and failed with `file_transfer_failed`. They are hashed in place, not copied; the limit is now 1 GiB, reported as `invalid_command_spec`.
   - Runtime file names (`worker`, `run.json`, …) were rejected in every path segment, for example `src/worker/main.c`, although runtime files live beside `work/`. Only empty and dot-prefixed segments are rejected now.
   - `.command-outputs` was created during finalization, outside the per-output error handling; a directory the command replaced made finalization fail on every repair. It is created at staging, and a replaced one is an output error.
7. **One reported defect was not one.** A dangling symlink as an optional output is already an error, because the path check rejects a symlink as the last component; a test now keeps it that way. Two test waits were fragile and were replaced: the launcher-loss test slept 0.1 s before repair instead of waiting until repair sees the killed group gone, and the timeout case gave Python 1 s to install its signal handler.
8. **The worker changelogs had two pin entries.** Each worker added a second unreleased entry for `466a373` above the one for `70e210f`. The review merged them into one entry for `2351e40` and updated `ai-context.md` and the example manifests.
9. **Repository documents described a pre-merge package.** The README, plan, contract, backlog, limits, audit and matrix spoke of local candidates, bundles, a ZIP and import helpers, and the log ended with instructions for applying the package. They now describe the merged state; the P2 log section keeps its record of the validation before merge. In the evidence, a record comparing the exported patches with the commits was dropped, and the notes that pointed to the package's helpers now point to `scripts/baseline.py`. The lock no longer carries `publication` and `implementation_base_commit`, and records two Cargo jobs as before. Plan 2.4 marks P2 merged, and its P3 brief carries P2's failure ledger.

### Baseline at the merged commits

The commits are the ones in `baseline-lock.json`: optimization-jobs `d9827d1`, fcmaes-rust `cca34c2`, LP-IP-craft `1162df7` and SQP-craft `b1d719c`. All three workers pin `2351e40`. The run used a fresh workspace and fetched everything from GitHub, without local mirrors. The environment was a 2-CPU container with CPython 3.13.17 and stable Rust 1.97.0 for both building and linting, because 1.88.0 cannot be downloaded there. The command was `scripts/baseline.py all --build-toolchain stable --jobs 2`, and the records are in [`evidence/p2-review/`](evidence/p2-review/).

- Fetch and verify (pins and shared paths) succeeded, and all 24 steps passed: 4 builds, smoke, fmt, Clippy and tests in all four workspaces, rustdoc, the fcmaes documentation consistency check, the review, MCP, integration and command/file harnesses, and the build–run–collect example.
- Rust tests: 56 in optimization-jobs, 329 in fcmaes-rust, 213 in LP-IP-craft, and 217 in SQP-craft with 1 ignored (the documentation census). The harnesses ran 27 review, 38 MCP, 16 integration and 19 command/file tests, with none skipped; the example verified the answer `002aff`.
- Smoke results equal `evidence/p2/baseline`. The objectives are 0.011643188766312476 (fcmaes, same `x`), 7.0 (LP-IP) and 0.25 (SQP). The job IDs, claims, evidence levels, the native results and the execution records are also unchanged, and the capabilities list `optimization` and `command` as supported, only `optimization` as enabled, with binary transfer available and no fleet.
- Only timing fields (including the remaining time limit among the LP-IP worker's effective options), the digests of files that contain them, and the binary hashes differ.

On GitHub, the optimization-jobs and worker pull requests and their post-merge `main` runs passed CI. That includes optimization-jobs' command/file harness, the Rust 1.88 job and the mixed-node checks with the pinned and the checkout SDK, each worker's `shared-pin.yml`, and fcmaes-rust's tutorial builds. This repository's pull request CI builds the merged set with Rust 1.88.0 and runs the smoke jobs.

### Not repeated

- Rust 1.88.0 builds locally: the toolchain cannot be downloaded in the review environment. This repository's CI builds the merged set with 1.88.0, and optimization-jobs' CI checks the declared Rust 1.88.
- The standalone tutorial builds, the local job tutorials and the legacy `fcmaes.job/0.1` run of the P2 log; the workers' CI builds their tutorials at the new pin.
- Positive detached systemd, SSH, cgroup containment and home hardware, as before.

## P3 — Explicit SSH placement and reconciliation

Recorded 24–25 October 2026 (UTC). Scope: RT-05 and RT-06 in plan 2.5. P0–P2, including their review fixes, were already merged. The new execution and transport code lives in optimization-jobs; experiment-craft owns the coordinated contract, baseline and next-gate plan. Solver mathematics, SDK interfaces, native claims and numerical tolerances are unchanged. This section records the implementation and its checks before merge; the [P3 review](#p3-review-and-merge) records the changes made in review and the baseline at the merged commits.

### GitHub assessment

Fresh checkouts of the five public `main` branches matched the merged P2 review. Bases: experiment-craft `aa6d4f13042249acc87c696cfb3d1e05b0632281`, optimization-jobs `d9827d107cd201332664db3c120f150b928579fa`, fcmaes-rust `cca34c2d0dfe2e40d44c8f346fdc7b6afecdca7d`, LP-IP-craft `1162df71daecb1d8307fcdc848e8529c6939d3bb`, SQP-craft `b1d719c1aaba8b879e352a564f56c581edd382da`. All workers pinned reviewed runtime `2351e40842d228d98880282a7788eb195c74d718`. A final read-only GitHub check found those heads unchanged. No remote branch, pull request, tag or release was created.

The unchanged P2 source passed 22 of 24 baseline steps on retry, including native smoke jobs. SQP tests stopped when a compiled cache executable lacked its execute bit (never executed); the command suite hit a pre-existing PID-marker readiness race. Rerunning that complete 19-test command suite on unchanged source passed. The final coordinated run invokes the tests again; the original permission failure is retained. The failed baseline and successful command retry are retained; this is not relabeled as a clean 24-step run.

### Runtime behavior

- `node init` creates a persistent random node identity. An old initialized node requires explicit `node identity --init`; discovery never silently creates or replaces it. Compact discovery reports canonical root, boot, capacity, worker digest/build/profiles, capabilities and user-manager/linger observations.
- `fleet nodes add/list/probe` stores explicit SSH endpoints and pinned identities. `fleet submit --node NAME --spec FILE` selects one node. Observation, reconciliation, resume, cancellation, guarded repair, execution record retrieval and collection use its persisted handle. This is CLI access; MCP still refuses commands.
- Only an absolute validated helper path and the fixed words `remote serve` reach the SSH command string. Roots, argv, environment, specifications and input metadata travel as JSON on stdin. The client uses batch mode, strict explicit known-host checks, no TTY or agent/port forwarding, and disables multiplexing and alternative/dynamic known-host paths. Identity files are optional explicit absolute paths; normal batch authentication may be used otherwise. Helper and known-host file paths use a restricted ASCII path alphabet; request data and remote roots may contain spaces/metacharacters.
- Control frames are capped at 4 MiB; transfers at 64 MiB per file and 256 MiB of inputs. Existing blob storage remains bounded to 1 GiB. Both helper I/O and client pipes have deadlines; the client drains bounded stderr and disk-spools binary output. After SSH exits, a two-second drain bounds inherited pipe lifetimes.
- The coordinator persists its identity, normalized work, node/endpoint, worker digest and checked input snapshots before uploading or dispatching. A key cannot silently bind changed work or another placement. A never-issued staging intent can resume from retained snapshots even if its original input has disappeared.
- A remote dispatch ledger precedes preparation; a durable `launching` barrier precedes the existing user-systemd launch. Repeated or uncertain submission only observes that same dispatch. Coordinator death, lost acknowledgements and remote start errors never trigger an automatic second start or movement to another node. Global, remote dispatch, local job, unit, provenance identity and resolved-spec digest remain correlated. An issued attempt that cannot be proved running/terminal stays uncertain and requires observation or guarded repair.
- New remote dispatch requires a responding systemd user manager and `Linger=yes`. There is no foreground/nohup fallback. Capability observations and successful unit creation do not establish logout/reboot behavior or containment on an actual host.
- Collection separately inspects and verifies a terminal native manifest, neutral record, sealed command output or native artifact. Intent precedes download; complete transport and exact size/SHA-256 checks precede atomic no-clobber publication. A prior matching collection intent can recover an already-published destination. Retrying collection does not execute a job.
- Remote `repair` calls the same guarded repair implementation as local jobs; active attempts retain `attempt_active`, conservative reservations and their native accounting. Native result/observation meanings remain separate from dispatch status.

Published and embedded schemas now include `execution.capabilities/0.3`, `execution.remote/0.1`, `execution.node/0.1` and `execution.fleet.job/0.1`. Historical capability schemas remain available. No Rust dependency or optimization-job-api source was changed. New code is private to the runner. Guides, ai-context and its embedded copy, error behavior, changelog and CI were updated together.

### Coordinated revisions

| Repository | Source commit |
|---|---|
| optimization-jobs | `fcc4d5fb313e98da2dd2fe9e182b03e44ea6332c` |
| fcmaes-rust | `063f9af927c0d36da75433234d6afcfcd266b920` |
| LP-IP-craft | `164eecae58be8f0fadb10940c7b0be49b9f8a22c` |
| SQP-craft | `110d505bbbec8d959a23ca470904313cd39a0d8d` |

All worker manifests/locks, including the four optional standalone fcmaes tutorial workers, pin the runtime above. Each existing current Unreleased pin entry was updated in place; the previous review's duplicate-entry fix is preserved. Worker source changes are pin/documentation changes only. The experiment-craft revision records this log, plan 2.5, the contracts, requirements and schema/source hashes, and the expanded reproducible baseline.

### Verification

Environment: Linux x86-64; Python 3.12.14; Rust 1.88.0 builds/tests and stable 1.99.1 lints/docs; an eight-CPU quota and 8 GiB memory. OpenSSH is the actual SSH client. AsyncSSH 2.24.1 provides the disposable endpoint; dependencies are pinned in requirements-baseline.txt. Schema validation and required real workers were enabled, with no optional skips hidden.

| Check | Result |
|---|---|
| Coordinated baseline | All 26 steps pass: exact-source/shared-pin verification, four release builds, real smoke jobs, formats, Clippy, Rust tests, rustdoc, documentation consistency, six Python suites and build–run–collect |
| Rust workspaces | 819 passed: runtime 60, fcmaes 329, LP/IP 213, SQP 217; one existing SQP documentation census test ignored |
| Shared suites | Review 27, MCP 38, mixed integration 16, command/file 19, remote fixture 13, real SSH 4; no skips |
| Before pin movement | Both old pinned-SDK and checkout-SDK runs passed all six suites plus six per-worker MCP checks each |
| Locked dependencies | Every manifest/lock that pins optimization-jobs resolved with `cargo metadata --locked` |
| Extras | Four standalone tutorial worker builds; fcmaes custom/simulation and SQP custom examples; three job tutorials; surrogate tutorial |
| Legacy | Real fcmaes.job/0.1 execution, native integer schema 1, and a verified execution-record attachment |
| Project | 27 unit tests including relative links/anchors |

The baseline uses fresh source checkouts with a reused derived dependency cache. Canonical GitHub dependency URLs resolve to exact local Git mirrors only within validation child processes, because these source objects are not yet public. Git configuration outside those processes is unchanged. The evidence retains source commits, tree/file hashes, staged executable hashes, exact argv, exit codes and raw test output; copied binaries and repetitive call dumps are omitted.

Native smoke results match the P2 baseline: sphere objective `0.011643188766312476`, LP/IP `7.0`, SQP `0.25`. Their native claims and evidence are retained. No solver output, numerical tolerance or assertion was relaxed.

The 13 remote fixture tests use real Rust helper/local processes with explicitly simulated SSH and service-manager commands. They cover persistent identities, launch gating, command opt-in/shared capacity, literal data/binary transfer, optimizer/native artifacts, lost launch acknowledgement, start failure without replay, coordinator death during dispatch and collection, resumable staging without its source, malformed/truncated frames, protocol deadlines and guarded repair. A dedicated Rust test now covers the previously missing retained-byte blob-quota boundary.

The four SSH tests use actual OpenSSH authentication, encryption and host-key pinning against a disposable AsyncSSH endpoint. They transfer 1 MiB of binary data, reject a wrong host key, run all three real Rust workers (including hashed LP model input and native schemas/accounting), and deliberately abort a live SSH connection after launch before reconciling/cancelling one start. **The service manager at that endpoint is simulated.** This does not claim an actual systemd service, logout/reboot persistence, cgroup containment or independent/home hosts.

### Failure ledger and fixes

1. The initial remote CLI fixture found that Clap conflated coordinator `--root` with endpoint `--remote-root`. The endpoint now has a distinct argument ID; all remote and real SSH suites pass afterward.
2. Looking up a missing dispatch during unsent staging initially replaced its resumable phase. The observer now preserves staging; a regression removes the original input and resumes using the persisted snapshot.
3. A P2 command test waited for PID files to exist but read an empty file before its writer completed. The readiness condition now waits for both files to contain numeric PIDs. Cancellation assertions are unchanged. The unchanged base's targeted retry and all current suites pass.
4. Initial compile, formatter and incremental thin-LTO/link checks failed during development. The diagnostics and successful follow-ups are retained. A serial build with the repository's unchanged release profile passed; no build-profile/solver workaround was committed.
5. The first coordinated build stopped with Rust E0463 (`can't find crate for lp_ip_craft_native`) despite the derived rlib/rmeta being present. Their sizes, modes and hashes were recorded. Only the local LP/IP native/core build-cache entries were invalidated with `cargo clean -p`; the complete baseline was rerun into a new evidence directory. The failing original record remains. A separate pre-change SQP invocation stopped because a compiled ELF could not be executed. A local ELF-mode inspection initially also matched linker objects; their original modes were restored for surviving byte-identical files, with concurrent build temporaries left alone. The early inspection found no executable needing repair at that time. The next complete baseline again stopped before executing SQP parallel because that compiled cache file had mode 0644. After compilation finished, an extensionless ET_EXEC/ET_DYN scan identified two generated executables with missing execute bits; their modes were restored to 0755 with identical SHA-256 values recorded. The full SQP suite then passed (217 tests, one existing census ignored), followed by a complete baseline into a third evidence directory. Both failed full-run records and the targeted retry are retained. No source or dependency-lock changes were made to address these build-cache failures.
6. Test drivers keep distinct inner/outer JSON summaries, avoiding the earlier iteration's overwritten tutorial-step records. Final results come from actual exit codes and complete logs rather than reconstructed optimistic counts.
7. After the accepted 26-step run passed, the evidence collector still pointed at the prior failed summary and correctly refused to package it. Its source path was corrected to the accepted run; the strict status/count assertions remain. The failed collector invocation is retained separately.

### Remaining acceptance and next work

No home machine was accessed. Actual user-systemd service persistence after SSH/session logout, reboot/linger recovery, kernel CPU/memory containment, multi-host failure behavior and power-loss recovery remain open. RT-07 must establish the native/systemd versus Slurm allocation authority in a suitable actual environment. RT-08 automatic placement remains blocked if that evidence is unavailable. Local P5 campaign work can proceed under its existing dependency rule without inventing a second resource scheduler.

Trusted same-user commands retain P2's limits: no filesystem sandbox or quota on undeclared working data, no hostile same-UID race containment, no containment of deliberate process-group/session escapes, and no snapshot of host interpreter/compiler libraries. Per-file and blob-store limits apply to declared/retained transfers. Normal failures clean staging data; SIGKILL can leave inspectable local partial staging. No automatic retry deletes snapshots or ambiguous dispatch evidence.

The next increment must inspect GitHub/review changes, refresh the lock when needed, preserve the no-replay/identity and MCP boundaries, and carry this failure ledger forward. Backend gate failures must not be replaced by simulated acceptance. No tag or publication is part of this iteration.

## P3 review and merge

Date: 2026-10-25 (UTC). Scope: a review of the P3 changes in all four repositories, fixes in separate commits, the merges in dependency order and a baseline run against the merged commits on GitHub.

### How the work was integrated

The implementation commits keep their recorded hashes: optimization-jobs `fcc4d5f`, fcmaes-rust `063f9af`, LP-IP-craft `164eeca`, SQP-craft `110d505` and experiment-craft `f05d253`. Each one's parent is the recorded GitHub base, and each tree equals its exported patch applied to that base. The review fixes are separate commits on top. The worker pins then moved from `fcc4d5f` to the reviewed optimization-jobs head `8b4489d`.

| Repository | Pull request | Commits | Merged as |
|---|---|---|---|
| optimization-jobs | [#23](https://github.com/dietmarwo/optimization-jobs/pull/23) | `fcc4d5f`, `6eec887`, `8b4489d` | `717f6a6` |
| fcmaes-rust | [#34](https://github.com/dietmarwo/fcmaes-rust/pull/34) | `063f9af`, `fc23efe` | `c3b0a39` |
| LP-IP-craft | [#36](https://github.com/dietmarwo/LP-IP-craft/pull/36) | `164eeca`, `1937263` | `1fd856d` |
| SQP-craft | [#38](https://github.com/dietmarwo/SQP-craft/pull/38) | `110d505`, `99f78da` | `e0a7556` |
| experiment-craft | this pull request | `f05d253` and the review commits | this merge |

The merge order was optimization-jobs, then the three workers, then this repository. Each worker's `shared-pin.yml` thereby found its pin on optimization-jobs `main`, and the lock names merged commits only.

### Findings

This review and an independent review of the remote code found no replay, injection, host-key bypass or unsafe write. Six identical concurrent submits sent one Submit and started one unit. Hostile replies were refused and nothing they carried was published: floods, oversized frames, trailing bytes, a foreign node ID and altered bodies. Real traffic validated against the published schemas. The defects were in how failures are classified. Each was reproduced before the fix, except the `$` case, which needs a real user manager. Findings 1–5 have regression tests that fail at `fcc4d5f`. All of them are fixed in `8b4489d`.

1. **Every failed Submit burned its request key.** A Submit that failed for any reason left the fleet job `unknown` for good, so an identical retry hit `request_key_conflict`. That also happened when nothing could have launched:
   - the request was too large for a control frame, or `ssh` was missing, so no byte was ever sent;
   - the node refused before writing its dispatch record, for example a re-registered worker.
   
   The coordinator now saves the dispatch intent only after SSH has started and before the request is written, so an error before that point leaves the job staging. The node records its refusals under the dispatch lock, so a refusal is final, can be proved after a lost answer, and reaches the caller with the node's own code.
2. **`fleet submit` exited 0** when the node's preparation failed and when the start was uncertain after the launch barrier. Both now fail, with the node's code or `start_unknown`.
3. **A dispatch interrupted before its launch barrier stayed `preparing` forever.** This happened when the helper died during preparation, for example after a control deadline. A lookup that can take the dispatch lock now records the dispatch as failed with code `interrupted`; nothing was launched.
4. **A repeated `fleet submit` did more than observe.**
   - It re-ran discovery, the command opt-in, the capacity check and the input snapshots before it looked at the persisted job. A disabled node or a removed input file therefore made it fail.
   - It did not resume a job that was still staging.
   
   It now compares the request with the persisted one, then continues or observes the job.
5. **Error codes were wrong in several places.**
   - `fleet resume` ran command jobs although `OPTIMIZATION_RUN_REFUSE_COMMANDS` was set; only `fleet submit` checked it.
   - An early helper error (no `node.json`, a moved root) was reported as `node_identity_mismatch`.
   - `cancel`, `execution` and `repair` of a dispatch without a local job failed with an uncoded path error; they now return `remote_dispatch_unknown`.
   - A node's runner codes now reach the caller as they are; any other node error is `remote_rejected`.
6. **Smaller fixes.**
   - `node identity --init` and `node commands` rewrote `node.json` under different locks. In 98 of 150 concurrent pairs, the printed node ID was not persisted.
   - systemd-run expands `$` in its command line, so a remote root containing `$` would launch with another `--root`. Such roots are now refused.
   - SSH now also disables DNS host keys, IP checks and tunnels. The guide says that `ssh` comes from `PATH` and reads the owner's configuration.
   - The paused transport fixture polled forever once its test had ended, leaving one process behind per run. It now gives up.
7. **Not changed, but documented.** If the launcher call itself fails after the barrier (`launch_unknown`), the existing guarded repair answers `liveness_unknown` until the node reboots, because a transient unit could still exist; the local repair rules stay as they are. An interrupted preparation can leave a prepared local job that was never launched, plus `.tmp*` or `.staging-*` directories, on the node.
8. **Documentation and wording.**
   - The runner README's remote section followed the license; it now precedes Tests, and the README says which suite needs asyncssh and the OpenSSH client.
   - The guide spoke of "a main desktop", which now reads "nodes". "behaviour" became "behavior", and the new section is wrapped.
   - In the worker changelogs, the delivered entry called P2's additions "retained", as if they had been released. The entry again lists what the pin adds since tag `v0.3.0`.
   - This repository's documents describe the merged state, and plan 2.5 carries P3's failure ledger into the RT-07 brief.

### Baseline at the merged commits

The commits are the ones in `baseline-lock.json`: optimization-jobs `717f6a6`, fcmaes-rust `c3b0a39`, LP-IP-craft `1fd856d` and SQP-craft `e0a7556`. All three workers pin `8b4489d`. The run used a fresh workspace and fetched everything from GitHub, without local mirrors. The environment was a 2-CPU container with CPython 3.13.17, the pinned `requirements-baseline.txt` (including asyncssh 2.24.1), OpenSSH 9.6p1, and stable Rust 1.97.0 for both building and linting, because 1.88.0 cannot be downloaded there. The command was `scripts/baseline.py all --build-toolchain stable --jobs 2`, and the records are in [`evidence/p3-review/`](evidence/p3-review/).

- Fetch and verify (pins and shared paths) succeeded, and all 26 steps passed: 4 builds, smoke, fmt, Clippy and tests in all four workspaces, rustdoc, the fcmaes documentation consistency check, the review, MCP, integration, command/file, remote and real-SSH harnesses, and the build–run–collect example.
- Rust tests: 60 in optimization-jobs, 329 in fcmaes-rust, 213 in LP-IP-craft, and 217 in SQP-craft with 1 ignored (the documentation census). The harnesses ran 27 review, 38 MCP, 16 integration, 19 command/file, 18 remote fixture and 4 real SSH tests, with none skipped, and no transport fixture was left running afterwards. The example verified the answer `002aff`.
- Smoke results equal `evidence/p3/baseline`. The objectives are 0.011643188766312476 (fcmaes, same `x`), 7.0 (LP-IP) and 0.25 (SQP). The job IDs, claims, evidence levels, native results and execution records are also unchanged.
- Only timing fields, the digests of files that contain them and the binary hashes differ. That includes the remaining time limit among the LP-IP worker's effective options. It also includes one more digit in an SQP `elapsed_seconds`, which makes its results journal one byte longer.

On GitHub, the optimization-jobs and worker pull requests and their post-merge `main` runs passed CI. That includes optimization-jobs' remote suites and its real-OpenSSH run with all three workers, under both the pinned and the checkout SDK, each worker's `shared-pin.yml`, and fcmaes-rust's tutorial builds. This repository's pull request CI builds the merged set with Rust 1.88.0 and runs the smoke jobs.

### Not repeated

- Rust 1.88.0 builds locally: the toolchain cannot be downloaded in the review environment. This repository's CI builds the merged set with 1.88.0, and optimization-jobs' CI checks the declared Rust 1.88.
- The standalone tutorial builds, the local job tutorials and the legacy `fcmaes.job/0.1` run of the P3 log. The workers' CI builds their tutorials at the new pin.
- Real systemd user services, logout and reboot, cgroup containment and home hardware, as before; RT-07 is that gate.
