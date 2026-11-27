# Roadmap

The living plan. Each owner edits only their own track section; decisions are added at the bottom,
one dated line each. Results live in each track's `experiments/` folder, rules in
[AGENTS.md](AGENTS.md).

## Final goal

Both ducks and the box start anywhere within a set radius of the target, at any angle, and the ducks
walk to the box and push it into the target together.

## How the pieces combine

1. **Steering** and **rendezvous** each find the central-controller settings that solve their part:
   turning the box from any angle, and getting two ducks that start apart to the box together.
2. Those settings are combined into **one curriculum** for the central controller, checked on every
   earlier test set so nothing is forgotten.
3. The final central controller is **distilled into per-duck controllers** (each duck runs on its own
   view).
4. That is compared with **D2 trained from scratch** on the same task, to see whether decentralized
   control needs the central teacher at all.

## Tracks

### Steering (Anmol)

- **Controller:** central. **Branch:** `steering`. **Folder:** `experiments/steering/`.
- **Status:** the long-turn blind spot is fixed on the Stage 1 range. With a real stand-still action,
  two central-policy seeds win 96% and 98% overall and 92% and 97% on the long-turn side, against
  66% and 68% overall and 21% and 18% long-turn for matched continued-training controls (200
  held-out starts). Both learned policies pivot on all 66 long-turn starts. Results:
  [experiments/steering/](experiments/steering/README.md).
  Small duck-noise adaptation is also complete (two seeds, 200 starts per policy/set). It gives no
  measurable noisy-set gain (-1.25 points, 95% CI -4.75 to +2.25) and reduces clean success by 3.75
  points (95% CI -6.77 to -0.73), concentrated on long-turn starts. Keep the original policies,
  which already win 94% and 91% on the noisy set. See the
  [noise result](experiments/steering/README.md#small-duck-start-noise).
- **Next steps:**
  1. Compare central and D2 on identical clean/noisy sets and document training histories; inspect
     box-loss and long-turn regressions before another noise-training change.
  2. Keep stand-still and widen the box angle range beyond ±45 deg with auto-widen.
  3. Check every wider-angle policy on the Stage 1 set for forgetting.
  4. Track the anchor/pusher role split (duck A currently does 77-80% of pushing), both-held stalls
     and the remaining near-target time-outs as the range grows.

### Rendezvous (Winston)

- **Controller:** central. **Branch:** `rendezvous`. **Folder:** `experiments/rendezvous/`.
- **Status:** starting. All runs so far start with both ducks touching the box.
- **Next steps:**
  1. A gap behind the box: the ducks start a short distance back, with and without a reward for
     approaching the box.
  2. Then the ducks start apart and have to come together at the box.
  3. Every time: check the stage 1 test set for forgetting.

### Decentralized (Ashwin)

- **Controller:** D2. **Branches:** `d2-steering` (current; renamed from `d2-from-scratch`, whose work is merged) and
  `chirp-partner-sensing` (merged). **Folders:** `experiments/d2-steering/`, `experiments/d2-from-scratch-comparison/`,
  `experiments/chirp-partner-sensing/`.
- **Status:** fixed-start comparison done, and all stage 1 policies re-evaluated on 200 held-out starts. D2
  (copied from the central controller, then trained) wins 66% (60 to 73), D1 64% and central stage 1 58%: no
  measurable difference between D2 and D1 (the 50-start 74% against 60% for D1 was noise), and central with the same
  extra training (stage 1b A) reaches 70%. Trained from scratch on the fixed start, D2 matches central from
  scratch (40% against 45%, 10 seeds each, no measurable difference), with more idling and over-turning;
  distilled D2 reaches 52% (3 seeds). Partner sensing by chirps (D2 fine-tuned with a noisy partner direction
  every 2 s and no partner heading) wins 63% of 200 held-out starts with both seeds, the same as D1 (64%) and D2
  with exact info (66%): no measurable effect on stage 1. The partner's true heading, a diagnostic, adds nothing
  measurable either (64%, +0.5 points, -3.6 to +4.6); it only changes how much the ducks idle.
- **Next steps:**
  1. Ducks start apart (reusing the rendezvous settings when available): compare D1, D2 with exact info and
     central there. On stage 1, where the ducks start side by side, partner info does not measurably
     matter (D1 = D2 on 200 starts), so this is where it could.
  2. Partner sensing tests come after step 1, on that setup (stage 1 cannot show a difference from the ducks'
     sensing), in this order: chirps (done on stage 1: no measurable effect), then missed chirps and front-back
     direction flips, then a randomized box mass with a short observation history, then vision with the box
     blocking the view (side by side the partner is about 90 degrees to the side, outside a front camera's view;
     each duck sees its partner on under 10% of steps), mixing about 30% earlier starts into training to avoid
     forgetting. The settings for these are built and off by default (`chirp.miss_prob`,
     `chirp.front_back_flip_prob`, `box.mass_range`, `obs.history_steps`, `vision.*`), with placeholder values
     until measured on the real ducks; `experiments/chirp-partner-sensing/` has the results and the plan.
  3. Last: distill the combined central controller (from steering and rendezvous) into these realistic-sensing
     ducks.

#### Steering and start noise (d2-steering)

Results: [experiments/d2-steering/](experiments/d2-steering/README.md); rejected nights in
[negative-results/](experiments/d2-steering/negative-results/). All numbers are on 200 held-out starts.

- **Night 1:** added a stand-still action, so one duck can wait while the other pivots. The long-turn side went
  from 15% to 74%.
- **Night 2:** fixed 2M-step budgets, 2 seeds. Run A reaches 94-96% overall. Training with start noise (run B) was
  measurably worse (-7.8 points overall).
- **Night 3 (rejected):** a -0.05 penalty when both ducks hold did not reduce stalls.
- **Night 4 (rejected):** capping exploration made the policy measurably worse (-17.2 points). Stalls are not
  caused by deterministic evaluation: sampling actions instead changes success by only -3.2 to +4.0 points.
- **Night 5:** wider start noise. A drops 13.5 points on L2 starts. Training on L2 directly recovers +6.5 overall
  and +14.4 on the long-turn side. No gradual step through L1 was needed.
- **Remaining failures:** mostly both ducks holding still (38 of the 47 failures on L2 starts). They stop about 70% of the
  way to the target, then sit idle for the rest of the episode (median stop at step 38 of 100). Of the 38, 10 end
  with the box inside the target and fail on the 15-degree angle test or the 1-second hold, and 18 more end within
  5 cm of it. A held duck cannot turn, so it has no small correction move.
- **Next (night 6):** let a held duck turn in place (speed zero, turn command passes through), trained on L2
  starts, warm-started from the L2 seeds.
- **Later:** a separate approach skill to bring each duck from anywhere to its docking spot, so the two chain into
  fully random starts.

## Decisions so far

- 2026-11-21: keep the central stand-still action. Against matched fixed-budget controls it raises
  success by 30.2 points overall (+24.2 to +36.3) and 75.0 points on the long-turn side (+65.2 to
  +84.8), with 96-98% overall success across two seeds. Widen the box-angle range next.

- 2026-11-12: Stage 1b's two fixes for the long-turn side failed (4 of 17 and 1 of 17 against 2 of
  17); keep the tooling and the negative result.
