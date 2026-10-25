# Small mixed scientific suites

Protocol: `877aba377b049b9d041a0cfeae8d8d7ea3ce0e7f38a42e81190023c071d7abd4`

Campaign status: `incomplete` (2 failed, 15 succeeded). A campaign that is not completed gives a snapshot, not a final result.

| Group | Common cap | Replication | Design | Description |
|---|---|---|---|---|
| fcmaes-sphere | 100 evaluations | seed | paired | BiteOpt populations over three common seeds; pipeline validation only |
| lp-ip-choice | 30 wall seconds | deterministic | unpaired | Known small binary model, presolve on/off; deterministic timing repeats |
| sqp-simplex | 100 iterations | start | unpaired | Three distinct constrained starts; preserve first-order and KKT evidence |
| numerical-check | 10 wall seconds | deterministic | unpaired | Known LP/IP and SQP answers checked by a sealed numerical-check command |
| invalid-output | 1 wall seconds | deterministic | unpaired | Deliberate missing required output: must stay failed and visible |
| timeout | 0.2 wall seconds | deterministic | unpaired | Deliberate native timeout: must stay failed and visible |

| Group | Arm | Planned | Complete | Metric (unit) | Complete feasible n | Available feasible n | Mean (complete) | Median (complete) | Target hits / planned; unresolved |
|---|---|---:|---:|---|---:|---:|---:|---:|---|
| fcmaes-sphere | default | 3 | 3 | objective (sum of squared coordinates) | 3 | 3 | 0.003907571236355141 | 7.415380636846597e-05 | 2 / 3; 0 |
| fcmaes-sphere | larger | 3 | 3 | objective (sum of squared coordinates) | 3 | 3 | 0.004716932371889599 | 0.004193232851226772 | 3 / 3; 0 |
| lp-ip-choice | presolve-on | 2 | 2 | objective (model objective) | 2 | 2 | 7 | 7 |  |
| lp-ip-choice | presolve-on | 2 | 2 | bound (model objective) | 2 | 2 | 6.999999999999999 | 6.999999999999999 |  |
| lp-ip-choice | presolve-on | 2 | 2 | gap (native relative gap) | 2 | 2 | 1.2688263138573217e-16 | 1.2688263138573217e-16 |  |
| lp-ip-choice | presolve-on | 2 | 2 | integrality (native integrality violation) | 2 | 2 | 0 | 0 |  |
| lp-ip-choice | presolve-off | 2 | 2 | objective (model objective) | 2 | 2 | 7 | 7 |  |
| lp-ip-choice | presolve-off | 2 | 2 | bound (model objective) | 2 | 2 | 6.999999999999999 | 6.999999999999999 |  |
| lp-ip-choice | presolve-off | 2 | 2 | gap (native relative gap) | 2 | 2 | 1.2688263138573217e-16 | 1.2688263138573217e-16 |  |
| lp-ip-choice | presolve-off | 2 | 2 | integrality (native integrality violation) | 2 | 2 | 0 | 0 |  |
| sqp-simplex | active-set | 3 | 3 | objective (model objective) | 3 | 3 | 0.25 | 0.25 |  |
| sqp-simplex | active-set | 3 | 3 | primal (native primal residual) | 3 | 3 | 0 | 0 |  |
| sqp-simplex | active-set | 3 | 3 | stationarity (native stationarity residual) | 3 | 3 | 7.401486830834377e-17 | 1.1102230246251565e-16 |  |
| numerical-check | check | 1 | 1 |  | 0 | 0 | None | None |  |
| invalid-output | check | 1 | 0 |  | 0 | 0 | None | None |  |
| timeout | check | 1 | 0 |  | 0 | 0 | None | None |  |

## Declared paired differences

Differences are left minus right; only complete feasible pairs enter these descriptive summaries.

