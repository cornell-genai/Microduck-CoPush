# Microduck-CoPush

Two simulated robot ducks learn to push a box into a target together (Cornell Generative AI
club, fall 2026).

[![PPO: both ducks push the box into the target](docs/media/overnight_ppo_success.gif)](docs/media/overnight_ppo_success.mp4)

**📈 [See the full progress timeline, with clips →](docs/TIMELINE.md)**

## Final goal

Two ducks start anywhere within a set distance of the target, facing any direction. The box can
be anywhere, at any angle. Without a script telling them what to do, the ducks learn to walk to
the box and push it into the target together.

## Current status (2026-11-12)

- **Current stage: Stage 1, random box start (training now).** The box starts in a random spot (up
  to 15 cm off in each direction) and at a random angle (up to 45 degrees). The ducks still start
  touching it.
- **Last finished result:** the ducks start against the box, and the target is 0.60 m ahead and
  0.30 m to the side, so the box has to turn on the way. Our learned controller gets the box in
  60 to 80% of the time when the box starts in a slightly random spot. That ties our best
  hand-written script. From the exact start it practiced on, it's faster than the script (32 vs 54
  steps) and uses both ducks equally. This is preliminary: we tested on only 5 episodes.

**How it works:** each duck walks and pushes with frozen, pretrained neural networks from Pollen
Robotics. On top of that, our controller picks each duck's forward speed and turn rate every 0.2 s.
That controller is trained with reinforcement learning (RL): it tries things in a physics simulator
(MuJoCo) and learns from a score called the reward. The method is PPO (Proximal Policy
Optimization), a standard RL algorithm.

## Progress

Clips play at 2x speed. Click one for the sharper video.

| | |
|---|---|
| [![two ducks pushing](docs/media/two_duck_push.gif)](docs/media/two_duck_push.mp4) | [![push_steer squaring](docs/media/push_steer_squaring.gif)](docs/media/push_steer_squaring.mp4) |
| **1. Two ducks and a box in the simulator.** A hand-written script pushes the box straight. | **2. The script gets a "stop" rule.** It straightens the box, then holds still. |
| [![PPO run A](docs/media/ppo_run_a_final.gif)](docs/media/ppo_run_a_final.mp4) | [![steer overshoot](docs/media/steer_overshoot.gif)](docs/media/steer_overshoot.mp4) |
| **3. First RL success.** The target is straight ahead, and the learned controller pushes it in faster than the script. | **4. A target to the side is out of reach.** The ducks can't turn the box in time. |
| [![pivot_push script](docs/media/overnight_pivot_push_script.gif)](docs/media/overnight_pivot_push_script.mp4) | [![PPO success](docs/media/overnight_ppo_success.gif)](docs/media/overnight_ppo_success.mp4) |
| **5. A pivot script makes it reachable.** One duck waits while the other turns the box, but it's almost a one-duck push. | **6. RL learns the side target.** Both ducks share the push and finish in 32 steps. |
| [![solo push](docs/media/overnight_solo_push.gif)](docs/media/overnight_solo_push.mp4) | [![box lost](docs/media/overnight_box_lost.gif)](docs/media/overnight_box_lost.mp4) |
| **Bug: one duck quits.** Allowed to stand still, duck B walks away and duck A pushes alone. | **Bug: crooked and lost.** Mid-training, the box reaches the target turned 65 degrees, then both ducks leave. |

## The reward function

Every step (0.2 s) the controller gets:

$$
r = w_{pos}\,(d_{before} - d_{after}) + w_{yaw}\,(\theta_{before} - \theta_{after}) - c_{time} + \text{(one-time events)}
$$

In words: points for moving the box closer to the target, points for turning it toward the right
angle, and a small cost for every step that passes. Because it rewards progress, not closeness,
standing next to the target earns nothing.

Current values (reward version v1.1, from [configs/copush.yaml](configs/copush.yaml)):

| Symbol | Meaning | Current value |
|---|---|---|
| $d$ | distance from the box's center to the target's center | in meters |
| $\theta$ | angle between the box and the target (a box turned 180 degrees counts as lined up) | in radians |
| $w_{pos}$ | points per meter the box moves toward the target | 10 |
| $w_{yaw}$ | points per radian the box turns toward the target angle | 1 |
| $c_{time}$ | cost per step | 0.03 |
| $R_{success}$ | bonus for success | +10 |
| $R_{fall}$ | penalty when a duck falls | −10 |
| $R_{box}$ | penalty when the box tips over or is lost | −10 |

**What ends an episode:**
- **Success (+10):** the box's center is inside the 0.40 × 0.20 m target, its angle is within
  15 degrees, and both ducks are standing, all held for 1 s.
- **A duck falls (−10):** its body tilts more than 60 degrees or drops below 7 cm, and it stays down
  for 0.2 s. A quick stumble doesn't count.
- **Box tipped (−10):** the box tilts more than 30 degrees.
- **Box lost (−10):** the box is more than 0.40 m from both ducks.
- **Time runs out:** 100 steps (20 s) with no other ending. There's no extra penalty beyond the
  per-step cost.

Two optional terms exist, but both are off in v1.1:
- a cooperation bonus that pays for both ducks pushing equally
- a penalty for a duck that leaves the box (0.02 per step in v1.2)

Why each value is what it is: [docs/REWARD_LOG.md](docs/REWARD_LOG.md).

## Next steps

- **Finish Stage 1:** reach 80% success with random box starts, tested on 20 held-out episodes
  instead of 5.
- **Start the ducks away from the box,** so they have to walk to it first. That's the next step
  toward the final goal.
- **Make the reward ask for teamwork,** so one duck can't quit and leave the other to push alone.

## Links

| | |
|---|---|
| [SETUP.md](SETUP.md) | install, run the simulator, train, test, troubleshoot |
| [docs/TIMELINE.md](docs/TIMELINE.md) | every milestone and experiment round, with clips |
| [docs/REWARD_LOG.md](docs/REWARD_LOG.md) | each reward version: what changed, why, and the results |
| [experiments/README.md](experiments/README.md) | the experiment for each stage and its results |
| [docs/DEMO.md](docs/DEMO.md) | a 5-minute demo outline |
