# Phase 1, D1 (own view only): fixed start

PPO from the distilled D1 weights on the fixed in-contact start (overnight layout), 400k simulator steps
(800k duck entries), like 01_reference.

- **Fixed start:** success at all 8 training checks and in the final run (30 steps; 01_reference: 32).
- **Stage 1 test set (not trained for it):** 38% (6/17, 13/16, 0/17); 01_reference 50%.
- **Wall time:** 25.0 min.

Results: [results/test_set.md](results/test_set.md), [results/training.json](results/training.json).
Model: `runs/decentral-p1-d1/model.zip`. Back to [the overview](../README.md).
