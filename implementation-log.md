# experiment-craft — iteration 01 implementation log

Date: 2026-10-24 (UTC). Scope: **P0 — audit and pin the foundation**, implementation plan v2.1. Home machines remain unavailable until January 2027.

## Outcome

The current Rust runner and all three real workers build and interoperate. The retained smoke jobs passed schema, numerical-evidence, request-identity and input-checksum checks. The ZIP adds reproducible baseline tooling and the agreed integration design to experiment-craft. It does not implement campaign execution, generic commands, transfers or a fleet.

This is a compatible execution baseline, not an all-green upstream CI certificate. The results below retain upstream failures and the corrected initial smoke-tool expectation.

## Source bases and changes

| Repository | Exact base commit | P0 change |
|---|---|---|
| experiment-craft | `bcd74e9e2ba2c04088601bde5a786013f2053a1d` | New tooling, fixtures, documentation and evidence; original LICENSE preserved |
| optimization-jobs | `f65e664f12cfa68c3e23a070147ea2a6fed87944` | No source or lockfile changes |
| fcmaes-rust | `bdd01e846226544e76cd1c9267e3c78719212041` | No source or lockfile changes |
| LP-IP-craft | `3645d2d6962f30d4962cb5700a3d0b1e392345d5` | No source or lockfile changes |
| SQP-craft | `3f155f9aa6acc680f9e6d4a0c8b80d26468e619d` | No source or lockfile changes |

All three worker workspaces pin the shared job crates to `37b30e428c5fdd017975e0093cc261243148257f`. Git object comparison confirms identical `crates/` and `docs/job-api/` trees at that revision and the current runner. Current crate manifests and ai-context.md agree on 0.3.0; the plan’s earlier documentation mismatch was stale. No dependency-pin change was needed.

## Implemented files

- `baseline-lock.json`: exact repository revisions and manifest/Cargo.lock/schema hashes, tested tools, protocol versions and evidence references.
- `scripts/baseline.py`: fetch exact revisions, reject source/lock drift, build the three workers and current runner, run existing checks, and retain evidence. Existing modified checkouts are never reset.
- `scripts/smoke.py` and `examples/smoke/`: one real job per worker, schema and numerical checks, same-key reuse, changed-identity conflict and changed-input-byte rejection.
- `tests/test_baseline.py`: six tests for clean-source verification, fresh detached fetching, revision/checksum drift and preservation of user edits/untracked source.
- `docs/reuse-audit.md`, `docs/integration-contract.md`, `docs/compatibility-matrix.md`, `docs/implementation-backlog.md`, `docs/known-limitations.md`: inspected code seams, current CLI/JSON contract, proposed additive interfaces, repository ownership and acceptance gates.
- `rust-toolchain.toml`, `requirements-baseline.txt`, README and the preserved plan v2.1: reproduction instructions and scope.
- `evidence/`: actual command records/logs, worker discovery, native manifests/journals, binary fingerprints, environment and Git tree comparisons.

## Environment and method

Linux x86_64; Rust 1.88.0 installed in an isolated toolchain; CPython 3.12.14; jsonschema 4.26.0. The container exposes 9 CPUs by affinity with an 8-CPU cgroup quota and 8 GiB memory limit. Cargo compilation used 2 jobs. OMP/OpenBLAS/MKL thread environment variables were set to 1. No home host was used.

The repositories were fetched at their latest merged default-branch revisions during this run. A separate rehearsal used the delivered fetch action to retrieve all four exact source pins into a fresh workspace and verify hashes. The delivered build action also passed against the verified original workspace using its existing Cargo cache. This was not a second cold rebuild of every dependency.

Recorded Rust commands used the isolated Rust 1.88.0 PATH, `CARGO_TARGET_DIR` pointing to a shared target directory, `CARGO_BUILD_JOBS=2`, and `--locked`. Worker release builds selected only each worker package, so the shared pinned runner was not selected as the runner executable. The delivered reproduction script builds the current runner last explicitly.

Python runtime suites used the recorded venv, `JOB_API_TARGET` pointing to those release binaries, `JOB_API_REQUIRE_SCHEMA=1`, `JOB_API_REQUIRE_WORKER=1`, and the fcmaes job-api tutorial directory. Rust docs used `RUSTDOCFLAGS="-D warnings"`.

## Actual command results

The compact commands below omit absolute workspace prefixes for readability. Each linked JSON record contains the full argv, working directory and timestamps; each log retains the actual output. Durations include compilation. Relative links resolve inside the experiment-craft directory in the ZIP.

