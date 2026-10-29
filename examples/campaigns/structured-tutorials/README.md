# Twenty structured tutorials through a local campaign

Apply the companion solver and optimization-jobs patches, keep the checkouts
as siblings, install the structured tutorial requirements, and build
`optimization-run`, `lp-ip-job-worker` and `sqp-job-worker`. Build the original
truss FEM replay helper as described in the shared tutorial setup.

```bash
python examples/campaigns/structured-tutorials/run.py --bin-dir /absolute/binaries --output /absolute/new/structured-campaign
```

The example creates its own foreground test node. Twenty command jobs run
the canonical application scripts; a dependent checker consumes their
sealed summaries. Two LP jobs vary presolve on the same allocation model,
and two SQP jobs vary backend on the same simplex model. The comparison
protocol is sealed before execution. All 25 jobs remain in the report.

Command artifacts retain application-reported numerical evidence. The
comparison engine does not infer solver claims from command exit status.
Formulation, mesh and cross-solver comparisons remain descriptive; the two
formal native comparison groups use only existing supported settings.

The scripts read the trusted sibling checkouts and installed Python
packages, with launch-time identity checks. Keep those sources unchanged
during execution. This example tests local foreground execution and checked
dependencies. It does not commission remote machines or demonstrate logout
survival.
