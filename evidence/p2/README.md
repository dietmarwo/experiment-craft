# P2 evidence

`baseline/summary.json` is the complete accepted 24-step run at the local candidate commits in `sources.json`. `checks/` retains each argv/result and raw output. Compiler builds/tests use Rust 1.88; stable lints and standalone tutorial builds use the recorded stable version. The new workspace reused only the prior compiled dependency cache. Candidate Git URL rewrites were scoped to child processes; no global config or remote repository was changed.

`initial/` retains source/environment/step summaries and the failed native-test logs. Four test invocations failed before executing a cached binary because execute permission was missing. The mode-repair JSON files retain unchanged SHA-256 values; source code was not changed. Both initial worker-test retries and the final complete baseline passed. Initial passing logs are not duplicated.

`compatibility-*-accepted` and `p2-*-sources.json` prove the new runtime with the existing pinned SDK and with the checkout SDK before worker pins moved. `pin-validation.json` checks every changed manifest (including optional tutorial job-worker features). `tutorials/` holds the four stable standalone builds, examples and local job/surrogate runs. `failures/` retains corrected dispatch/discovery test failures and session-driver setup failures.

`baseline/smoke/` keeps native results, neutral records and their summary; it omits copied worker executables and repetitive per-call discovery dumps. `command-example/` keeps build/run specifications, CLI results and the checked 002aff binary answer summary. No compiler output binaries are committed as evidence.

`session-drivers/` are historical session tooling with this workspace layout; use the patch package's portable import/reproduction helpers or `scripts/baseline.py` after the commits are published. Logs contain absolute paths as provenance, not portable configuration. The same 27 project unit tests and five patch-tree/bundle checks are recorded during packaging.
