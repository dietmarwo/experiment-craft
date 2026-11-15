# Domain-evaluator seed and optimizer campaign

This executed example uses the [shared driver](https://github.com/dietmarwo/optimization-jobs/blob/main/tutorials/domain-evaluators/README.md)
and the [hydro-craft walkthrough](https://github.com/dietmarwo/hydro-craft/blob/main/docs/command-jobs.md).
Follow its setup first: four sibling repositories, the verified wheels, Python
requirements, experiment-craft installation, and the runner/two CLI builds.

From the sibling parent with its virtual environment active:

```sh
python experiment-craft/examples/campaigns/domain-evaluators/run.py --sources . \
  --evaluator hydro-craft --output hydro-campaign --workers 2
python experiment-craft/examples/campaigns/domain-evaluators/run.py --sources . \
  --evaluator thermo-craft --output thermo-campaign --workers 2
```

Use `--preset study` for 20,000 evaluations and five seeds per optimizer;
`--seeds 1,2,3,4,5 --evals 400` changes the small exercise explicitly. Output
paths must be new. The smoke preset produces four search jobs and one check
job. Search jobs use fcmaes CMA-ES or DE with serial seeded ask/tell and native
population scoring; `workers` equals each search's reserved CPU slots.

[run.py](run.py) fills [manifest-template.json](manifest-template.json) with
explicit seed × optimizer arms, hashed staged inputs, `needs`, sealed output
bindings and bounded wall/slot budgets. The template's empty `steps` is a
starting point, not a runnable manifest. The generated `source/campaign.json`
is the exact runnable manifest. Individual arm IDs avoid an ambiguous output
binding from a multi-variant matrix; the public campaign schema is unchanged.

The dependent check consumes every sealed `best` output, validates arm identity
and work accounting, and replays parameters through the staged native CLI.
`checks.json` preserves full records plus train/validation/test RMSE (hydro) or
nominal/held-out efficiency (thermo). `report/report.json`, `report/results.csv`
and `report/report.md` retain native execution states, including failed and
blocked rows. A failed prerequisite blocks the check. A failing check still
writes its scientific rows before exiting nonzero. The final summary reports
failure; no row is dropped to make a campaign pass.

The script calls `drive` again after completion and checks that the state and
native job count are unchanged. This is local foreground repeatability, not a
logout/reboot persistence test. The campaign uses existing runner admission,
input staging, supervision, output collection and recovery; it adds no service.

Commands are trusted processes under the runner user and are refused over MCP.
Their native result has no objective, feasibility or optimality claim. The
scientific check is descriptive model evidence; it is not a scientific-comparison
adapter. Hydro's catchment is synthetic and thermo's fixed Rankine model is not
plant qualification. These evaluators remain outside `baseline-lock.json`.
