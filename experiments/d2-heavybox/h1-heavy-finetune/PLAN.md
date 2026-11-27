# h1 plan: fine-tune the push policy on a box one duck cannot push alone

*Written 2026-11-25, before launching. Config: [../h1-heavy-finetune.yaml](../h1-heavy-finetune.yaml). Run script: `scripts/rl/run_h1_heavy_finetune.py`. Background: [../h0-mass-investigation/README.md](../h0-mass-investigation/README.md).*

## Why

The box (0.15 kg) is light enough for one duck to push alone. The frozen push policy (night 5 "L2-s2") learned roles: duck A pushes, duck B steadies and often does not push, and about half of its successes are one duck doing under 25% of the pushing. At 4x the mass, a solo push failed 0 of 50 times for either duck in h0, but the frozen policy with both ducks managed only 10 of 50, because it never trained on that box.

## What changes (one change: the box task)

Everything else is night 5's Run L2: reward v1.1 terms, L2 duck start noise (heading up to 30 degrees, spacing up to 8 cm), stage 1 box range, the stand-still action, the same PPO (proximal policy optimization) settings, 2M duck steps. The default config does not change in this run (note added 2026-11-27: after the run the heavy box was made the default, and earlier configs pin the light box).

| setting | now | h1 | why |
|---|---|---|---|
| box mass | 0.15 kg | **0.60 kg** (4x; 5.9 N to slide) | lightest box in h0 where a solo push failed for both ducks |
| box size, friction | 28 x 10 x 9 cm, 1.0 | unchanged | a deeper box moves the docking spots; more friction tips the box |
| time limit | 100 steps (20 s) | **130 steps (26 s)** | see below |
| time penalty | 0.03 per step | **0.023077 per step** (reward version `v1.1-t130`) | a full episode still costs -3 (3 / 130) |
| mass randomization range | 0.10 to 0.25 kg | 0.40 to 1.00 kg (4x) | set, but not active: Run L2 trained with a fixed mass, and so does h1 |
| test and check sets | 200 starts | the same starts with the shortest targets removed | see below |
| warm start | night 2 Run A | **L2-s2** (`runs/d2-steering-night5/l2-s2/model.zip`) | fine-tune the official push policy |

### Time limit

Open-loop speed on the 0.60 kg box (h0, full command, 10 s): one duck 0.0195 m/s (the faster of the two), two ducks 0.0357 m/s.

Target distances (from [results/targets.json](results/targets.json)). "Centre" is box start to target centre. "To enter" is how far the box centre must travel before it is inside the target, which is what success needs; the target is 40 x 20 cm, so this is 10 to 20 cm shorter.

| set | n | centre: min / 10th / 50th / 90th / max (m) | to enter: min / 10th / 50th / 90th / max (m) |
|---|---|---|---|
| clean (`stage1_large`), L1, L2 (same box poses) | 200 | 0.50 / 0.56 / 0.68 / 0.79 / 0.87 | 0.39 / 0.45 / 0.57 / 0.68 / 0.75 |
| noisy (`stage1_noisy_large`) | 200 | 0.49 / 0.56 / 0.68 / 0.79 / 0.87 | 0.38 / 0.45 / 0.56 / 0.68 / 0.75 |
| old check set (`stage1_checks`) | 50 | 0.50 / 0.56 / 0.67 / 0.81 / 0.86 | 0.39 / 0.45 / 0.56 / 0.70 / 0.74 |
| old noisy check set (`stage1_noisy_checks`) | 50 | 0.49 / 0.58 / 0.68 / 0.78 / 0.84 | 0.38 / 0.46 / 0.57 / 0.67 / 0.72 |

- **Decision: 130 steps (26 s).** Two ducks cover 0.93 m in 26 s, 37% more than the 90th-percentile distance to enter the target on the test sets (0.675 m) and 33% more than the largest 90th percentile of any set (0.70 m). The rule was at least 30%.
- **I used the distance to enter the target, not the centre distance,** for both the two-duck margin and the solo reach. By centre distance 26 s gives two ducks only 18% margin over the 90th percentile (0.785 m), and reaching 30% would take 29 s, where one duck alone could reach the edge of close to half of the targets.
- **One duck in 26 s covers 0.507 m.** That reaches the target for 59 of 200 starts (29.5%) on the clean, L1 and L2 sets and 58 of 200 on the noisy set (by centre distance it would be 4 of 200). That is over the 20% line, so the heavy-box sets leave those starts out.

