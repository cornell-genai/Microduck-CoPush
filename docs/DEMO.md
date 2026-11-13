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
   Two follow-up fixes raised the score to 72% (more practice on hard starts) and 68% (a smaller time
   penalty), but the hard side is still 4 of 17 at best.
   Play: [stage1b_stage1_vs_a_long_turn.mp4](media/stage1b_stage1_vs_a_long_turn.mp4) (stage 1 left, more practice right)
   **Then give each duck its own controller:** the same network runs separately on each duck's own view.
   With the partner's position in view, it succeeds on 74% of the same 50 starts (5 of 17 on the hard
   side), and both ducks still share the push. One seed, and central with the same extra training got
   72%, so read it as "as good as one central brain".
   Play: [decentral_stage1_vs_d2_hard_start.mp4](media/decentral_stage1_vs_d2_hard_start.mp4)
   (central left, per-duck right, box turned +32 degrees)
5. **What we learned about reward design (1 min):**
   - When we let a duck stand still, it stopped helping: one duck pushed alone, because the reward
     never asks for two.
     Play: [overnight_solo_push.mp4](media/overnight_solo_push.mp4)
   - A cooperation bonus raised the score without changing what the ducks did. Compare success
     rates, not scores.
   - Training checks said 80% but the exam said 60%: the 20 check starts happened to be easy. Test on
     a fixed, evenly spread set. With 50 evenly spread check starts, the checks matched the exam.
   - Making waiting cheaper (time penalty 0.03 to 0.01) brought back standing still on hard starts.
     Play: [stage1b_b_idle_drift.mp4](media/stage1b_b_idle_drift.mp4)
6. **Next (30 s):** each duck now has its own controller by default. Next: a second seed, separate
   weights per duck, and a fix for the hard side (a long turn, about 55 degrees, before pushing). Then
   stage 2: the ducks start away from the box.
