# Scientific comparison pipeline check

Campaign: `1b9fb01de78f38a761ebdc0c68a55e36ab90d542367c5edf539435a5b717e4ee`

| Step | State | Kind | Worker/profile | Native claims |
|---|---|---|---|---|
| bite-default-4ff289a255a2ac75 | succeeded | optimization | fcmaes fcmaes.retry/1 | best_found |
| bite-default-982329a8aa3b0d15 | succeeded | optimization | fcmaes fcmaes.retry/1 | best_found |
| bite-default-f710263e96bda59b | succeeded | optimization | fcmaes fcmaes.retry/1 | best_found |
| bite-larger-4ff289a255a2ac75 | succeeded | optimization | fcmaes fcmaes.retry/1 | best_found |
| bite-larger-982329a8aa3b0d15 | succeeded | optimization | fcmaes fcmaes.retry/1 | best_found |
| bite-larger-f710263e96bda59b | succeeded | optimization | fcmaes fcmaes.retry/1 | best_found |
| invalid-output | failed | command |   |  |
| prepare | succeeded | command |   |  |
| sqp-a | succeeded | optimization | sqp sqp.solve/1 | first_order |
| sqp-b | succeeded | optimization | sqp sqp.solve/1 | first_order |
| sqp-c | succeeded | optimization | sqp sqp.solve/1 | first_order |
| timeout | failed | command |   |  |
| lp-off-1 | succeeded | optimization | lp-ip lp-ip.solve/1 | numerical_optimum |
| lp-off-2 | succeeded | optimization | lp-ip lp-ip.solve/1 | numerical_optimum |
| lp-on-1 | succeeded | optimization | lp-ip lp-ip.solve/1 | numerical_optimum |
| lp-on-2 | succeeded | optimization | lp-ip lp-ip.solve/1 | numerical_optimum |
| numerical-check | succeeded | command |   |  |

Native results preserve their own claims, evidence and work counters. A completed run is not an optimality proof.
No cross-profile ranking or home-fleet performance comparison is made. Declared slot-second reservations are admission bounds, not measured slot-hours.
