# Zero-shot: the trained D2 policy hearing chirps instead of exact partner info

No training. The D2 stage 1 policy (`runs/decentral-p2-d2/model.zip`) runs on the stage 1 test set with
chirps on. Command: [run.sh](run.sh); settings: [config.yaml](config.yaml); full tables and per-episode
data: [results/comparison.md](results/comparison.md), [results/comparison.json](results/comparison.json).

One deterministic episode per start, 50 starts, one noise seed (the env seeds the chirp noise, so reruns
repeat). Under 50 episodes a rate has a standard error of about 7 points, so rows within about 10 points
of each other are not distinguishable.

| policy | success (50) | < -15 deg | -15 to +15 | > +15 deg | falls | box lost | push share A | both touch |
|---|---|---|---|---|---|---|---|---|
| **D2, exact partner info** (reference) | **74%** | 17/17 | 15/16 | 5/17 | 5 | 2 | 51% | 94% |
| **D1, own view only** (reference) | **60%** | 15/17 | 14/16 | 1/17 | 2 | 0 | 48% | 92% |
| chirp every 2 s, 30 deg | 34% | 6/17 | 9/16 | 2/17 | 3 | 1 | 55% | 84% |
| chirp every 2 s, 10 deg | 42% | 7/17 | 12/16 | 2/17 | 5 | 3 | 56% | 88% |
| chirp every 0.5 s, 30 deg | 38% | 7/17 | 12/16 | 0/17 | 5 | 1 | 56% | 90% |
| chirp every 4 s, 60 deg | 30% | 5/17 | 10/16 | 0/17 | 3 | 2 | 54% | 89% |
| *extra:* 2 s, 30 deg, distance heard (30% error) | 34% | 6/17 | 8/16 | 3/17 | 5 | 4 | 55% | 93% |
| *extra:* no noise, every step, heading zeroed | 36% | 6/17 | 9/16 | 3/17 | 3 | 1 | 53% | 89% |

Lazy-duck episodes: 0 in every row except chirp 2 s, 30 deg (1). D2 exact (74%) matches the earlier
stage 1 test-set result, so this pipeline reproduces it.

## What it says

- **Chirps with no retraining cost the policy about 30 to 45 points** (74% down to 30 to 42%), and the
  policy ends up below D1 (60%).
- **The four chirp settings are not distinguishable from each other** (30 to 42%, inside the
  7-point error of each). The trend one would expect (less noise and faster chirps do better) is not
  visible here, and 10 deg is only nominally the best.
- **Most of the drop is not noise, it is the missing heading.** With no noise at all and a chirp every
  step (the exact partner position), but the two heading entries zeroed, the policy gets 36%, the same
  as the noisy settings. The policy was trained with heading entries that are always a unit vector
  (sin, cos), and (0, 0) is a value it has never seen. So this zero-shot test cannot say how much the
  noise itself hurts; fine-tuning (Part 2) is what answers that.
- **The failure looks like overshooting:** 17 to 27 of 50 episodes end with the box farther from the
  target than it started (D2 exact: 1), and 21 to 30 time out (D2 exact: 6). Cooperation holds: both
  ducks touch the box on 84 to 93% of steps, and push share is about even.

## Diagnostic: the same settings with the true partner heading filled in

Not something a duck could hear: [run_true_heading.sh](run_true_heading.sh), results in
[results-true-heading/](results-true-heading/comparison.md). Same four chirp settings, same noisy
direction, but the partner's exact heading is given at every step instead of zeros. It isolates what the
missing heading costs.

| chirp setting | heading zeroed (the real case) | true heading filled in | long-turn side (> +15 deg), true heading | falls / box lost, true heading |
|---|---|---|---|---|
| every 2 s, 30 deg | 34% | **62%** | 0/17 | 4 / 0 |
| every 2 s, 10 deg | 42% | **66%** | 3/17 | 5 / 2 |
| every 0.5 s, 30 deg | 38% | **70%** | 3/17 | 2 / 0 |
| every 4 s, 60 deg | 30% | **50%** | 2/17 | 3 / 0 |
| control: no noise, every step | 36% | **74%** | 5/17 | 5 / 2 |
| D2, exact info (reference) | 74% | 74% | 5/17 | 5 / 2 |

The control row (no noise, true heading) is D2 with exact information, and it reproduces D2's 74%
(37 of 50, the same episodes), so the diagnostic is wired correctly.

- **Restoring the heading brings back 20 to 32 points** (62%, 66%, 70% and 50% against 34%, 42%, 38% and
  30%). Dropping the heading is the larger part of the zero-shot loss, as suspected.
- **With the heading, the noise shows a trend:** the milder the chirps, the better (0.5 s and 30 deg:
  70%; 2 s and 10 deg: 66%; 2 s and 30 deg: 62%; 4 s and 60 deg: 50%). The top three are within the
  7-point error of each other; 4 s and 60 deg is clearly lower. So noise alone costs 4 to 24 points
  here, less than the missing heading did.
- **The long-turn side suffers most from noise:** at 2 s and 30 deg it wins 0 of 17 (D2 exact: 5 of 17),
  and the time-outs rise (15 of 50 against 6).
- **What this means for Part 2:** with the heading removed, the policy has to be fine-tuned to cope.
  Of the zero-shot loss, about 12 points (2 s, 30 deg) are noise and about 28 more are the missing
  heading, so the fine-tuned policy has a lot to recover, and the heading may be the harder part.
