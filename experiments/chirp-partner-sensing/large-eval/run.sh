#!/bin/bash
# Evaluation only (no training): D2 exact, D1, Part 2 (seed 1), Run 2 (seed 2) and Run 1 (true-heading diagnostic) on the
# 200-start held-out set, then 95% confidence intervals and paired comparisons. Needs runs/ (the trained policies).
cd "$(dirname "$0")/../../.."
R=runs/chirp-partner-sensing
D2=runs/decentral-p2-d2/model.zip
OUT=experiments/chirp-partner-sensing/large-eval/results
scripts/rl.sh scripts/rl/compare_policies.py \
  --config experiments/stage1-random-box-pose/config.yaml --test-set experiments/test_sets/stage1_large.json \
  --policy d2_exact=$D2@partner --policy d1=runs/decentral-p2-d1/model.zip@own \
  --policy part2_seed1=$R/finetune-2s-30deg/model.zip@partner@chirp:2:30 \
  --policy run2_seed2=$R/finetune-2s-30deg-s2/model.zip@partner@chirp:2:30 \
  --policy run1_true_heading=$R/finetune-true-heading/model.zip@partner@chirp:2:30@heldheading \
  --out $OUT
scripts/rl.sh scripts/rl/ci_report.py --comparison $OUT/comparison.json --out $OUT/ci_report.md \
  --pair run1_true_heading:part2_seed1 --pair run1_true_heading:run2_seed2 --pair part2_seed1:run2_seed2 \
  --pair d2_exact:run1_true_heading --pair d2_exact:part2_seed1 --pair d2_exact:run2_seed2 --pair part2_seed1:d1 --pair run2_seed2:d1 --pair d2_exact:d1 \
  --pooled run1_true_heading:part2_seed1,run2_seed2
