# Twenty structured tutorials through a local campaign

This example runs the twenty-chapter
[structured tutorial series](https://github.com/dietmarwo/optimization-jobs/blob/main/tutorials/structured/README.md)
as one campaign. Clone optimization-jobs, LP-IP-craft, SQP-craft and
fcmaes-rust next to this checkout, install the series' requirements, and build
`optimization-run`, `lp-ip-job-worker` and `sqp-job-worker` into one directory.
Build the original truss FEM replay helper and set `TRUSS_REPLAY_BIN` as the
series' setup describes. The chapters come from those checkouts, not from the
commits in `baseline-lock.json`.

```bash
python examples/campaigns/structured-tutorials/run.py --bin-dir /absolute/binaries --output /absolute/new/structured-campaign
```

The example creates its own foreground test node. Twenty command jobs run
the canonical application scripts; a dependent checker consumes their
sealed summaries. Two LP jobs vary presolve on the same allocation model,
and two SQP jobs vary backend on the same simplex model. The comparison
protocol is sealed before execution. Every step stays in the report, which
is written before the campaign's status is judged; the run exits 1 unless all
steps succeed.

Command artifacts retain application-reported numerical evidence. The
comparison engine does not infer solver claims from command exit status.
Formulation, mesh and cross-solver comparisons remain descriptive; the two
formal native comparison groups use only existing supported settings.

The scripts read the trusted sibling checkouts and installed Python
packages, with launch-time identity checks. Keep those sources unchanged
during execution. This example tests local foreground execution and checked
dependencies. It does not commission remote machines or demonstrate logout
survival.
