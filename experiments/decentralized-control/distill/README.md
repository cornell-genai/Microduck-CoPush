# Distill: copy the centralized stage 1 policy into D1 and D2

Records the stage 1 policy on 600 training episodes (half with action noise), then adds one DAgger round of
300 episodes. D1 and D2 are fit to each duck's command from that duck's own view. The critic is fit to the team returns.

- **Copy quality (held out):** D1 R² 0.92 speed, 0.95 turn; D2 R² 0.95 speed, 0.96 turn.
- **Copy only, test set:** D1 62%, D2 64% (teacher 60%); both succeed from the fixed start.
- **Wall time:** 7.9 min.

Full results: [results/distill.md](results/distill.md). Weights: `runs/decentral-distill/{d1,d2}.zip`.
Back to [the overview](../README.md).
