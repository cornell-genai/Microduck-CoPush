# Run 2: Part 2 repeated with seed 2

Identical to Part 2 ([../finetune-2s-30deg/](../finetune-2s-30deg/README.md); chirps every 2 s, 30 degrees, heading
removed) with PPO seed 2 (Part 2 used seed 1). Settings: [config.yaml](config.yaml). Trained 1M simulator steps
(71 min), early stop did not fire (final check-set success 72%).

**Stage 1 test set: 62% (31/50)**; sides 17/17, 13/16, 1/17. Idle share 20.9%, 10 overshoots, 16 time-outs, 3 falls.
Part 2 seed 1 got 60%, so the two seeds differ by 2 points on the test set (and by 4 on the check set, the other way),
well inside the noise of 50 starts. Details: [../diagnostics/README.md](../diagnostics/README.md).
