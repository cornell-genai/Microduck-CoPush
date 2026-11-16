# Visibility check: can the ducks see each other?

No training. How often does each duck see its partner with a front camera (field of view 120 degrees, range
0.8 m; both are placeholders until measured on the real camera), with and without the box blocking the view?
The trained D2 stage 1 policy on the stage 1 test set (50 starts), run by [run.sh](run.sh) (settings:
[config.yaml](config.yaml)); results in [results/visibility.md](results/visibility.md) and
[results/visibility.json](results/visibility.json).

| run | box blocks the view | duck A sees B | duck B sees A | both see each other |
|---|---|---|---|---|
| D2 acting on exact info (its own trajectories) | no | 6.5% | 5.1% | 0.1% |
| D2 acting on exact info | yes | 6.3% | 2.7% | 0.0% |
| D2 with vision on, chirps out of view | no | 2.5% | 3.3% | 0.0% |
| D2 with vision on, chirps out of view | yes | 2.4% | 2.2% | 0.0% |

**Under 10% in every case, so this confirms the plan:** with the ducks side by side, the partner is about
90 degrees to the side, outside a front camera's view, so vision cannot help until the ducks start apart.
That is why vision comes after the apart-start step (step 5 after step 4 in [ROADMAP.md](../../../ROADMAP.md)).
The box takes a little more away (duck B: 5.1% down to 2.7%). With vision on and chirps as the fallback, the
untrained D2 policy wins 17 of 50 starts, the same as chirps alone (34%), because the camera rarely sees the
partner.
