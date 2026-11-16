#!/bin/bash
# Zero-shot check: the trained D2 stage 1 policy (and D1) on the stage 1 test set, with chirps on at
# several settings, no retraining. Run from the repo root. Results: results/comparison.md and .json.
# @chirp:<interval_s>:<direction_noise_deg>[:<distance_noise>]; the distance is heard when the third number is given.
cd "$(dirname "$0")/../../.."
D2=runs/decentral-p2-d2/model.zip
scripts/rl.sh scripts/rl/compare_policies.py \
  --config experiments/stage1-random-box-pose/config.yaml \
  --test-set experiments/test_sets/stage1.json \
  --policy d2_exact=$D2@partner \
  --policy d1=runs/decentral-p2-d1/model.zip@own \
  --policy chirp_2s_30deg=$D2@partner@chirp:2:30 \
  --policy chirp_2s_10deg=$D2@partner@chirp:2:10 \
  --policy chirp_0.5s_30deg=$D2@partner@chirp:0.5:30 \
  --policy chirp_4s_60deg=$D2@partner@chirp:4:60 \
  --policy extra_chirp_2s_30deg_dist30=$D2@partner@chirp:2:30:0.3 \
  --policy extra_no_noise_no_heading=$D2@partner@chirp:0.2:0:0 \
  --out experiments/chirp-partner-sensing/zero-shot/results
