# Re-evaluating the stage 1 policies on 200 held-out starts

**Status:** done (2026-11-15). Eval only, no training: 30 policies, each on the 200 starts of
`experiments/test_sets/stage1_large.json`, with 95% confidence intervals. The 50-start numbers recorded in the READMEs
were good to only about +-13 points; this checks which earlier claims survive.

**Short version:** the big, structural findings hold (learned policies beat scripts, random-start training helped,
stage 1b's extra training helped, central and decentralized from scratch are the same). The headline "D2 74% against
central and D1 60%, so seeing the partner helps" was **noise**: D2 66%, D1 64%.

## The set and the method

- **Set:** 200 starts over stage 1's full box range, even in box angle (one start in each of 200 equal slices of the +-45
  degrees; 67 / 67 / 66 on the three sides), its own seed (20261115), no start shared with the 50-start test set or the
  check set, never trained on. Provenance: [config.yaml](config.yaml).
- **Evaluation:** one deterministic episode per start, env from `experiments/stage1-random-box-pose/config.yaml` for every
  policy. Rates carry Wilson 95% intervals; a difference between two policies is paired (same starts) with a normal
  interval and an exact McNemar test; groups of seeds use a t interval across seeds. "No measurable difference" means the
  interval contains 0. Everything: [results/reevaluation.md](results/reevaluation.md), per-episode data and metrics:
  [results/comparison.json](results/comparison.json), [results/comparison.md](results/comparison.md). Rerun with
  [run.sh](run.sh) then [make_tables.py](make_tables.py).

## Old (50 starts, superseded) against new (200 starts)

| policy | old, 50 starts (superseded) | new, 200 starts (95% interval) |
|---|---|---|
| stage 1, central | 60% | **58%** (51 to 65) |
| 01_reference (central, fixed start) | 50% | **50%** (44 to 57) |
| stage 1b A (central, hard starts oversampled) | 72% | **70%** (64 to 76) |
| stage 1b B (central, smaller time penalty) | 68% | **65%** (58 to 71) |
| D1 (decentralized, own view) | 60% | **64%** (57 to 70) |
| D2 (decentralized, own view + partner) | 74% | **66%** (60 to 73), the old 74% is outside this interval |
| D2 distilled, 3 seeds (fixed-start runs) | 48%, 48%, 58% | **51%, 49%, 55%** (about 42 to 61 each) |
| pivot_push (script) | 32% | **38%** (32 to 45) |
| push_steer (script) | 18% | **20%** (15 to 26) |
| central from scratch, 10 seeds, mean | 46% | **45%** (40 to 51 across seeds) |
| D2 from scratch, 10 seeds, mean | 40% | **40%** (33 to 47 across seeds) |

Per box-angle side, all policies (successes out of 66 or 67 starts, with intervals) are in the results file. The pattern
is the same everywhere: the learned policies win 52 to 99% on the two easier sides, but on the long-turn side (box
turned more than +15 degrees) every policy wins **0 to 24%**:
stage 1 5%, 01_reference 6%, stage 1b A 21%, B 12%, D1 9%, D2 15%, pivot_push 24%, push_steer 0%.

## Which earlier claims hold?

Paired difference in success on the same 200 starts (percentage points):

