# Prepare sweep and check

Campaign: `3ef47f11bccd00c5d12c4e06e45f5d37133cca7878abe7fe1c7ac9c97dd958b2`

| Step | State | Kind | Worker/profile | Native claims |
|---|---|---|---|---|
| prepare | succeeded | command |   |  |
| fcmaes-4ff289a255a2ac75 | succeeded | optimization | fcmaes fcmaes.retry/1 | best_found |
| fcmaes-982329a8aa3b0d15 | succeeded | optimization | fcmaes fcmaes.retry/1 | best_found |
| fcmaes-f710263e96bda59b | succeeded | optimization | fcmaes fcmaes.retry/1 | best_found |
| lp-ip | succeeded | optimization | lp-ip lp-ip.solve/1 | numerical_optimum |
| sqp | succeeded | optimization | sqp sqp.solve/1 | first_order |
| check | succeeded | command |   |  |

Native results preserve their own claims, evidence and work counters. A completed run is not an optimality proof.
No cross-profile ranking or home-fleet performance comparison is made. Declared slot-second reservations are admission bounds, not measured slot-hours.
