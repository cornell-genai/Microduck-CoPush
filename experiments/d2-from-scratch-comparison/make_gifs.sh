#!/bin/bash
# GIFs of each setup's final policy (seed 1) on the same fixed start (eval seed 10000), and all three
# side by side, into comparison/. Each GIF must stay under 1 MB.
#
#   experiments/d2-from-scratch-comparison/make_gifs.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
OUT=experiments/d2-from-scratch-comparison/comparison
FONT=/System/Library/Fonts/Supplemental/Arial.ttf
NAMES=(central-scratch d2-scratch d2-distilled)
LABELS=("central, from scratch" "D2, from scratch" "D2, distilled")
VIDEOS=(runs/overnight-20261112/runs/01_reference/videos/step_401408_final.mp4
        runs/d2-from-scratch/d2-scratch-s1/videos/step_802816_final.mp4
        runs/decentral-p1-d2/videos/step_802816_final.mp4)
FPS=8

label() {   # $1 label, $2 width: a filter that scales, captions at the bottom and holds the last frame 1.5 s
  echo "hqdn3d=4:3:6:6,scale=$2:-2,drawtext=fontfile=$FONT:text='$1':x=(w-tw)/2:y=h-th-8:fontsize=$(( $2 / 24 )):fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=5,tpad=stop_mode=clone:stop_duration=1.5,fps=$FPS"
}

for i in 0 1 2; do
  ffmpeg -v error -y -i "${VIDEOS[$i]}" -filter_complex \
    "[0:v]$(label "${LABELS[$i]}" 360),split[a][b];[a]palettegen=max_colors=32:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle" \
    -loop 0 "$OUT/final_${NAMES[$i]}.gif"
done

ffmpeg -v error -y -i "${VIDEOS[0]}" -i "${VIDEOS[1]}" -i "${VIDEOS[2]}" -filter_complex \
  "[0:v]$(label "${LABELS[0]}" 260)[a];[1:v]$(label "${LABELS[1]}" 260)[b];[2:v]$(label "${LABELS[2]}" 260)[c];
   [a][b][c]hstack=inputs=3,split[x][y];[x]palettegen=max_colors=32:stats_mode=diff[p];[y][p]paletteuse=dither=none:diff_mode=rectangle" \
  -loop 0 "$OUT/final_side_by_side.gif"

ls -l "$OUT"/*.gif | awk '{printf "%7.0f KB  %s\n", $5 / 1024, $9}'
