# Phase 2, D2 (own view plus partner): random box starts

PPO from phase 1 D2 on stage 1's random box starts (offset up to 0.15 m, angle up to 45°), 1M simulator
steps. Checks every 50k steps on the 50-start check set; never 3 in a row at 80%, so no early stop.

- **Stage 1 test set:** **74%** (17/17, 15/16, 5/17); centralized stage 1 60% (15/17, 13/16, 2/17).
- **Checks:** 50% to 74%, final 66%.
- **Wall time:** 67.7 min.

Results: [results/test_set.md](results/test_set.md), [results/training.json](results/training.json).
Model: `runs/decentral-p2-d2/model.zip`. Back to [the overview](../README.md).