| Check | Result | Duration (s) | Test counts, where reported |
|---|---|---:|---|
| [build-runner](evidence/checks/build-runner.json) | passed (exit 0) | 58.9 |  |
| [fetch-worker-pin](evidence/checks/fetch-worker-pin.json) | passed (exit 0) | 4.7 |  |
| [build-fcmaes](evidence/checks/build-fcmaes.json) | passed (exit 0) | 83.9 |  |
| [build-lp-ip](evidence/checks/build-lp-ip.json) | passed (exit 0) | 64.6 |  |
| [build-sqp](evidence/checks/build-sqp.json) | passed (exit 0) | 49.9 |  |
| [review](evidence/checks/review.json) | passed (exit 0) | 20.4 | 24 tests; 0 skipped |
| [mcp](evidence/checks/mcp.json) | passed (exit 0) | 65.2 | 36 tests; 0 skipped |
| [baseline-unit](evidence/checks/baseline-unit.json) | passed (exit 0) | 0.3 | 5 tests; 0 skipped |
| [baseline-verify](evidence/checks/baseline-verify.json) | passed (exit 0) | 1.3 |  |
| [smoke](evidence/checks/smoke.json) | failed (exit 1) | 0.8 |  |
| [smoke-verified](evidence/checks/smoke-verified.json) | passed (exit 0) | 1.1 |  |
| [integration](evidence/checks/integration.json) | passed (exit 0) | 11.6 | 16 tests; 0 skipped |
| [runner-fmt](evidence/checks/runner-fmt.json) | passed (exit 0) | 0.3 |  |
| [runner-clippy](evidence/checks/runner-clippy.json) | passed (exit 0) | 15.8 |  |
| [runner-tests](evidence/checks/runner-tests.json) | passed (exit 0) | 51.5 | 46 passed, 0 failed, 0 ignored |
| [fcmaes-fmt](evidence/checks/fcmaes-fmt.json) | passed (exit 0) | 0.5 |  |
| [fcmaes-clippy](evidence/checks/fcmaes-clippy.json) | failed (exit 101) | 32.0 |  |
| [fcmaes-tests](evidence/checks/fcmaes-tests.json) | passed (exit 0) | 607.6 | 329 passed, 0 failed, 0 ignored |
| [baseline-fetch](evidence/checks/baseline-fetch.json) | passed (exit 0) | 26.9 |  |
| [baseline-unit-final](evidence/checks/baseline-unit-final.json) | passed (exit 0) | 0.4 | 6 tests; 0 skipped |
| [lp-ip-fmt](evidence/checks/lp-ip-fmt.json) | passed (exit 0) | 0.5 |  |
| [lp-ip-clippy](evidence/checks/lp-ip-clippy.json) | failed (exit 101) | 11.6 |  |
| [lp-ip-tests](evidence/checks/lp-ip-tests.json) | passed (exit 0) | 69.3 | 213 passed, 0 failed, 0 ignored |
| [sqp-fmt](evidence/checks/sqp-fmt.json) | passed (exit 0) | 0.5 |  |
| [sqp-clippy](evidence/checks/sqp-clippy.json) | failed (exit 101) | 25.1 |  |
| [sqp-tests](evidence/checks/sqp-tests.json) | passed (exit 0) | 49.1 | 217 passed, 0 failed, 1 ignored |
| [runner-docs](evidence/checks/runner-docs.json) | passed (exit 0) | 2.4 |  |
| [fcmaes-doc-consistency](evidence/checks/fcmaes-doc-consistency.json) | passed (exit 0) | 0.2 |  |
| [baseline-build](evidence/checks/baseline-build.json) | passed (exit 0) | 1.2 |  |
| [smoke-final](evidence/checks/smoke-final.json) | passed (exit 0) | 1.0 |  |
| [review-final](evidence/checks/review-final.json) | passed (exit 0) | 19.0 | 24 tests; 0 skipped |
| [mcp-final](evidence/checks/mcp-final.json) | passed (exit 0) | 60.7 | 36 tests; 0 skipped |
| [integration-final](evidence/checks/integration-final.json) | passed (exit 0) | 11.1 | 16 tests; 0 skipped |

### Commands executed

