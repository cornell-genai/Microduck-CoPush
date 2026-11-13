# Decentralized control: each duck runs its own controller

**Status:** done (2026-11-12). With random box starts, **D2 (own view plus partner) gets 74%** on stage 1's
50-start test set. The centralized stage 1 policy gets 60%, and **D1 (own view only) also gets 60%**. D2 is
the only policy so far to win 5 of the 17 long-turn starts (box turned more than +15°). One seed each.

## The one change

Before this, one controller saw the whole scene and picked commands for both ducks. Now each duck runs the
same network on its own view, in its own frame (x along its heading, y to its left), and picks only its
own forward speed and turn rate. Both ducks share the network weights, the team reward and the episode
endings. Code: [copush/decentral.py](../../copush/decentral.py); tests:
[tests/test_decentral.py](../../tests/test_decentral.py).

- **D1, own view only (15 numbers):** the box relative to the duck, the target relative to the box, the box
  angle error, box speed and turn rate, the duck's own speed, whether it touches the box, and whether it
  is on Shoe Push (the pushing policy).
- **D2, own view plus partner (19 numbers):** D1 plus the partner's position and heading relative to this duck.

Training uses Stable-Baselines3 PPO, with each duck as its own environment entry (8 simulations give 16
entries). Step counts below are simulator steps; the configs count entries, which is twice as many.

## Steps

| step | what | folder | wall time |
|---|---|---|---|
| 0 | Distill: copy the centralized stage 1 policy into D1 and D2 (behavior cloning plus one DAgger round) | [distill/](distill/) | 7.9 min |
| 1 | Phase 1: PPO from the distilled weights, fixed in-contact start (overnight layout), 400k steps | [p1-d1/](p1-d1/), [p1-d2/](p1-d2/) | 25.0, 25.5 min |
| 2 | Phase 2: PPO from phase 1, random box starts (stage 1 range), 1M steps | [p2-d1/](p2-d1/), [p2-d2/](p2-d2/) | 76.1, 67.7 min |

DAgger means the student drives and the teacher labels what it should have done, so the copy learns to
recover from its own mistakes.

## 0. Distillation: how well each copies the central policy

Held-out copy quality (R² = 1 is a perfect copy; 0 is no better than the average command):

| variant | R² forward speed | R² turn rate | mean error, speed | mean error, turn |
|---|---|---|---|---|
| D1 | 0.920 | 0.946 | 0.018 m/s | 0.145 rad/s |
| D2 | 0.951 | 0.963 | 0.011 m/s | 0.115 rad/s |

From copying alone, with no PPO, D1 gets 62% and D2 gets 64% on the test set (teacher 60%). Both succeed from
the fixed start. Seeing the partner makes the copy closer, which makes sense: the central policy knows where
both ducks are. Full table: [distill/results/distill.md](distill/results/distill.md).

## 1. Phase 1: fixed start

The gate passed. Both variants succeed from the fixed start at every training check (3 episodes every 50k
steps, 8 checks each) and in the final run. 01_reference is the centralized PPO policy trained on this start.

| policy | fixed start | test set (not trained on random starts) | < −15° | −15° to +15° | > +15° |
|---|---|---|---|---|---|
| 01_reference (centralized) | success, 32 steps | 50% | 10/17 | 14/16 | 1/17 |
| D1 | success, 30 steps | 38% | 6/17 | 13/16 | 0/17 |
| D2 | success, 31 steps | 48% | 9/17 | 14/16 | 1/17 |

Both variants match the centralized policy on the start they trained on. Fine-tuning on one start cost them
the generality they had copied: 62% → 38% (D1) and 64% → 48% (D2) on random starts. Phase 2 won it back.

## 2. Phase 2: random box starts (stage 1 test set, 50 starts)

| policy | overall | < −15° | −15° to +15° | > +15° (long turn) | mean steps (successes) |
|---|---|---|---|---|---|
| stage1 (centralized) | 60% | 15/17 | 13/16 | 2/17 | 34 |
| D1 (own view) | 60% | 15/17 | 14/16 | 1/17 | 33 |
| **D2 (own view + partner)** | **74%** | **17/17** | **15/16** | **5/17** | 34 |

