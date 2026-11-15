# Chirp partner sensing: can two ducks cooperate when they only hear each other?

**Status:** Part 1 done (2026-11-15): the chirp observation is built and tested, and the trained D2
policy was checked zero-shot, with the heading zeroed and (as a diagnostic) with the true heading.
Part 2 (fine-tune with chirps) is training. Part 3 (sweep) not started.

## The question

D2 (each duck runs the same network on its own view plus its partner's exact position and heading)
reaches 74% on the stage 1 test set. A real MicroDuck would not know its partner's exact position. It
could hear it: a chirp gives a rough direction (and maybe a rough distance), once in a while. Does
decentralized control still work with that?

## The chirp observation

Code: [copush/chirp.py](../../copush/chirp.py); tests: [tests/test_chirp.py](../../tests/test_chirp.py).
Everything is a config setting under `chirp:` in [configs/copush.yaml](../../configs/copush.yaml), off by
default (so every earlier config behaves as before).

| setting | default | meaning |
|---|---|---|
| `enabled` | false | on: a decentral controller with `include_partner` hears chirps instead of seeing its partner |
| `interval_s` | 2.0 | seconds between one duck's chirps |
| `direction_noise_deg` | 30 | standard deviation of the bearing error (Gaussian) |
| `distance` | false | on: each chirp also carries a rough distance |
| `distance_noise` | 0.3 | standard deviation of the relative distance error |
| `nominal_distance_m` | 0.20 | the vector length when distance is off (not asked for; needed to keep the size) |
| `heading` | zero | zero: the partner's heading is not heard (0 in the observation); true: the exact heading is filled in (diagnostic only) |

How it works:
- **Same size as D2 (19 numbers),** so the trained D2 policy is reused directly with no warm-start
  tricks. The two partner-position numbers become the heard direction and distance, as a vector in the
  duck's own frame. With distance off the vector has the nominal length 0.20 m (the ducks are 0.19 m
  apart on average on the stage 1 test set).
- **Partner heading is not available from sound,** so its two numbers (sin, cos) are set to 0.
- **Held until the next chirp,** in the duck's own frame (it does not rotate as the duck turns).
- **Staggered:** each duck's chirp times are shifted by its own random offset in [0, interval), drawn at
  every reset, and both ducks hear one chirp at the start of the episode. A chirp is heard at the
  first 0.2 s control step at or after its time.
- The noise comes from the env's seeded random generator, so evaluation with the same seeds repeats.

## The order of work (decentralized track)

1. **Retrain with chirps (Part 2, in progress):** the baseline for realistic sensing.
2. **Missed chirps and front-back direction flips:** the same sense, more realistic.
3. **Randomize the box mass, with observation history:** stops the policy memorizing push timing, and
   the history lets it sense the mass.
4. **Ducks start apart** (reusing the rendezvous settings when available): test chirps until
   performance fails.
5. **Vision, and the box blocking the view:** partner info only when the partner is inside the front
   camera's field of view, within range, and not hidden behind the box. Mix about 30% earlier starts
   into training to avoid forgetting. Vision comes after step 4 because, side by side, the partner is
   about 90 degrees to the side, outside a front camera's view, so vision only matters once the ducks
   start apart.
6. **Final:** distill the combined central controller (from steering and rendezvous) into these
   realistic-sensing ducks.

The idea behind it: the central controller (the privileged teacher) sees everything, and the decentralized
ducks (the students) only get what a real duck could sense. Steps 2, 3 and 5 are built as settings but
**not run yet** (all off by default, with tests):

| setting | default | what it does | value |
|---|---|---|---|
| `chirp.miss_prob` | 0 | chance that a chirp is lost (the duck keeps its last one) | placeholder |
| `chirp.front_back_flip_prob` | 0 | chance that a heard direction is mirrored front to back | placeholder |
| `box.mass_range` | null | the box mass is drawn from [lo, hi] kg each episode | placeholder |
| `obs.history_steps` | 1 | stack the last N observations, newest first (1 = just the current one) | N = 1 keeps the old behavior |
| `vision.enabled`, `vision.fov_deg`, `vision.range_m` | off, 120, 0.8 | partner info only while in the front camera's view and range; otherwise the last chirp (needs chirps on) | placeholders |
| `vision.occlusion` | off | the box blocks the view: the partner is hidden when the line of sight crosses the box (needs vision on) | the box is the real size, 28 by 10 cm |

All "placeholder" values are made up until measured on the real ducks. Code: `copush/chirp.py`,
`copush/vision.py`, `copush/env.py`, `copush/decentral.py`; tests: `tests/test_chirp.py`,
`tests/test_realistic_sensing.py`.

## Runs

| run | what | status |
|---|---|---|
| [zero-shot/](zero-shot/) | trained D2 with chirps, no training, stage 1 test set; plus a diagnostic with the true heading | done |
| [finetune-2s-30deg/](finetune-2s-30deg/) | Part 2: fine-tune D2 with chirps every 2 s, 30 deg, heading removed, stage 1 random box starts, up to 1M steps | training (started 2026-11-15 13:40) |

## Results so far

Zero-shot, 50 test starts: **D2 74% with exact info, D1 60%, D2 with chirps 30 to 42% across four
settings.** Most of that drop comes from the zeroed heading, not the noise: with no noise at all but the
heading zeroed it is 36%. With the true heading filled in (a diagnostic), the same four settings give
50 to 70% (62% at 2 s and 30 deg). Details and tables: [zero-shot/README.md](zero-shot/README.md).

## Ideas (not started)

The partner heading cannot be heard, and zero-shot it was the larger part of the loss. Two ways to get it
back without cheating:
- **Estimate the partner's heading from how its heard position changes between chirps.** A walking duck
  moves along its heading, so two chirps give a direction of travel.
- **Encode the heading in the chirp itself:** each chirp carries a coarse heading (a few bits, for
  example 8 compass directions) along with the direction.