- **build-runner**, `optimization-jobs`: `cargo build --release --locked`; [raw log](evidence/checks/build-runner.log).
- **fetch-worker-pin**, `optimization-jobs`: `git fetch --depth 1 origin 37b30e428c5fdd017975e0093cc261243148257f`; [raw log](evidence/checks/fetch-worker-pin.log).
- **build-fcmaes**, `fcmaes-rust`: `cargo build --release --locked -p fcmaes-job-worker`; [raw log](evidence/checks/build-fcmaes.log).
- **build-lp-ip**, `LP-IP-craft`: `cargo build --release --locked -p lp-ip-job-worker`; [raw log](evidence/checks/build-lp-ip.log).
- **build-sqp**, `SQP-craft`: `cargo build --release --locked -p sqp-job-worker`; [raw log](evidence/checks/build-sqp.log).
- **review**, `optimization-jobs`: `python scripts/job-api/test_review.py -v`; [raw log](evidence/checks/review.log).
- **mcp**, `optimization-jobs`: `python scripts/job-api/test_mcp.py -v`; [raw log](evidence/checks/mcp.log).
- **baseline-unit**, `experiment-craft`: `python -m unittest discover -s tests -v`; [raw log](evidence/checks/baseline-unit.log).
- **baseline-verify**, `experiment-craft`: `python scripts/baseline.py verify --workspace $WORKSPACE`; [raw log](evidence/checks/baseline-verify.log).
- **smoke**, `experiment-craft`: `python scripts/smoke.py --bin-dir $WORKSPACE/target/release --schemas $WORKSPACE/repos/optimization-jobs/docs/job-api/schemas --output $WORKSPACE/smoke-first`; [raw log](evidence/checks/smoke.log).
- **smoke-verified**, `experiment-craft`: `python scripts/baseline.py smoke --workspace $WORKSPACE --output $WORKSPACE/baseline-smoke`; [raw log](evidence/checks/smoke-verified.log).
- **integration**, `optimization-jobs`: `python scripts/job-api/test_integration.py -v`; [raw log](evidence/checks/integration.log).
- **runner-fmt**, `optimization-jobs`: `cargo fmt --all -- --check`; [raw log](evidence/checks/runner-fmt.log).
- **runner-clippy**, `optimization-jobs`: `cargo clippy --locked --workspace --all-targets -- -D warnings`; [raw log](evidence/checks/runner-clippy.log).
- **runner-tests**, `optimization-jobs`: `cargo test --release --locked --workspace`; [raw log](evidence/checks/runner-tests.log).
- **fcmaes-fmt**, `fcmaes-rust`: `cargo fmt --all -- --check`; [raw log](evidence/checks/fcmaes-fmt.log).
- **fcmaes-clippy**, `fcmaes-rust`: `cargo clippy --locked --workspace --all-targets -- -D warnings`; [raw log](evidence/checks/fcmaes-clippy.log).
- **fcmaes-tests**, `fcmaes-rust`: `cargo test --release --locked --workspace`; [raw log](evidence/checks/fcmaes-tests.log).
- **baseline-fetch**, `experiment-craft`: `python scripts/baseline.py fetch --workspace $WORKSPACE/fetch-rehearsal`; [raw log](evidence/checks/baseline-fetch.log).
- **baseline-unit-final**, `experiment-craft`: `python -m unittest discover -s tests -v`; [raw log](evidence/checks/baseline-unit-final.log).
- **lp-ip-fmt**, `LP-IP-craft`: `cargo fmt --all -- --check`; [raw log](evidence/checks/lp-ip-fmt.log).
- **lp-ip-clippy**, `LP-IP-craft`: `cargo clippy --locked --workspace --all-targets -- -D warnings`; [raw log](evidence/checks/lp-ip-clippy.log).
- **lp-ip-tests**, `LP-IP-craft`: `cargo test --release --locked --workspace`; [raw log](evidence/checks/lp-ip-tests.log).
- **sqp-fmt**, `SQP-craft`: `cargo fmt --all -- --check`; [raw log](evidence/checks/sqp-fmt.log).
- **sqp-clippy**, `SQP-craft`: `cargo clippy --locked --workspace --all-targets -- -D warnings`; [raw log](evidence/checks/sqp-clippy.log).
- **sqp-tests**, `SQP-craft`: `cargo test --release --locked --workspace`; [raw log](evidence/checks/sqp-tests.log).
- **runner-docs**, `optimization-jobs`: `cargo doc --locked --no-deps`; [raw log](evidence/checks/runner-docs.log).
- **fcmaes-doc-consistency**, `fcmaes-rust`: `python scripts/check_doc_consistency.py`; [raw log](evidence/checks/fcmaes-doc-consistency.log).
- **baseline-build**, `experiment-craft`: `python scripts/baseline.py build --workspace $WORKSPACE --output $WORKSPACE/build-rehearsal`; [raw log](evidence/checks/baseline-build.log).
- **smoke-final**, `experiment-craft`: `python scripts/baseline.py smoke --workspace $WORKSPACE --output $WORKSPACE/final-smoke`; [raw log](evidence/checks/smoke-final.log).
- **review-final**, `optimization-jobs`: `python scripts/job-api/test_review.py -v`; [raw log](evidence/checks/review-final.log).
- **mcp-final**, `optimization-jobs`: `python scripts/job-api/test_mcp.py -v`; [raw log](evidence/checks/mcp-final.log).
- **integration-final**, `optimization-jobs`: `python scripts/job-api/test_integration.py -v`; [raw log](evidence/checks/integration-final.log).

