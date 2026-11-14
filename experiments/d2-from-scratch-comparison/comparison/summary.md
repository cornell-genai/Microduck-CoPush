# Setup comparison

Runs: `experiments/d2-from-scratch-comparison/runs.yaml`. Steps are simulator steps. Fixed-start numbers come
from each run's deterministic eval episodes (videos/evals.jsonl); test-set numbers from
`experiments/test_sets/stage1.json` (one deterministic episode per start, scripts/rl/compare_policies.py).

| setup | seed | first fixed-start success | final fixed-start eval | final push share A | test success | test push share A | both touching | lazy duck |
|---|---|---|---|---|---|---|---|---|
| central, from scratch | 1 | 70,000 | success, 32 steps, return +15.6 | 49% | 50% | 50% | 98% | 0/50 |
| central, from scratch | 2 | 170,000 | success, 37 steps, return +15.1 | 45% | 28% | 54% | 88% | 1/50 |
| central, from scratch | 3 | 30,000 | success, 32 steps, return +15.2 | 49% | 44% | 53% | 98% | 0/50 |
| central, from scratch | 4 | 200,000 | success, 36 steps, return +14.2 | 48% | 40% | 54% | 93% | 0/50 |
| central, from scratch | 5 | 100,000 | success, 32 steps, return +15.4 | 53% | 32% | 53% | 94% | 0/50 |
| central, from scratch | 6 | 50,000 | success, 32 steps, return +15.3 | 53% | 48% | 52% | 95% | 0/50 |
| central, from scratch | 7 | 25,000 | success, 32 steps, return +15.4 | 50% | 54% | 54% | 87% | 4/50 |
| D2, from scratch | 1 | 75,000 | success, 35 steps, return +15.3 | 46% | 32% | 55% | 92% | 0/50 |
| D2, from scratch | 2 | 50,000 | success, 34 steps, return +14.8 | 53% | 28% | 54% | 94% | 0/50 |
| D2, from scratch | 3 | 150,000 | success, 32 steps, return +15.3 | 56% | 38% | 55% | 93% | 0/50 |
| D2, from scratch | 4 | 50,000 | success, 32 steps, return +14.9 | 50% | 50% | 50% | 98% | 0/50 |
| D2, from scratch | 5 | 25,000 | success, 33 steps, return +15.4 | 51% | 34% | 51% | 91% | 0/50 |
| D2, from scratch | 6 | 125,000 | success, 32 steps, return +14.6 | 45% | 60% | 53% | 97% | 0/50 |
| D2, from scratch | 7 | 125,000 | success, 31 steps, return +15.1 | 55% | 40% | 53% | 93% | 0/50 |
| D2, distilled | 1 | 10,000 | success, 31 steps, return +15.6 | 48% | 48% | 50% | 94% | 0/50 |
| D2, distilled | 2 | 25,000 | success, 30 steps, return +15.7 | 53% | 48% | 52% | 95% | 0/50 |
| D2, distilled | 3 | 25,000 | success, 30 steps, return +15.7 | 49% | 58% | 51% | 91% | 0/50 |

Plots: [learning_curves.png](learning_curves.png), [test_set_success.png](test_set_success.png), [cooperation.png](cooperation.png).
