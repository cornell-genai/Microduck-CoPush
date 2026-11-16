# Run 1: chirps + the true partner heading (DIAGNOSTIC)

Part 2 with one change: the partner's true heading is also given, heard at each chirp and held until the next
(`chirp.heading: true_held`). Not a realistic setting, since sound cannot provide it: it asks whether the missing
heading is what separates the chirp policy (60%) from D2 (74%). Settings: [config.yaml](config.yaml). Trained 1M
simulator steps (62 min), early stop did not fire (final check-set success 64%).

**Stage 1 test set: 72% (36/50)**; sides 16/17, 15/16, 5/17. Idle share 8.8%, 4 overshoots, 11 time-outs, 1 fall.
Compared with D2, D1, Part 2 and Run 2, with the caveats about noise: [../diagnostics/README.md](../diagnostics/README.md).
**On 200 new starts it wins 64%, the same as the heading-removed runs (63% and 63%):** the 72% above was noise; see
[../large-eval/README.md](../large-eval/README.md).
