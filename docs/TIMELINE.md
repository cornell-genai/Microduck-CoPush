# CoPush timeline

One row per milestone or experiment round, oldest first. Clips play at 2x speed. Reward details
are in [REWARD_LOG.md](REWARD_LOG.md), and the 5-minute demo is in [DEMO.md](DEMO.md).

**Now (2026-11-12):** with both ducks starting against the box, PPO (the reinforcement learning
coordinator) gets the box into a target 0.30 m to the side, which needs a turn. From the start it
trained on, it succeeds and beats the hand-written script. With the box starting in a random spot,
it succeeds 60 to 80% of the time across 3 seeds, which ties the script. That's preliminary: only 5
episodes.

| Date | Stage | One change | Result (plain words) | Eval size | Video |
|---|---|---|---|---|---|
| 2026-11-11 | Two ducks and a box in the sim | First two-duck simulation | A scripted controller pushes the box straight | not measured | [mp4](media/two_duck_push.mp4) |
| 2026-11-12 | Walk to the box, far target | First reward (v1) | Standing still scored better than every controller that pushed | 20 per controller | none |
| 2026-11-12 | In contact, target straight ahead | Reward v1.1 and an in-contact start | Every controller succeeds, even random actions, and PPO run A succeeds 100%. Too easy to tell controllers apart | 5 per controller | [mp4](media/ppo_run_a_final.mp4) |
| 2026-11-12 | In contact, target 0.30 m to the side, 0.40 m ahead | Target moved to the side | No controller succeeds. The ducks can't turn the box in time | 10 per controller | [mp4](media/steer_overshoot.mp4) |
| 2026-11-12 | In contact, target 0.30 m to the side, 0.60 m ahead | New `pivot_push` script and a reachability sweep | The script reaches this target 4 of 5 times, but duck A does 97% of the pushing | 5 randomized per target | [gif](media/overnight_pivot_push_script.gif) |
| **2026-11-12** | **Same layout, PPO** | **First PPO training on this layout (7 runs overnight)** | **PPO succeeds 60 to 80% across 3 seeds with random starts and ties the script. From the fixed start it trained on, it beats the script. None of the 4 tweaks changed results beyond the seed spread** | **5 randomized + 1 fixed (preliminary)** | [gif](media/overnight_ppo_success.gif) · [side by side](media/overnight_script_vs_ppo_side_by_side.mp4) |

---

## 2026-11-11: two ducks, one box

- Two simulated MicroDucks, a box and a target area in MuJoCo. Each duck walks with frozen,
  pretrained policies, and our code only picks speed and turn rate.
- A scripted controller pushes the box straight.

## 2026-11-12: the first reward paid for doing nothing

- Under reward v1, standing still scored better than every controller that pushed.
- Bugs found:
  - The scripted push overshot and gave back all its progress.
  - Losing the box was cheaper than trying and missing.
  - A 0.02 s stumble counted as a fall.
- Fix (v1.1): start both ducks against the box. Losing the box now costs as much as a fall, and
  waiting costs more.

## 2026-11-12: target straight ahead was too easy

- Every controller succeeded, including random actions (5 of 5).
- PPO run A succeeded 5 of 5, slightly ahead of the scripts because it learned to push faster.

## 2026-11-12: target to the side was out of reach

- 0 of 10 for every controller. Shoe Push turns only about 5 degrees every 2 s while pushing, so the
  box passes the target before it has turned.

## 2026-11-12: a pivot script makes the side target reachable

- `pivot_push`: one duck stops, the other pushes alone until the box points at the target, then
  both push.
- A sweep over target positions picked the hardest one the script still reaches: 0.60 m ahead and
  0.30 m to the right, 4 of 5 times.

| `pivot_push` script |
|---|
| [![pivot_push script](media/overnight_pivot_push_script.gif)](media/overnight_pivot_push_script.mp4) |

## 2026-11-12, overnight: early RL success on the side target

- 7 PPO runs of 400k steps each. All finished, and all of them learned the task.
- From the fixed start (the one it trained on), PPO succeeds in 32 to 40 steps with both ducks
  pushing about equally. The script takes 54 steps, with one duck doing almost all the work.
- With the box starting in a random spot, PPO succeeds 4 of 5 times (3 of 5 for seed 2), the same
  as the script. This is preliminary: 5 episodes.
- The stand-still action, contact penalty, cooperation bonus and curriculum had no measurable
  effect: they all stayed inside the spread between 3 seeds.

| PPO: both ducks push it in |
|---|
| [![PPO success](media/overnight_ppo_success.gif)](media/overnight_ppo_success.mp4) |

Side by side from the same start, script on the left and PPO on the right:
[overnight_script_vs_ppo_side_by_side.mp4](media/overnight_script_vs_ppo_side_by_side.mp4)

**Odd behavior and bugs:**

| One duck pushes, the other walks away | The box reaches the target crooked, then both ducks leave |
|---|---|
| [![solo push](media/overnight_solo_push.gif)](media/overnight_solo_push.mp4) | [![box lost](media/overnight_box_lost.gif)](media/overnight_box_lost.mp4) |
| Stand-still run, final policy. It still succeeds, because the reward never asks for two ducks. | Contact-penalty run, mid-training (130k steps). The box ends 65 degrees off and is lost. |

- The cooperation bonus pays even on failed episodes, so it rewards balanced contact, not progress.
  No run exploited it yet.
- In seed 2, duck B barely moves and acts as a pivot while A pushes, the same idea as the script.

**Next:** train with the box starting in a random spot, and evaluate on at least 20 episodes.