## Retained numerical smoke results

| Worker | Recorded objective | Required interpretation |
|---|---:|---|
| fcmaes: 2D sphere, seed 1, 100 evaluations | 0.011643188766312476 | best_found; objective and bounds rechecked |
| LP-IP: choose one binary variable, objective offset 5 | 7.0 | numerical_optimum; x=[1,0], numerical bound 7; integrality and feasibility rechecked |
| SQP: 4D simplex quadratic | 0.25 | first_order; x=[0.25,0.25,0.25,0.25], stationarity <= 1e-6 |

All three use a single node with capacity 1 and one task. Repeated identical requests return the same job ID without changing the result journal. Changed specifications under the same key produce request_key_conflict. Changed model bytes under the original hash produce invalid_job. These are native jobs, not mocked solver outputs. See evidence/smoke/summary.json and the retained manifests.

## Findings and deviations

1. The agreed ownership split is supported by the code: Rust owns execution, staging, admission and recovery; Python will own campaigns and scientific reporting. The runner’s hard-coded worker invocation and optimization result processing are the main seams for P1.
2. The existing runtime stages/validates before request-key lookup. Client recovery should use persisted handles and preserve input/worker identity; future fleet design must make immutable resolution explicit.
3. All three pinned solver workspaces have strict Clippy diagnostics under Rust 1.88: fcmaes da.rs:491/:506 (needless_range_loop), LP-IP crates/native/src/lu.rs:1182 (collapsible_else_if), and SQP crates/sqp-job-worker/src/lib.rs:134 (uninlined_format_args). Worker builds and native integration succeed. No upstream code was changed or lint suppressed to hide these issues; FC-01, LP-01 and SQP-01 record the follow-ups. A failed check may stop before subsequent warnings.
4. The first development smoke run incorrectly expected invalid_spec for corrupt input. Actual runner behavior is invalid_job. The checker was corrected and its entire three-worker smoke rerun passed. The failed initial run remains in the evidence.
5. Full workspace checks changed the fcmaes and SQP executable fingerprints. The delivered release-build action and three-job smoke were rerun; final binaries are recorded separately from the initial observations. The shared review/MCP/integration suites were repeated against the final set. No bit-identical-build claim is made.
6. No runtime compatibility fix was necessary. The preserved project LICENSE is byte-identical to the initial commit.

## Unavailable and out-of-scope validation

- The runner reported no systemd user manager. The MCP systemd test passed the systemd_unavailable branch; it did not validate successful detached launch. The container’s systemctl command printed an unavailable message despite exit 0, so that exit code is not positive service evidence.
- No logout/reboot/power-loss, lingering or kernel-enforced resource/escaping-descendant containment checks on the home machines or a suitable systemd VM.
- No real SSH/fleet transfer, multi-node placement, Slurm comparison, GPU/driver, full-load thermal or physical-core/SMT commissioning.
- No full Python-binding wheel matrices, mdBook build, long benchmarks or complete application tutorial sweep. Native Rust/runtime checks are explicitly enumerated above. SQP intentionally ignores one documentation census test; its 217 passing Rust tests and one ignored test are reported separately.
- No generic command, transfer or fleet feature is claimed implemented. No package publication, release tag, remote push or PR was created.

## Delivery and next iteration

The ZIP contains experiment-craft source, evidence and a patch against its initial commit, plus application instructions and file checksums. Upstream source trees, compiled binaries, toolchain caches and virtual environments are excluded; exact source pins and dependency locks support online reconstruction. Raw evidence paths belong to the original container. The retained attempt files are review evidence, not a restorable node backup.

P0’s acceptance requirement—a reproducible pinned build and one small real job per available worker—is met. The strict upstream lint gate remains explicitly open. The next implementation step is OJ-01 in optimization-jobs: extract execution mechanics behind the existing optimization interface, preserve native semantics, and rerun this compatibility baseline before command/fleet additions.
