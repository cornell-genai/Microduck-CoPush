# CoPush sim cheat sheet

`scripts/copush.sh [mode] [options]`. Full guide: [SIM_GUIDE.md](SIM_GUIDE.md).

## Keys (type in the terminal, not the viewer)

| | A | B |
|---|---|---|
| vx +/− 0.05 | W / S | I / K |
| vyaw left/right 0.3 | A / D | J / L |
| policy velstand ↔ shoepush | 1 | 2 |
| stop | X | M |

**Space** stop both · **R** reset · **N** note marker · **Q** quit. A movement key during `--script` takes over manually.

## Flags

| Flag | Meaning |
|---|---|
| `--viewer` / `--headless` | window + keys, real time / no window, ~20× real time (default) |
| `--duration S` | sim seconds (headless default 15; viewer runs until Q) |
| `--script push_forward` | velstand vx 0.2 to the box, shoepush vx 0.2 from first contact |
| `--script push_hold` | same, then steer with `HeadingHoldPush` toward the target |
| `--record` | `video.mp4` with overlay (~0.8× real time headless; slows the viewer to ~0.4×) |
| `--duck-a X,Y,YAW` `--duck-b ...` `--box ...` `--target ...` | start poses (m, m, deg) |
| `--box-mass KG` `--target-size L,W` | box mass, target rectangle |
| `--policy-a` / `--policy-b velstand\|shoepush` | policy at reset |
| `--config FILE` | another YAML (e.g. `runs/<ts>/config.yaml`) |
| `--reward progress` · `--quiet` | reward function · no headless status lines |

## Command recipes (measured in this sim)

| To | Do | What happens |
|---|---|---|
| Approach the box | velstand, vx 0.2 | ~0.075 m/s; reaches a box 0.35 m ahead in ~3.4 s |
| Push | switch to shoepush (1 / 2) at contact, vx 0.2 | pushes with the hips (90–95% of contact) |
| Steer while pushing | vyaw −1.5 … +1.5 | drifts **left** at 0; over 7 s the box turned +21° (−1.5), +30° (0), +75° (+1.5): right turns are weak |
| Turn in place | velstand, vyaw ≥ 1.2 | 1.2 → 1.26 rad/s (here it already turns from ~0.5) |
| Back up | velstand, vx −0.3 | ~0.07 m/s backward; −0.2 does not move |
| Avoid | shoepush with no box ahead | fell in 5 of 6 tries, after 3–8.5 s |

## Record a trial and take reward-hacking notes

1. `scripts/copush.sh --headless --duration 15 --script push_forward --record` (or `--viewer` and drive, pressing **N** whenever something odd happens)
2. Open `runs/<ts>/video.mp4` and `runs/<ts>/notes.md`. The Outcome section is already filled in.
3. In `events.log`, read the `SUSPECT` lines:
   - `contact_share`: one duck does more than 80% of the pushing
   - `bad_part_*`: the duck pushes with its trunk or head more than its hips
   - `spin`: the box turns but doesn't move
   - `reward_vs_dist`: the reward rises but the box gets no closer
   - `fall_*`: a duck fell
   - `edge`: the box keeps crossing the target edge
4. In `state.csv`, plot `cum_reward` against `box_to_target` and `inside`. Gaming looks like reward going up while the distance does not go down.
5. Answer the three questions in notes.md: what the ducks did, whether that was expected, and whether the reward was gamed. Describe each NOTE marker.
