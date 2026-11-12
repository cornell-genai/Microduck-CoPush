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
4. **Current best (1.5 min):** PPO gets the box into a target 0.30 m to the side. Trained on random
   box starts (up to 0.15 m off, turned up to 45 degrees), it succeeds on 60% of 50 test starts it
   never saw. The policy it started from gets 50%, and the best hand-written script gets 32%.
   Play: [stage1_pivot_push_vs_ppo_hard_start.mp4](media/stage1_pivot_push_vs_ppo_hard_start.mp4)
   (script left, PPO right, on a hard start)
   Be honest about the gap: it fails almost every start where the box is turned more than 15 degrees
   one way (2 of 17). Play: [stage1_failure_positive_angle.mp4](media/stage1_failure_positive_angle.mp4)
   Show the plot: [difficulty.png](../experiments/stage1-random-box-pose/results/difficulty.png)
5. **What we learned about reward design (1 min):**
   - When we let a duck stand still, it stopped helping: one duck pushed alone, because the reward
     never asks for two.
     Play: [overnight_solo_push.mp4](media/overnight_solo_push.mp4)
   - A cooperation bonus raised the score without changing what the ducks did. Compare success
     rates, not scores.
   - Training checks said 80% but the exam said 60%: the 20 check starts happened to be easy. Test on
     a fixed, evenly spread set.
6. **Next (30 s):** fix the one-direction blind spot, then stage 2: the ducks start away from the box.