### Heavy-box sets (new files; the old ones are untouched)

- **Test sets:** `experiments/test_sets/stage1_heavy_{clean,noisy,L1,L2}_large.json`: the same starts, ids and episode seeds as the 200-start sets, without the starts whose box needs to travel less than 0.507 m to enter the target. 141 starts each (noisy: 142). These are below the 200 starts AGENTS.md asks for, so their intervals are wider (about +-8 points).
- **Check set:** `experiments/test_sets/stage1_heavy_checks.json`, 200 new starts (300 drawn over the same box range with a new seed, the short targets removed, the first 200 kept), L2 duck start noise, episode seeds 20000 + id. No box pose repeats a test-set one. A new set was needed anyway: the old check sets have 50 starts, too few for the decision rule below.
- **Training starts are not trimmed.** Training samples the full stage 1 box range, as Run L2 did.

### Start check

A start with noise is redrawn if the box moved more than 1 cm or turned more than 2 degrees while the ducks settled (`copush/env.py`). With a heavy box a duck placed into the box moves it less, so the check could miss more bad starts. Measured on 500 L2-noise training starts each ([results/start_check.json](results/start_check.json)): **0 rejected on the light box, 7 of 507 draws (1.4%) on the heavy box.** So the check does not get weaker in count; it fires slightly more often. The check is kept as it is.

## Training

- 3 seeds (PPO seeds 1, 2, 3), all warm-started from L2-s2. 2M duck steps each (1M simulator steps), as Run L2.
- Every 200k steps a checkpoint is kept and evaluated on the check set (200 starts).
- **Early stop:** a seed with 0 task successes on the check set at 400k steps stops there and is reported.
- **Pick, per seed:** the checkpoint with the most cooperative successes on the check set (contact impulse, 25%). Ties go to more task successes, then the earlier checkpoint.

## Decision rule (written before the run)

Cooperative success = task success and each duck at least 25% of the contact impulse (contact force on the box, added up over the episode). A solo test forces one duck to stand still for the whole episode.

**h1 works if, on the check set, both hold:**
1. **Cooperative success is measurably above frozen L2-s2 on the same heavy box.** Paired on the same 200 starts, the picks of the trained seeds averaged per start, minus frozen L2-s2: the 95% interval excludes 0 and every seed is on the same side.
2. **Both solo tests stay under 10% task success:** duck A idle and duck B idle, for every seed's pick.

**Add the balanced-push bonus next** (commit `be67cb3`, `reward.cooperation_mode: gated_balanced`, off by default) **if** h1 meets the solo rule (2) **but** duck B (or either duck) still does under 25% of the pushing in more than a third of a seed's successes.

If rule 1 fails, the heavy box alone does not make this policy cooperate better and the bonus is not the next step either: report what the failures are (timeouts, falls, tip-overs) first.

## Evaluation after training (test sets)

Frozen L2-s2 on the heavy box and each seed's pick, on the four heavy test sets:
- task success, cooperative success by both measures (contact impulse and along the box-to-target line, 25%), solo tests (A idle, B idle), the share of the pushing done by the duck doing less (0 to 10, 10 to 25, 25 to 40, 40 to 50%), falls, tip-overs, timeouts, steps to success (mean, max); 95% intervals;
- paired comparisons against frozen L2-s2, seeds averaged per start, same "measurable" rule;
- forgetting check: each pick on the light box (clean 200-start set, 100 steps, original config);
- full pipeline: the r6 rendezvous policy, then the best pick, on `rendezvous_large.json` with the heavy box, against r6 then frozen L2-s2 on the heavy box. The rendezvous policy was trained with the light box and is not retrained;
- 4 clips: two cooperative successes, one failure, one solo test.

## Known limits

- One push policy (L2-s2, one seed) is fine-tuned; the 3 seeds differ only in the PPO seed.
- The open-loop speeds are from one straight push each; a steering policy is slower, so the real margin is smaller than 33%.
- The test sets have 141 starts, not 200.
