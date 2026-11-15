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
- **Status:** fixed-start comparison done. D2 copied from the central controller reached 74% on the
  stage 1 test set (central 60%). Trained from scratch on the fixed start, D2 matches central from
  scratch on the test set (40% against 46%, 10 seeds each, no measurable difference), with more idling
  and over-turning; distilled D2 reaches 51% (3 seeds).
- **Next steps:**
  1. Rerun the comparison on harder setups (random box starts, ducks starting apart).

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

## Open questions

- Is the long turn a missing action (stand still) or a missing reward signal (pointing)?
- In what order, or mix, should steering and rendezvous settings go into the combined curriculum?
- After distillation, should the two ducks share one network or have separate ones?
- How should the D2-from-scratch comparison count the central teacher's training: as a head start,
  or as part of the budget?
- How far apart can the ducks start before walking to the box dominates training time?