| Group | Left arm | Right arm | Metric | Planned | Included | Excluded | Mean difference |
|---|---|---|---|---:|---:|---:|---:|
| fcmaes-sphere | default | larger | objective | 3 | 3 | 0 | -0.0008093611355344589 |

## Native accounting and evidence

| Group | Arm | Feasibility | Claims | Evidence levels | Known work and missing runs |
|---|---|---|---|---|---|
| fcmaes-sphere | default | {"true":3} | {"best_found":3} | {"rechecked":3} | {"evaluations":{"known_runs":3,"known_total":300,"unknown_runs":0},"validation_evaluations":{"known_runs":3,"known_total":3,"unknown_runs":0}} |
| fcmaes-sphere | larger | {"true":3} | {"best_found":3} | {"rechecked":3} | {"evaluations":{"known_runs":3,"known_total":300,"unknown_runs":0},"validation_evaluations":{"known_runs":3,"known_total":3,"unknown_runs":0}} |
| lp-ip-choice | presolve-on | {"true":2} | {"numerical_optimum":2} | {"rechecked":2} | {"nodes":{"known_runs":2,"known_total":2,"unknown_runs":0},"simplex_iterations":{"known_runs":2,"known_total":2,"unknown_runs":0},"validation_evaluations":{"known_runs":2,"known_total":2,"unknown_runs":0}} |
| lp-ip-choice | presolve-off | {"true":2} | {"numerical_optimum":2} | {"rechecked":2} | {"nodes":{"known_runs":2,"known_total":2,"unknown_runs":0},"simplex_iterations":{"known_runs":2,"known_total":2,"unknown_runs":0},"validation_evaluations":{"known_runs":2,"known_total":2,"unknown_runs":0}} |
| sqp-simplex | active-set | {"true":3} | {"first_order":3} | {"rechecked":3} | {"derivatives":{"known_runs":3,"known_total":7,"unknown_runs":0},"functions":{"known_runs":3,"known_total":9,"unknown_runs":0},"iterations":{"known_runs":3,"known_total":4,"unknown_runs":0},"qp_iterations":{"known_runs":3,"known_total":2,"unknown_runs":0},"validation_calls":{"known_runs":3,"known_total":6,"unknown_runs":0}} |
| numerical-check | check | {"unknown":1} | {"unknown":1} | {"unknown":1} | {} |
| invalid-output | check | {"unknown":1} | {"unknown":1} | {"unknown":1} | {} |
| timeout | check | {"unknown":1} | {"unknown":1} | {"unknown":1} | {} |

## All campaign steps

| Step | State | Included / exclusion |
|---|---|---|
| bite-default-4ff289a255a2ac75 | succeeded | included |
| bite-default-982329a8aa3b0d15 | succeeded | included |
| bite-default-f710263e96bda59b | succeeded | included |
| bite-larger-4ff289a255a2ac75 | succeeded | included |
| bite-larger-982329a8aa3b0d15 | succeeded | included |
| bite-larger-f710263e96bda59b | succeeded | included |
| invalid-output | failed | included |
| prepare | succeeded | Shared input preparation; status and raw native result remain in the campaign report |
| sqp-a | succeeded | included |
| sqp-b | succeeded | included |
| sqp-c | succeeded | included |
| timeout | failed | included |
| lp-off-1 | succeeded | included |
| lp-off-2 | succeeded | included |
| lp-on-1 | succeeded | included |
| lp-on-2 | succeeded | included |
| numerical-check | succeeded | included |

Descriptive summaries only; no ranking, significance test or optimality certification.
Fixed-work and fixed-time protocols use declared caps; actual work and early termination remain visible.
Complete-feasible metrics require an accepted complete single-task result, known accounting and feasibility=true.
Available-feasible metrics may include partial or failed runs and are reported separately.
Targets use all planned runs as the denominator; failures, missing and unknown outcomes are unresolved.
Deterministic repeats measure timing reproducibility, not independent quality discoveries.
Elapsed times describe this execution environment and are not home-fleet performance.
