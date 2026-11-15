#!/bin/bash
# Diagnostic only: the same four chirp settings as run.sh, but with the partner's exact heading filled in
# (chirp.heading: true) instead of zeros, no training. Isolates what the missing heading costs.
# @trueheading fills in the exact heading. Results: results-true-heading/comparison.md and .json.
cd "$(dirname "$0")/../../.."
D2=runs/decentral-p2-d2/model.zip
scripts/rl.sh scripts/rl/compare_policies.py \
  --config experiments/stage1-random-box-pose/config.yaml \
  --test-set experiments/test_sets/stage1.json \
  --policy d2_exact=$D2@partner \
  --policy th_chirp_2s_30deg=$D2@partner@chirp:2:30@trueheading \
  --policy th_chirp_2s_10deg=$D2@partner@chirp:2:10@trueheading \
  --policy th_chirp_0.5s_30deg=$D2@partner@chirp:0.5:30@trueheading \
  --policy th_chirp_4s_60deg=$D2@partner@chirp:4:60@trueheading \
  --policy th_control_no_noise=$D2@partner@chirp:0.2:0:0@trueheading \
  --out experiments/chirp-partner-sensing/zero-shot/results-true-heading