Training checks (50 fixed check-set starts every 50k steps) never reached 80%, so neither run stopped early.
D1 ranged from 50% to 68%; D2 from 50% to 74%, at 64% to 74% for most of the second half. Its final check was 66%,
and the test set gave 74%. Both are 50-start estimates of the same policy, so treat the luck range as about ±7 points.

### Cooperation and failures (all 50 starts)

| policy | push share A | both ducks touching | lazy duck | falls | box lost | overshoot | timeouts | idle steps |
|---|---|---|---|---|---|---|---|---|
| stage1 | 46% | 86% | 2/50 | 3 | 0 | 14 | 17 | 13.5% |
| D1 | 48% | 92% | 0/50 | 2 | 0 | 4 | 18 | 20.6% |
| D2 | 51% | 94% | 0/50 | 5 | 2 | 1 | 6 | 14.6% |

*Both ducks touching* is the share of steps where both ducks are touching the box. *Lazy duck* is an episode where one duck has under
20% of the contact time. *Idle* is a step where both ducks are commanded below 0.05 m/s.

- **Cooperation got better, not worse.** Each decentralized duck pushes about half the time, both touch the box
  together more often (92 to 94% of steps against 86%), and neither variant has a lazy duck.
- **Monitor flags:** contact_share on 16 to 19 episodes for all three policies, so it isn't new. reward_vs_dist
  rises for D1 (9 against 3). D2 has the most falls (5, against 3) and the only lost boxes (2) and edge flag (1).
- **D1 spins the box on long-turn starts:** it turns the box 182° in total on average there, against the 55°
  needed (stage 1: 38°). Without the partner's position it seems to keep turning instead of committing to the push.
  D2 turns 102° in total and reaches the push in the same 16 of 17 starts.
- **D2 rarely overshoots** (1 against 14) and times out far less (6 against 17).
- Full table: [results/comparison.md](results/comparison.md).

### Does seeing the partner help?

Yes, in every measure here: a closer copy (R² 0.95 against 0.92), a smaller loss in phase 1 (48% against 38%), and
14 points more in phase 2 (74% against 60%), mostly on the long-turn side (5/17 against 1/17). One seed per variant, though.

**Caveat on D2 against centralized:** D2 had 1.4M more training steps than stage 1 (400k + 1M). Stage 1b's
experiment A, centralized with 1M more steps, reached 72% (4/17 long-turn). So D2's gain over stage 1 is within
what extra training alone gives. What it shows is that decentralized control **costs nothing** here, and that the
partner's position is the useful extra input.

## Side-by-side video

Test start 19 (box 10 cm back, 11 cm right, turned +32°): stage 1 times out after 100 steps and D2 succeeds in
41. Local file (videos are git-ignored):
`experiments/decentralized-control/p2-d2/results/videos/side_by_side/start19_stage1_vs_d2.mp4`. A compressed
copy is in [docs/media/](../../docs/media/).

## Next

- A second seed of D2 and D1 to measure the luck range.
- A centralized control run with the same total steps, to separate extra training from the change.
- Separate (not shared) weights per duck, and starting the ducks away from the box.

## Reproduce

```sh
scripts/rl.sh scripts/rl/distill.py --config experiments/decentralized-control/distill/config.yaml   # ~8 min
nohup scripts/rl/overnight.sh --config configs/decentral.yaml >> runs/decentral-20261112/queue.log 2>&1 &   # ~3.3 h
for v in p1-d1 p1-d2 p2-d1 p2-d2; do
  scripts/rl.sh scripts/rl/test_set.py eval --config experiments/decentralized-control/$v/config.yaml \
      --out experiments/decentralized-control/$v/results
done
scripts/rl.sh scripts/rl/compare_policies.py --config experiments/stage1-random-box-pose/config.yaml \
    --test-set experiments/test_sets/stage1.json --policy stage1=runs/stage1-random-box-pose/model.zip \
    --policy d1=runs/decentral-p2-d1/model.zip@own --policy d2=runs/decentral-p2-d2/model.zip@partner \
    --out experiments/decentralized-control/results
scripts/rl.sh scripts/rl/test_set.py side-by-side --config experiments/decentralized-control/p2-d2/config.yaml \
    --left stage1 --right d2 --start 19 --out experiments/decentralized-control/p2-d2/results
```
