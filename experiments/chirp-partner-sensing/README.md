# Chirp partner sensing: can two ducks cooperate when they only hear each other?

**Status:** Part 1 done (2026-11-15): the chirp observation is built and tested, and the trained D2
policy was checked zero-shot. Parts 2 (fine-tune with chirps) and 3 (sweep) not started.

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

## Runs

| run | what | status |
|---|---|---|
| [zero-shot/](zero-shot/) | trained D2 with chirps, no training, stage 1 test set | done |

## Results so far

Zero-shot, 50 test starts: **D2 74% with exact info, D1 60%, D2 with chirps 30 to 42% across four
settings.** Most of that drop comes from the zeroed heading, not the noise: with no noise at all but the
heading zeroed it is 36%. Details and table: [zero-shot/README.md](zero-shot/README.md).
