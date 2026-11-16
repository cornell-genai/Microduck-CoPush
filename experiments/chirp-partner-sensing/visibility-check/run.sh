#!/bin/bash
# Visibility check, no training: how often each duck sees its partner (front camera, fov 120 deg, range 0.8 m,
# both placeholders) with the trained D2 stage 1 policy on the stage 1 test set, with and without the box
# blocking the view. Run from anywhere; results in results/visibility.md and .json.
cd "$(dirname "$0")/../../.."
scripts/rl.sh scripts/rl/visibility_check.py \
  --config experiments/stage1-random-box-pose/config.yaml \
  --test-set experiments/test_sets/stage1.json \
  --policy runs/decentral-p2-d2/model.zip \
  --out experiments/chirp-partner-sensing/visibility-check/results
