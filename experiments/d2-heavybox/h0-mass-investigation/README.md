# h0: how heavy must the box be to need two ducks?

*Evaluation only, no training (2026-11-24 to 25). Policy: the frozen night 5 push policy L2-s2 (`runs/d2-steering-night5/l2-s2/model.zip`, sha256 `ab82e344b275ce617123cf89b70d998f2dbf9003e7fd8feec437607503dd3366`), one training seed. Starts: the clean stage 1 test set (`experiments/test_sets/stage1_large.json`), per-start seeds 10000 + i. Scripts and per-episode results are in this folder; nothing in `copush/` or `configs/` was changed.*

## Question

The box (0.15 kg) is light enough for one duck to push alone, and about half of L2-s2's successes are one duck pushing. What box makes a solo push fail while two ducks can still succeed?

## Physics (`physics.py`, `slide.py`, `results/physics.json`)

- Box: 0.15 kg, 28 x 10 x 9 cm, friction 1.0 against the floor and every duck part. Duck: 0.74 kg.
- Force to slide the box = friction x weight: 1.47 N at 1x, 2.9 N at 2x, 5.9 N at 4x (confirmed by pulling on the box).
- One duck against a box that cannot move: 1.7 to 2.5 N sustained, bursts of 3.5 to 4.8 N over 0.2 s. Two ducks: about 4.9 N sustained.
- The ducks push mostly with their hips, typically 8 cm up the 9 cm box, so the box rocks (up to about 9 to 10 degrees in a typical push).

Open loop (constant full-speed command, distance in 10 s):

| mass | one duck | both ducks |
|---|---|---|
| 1x | 0.70 to 0.86 m | 1.12 m |
| 2x | 0.48 to 0.49 m | 0.82 m |
| 3x | 0.29 to 0.32 m | 0.62 m |
| 4x | 0.18 to 0.20 m | 0.36 m |
| 6x | 0.05 to 0.06 m | 0.21 m |
| 8x | 0.02 to 0.03 m | 0.19 m |

## Mass sweep (`sweep.py`; both ducks, duck A alone, duck B alone)

"Alone" = the other duck is commanded to stand still every step. Cooperative here = task success with each duck at least 25% of the along-the-line push. 1x, 2x, 2.5x and 3x are on 200 starts (95% Wilson intervals); the rest on 50.

| mass (slide force) | both: task success | both: cooperative | A alone | B alone | falls / tip-overs (both) | steps to success, both: mean (max) |
|---|---|---|---|---|---|---|
| 1x (1.5 N) | 97.5% (94.3 to 98.9) | 50.5% | 59.5% (52.6 to 66.1) | 0.0% (0 to 1.9) | 0 / 0 | 37 (75) |
| 1.5x, 50 starts | 46/50 | 23/50 | 41/50 | 0/50 | 0 / 0 | 42 (61) |
| 2x (2.9 N) | 86.5% (81.1 to 90.6) | 34.5% | 84.5% (78.8 to 88.9) | 7.5% | 1 / 4 | 50 (89) |
| 2.25x, 50 starts | 38/50 | 14/50 | 39/50 | 3/50 | 0 / 0 | 53 (83) |
| 2.5x (3.7 N) | 70.0% (63.3 to 75.9) | 29.0% | 64.0% (57.1 to 70.3) | 9.5% | 0 / 4 | 55 (93) |
| 2.75x, 50 starts | 31/50 | 13/50 | 29/50 | 2/50 | 0 / 1 | 57 (86) |
| 3x (4.4 N) | 49.5% (42.6 to 56.4) | 25.5% | 31.5% (25.5 to 38.2) | 3.0% | 1 / 2 | 61 (98) |
| 4x (5.9 N), 50 starts | 10/50 | 7/50 | 0/50 | 0/50 | 1 / 0 | 72 (100) |
| 6x (8.8 N), 50 starts | 0/50 | 0/50 | 0/50 | 0/50 | 4 / 0 | none |

- Duck A alone is as good as both ducks up to 2x. Both minus A alone on the same starts: +2.0 points (-2.8 to +6.8) at 2x, +6.0 (+0.5 to +11.5) at 2.5x, +18.0 (+10.9 to +25.1) at 3x.
- Duck B alone fails because it does not push (no push at all in 102 of 200 episodes at 1x), not because it is weaker.
- The both-duck numbers are a lower bound: L2-s2 was trained on the light box with a 100-step limit.

## Friction, deeper box, lower centre of mass (50 starts, 2.5x unless noted)

| setting | both: task success | tip-overs | falls | box rocking, 95th percentile |
|---|---|---|---|---|
| 2.5x, as is | 31/50 | 1 | 0 | 9 deg |
| 0.15 kg, box-floor friction 2.5 (same slide force) | 0/50 | 47 | 0 | 36 deg |
| 2.5x, 14 cm deep | 32/50 | 0 | 0 | 2 deg |
| 2.5x, centre of mass 2.5 cm lower | 35/50 | 0 | 0 | 7 deg |

Raising friction instead of mass tips the box. A deeper box or a lower centre of mass removes the tip-overs.

## Conclusion

4x (0.60 kg, 5.9 N to slide) is the lightest box tested where a solo push fails reliably (0 of 50 for either duck), but frozen L2-s2 with both ducks manages only 10 of 50 there. Next (h1): fine-tune the push policy on the 4x box with a longer time limit.

## Files

| file | what |
|---|---|
| `results/physics.json`, `physics.log` | parameters, slide test, wall test, open-loop ladder |
| `results/solo200_1x.json` | 1x, 200 starts, three modes |
| `results/mass50.json`, `results/heavy50.json` | 50-start sweep (1.5x to 3x; 4x and 6x) |
| `results/mass200.json` | 200-start reruns at 2x, 2.5x, 3x |
| `results/fric50.json` | friction 2.5 on the light box |
| `results/deep50.json`, `results/com50.json` | 14 cm deep box; centre of mass 2.5 cm lower (valid reruns) |
| `results/deep50_invalid_inplace_resize.json` | **INVALID.** The box was resized in the compiled model, which gave wrong contacts (24 to 28 falls). Kept for the record; do not use. |
| `results/com50_invalid_no_effect.json` | **INVALID.** The centre-of-mass change did not take effect (episodes identical to the unchanged box). Kept for the record; do not use. |
