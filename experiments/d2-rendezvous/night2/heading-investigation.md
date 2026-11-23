# Why heading error stayed near 80 degrees in night 2 (diagnosis only, no reward/config change)

*Investigates night 2's open question (SUMMARY.md): position error improved a lot over night 1 (down to 26-30 cm)
but heading error stayed near 80 degrees throughout, essentially random. This is a diagnosis, not a fix: no reward
or training config is changed here (that is night 3's job, once this points at the right change).*

## 1. Can velstand walk and turn at the same time?

`scripts/rl/diag_velstand_turn.py`: one duck, 2-second runs at a fixed command, logging yaw and position every
control step (50 Hz). First the three commands from the task (duck starts at rest):

| run | command | net heading change | mean forward speed | net distance |
|---|---|---|---|---|
| walk_only | vx=0.25, vyaw=0.0 | -2.4 deg | 0.092 m/s | 0.179 m |
| turn_only | vx=0.00, vyaw=0.5 | +46.1 deg | 0.026 m/s | 0.050 m |
| combined | vx=0.25, vyaw=0.5 | +38.4 deg | 0.085 m/s | 0.160 m |

Combined is 83% of turn_only's heading change and 93% of walk_only's forward speed. **There is mild coupling (each
axis loses 7-17% to the other), but walking and turning together works** -- it is not "pick one."

That raised the question of what happens at the smaller vyaw a half-trained policy is more likely to output, so the
same script was re-run (ad hoc, not saved as a permanent CSV) at vyaw = 0.1 to 1.0, both standing and walking:

| vyaw commanded | net heading, standing (vx=0) | net heading, walking (vx=0.25) |
|---|---|---|
| 0.1 | +3.4 deg | +5.7 deg |
| 0.2 | +4.6 deg | +11.0 deg |
| 0.3 | +7.1 deg | +18.4 deg |
| 0.4 | +35.1 deg | +33.8 deg |
| 0.5 | +46.1 deg | +38.4 deg |
| 0.7 | +69.6 deg | +63.1 deg |
| 1.0 | +114.7 deg | +101.0 deg |

**Standing still, there is a hard dead zone**: below about 0.35-0.4 rad/s commanded, velstand barely turns in place
at all (3-7 degrees in 2 seconds -- consistent with `copush.env.VELSTAND_TURN_MIN = 0.5`, the threshold the scripted
`PushSteer` controller already bumps small in-place turn commands up to, to avoid commanding a turn that does
nothing). **Walking removes that dead zone**: at the same small vyaw, a walking duck turns proportionally and
noticeably *more* than a standing one (0.2 rad/s: 11.0 deg walking vs 4.6 deg standing). Only above about 0.4 rad/s
does standing catch up and then turn a little faster than walking.

**So the dead zone is real but conditional: it only bites a duck that has stopped (or nearly stopped) walking.** A
duck still closing its distance has no trouble making fine heading corrections.

## 2. What the trained policy (night 2, seed 1) actually does

Replayed four episodes through the saved model (`runs/d2-rendezvous-night2/s1/model.zip`, deterministic) with every
command and error logged. Full per-start logs are illustrative examples, not saved as a permanent artifact (easy to
regenerate: see the snippet at the bottom).

**Start 9 -- walks into position while facing backward and never corrects.** Duck A's position error falls
steadily (66.9 cm -> 12.9 cm over the episode) while its heading error oscillates *between 114 and 178 degrees the
entire time* -- it is consistently facing close to the exact opposite of its target heading, with small wobbles, and
makes no sustained attempt to turn around. Walking toward a spot does not require facing it, and the reward does not
seem to make the policy bother.

**Starts 59, 76, 86 -- the policy finds low heading error, then loses it again.** All three dip to within 15 degrees
of the correct heading at some point mid-episode (76 reaches 2.9 degrees at step 15; 86 reaches 1.9 degrees at step
25), while also closing in on position. But the commanded vyaw keeps swinging in large, frequently alternating steps
(start 76, duck A: vyaw +1.50, +1.50, -1.50, +1.08, -1.13, +0.15, +0.20, -1.50, -1.50, +0.87, +0.08 -- sign flips
almost every logged step) even once aligned, so the duck overshoots past the correct heading and the error climbs
back up (76: 2.9 deg at step 15 -> 82.9 deg at step 40). None of the four episodes ever holds both position and
heading inside the arrival tolerance long enough to register a single arrival (matching the 0/200 result).

**So it is neither "standing still with the wrong heading" nor simple circling: it is closing position while
drifting through headings almost at random, occasionally passing near the right one by chance and immediately
passing back out of it.** The heading-error histogram across all 200 x 2 ducks is close to flat from 0 to 180
degrees (72, 58, 43, 43, 41, 33, 31, 42, 37 per 20-degree bin) -- exactly what "essentially random" looks like, not a
bimodal near-0/near-180 split that a facing-backward bias alone would produce.

## 3. Plain recommendation

**(a) Reward reweighting is the most likely fix, not (c) a structural action-space problem.** Section 1 rules out a
hard walk-xor-turn limitation: the duck can make fine heading corrections while walking, which is when almost all
of this drifting happens. The dead zone is real but only matters once a duck is nearly stopped, and most of the
heading failures above happen mid-walk, not at a standstill.

What the reward does not do: reward *holding* a good heading, only the instantaneous error at each step, and weight
heading only 0.3 (vs. 1.0 for position, with position further favoured early in the curriculum since starts are
close -- 15-20 cm against the 0.8 m normalizer -- so a wandering heading costs little compared to the gains from
closing distance). A policy that passes through a good heading and keeps turning anyway is not charged any more for
it than one that stops there, so there is no training signal distinguishing "aligned and holding" from "aligned and
about to leave again."

Suggested direction for night 3 (not applied here): raise `w_yaw` relative to `w_dist` and/or add a term that
rewards *staying* near the target heading for consecutive steps (not just the single all-or-nothing hold_s arrival
bonus, which an oscillating policy rarely survives long enough to collect), rather than changing the action space or
the distance normalizer. (b) a normalization change (e.g. normalizing heading error by something other than pi) is a
smaller, complementary lever worth trying alongside (a), not a replacement for it. (d) nothing else surfaced in this
investigation (no fall-related truncation, no collision interference, and the dead zone -- the one candidate
"something else" -- turned out not to explain the mid-walk oscillation).

## Reproduce

```
scripts/rl.sh scripts/rl/diag_velstand_turn.py                 # the three-command table (section 1)
```

The small-vyaw sweep and the per-start replay (section 1's second table, section 2) were run ad hoc from the
`scripts/rl.sh -c "..."` snippets in this session's history, reusing `diag_velstand_turn.run_one` and
`copush.rendezvous.policy_act` respectively; neither writes a permanent file, since they were exploratory.
