#!/bin/bash
# Small labeled thumbnail GIFs (each under 1 MB) for experiments/README.md, made from the side-by-side
# clips in docs/media/ (and, for the last one, from three videos in runs/). A label is drawn on each panel.
#
#   scripts/make_stage_thumbs.sh
set -euo pipefail
cd "$(dirname "$0")/.."
FONT=/System/Library/Fonts/Supplemental/Arial.ttf

thumb() {   # $1 clip name in docs/media, $2 left label, $3 right label
  local box="fontfile=$FONT:fontsize=11:fontcolor=white:box=1:boxcolor=black@0.7:boxborderw=4:y=h-th-6"
  ffmpeg -v error -y -i "docs/media/$1.mp4" -filter_complex \
    "[0:v]scale=360:-2,fps=5,drawtext=$box:text='$2':x=w/4-tw/2,drawtext=$box:text='$3':x=3*w/4-tw/2,tpad=stop_mode=clone:stop_duration=1.5,split[x][y];
     [x]palettegen=max_colors=24:stats_mode=diff[p];[y][p]paletteuse=dither=none:diff_mode=rectangle" \
    -loop 0 "docs/media/$1_thumb.gif"
}

thumb3() {  # the three from-scratch videos side by side (runs/ must hold them), one label each
  local box="fontfile=$FONT:fontsize=11:fontcolor=white:box=1:boxcolor=black@0.7:boxborderw=4:y=h-th-6"
  local V=(runs/overnight-20261112/runs/01_reference/videos/step_401408_final.mp4
           runs/d2-from-scratch/d2-scratch-s1/videos/step_802816_final.mp4
           runs/decentral-p1-d2/videos/step_802816_final.mp4)
  ffmpeg -v error -y -i "${V[0]}" -i "${V[1]}" -i "${V[2]}" -filter_complex \
    "[0:v]scale=150:-2,drawtext=$box:text='$1':x=(w-tw)/2[a];[1:v]scale=150:-2,drawtext=$box:text='$2':x=(w-tw)/2[b];
     [2:v]scale=150:-2,drawtext=$box:text='$3':x=(w-tw)/2[c];[a][b][c]hstack=inputs=3,fps=5,tpad=stop_mode=clone:stop_duration=1.5,split[x][y];
     [x]palettegen=max_colors=24:stats_mode=diff[p];[y][p]paletteuse=dither=none:diff_mode=rectangle" \
    -loop 0 docs/media/central_vs_decentral_thumb.gif
}

thumb stage1_pivot_push_vs_ppo_hard_start   "Script (pivot_push)"  "Learned (stage 1)"
thumb stage1b_stage1_vs_a_long_turn         "Stage 1"              "Stage 1b fix A"
thumb decentral_stage1_vs_d2_hard_start     "Central"              "Decentralized (D2)"
thumb3 "Central" "D2, scratch" "D2, distilled"
ls -l docs/media/*_thumb.gif | awk '{printf "%7.0f KB  %s\n", $5 / 1024, $9}'
