#!/bin/sh
# Download the policies the B0 scripts use into data/policies/ (gitignored; never commit ONNX/.pt).
#
#   data/policies/robert/shoe_push/{forward,backward}/policy.onnx   pisdeburra/robert-policies
#   data/policies/velstand_v6/velstand.onnx    Hub pollen-robotics/microduck-policies @ v6 (== v5):
#                                              the velstand Shoe Push was warm-started from
#   data/policies/velstand_v8/velstand.onnx    @ v8: what duck-sim fetches today
#
# Uses the `hf` CLI from microduck_rl's venv (huggingface_hub is already there).
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RL="${DUCK_SIM_RL:-$(cd "$ROOT/.." && pwd)/microduck_rl}"
OUT="$ROOT/data/policies"
HF="uv run --project $RL hf"
mkdir -p "$OUT"
$HF download pisdeburra/robert-policies --local-dir "$OUT/robert"
for tag in v6 v8; do
    $HF download pollen-robotics/microduck-policies velstand.onnx --revision "$tag" --local-dir "$OUT/velstand_$tag"
done
echo "policies in $OUT"
