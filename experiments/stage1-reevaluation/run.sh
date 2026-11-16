#!/bin/bash
# Re-evaluate the earlier stage 1 policies on the 200-start held-out set (evaluation only, no training), each policy's
# starts spread over 8 worker processes; the wall time per policy is printed and saved in results/comparison.json.
# Needs runs/ (the trained policies: scripts/get_policies.sh and the run folders). Then: make_tables.py.
cd "$(dirname "$0")/../.."
R=runs/overnight-20261112/runs
S=runs/d2-from-scratch
args=(
  --policy stage1_central=runs/stage1-random-box-pose/model.zip
  --policy central_scratch_s1=$R/01_reference/model.zip        # = 01_reference
  --policy stage1b_A=runs/stage1b-a-oversample-hard/model.zip
  --policy stage1b_B=runs/stage1b-b-lower-time-penalty/model.zip
  --policy d1=runs/decentral-p2-d1/model.zip@own
  --policy d2=runs/decentral-p2-d2/model.zip@partner
  --policy d2_distilled_s1=runs/decentral-p1-d2/model.zip@partner
  --policy d2_distilled_s2=$S/d2-distilled-s2/model.zip@partner
  --policy d2_distilled_s3=$S/d2-distilled-s3/model.zip@partner
  --policy central_scratch_s2=$R/06_seed2/model.zip
  --policy central_scratch_s3=$R/07_seed3/model.zip
)
for s in 4 5 6 7 8 9 10; do args+=(--policy central_scratch_s$s=$S/central-scratch-s$s/model.zip); done
for s in 1 2 3 4 5 6 7 8 9 10; do args+=(--policy d2_scratch_s$s=$S/d2-scratch-s$s/model.zip@partner); done
scripts/rl.sh scripts/rl/compare_policies.py \
  --config experiments/stage1-random-box-pose/config.yaml --test-set experiments/test_sets/stage1_large.json \
  --baseline pivot_push --baseline push_steer "${args[@]}" --workers 8 \
  --out experiments/stage1-reevaluation/results