| claim (old 50-start evidence) | difference (95% interval) | verdict |
|---|---|---|
| PPO beats 01_reference (60% against 50%) | +7.5 (+1.8 to +13.2) | **holds** |
| PPO beats the best script, pivot_push (60% against 32%) | +19.5 (+10.7 to +28.3) | **holds** |
| PPO beats push_steer (60% against 18%) | +38.0 (+29.7 to +46.3) | **holds** |
| Stage 1b A beats stage 1 (72% against 60%) | +12.5 (+7.7 to +17.3) | **holds** |
| Stage 1b B beats stage 1 (68% against 60%) | +7.0 (+2.5 to +11.5) | **holds** |
| D2 beats the central stage 1 policy (74% against 60%) | +8.5 (+3.7 to +13.3) | holds, but **confounded**: D2 had 1.4M more training steps, and stage 1b A (central, 1M extra steps) is as good (A minus D2: +4.0, -0.1 to +8.1) |
| **D2 beats D1: seeing the partner helps (74% against 60%)** | **+2.5 (-2.2 to +7.2)** | **noise: no measurable difference** |
| D2 wins the long-turn side more than D1 (5/17 against 1/17) | +6.1 (-3.3 to +15.4), n=66 | **noise** |
| D2 wins the long-turn side more than central stage 1 (5/17 against 2/17) | +10.6 (+3.1 to +18.1), n=66 | holds (same extra-training confound) |
| D1 matches the central stage 1 policy (60% against 60%) | +6.0 (+1.5 to +10.5) | does not hold: D1 is higher (extra training again) |
| Stage 1b A did not fix the long-turn side (4/17 against 2/17) | +16.7 (+7.6 to +25.7), n=66 | **not supported**: A raised it from 5% to 21%, though it is still mostly lost |
| Stage 1b B did not fix the long-turn side (1/17 against 2/17) | +7.6 (+1.1 to +14.0), n=66, p = 0.06 | borderline |
| Central from scratch and D2 from scratch are the same (46% against 40%, 10 seeds each) | +5.3 (-3.5 to +14.0) across seeds | **holds: no measurable difference** |
| D2 distilled is the best of the three setups (51% against 46% and 40%, 3 seeds) | 52% (45 to 58) against 45% (40 to 51) | **not supported**: the intervals overlap (only 3 seeds) |

**In plain words**
- **Holds:** learned beats scripted; training on random starts helped; stage 1b's extra training and hard-start
  oversampling helped (A: 58% to 70%); decentralized control costs nothing (D2 66%, against 58% for central stage 1 and
  70% for central with the same extra training); one brain and two are the same when trained from scratch.
- **Noise:** the D2 74% against D1/central 60% (a 14-point gap on 50 starts is inside +-13 points of error), so
  "seeing the partner helps" is not supported (D2 minus D1: +2.5, interval -2.2 to +7.2), nor is D2's advantage on the
  long-turn side over D1.
- **Corrected:** stage 1b A did improve the long-turn side (5% to 21%); the earlier "did not fix it" came from 17 starts.
  The side is still mostly lost for every policy (0 to 24%), the scripted pivot_push being the best at 24%.
- **Caveat on extra training:** D1, D2 and stage 1b A/B all had 1M or more steps than stage 1; comparisons with stage 1
  mix the change under test with extra training.

## Wall time (8 worker processes per policy)

The 200 starts of each policy are dealt out round robin to 8 worker processes (`compare_policies.py --workers 8`); each
worker builds its environment and loads the policy once, and the policies run one after another. Every episode is seeded
by its start, so the results are identical to the sequential run (checked: 200 of 200 episodes identical for D2).

| | wall time per policy |
|---|---|
| all 30 policies | 34 to 57 s each (median 42 s), **21.7 min in total** |
| central policies (stage 1, 1b A and B, 01_reference) | 34 to 41 s |
| D1 and D2 (stage 1 phase 2) | 35 s and 34 s |
| 10 central from scratch | 38 to 47 s |
| 10 D2 from scratch | 42 to 57 s |
| the 2 scripts | 42 s and 47 s |

The earlier one-process-per-policy run took about 2 min 45 s for 5 policies side by side (roughly 160 s per policy on
one core); 8 workers bring a policy to about 35 to 57 s, 3 to 5 times faster per policy. Not 8 times: each worker builds
its own environment, and the slowest worker sets the time. The full per-policy table is in
[results/reevaluation.md](results/reevaluation.md).

## Not re-evaluated

The phase 1 D1 policy, and the earlier stage policies (stand, random, push_forward), were not run on the large set; their
50-start numbers stay as recorded and are superseded in spirit by this one. The 200-start set is a stage 1 set: other
stages need their own.
