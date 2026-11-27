# h1 summary: fine-tuning the push policy on a box one duck cannot push alone

*Run 2026-11-25. Plan and decision rule (written before the run): [PLAN.md](PLAN.md). Tables: [results/results_200.md](results/results_200.md) (200-start test sets, current) and [results/results.md](results/results.md) (check set, 141-start test sets, forgetting, pipeline). Per-episode data: [results/episodes.json](results/episodes.json). Config: [../h1-heavy-finetune.yaml](../h1-heavy-finetune.yaml).*

## Answer to the decision rule

**h1 works, and the balanced-push bonus is not needed next.** Both parts of the rule in PLAN.md hold on the check set (200 starts, heavy box, the set also used to pick each seed's checkpoint):

1. **Cooperative success is measurably above the frozen policy.** The three seeds averaged per start, minus frozen L2-s2 on the same starts: **+37.2 points (95% interval +30.9 to +43.4)**; each seed alone +37.0, +40.0, +34.5. Frozen L2-s2 gets 25.0% (19.5 to 31.4); the h1 picks get 62.0%, 65.0% and 59.5%.
2. **Both solo tests stay under 10% task success for every seed.** Duck B alone (A forced to stand still): 1.0%, 2.5%, 0.0%. Duck A alone (B forced to stand still): 8.5%, 5.0%, 5.5%. Caveat: seed 1's 8.5% has a 95% interval of 5.4 to 13.2, so it is under the line by its point value, not by its interval.

**Bonus rule:** the bonus was to be added if one duck still did under 25% of the pushing in more than a third of a seed's successes. It is 5 of 129 (4%), 3 of 133 (2%) and 1 of 120 (1%). So no.

"Cooperative success" means the box ends in the target and each duck did at least 25% of the pushing, measured by contact impulse (contact force on the box added up over the episode). "Frozen L2-s2" is the official push policy from night 5, trained on the light box and run unchanged on the heavy one. "Measurable" means the 95% interval excludes 0 and every seed is on the same side.

## Test sets, 200 starts each (current; never used for training or picking)

Added 2026-11-27. The four heavy test sets were topped up from 141 (142) to 200 starts: the old starts unchanged, plus new starts drawn from the same distribution (rng seeds 20261127 for clean, L1 and L2, which share box poses, and 20261128 for noisy), keeping only draws that pass the same filter (the box must travel more than 0.507 m to enter the target, so one duck cannot get there in 130 steps at its open-loop speed). No new box pose repeats one in the check set or in any other set. Files: `experiments/test_sets/stage1_heavy_{clean,noisy,L1,L2}_200.json`. All 6,780 old-start episodes (every policy and mode) came out identical to the first run. Full tables: [results/results_200.md](results/results_200.md); per-episode data: [results/episodes_200.json](results/episodes_200.json); script: `scripts/rl/h1_fill_eval.py`.

Heavy box (0.60 kg), 130-step limit (26 s), one episode per start, 95% Wilson intervals. Each cell is task success / cooperative success, with the interval for cooperative success.

| set | frozen L2-s2 | h1 seed 1 | h1 seed 2 | h1 seed 3 | h1 minus frozen, cooperative (3 seeds averaged) |
|---|---|---|---|---|---|
| clean | 32.5% / 24.0% (18.6 to 30.4) | 71.5% / 70.5% (63.8 to 76.4) | 71.0% / 71.0% (64.4 to 76.8) | 69.5% / 69.0% (62.3 to 75.0) | +46.2 (+39.6 to +52.7), measurable |
| noisy | 35.5% / 26.0% (20.4 to 32.5) | 69.5% / 69.5% (62.8 to 75.5) | 71.0% / 71.0% (64.4 to 76.8) | 64.5% / 64.0% (57.1 to 70.3) | +42.2 (+35.8 to +48.5), measurable |
| L1 start noise | 31.5% / 27.5% (21.8 to 34.1) | 67.0% / 63.5% (56.6 to 69.9) | 71.5% / 70.0% (63.3 to 75.9) | 62.5% / 61.0% (54.1 to 67.5) | +37.3 (+30.9 to +43.8), measurable |
| L2 start noise | 31.5% / 26.5% (20.9 to 33.0) | 65.5% / 64.0% (57.1 to 70.3) | 66.5% / 65.0% (58.2 to 71.3) | 61.5% / 60.5% (53.6 to 67.0) | +36.7 (+30.6 to +42.7), measurable |

Task success also rose measurably on every set (+32.8 to +38.2 points). The 200-start numbers agree with the 141-start ones below: every rate is inside the earlier interval.

- **Who pushes.** In h1 successes the duck doing less does 40 to 50% of the pushing in 95 to 100% of successes (per seed and set). For the frozen policy it is 62 to 76%, with 13 to 27% of its successes in the 10 to 25% bucket.
- **Solo tests.** Duck B alone (A forced to stand still): 0.0 to 5.5% (the 5.5% is seed 2 on noisy, 11 of 200). Duck A alone: 2.5 to 8.5% (the 8.5% is seed 1 on clean, 17 of 200, interval 5.4 to 13.2). All under 10% by their point values. Frozen L2-s2 alone: 0 or 1 success per set. Every solo success took 112 to 130 of the 130 steps.
- **Falls and tip-overs.** Falls 0 to 9 per 200 for h1 (frozen 2 to 6); tip-overs 0 to 4 (frozen 0 to 1); box lost 0 or 1 (frozen 0).
- **What the remaining failures are.** Mostly timeouts, which means hitting the 130-step limit: 47 to 71 of 200 per seed and set (frozen: 125 to 134). In 384 of those 710 timeouts (54%) one duck did under 10% of the pushing. 34 to 41 starts per set fail for all three seeds.
- **Speed.** Successes take 70 to 73 steps on average (frozen: 77 to 85); the slowest take 123 to 130.
- **Overshoots** are not recorded and were not measured.

### Margin to the target centre

PLAN.md sized the 130-step limit by the distance the box must travel to ENTER the target. Measured to the target CENTRE the margin is smaller ([results/targets_200.json](results/targets_200.json)):

| distance from the box start | 10th / 50th / 90th percentile / max (m) | two ducks' open-loop reach in 130 steps (0.928 m) over the 90th percentile | starts one duck could reach (0.507 m) |
|---|---|---|---|
| to enter the target | 0.53 / 0.60 / 0.69 / 0.75 | +35% | 0 of 200 |
| to the target centre | 0.64 / 0.72 / 0.80 / 0.87 | **+16%** | 0 of 200 |

So by centre distance the two-duck margin is 16%, not the 30% the plan asked for, and the open-loop speed is an upper bound for a policy that also has to steer. The timeouts are not simply the farthest targets, though: the centre distance of h1's timeouts (mean 0.72 to 0.73 m) is about the same as that of its successes (0.71 m). What causes them was not tested.

## Test sets, 141 starts (superseded by the 200-start sets above)

Heavy box (0.60 kg), 130-step (26 s) limit, 141 starts per set (142 for noisy), one episode per start, 95% Wilson intervals. These sets are smaller than the 200 starts AGENTS.md asks for, because the starts one duck could reach alone were removed (PLAN.md).

| set | frozen L2-s2: task / cooperative | h1 seed 1 | h1 seed 2 | h1 seed 3 | h1 minus frozen, cooperative (3 seeds averaged) |
|---|---|---|---|---|---|
| clean | 32.6% / 22.7% (16.6 to 30.3) | 73.8% / 73.0% (65.2 to 79.7) | 70.2% / 70.2% (62.2 to 77.1) | 71.6% / 70.9% (63.0 to 77.8) | +48.7 (+40.7 to +56.7), measurable |
| noisy | 36.6% / 27.5% (20.8 to 35.3) | 69.7% / 69.7% (61.7 to 76.7) | 72.5% / 72.5% (64.7 to 79.2) | 64.8% / 64.1% (55.9 to 71.5) | +41.3 (+33.8 to +48.9), measurable |
| L1 start noise | 29.8% / 27.0% (20.3 to 34.8) | 65.2% / 61.7% (53.5 to 69.3) | 70.9% / 69.5% (61.5 to 76.5) | 63.1% / 61.0% (52.8 to 68.7) | +37.1 (+29.6 to +44.6), measurable |
| L2 start noise | 32.6% / 27.7% (20.9 to 35.6) | 67.4% / 65.2% (57.1 to 72.6) | 65.2% / 64.5% (56.4 to 72.0) | 64.5% / 63.8% (55.6 to 71.3) | +36.9 (+29.7 to +44.0), measurable |

Each cell is task success / cooperative success, with the interval for cooperative success. Task success also rose measurably on every set (+32.4 to +39.2 points). Between seeds: their intervals overlap on every set, and on clean and L2 there is no measurable difference. On L1 seed 2 is ahead of seeds 1 and 3 in a paired comparison on the same starts (+7.8, interval +0.7 to +14.9, and +8.5, +1.3 to +15.8), and on noisy it is borderline ahead of seed 3 (+8.5, +0.0 to +16.9). Those are 3 of 24 pairwise comparisons with no correction for running that many, so treat seed 2's lead as weak.

- **Who pushes.** In h1 successes the duck doing less almost always does 40 to 50% of the pushing: 95 to 100% of successes per seed and set. For the frozen policy on the heavy box it is 59 to 83%, with 10 to 30% of its successes in the 10 to 25% bucket.
- **Solo tests on the test sets.** Duck B alone: 0.0 to 6.3% (the 6.3% is seed 2 on noisy, 9 of 142). Duck A alone: 2.1 to 9.2% (the 9.2% is seed 1 on clean, 13 of 141). Frozen L2-s2 alone: 0 or 1 success per set. So fine-tuning made a solo push slightly more possible than the plan assumed: every solo success on the test sets took 112 to 130 of the 130 steps (109 to 130 on the check set), so they are starts where one duck just makes it before the limit. PLAN.md sized the sets from an open-loop push speed (0.0195 m/s for one duck); the solo successes suggest a trained duck is a little faster than that, but its solo speed was not measured.
- **Falls and tip-overs.** Few and not worse than frozen: 0 to 6 falls and 0 to 3 tip-overs per 141 starts for h1, against 1 to 5 and 0 to 1 for frozen. Box lost: 0 in the two-duck test-set runs (1 in a frozen solo test; 1 per h1 seed on the check set).
- **What the remaining failures are.** Nearly all timeouts: 34 to 47 of about 141 per seed and set (frozen: 86 to 93). In about half of those timeouts one duck did under 10% of the pushing (12 to 32 per seed and set), which is a duck that lost the box or never got onto it, as in the failure clip. The rest are both ducks pushing and running out of time. 21 of the 141 clean starts fail for all three seeds.
- **Speed.** Successes take 70 to 74 steps on average (frozen: 75 to 84), and the slowest finish at 118 to 130 steps, so the 26 s limit still binds for some starts.
- **Overshoots** are not recorded by this run and were not measured.

## Forgetting check: the light box

Each h1 pick on the original 0.15 kg box, clean 200-start test set, 100-step limit, original config.

| policy | task success | cooperative success |
|---|---|---|
| frozen L2-s2 | 97.5% (94.3 to 98.9) | 50.5% (43.6 to 57.4) |
| h1 seed 1 | 43.5% (36.8 to 50.4) | 40.0% (33.5 to 46.9) |
| h1 seed 2 | 56.5% (49.6 to 63.2) | 43.0% (36.3 to 49.9) |
| h1 seed 3 | 24.5% (19.1 to 30.9) | 17.5% (12.9 to 23.4) |

**h1 forgot the light box.** Task success fell by 56.0 points (50.9 to 61.1) with the seeds averaged; cooperative success fell by 17.0 points (12.4 to 21.6). Most light-box failures are timeouts (82 to 138 of 200). h1 is a heavy-box policy, not a replacement for L2-s2 on the light box. I did not look into why (for example whether the ducks now push too hard for a light box).

## Full pipeline: walk to the box, then push

The r6 rendezvous policy (trained on the light box, not retrained) brings the ducks to the box, then the push policy takes over. Heavy box, `experiments/test_sets/rendezvous_large.json`, 200 starts. The best h1 pick by check-set cooperative success is seed 2.

| push policy | docked | task success | cooperative success |
|---|---|---|---|
| frozen L2-s2 | 168 of 200 | 37.5% (31.1 to 44.4) | 27.5% (21.8 to 34.1) |
| h1 seed 2 | 168 of 200 | 69.5% (62.8 to 75.5) | 64.5% (57.7 to 70.8) |

h1 seed 2 minus frozen, same starts: task success +32.0 (+24.4 to +39.6), cooperative success +37.0 (+29.5 to +44.5). **One push seed, so this is preliminary.** These starts were not trimmed for solo reach, so some may be reachable by one duck.

## Clips

In [gifs/](gifs/), all h1 seed 2 on the L2 heavy test set:
- [cooperative_success_start001.gif](gifs/cooperative_success_start001.gif): success in 71 steps, duck A 53% of the pushing
- [cooperative_success_start002.gif](gifs/cooperative_success_start002.gif): success in 65 steps, duck A 50%
- [failure_start004.gif](gifs/failure_start004.gif): timeout, duck A did all the pushing and duck B never pushed the box
- [solo_test_duck_a_idle_start001.gif](gifs/solo_test_duck_a_idle_start001.gif): duck A forced to stand still; duck B alone times out

## Training

Three PPO (proximal policy optimization) seeds, all fine-tuned from L2-s2, 2M duck steps each, a checkpoint every 200k steps scored on the check set. No seed was stopped early (98, 87 and 81 task successes of 200 at 400k steps). Picks: seed 1 at 1.8M steps, seeds 2 and 3 at the last checkpoint (2.0M). Seeds 2 and 3 scored their best at the last checkpoint, but the check-set score swings by up to 16 successes between checkpoints (seed 2: 126 at 1.2M, 110 at 1.6M, 130 at the end), so this does not show they were still improving. Checkpoints are in `runs/d2-heavybox-h1/s<seed>/` (git-ignored).

## Limits

- One starting policy (L2-s2); the three seeds differ only in the PPO seed.
- The decision rule was scored on the check set, which also picked the checkpoints, so those rates are slightly optimistic. The test sets, which picked nothing, show the same result.
- The first heavy test sets had 141 starts; they were topped up to 200 on 2026-11-27 (section above). The full-pipeline comparison and the forgetting check were not rerun.
- The 130-step limit gives two ducks a 16% open-loop margin to the target centre (35% to entering the target).
- The full-pipeline comparison uses one push seed.
- The run saves two checkpoints close together twice: at 400,000 and 401,408 steps (the early-stop check, then the resume) and at 2,001,408 and 2,002,944 steps (the end). The second pair decided the picks for seeds 2 and 3 (130 against 128 and 119 against 116 cooperative successes, 1,536 steps apart), which is inside the noise of the check set.

## What it means and what next

On a box that needs two ducks, fine-tuning for 2M steps moved the push policy from about a quarter to about two thirds cooperative success, and in almost every success the two ducks split the pushing close to evenly. No reward term for sharing the push was needed. This is one starting policy, and the run changed the box mass together with the time limit and the time penalty, so it does not separate their effects. The problem is not gone from the failures: in about half of the h1 timeouts (384 of 710 over the four 200-start test sets and three seeds) one duck did under 10% of the pushing.

Proposed next step: go after the timeouts, since they are almost all of the remaining failures. Two candidates, one per run: (a) train longer, to find out whether 2M steps is the ceiling (this run cannot tell); (b) look at the timeouts where one duck is off the box and see whether it lost contact mid-push or never docked. Decided 2026-11-27 by the team lead: the heavy box (0.60 kg, 130-step push limit, time penalty 3 / 130 per step) is the official push task, and it is now the default in `configs/copush.yaml`; earlier experiment configs pin the light box through `configs/copush-light-box.yaml`. h1 is the heavy-box push policy; L2-s2 stays the light-box one, because h1 does not work on the light box. The best pick (seed 2) is on the policy release as `d2-push-heavy-h1-s2`.
