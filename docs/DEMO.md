# 5-minute demo

Current as of 2026-11-12. Clips are in [media/](media/) and play at 2x speed.

1. **The task (30 s):** two ducks push a box into a target.
   Play: [two_duck_push.mp4](media/two_duck_push.mp4)
2. **How it learns (1 min):** a small neural network gives each duck a forward speed and a turn
   rate every 0.2 s. Walking and pushing come from frozen, pretrained policies, so the network only
   coordinates. It's trained with PPO, a standard reinforcement learning (RL) method.
3. **Where we started (1 min):** the first reward paid more for standing still than for pushing.
   Then a target to the side was out of reach, because the ducks turn the box only about 5 degrees
   every 2 s.
   Play: [steer_overshoot.mp4](media/steer_overshoot.mp4)
4. **Current best (1.5 min):** PPO gets the box into a target 0.30 m to the side. From the start it
   trained on, it's faster than the hand-written script (32 vs 54 steps) and uses both ducks
   equally. With the box starting in a random spot, it succeeds 4 of 5 times, which ties the script
   (preliminary, 5 episodes).
   Play: [overnight_script_vs_ppo_side_by_side.mp4](media/overnight_script_vs_ppo_side_by_side.mp4)
   (script left, PPO right)
5. **What we learned about reward design (1 min):**
   - When we let a duck stand still, it stopped helping: one duck pushed alone, because the reward
     never asks for two.
     Play: [overnight_solo_push.mp4](media/overnight_solo_push.mp4)
   - A cooperation bonus raised the score without changing what the ducks did. Compare success
     rates, not scores.
6. **Next (30 s):** train with the box starting in random spots, and test on 20 or more episodes.
