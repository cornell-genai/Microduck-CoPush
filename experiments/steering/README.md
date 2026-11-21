# Central steering: learn the long clockwise turn

**Question:** the Stage 1 central controller wins only 5% of the 66 held-out starts where the box
begins more than +15 degrees from the target. It turns about 40 degrees before pushing, but these
starts need roughly 55 degrees. Does giving the central controller a real stand-still action let it
hold one duck as a pivot and finish the turn?

**Status:** experiment prepared, full training not run yet. Run it with:

```sh
scripts/rl.sh scripts/rl/overnight_central_steering.py --dry-run
scripts/rl.sh scripts/rl/overnight_central_steering.py
```

## Experiment

Both groups warm-start from the released Stage 1 central policy and train for a fixed 1,000,000
additional simulator steps on the unchanged Stage 1 box-start range. There are two PPO seeds per
group and no early stopping.

| group | one change | config |
|---|---|---|
| control | none; measures the effect of the extra training budget | [control/config.yaml](control/config.yaml) |
| stand-still | a commanded forward speed below 0.02 m/s holds that duck on velstand | [stand-still/config.yaml](stand-still/config.yaml) |

The matched control fills the gap in Stage 1b: its two runs each received extra training, so their
improvements could not be separated from the effect of the proposed change.

## Fixed evaluation rules

- Evaluate every policy on the same 200 starts in `experiments/test_sets/stage1_large.json`.
- Report success overall and for all three angle sides with 95% intervals.
- Compare the mean of the two stand-still seeds with the mean of the two control seeds, paired by
  start. Call a change measurable only when the paired 95% interval excludes zero and the two
  groups' seed-rate ranges do not overlap.
- Also report pivots, turn before push, falls, box loss, overshoots, time-outs, both-held stalls and
  push share, plus one success and one failure clip.

If stand-still measurably improves the long-turn side without hurting the other sides, the next
step is to widen the box-angle range. Otherwise, the next isolated change is reward shaping for
aiming the push face before pushing.
