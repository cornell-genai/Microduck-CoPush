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
- **Status:** starting. Stage 1 (random box starts up to 15 cm and 45 deg) succeeds on 60% of its
  50 test starts; the long-turn side (box turned more than +15 deg) only 2 of 17. Stage 1b's two
  fixes (oversampling hard starts, a smaller time penalty) did not fix it (4 of 17 and 1 of 17).
- **Next steps:**
  1. Stand-still action (lets one duck hold so the other pivots the box) on the stage 1 hard starts.
  2. If that is not enough: a reward for pointing the push face at the target.
  3. Widen the box angle range beyond ±45 deg with auto-widen.

### Rendezvous (Winston)

- **Controller:** central. **Branch:** `rendezvous`. **Folder:** `experiments/rendezvous/`.
- **Status:** starting. All runs so far start with both ducks touching the box.
- **Next steps:**
  1. A gap behind the box: the ducks start a short distance back, with and without a reward for
     approaching the box.
  2. Then the ducks start apart and have to come together at the box.
  3. Every time: check the stage 1 test set for forgetting.

### Decentralized (Ashwin)

- **Controller:** D2. **Branch:** `d2-from-scratch`. **Folder:**
  `experiments/d2-from-scratch-comparison/`.
- **Status:** fixed-start comparison done, and all stage 1 policies re-evaluated on 200 held-out starts. D2
  (copied from the central controller, then trained) wins 66% (60 to 73), D1 64% and central stage 1 58%: no
  measurable difference between D2 and D1 (the 50-start 74% against 60% for D1 was noise), and central with the same
  extra training (stage 1b A) reaches 70%. Trained from scratch on the fixed start, D2 matches central from
  scratch (40% against 45%, 10 seeds each, no measurable difference), with more idling and over-turning;
  distilled D2 reaches 52% (3 seeds).
- **Next steps:**
  1. Ducks start apart (reusing the rendezvous settings when available): compare D1, D2 with exact info and
     central there. On stage 1, where the ducks start side by side, partner info does not measurably
     matter (D1 = D2 on 200 starts), so this is where it could.
  2. Partner sensing tests (chirps, then vision) come after step 1, on that setup: stage 1 cannot show a
     difference from the ducks' sensing. Partner sensing by chirps: each duck hears a noisy direction to its
     partner every few seconds instead of its exact position and heading. First checks are on the
     `chirp-partner-sensing` branch (chirps cost nothing measurable on stage 1: 63% against 66% for exact info).

## Decisions so far

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
