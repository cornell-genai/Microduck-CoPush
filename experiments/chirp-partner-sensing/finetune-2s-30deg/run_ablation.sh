#!/bin/bash
# What does the fine-tuned chirp policy rely on? No training: the same policy on the stage 1 test set with
# the chirp information changed. random_direction: a chirp every 2 s with a random direction (uninformative,
# noise 10000 deg); exact_every_2s: exact direction, every 2 s; exact_every_step: the exact partner vector
# every step (heading still zero). Results: results-ablation/comparison.md and .json.
cd "$(dirname "$0")/../../.."
FT=runs/chirp-partner-sensing/finetune-2s-30deg/model.zip
scripts/rl.sh scripts/rl/compare_policies.py \
  --config experiments/stage1-random-box-pose/config.yaml --test-set experiments/test_sets/stage1.json \
  --policy ft_chirp_2s_30deg=$FT@partner@chirp:2:30 \
  --policy ft_random_direction=$FT@partner@chirp:2:10000 \
  --policy ft_exact_every_2s=$FT@partner@chirp:2:0 \
  --policy ft_exact_every_step=$FT@partner@chirp:0.2:0:0 \
  --policy d1=runs/decentral-p2-d1/model.zip@own \
  --out experiments/chirp-partner-sensing/finetune-2s-30deg/results-ablation
