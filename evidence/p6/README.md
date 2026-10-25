# P6 local scientific comparison evidence

Recorded on 25 October 2026 from experiment-craft base
1577721f67a23240c71cceb9022e2ae8e59136a0, the merged P5 implementation and review
fixes. The four public native revisions and worker SDK pin are unchanged from
the merged baseline in baseline-lock.json. Native source checkouts are fresh;
only compiled dependencies were reused.

- [Native baseline](native-baseline/summary.json): all 26 steps, with exact
  source/toolchain/environment/binary records and unedited per-step logs.
- [Campaign checks](campaign/): unit, required real-runtime, source-pin and wheel
  checks; installed-console comparisons outside the checkout create no jobs.
- [Scientific demonstration](scientific-demo/summary.json): 17 real jobs, 15
  successes and two deliberate failures; raw source, state, events, binding,
  native results and both report formats are retained.
- [Comparison report](scientific-demo/comparison/comparison.md): explicit
  designs, cohorts, native accounting, paired differences and all step statuses.
- [Failures](failures/): initial missing lower-bound counter, an undersized test
  fixture budget, the existing cancellation/deadline race under build load,
  and the absent no-isolation build backend. These remain separate from passes.

See the [P6 implementation log](../../implementation-log.md#p6--scientific-comparisons)
for interpretation and retry details. A single ignored upstream SQP census
case is recorded in its native test output; required live suites never skip.
No actual user service, logout/reboot, cgroup, independent home nodes or
home-fleet performance was tested. Real SSH harnesses use a simulated manager.
No binary executable, native build/dependency cache, credential or Library
transfer metadata is retained here. Scratch paths in raw logs are historical.
