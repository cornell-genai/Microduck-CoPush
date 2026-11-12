---
name: copush-progress
description: Record CoPush progress after an experiment, training run, or milestone, and keep demo materials current. Use when asked to update progress, log results, prepare a demo or team meeting, or after any run finishes.
---

# CoPush progress tracking

Keeps a clear, honest record of what the team did and found, so anyone can show the
project in 5 minutes. This skill only edits docs and media. Never change code, configs,
or reward settings while using it.

## Files this skill maintains

| File | Purpose | Committed? |
|---|---|---|
| `docs/TIMELINE.md` | One row per milestone or experiment round | yes |
| `docs/REWARD_LOG.md` | One entry per reward version (already exists) | yes |
| `docs/DEMO.md` | 5-minute demo outline, always current | yes |
| `docs/media/` | A few short "hero" videos, each under 1 MB | yes |
| `README.md` | Status line and video table at the top | yes |
| `notes/progress_blog.md` | Personal blog ideas and findings | no (git-ignored) |

Create any missing file using the templates below.

## Steps after each run or round

1. **Gather facts** from the run folders (SUMMARY.md, report.md, DECISIONS.md,
   evals.jsonl, video index.md). Every claim must point to a run folder. If a number
   isn't in the files, say it's unknown rather than estimating.
2. **Add a TIMELINE row** (template below). One row per round.
3. **Update REWARD_LOG.md** only if the reward changed.
4. **Pick a hero video** if this round is a milestone (first success on a new stage,
   a new behavior, a clear before/after). Compress and copy it to `docs/media/`
   (commands below). Keep docs/media small: replace older hero videos for the same
   stage instead of adding more.
5. **Make a side-by-side video** when comparing two controllers on the same start
   (for example script vs PPO). These are the most convincing demo material.
6. **Update DEMO.md** so it shows the current best story.
7. **Update the README status line** with the latest headline result.
8. **Append to notes/progress_blog.md:** surprising findings, reward hacking examples,
   bugs, and lessons, each with key numbers and a link.
9. **Commit** the docs changes (see Git rules).
10. **Report back** in short bullets: what was added, the headline result, and paths.

## Honesty rules

- **One change per round.** Say what the single change was compared to the reference.
- **Luck range:** when several seeds of the same setup exist, report their spread and
  call any difference inside it "no measurable effect."
- **Compare by success rate, not return, when rewards differ.** A bonus term raises
  return without meaning better behavior.
- **State the evaluation size** (number of episodes, fixed or randomized start). Flag
  results from fewer than 20 episodes as preliminary.
- **Don't overstate.** If PPO only beats a script from the start it trained on, say
  exactly that.
- **Flag reward hacking or odd behavior** (one duck doing all the work, standing still,
  losing the box on purpose, monitor flags) even when success is high.

## Writing style

- Plain words a new club member understands. Explain any acronym the first time.
- Headline numbers as sentences: "PPO gets the box to the off-axis target 80% of the
  time," not "eval return +15.59."
- Short. No em dashes.

## Templates

### TIMELINE.md

```markdown
# CoPush timeline

| Date | Stage | One change | Result (plain words) | Eval size | Video |
|---|---|---|---|---|---|
| 2026-11-12 | In contact, off-axis target | First PPO training on this layout | PPO succeeds 60 to 80% across 3 seeds; ties the script with random starts, beats it from the fixed start | 5 randomized | [video](media/...) |
```

### DEMO.md

```markdown
# 5-minute demo

1. **The task (30 s):** two ducks push a box into a target. Play: <video>
2. **How it learns (1 min):** a small network gives each duck a speed and turn every
   0.2 s; walking and pushing come from frozen pretrained policies.
3. **Where we started (1 min):** what failed and why. Play: <video>
4. **Current best (1.5 min):** headline result. Play: <side-by-side video>
5. **What we learned about reward design (1 min):** 1 or 2 examples from the reward log.
6. **Next (30 s):** the next stage.
```

## Video commands

Compress a clip to under 1 MB (adjust scale or crf if still too big):

```
ffmpeg -i INPUT.mp4 -vf "scale=480:-2" -c:v libx264 -preset veryfast -crf 30 -an docs/media/NAME.mp4
```

Side by side (both clips same height):

```
ffmpeg -i LEFT.mp4 -i RIGHT.mp4 -filter_complex "[0:v]scale=-2:270[a];[1:v]scale=-2:270[b];[a][b]hstack=inputs=2" -c:v libx264 -preset veryfast -crf 30 -an docs/media/NAME_side_by_side.mp4
```

Check the size with `ls -lh docs/media/`.

## Git rules

- Commit only docs, README, and docs/media on the current branch.
- Use the user's git identity. No Claude co-author lines, no "Generated with" lines.
- Don't push or merge unless the user asks.
- notes/ and runs/ stay git-ignored.
