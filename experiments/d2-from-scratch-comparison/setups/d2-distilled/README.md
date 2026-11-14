# d2-distilled

D2 (each duck: own view plus partner), started from a copy of the centralized stage 1 policy
(behavior cloning plus one DAgger round, `runs/decentral-distill/d2.zip`), then PPO on the fixed start.
The only difference from d2-scratch is `init: distilled`.

- **Config:** [config.yaml](config.yaml) (for new seeds)
- **Seed 1 is a reused run:** `runs/decentral-p1-d2`, the decentralized-control phase 1 D2 run
  ([experiments/decentralized-control/p1-d2/](../../../decentralized-control/p1-d2/)). Same settings;
  it evaluated every 10k simulator steps.
- **Head start, read with care:** the copied teacher (stage 1) had already trained 400k steps on
  this start (01_reference) plus 980k steps on random box starts. So d2-distilled is not "the same budget"; it measures
  what copying buys.
- **Test set results:** [results/test_set/](results/test_set/)
