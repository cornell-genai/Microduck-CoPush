#!/bin/bash
# The side-by-side clip: D2 with exact partner info against the fine-tuned chirp policy, on stage 1 test start 8
# (box turned more than +15 deg; D2 exact wins, the chirp policy does not). Needs runs/ (get_policies.sh).
cd "$(dirname "$0")/../../.."
scripts/rl.sh scripts/rl/side_by_side_policies.py \
  --config experiments/stage1-random-box-pose/config.yaml --test-set experiments/test_sets/stage1.json --start 8 \
  --left "D2, exact partner info=runs/decentral-p2-d2/model.zip@partner" \
  --right "D2 with chirps (2 s, 30 deg)=runs/chirp-partner-sensing/finetune-2s-30deg/model.zip@partner@chirp:2:30" \
  --out experiments/chirp-partner-sensing/finetune-2s-30deg/results
