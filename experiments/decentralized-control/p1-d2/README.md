# Phase 1, D2 (own view plus partner): fixed start

PPO from the distilled D2 weights on the fixed in-contact start (overnight layout), 400k simulator steps
(800k duck entries), like 01_reference.

- **Fixed start:** success at all 8 training checks and in the final run (31 steps; 01_reference: 32).
- **Stage 1 test set (not trained for it):** 48% (9/17, 14/16, 1/17); 01_reference 50%.
- **Wall time:** 25.5 min.

Results: [results/test_set.md](results/test_set.md), [results/training.json](results/training.json).
Model: `runs/decentral-p1-d2/model.zip`. Back to [the overview](../README.md).