- 2026-11-12: D2 (own view plus partner) matched the central controller (74% against 60%, within what
  similar extra training gives central: 72%).
- 2026-11-13: Distillation into per-duck controllers moves to the end, after the central controller
  solves the full task.
- 2026-11-13: Anmol and Winston work on the central controller; Ashwin on decentralized.
- 2026-11-13: The default controller in `configs/copush.yaml` is central again; D2 stays selectable.
- 2026-11-14: 10 seeds: D2 from scratch matches central; distillation still planned for the end.
- 2026-11-15: Results are reported on the 200-start stage 1 set (`stage1_large.json`) with 95% intervals.
  The 50-start comparisons were mostly noise (a rate on 50 starts is good to about +-13 points); the re-evaluation
  is in `experiments/stage1-reevaluation/`.
- 2026-11-15: The long-turn side (box turned more than +15 degrees) is every policy's bottleneck: on 200 held-out
  starts every policy wins 0 to 24% of these starts (stage 1 5%, stage 1b A 21%, D2 15%, the pivot_push script
  24%), while the learned policies win 52 to 99% of the two easier sides.
- 2026-11-15: Partner-sensing tests (chirps, vision) move to after the ducks-start-apart setup, since on stage 1
  partner info does not measurably matter.
- 2026-11-15: The decentralized track focuses on realistic sensing (chirps, vision) as the student side of a
  privileged-teacher pipeline: the central controller sees everything, and the per-duck controllers only get what a
  real duck could sense.
- 2026-11-15: Chirps (and the partner's true heading) have no measurable effect on stage 1: 63 to 64% against 66% with
  exact info on 200 held-out starts (`experiments/chirp-partner-sensing/`). Vision and the box blocking the view come
  after the apart-start step, since side by side each duck sees its partner on under 10% of steps.
- 2026-11-15 (corrections from the 200-start re-evaluation, `experiments/stage1-reevaluation/`): (1) D2 does not
  beat D1 by a measurable amount (D2 66%, D1 64%; the 50-start 74% against 60% was noise), so "seeing the partner
  helps" is not supported. D2 and D1 are above central stage 1 (58%) but had 1.4M more training steps, and central stage
  1b A (same extra training) reaches 70%; the 2026-11-12 decision above that read D2 as matching central stands. (2) Stage 1b's fixes did
  help the long-turn side (A from 5% to 21%, B to 12%), though it is still mostly lost; the 2026-11-12 line calling them
  failures came from 17 starts. The Steering section above still carries the 50-start numbers (Anmol's section, not edited).

## Open questions

- Is the long turn a missing action (stand still) or a missing reward signal (pointing)?
- In what order, or mix, should steering and rendezvous settings go into the combined curriculum?
- After distillation, should the two ducks share one network or have separate ones?
- How should the D2-from-scratch comparison count the central teacher's training: as a head start,
  or as part of the budget?
- How far apart can the ducks start before walking to the box dominates training time?
