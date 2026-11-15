---
name: copush-progress
description: Record CoPush progress after an experiment, training run, or milestone, and keep demo materials current. Use when asked to update progress, log results, prepare a demo or team meeting, or after any run finishes.
---

# CoPush progress tracking

Keeps a clear, honest record of what the team did and found, so anyone can show the
project in 5 minutes. This skill only edits docs and media. Never change code, configs,
or reward settings while using it.

Read [AGENTS.md](../../../AGENTS.md) first (project rules, tracks, git rules, report format)
and [ROADMAP.md](../../../ROADMAP.md) (the plan, each track's status and next steps).

## Files this skill maintains

| File | Purpose | Committed? |
|---|---|---|
| `docs/TIMELINE.md` | One row per milestone or experiment round | yes |
| `docs/REWARD_LOG.md` | One entry per reward version (already exists) | yes |
| `docs/DEMO.md` | 5-minute demo outline, always current | yes |
| `docs/media/` | A few short "hero" videos and labeled thumbnail GIFs, each under 1 MB | yes |
| `docs/DIAGRAMS.md` | Small illustrated SVG diagrams (in `docs/media/diagrams/`): central vs decentralized, training loop, ladder, chirps, data flow | yes |
| `README.md` | Project page, focused on central vs decentralized: labeled top GIF, system diagram, results, behaviors table, next steps (template below) | yes |
| `experiments/README.md` | Index of the stages, same style as the README (template below) | yes |
| `ROADMAP.md` | The plan: one section per track (status, next steps), dated decisions, open questions | yes |
| `SETUP.md` | Every terminal command: install, sim, training, tests, queue, thumbnails, troubleshooting. The only place commands go | yes |
| `AGENTS.md` | Stable rules and context for AI agents; change only when a rule changes | yes |
| `notes/progress_blog.md` | Personal blog ideas and findings | no (git-ignored) |

Create any missing file using the templates below.

**Keep the .md count lean.** The live docs are README.md, AGENTS.md, SETUP.md and
ROADMAP.md at the root, docs/REWARD_LOG.md, docs/DEMO.md, docs/TIMELINE.md and docs/DIAGRAMS.md,
experiments/README.md, plus one README per experiment folder. Add to one of these rather than creating a new .md file;
outdated docs go to `docs/archive/`, not next to the live ones.

## Steps after each run or round

On a side branch, write results in that experiment's own folder (`experiments/<name>/`),
and update only your track's row in the README's "Behaviors we're teaching" table and your
track's section of ROADMAP.md. The rest of steps 2, 6 and 7 (TIMELINE, DEMO, the rest of the
README and experiments/README.md, DIAGRAMS) happen only when the branch is merged to main, by
the lead; see the Branch rule below.

1. **Gather facts** from the run folders (SUMMARY.md, report.md, DECISIONS.md,
   evals.jsonl, video index.md). Every claim must point to a run folder. If a number
   isn't in the files, say it's unknown rather than estimating.
2. **Add a TIMELINE row** (template below). One row per round. On a side branch, update
   only your own track section of ROADMAP.md (status, next steps); add a dated line to
   its Decisions list when the team decides something.
3. **Update REWARD_LOG.md** only if the reward changed.
4. **Pick a hero video** if this round is a milestone (first success on a new stage,
   a new behavior, a clear before/after). Compress and copy it to `docs/media/`
   (commands below). Keep docs/media small: replace older hero videos for the same
   stage instead of adding more.
5. **Make a side-by-side video** when comparing two controllers on the same start
   (for example script vs PPO). These are the most convincing demo material.
6. **Update DEMO.md** so it shows the current best story.
7. **Refresh the README and experiments/README.md on every merge to main** (the lead). Keep the
   README's structure (template below) and update:
   - **Top GIF:** the three-way clip (central, decentralized, distilled), each panel labeled with
     a clear text label; under 1 MB. Replace it when a better comparison exists.
   - **Current status:** current stage, headline result in plain words, date, and which
     controller the result used (central is the default unless the config says otherwise).
   - **How it works:** keep the system diagram in step with the code.
   - **Central vs decentralized:** the main result (from scratch, with seeds and ranges) first, then
     earlier results clearly labeled as earlier, with their caveats. Never drop a caveat.
   - **Behaviors we're teaching:** one row per track. On a side branch each track updates only its own
     row (plain language, status, link to its experiment folder).
   - **Progress:** add the new hero GIF in order, with a one-line caption of the milestone.
   - **Reward function:** regenerate the formula and the value table from the current
     config (`configs/copush.yaml`: `reward` with `reward_versions[reward.version]` applied
     on top; or `copush.config.effective_reward`), and the episode endings from
     `copush/rewards.py` and `copush/env.py`. Never fill in values from memory.
   - **Next steps:** 2 to 4 bullets, one per track, linking to ROADMAP.md for the full plan.
   - **experiments/README.md:** one row per finished stage with a small labeled thumbnail GIF linked
     to its folder; its result in plain words (a stage that has several seeds reports the mean and range).
   - **docs/DIAGRAMS.md:** update a diagram only when what it shows has changed.
   No terminal command goes in the README, experiments/README.md, TIMELINE or DEMO; a new command goes
   in SETUP.md and the README links to it.
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
- **Name the controller.** The default is central (one network for both ducks;
  `controller` in `configs/copush.yaml`). Decentralized D2 (each duck runs the shared
  network on its own view plus its partner) is selectable. Say which one a result used,
  and compare D2 against central only at equal training.

## Branch rule

On side branches, results go in that experiment's own folder
(`experiments/<name>/README.md` and its results). The PR also updates only that track's row in
the README "Behaviors we're teaching" table and that track's section of ROADMAP.md, in plain
language with a link to the experiment folder. The rest of the README, experiments/README.md,
docs/TIMELINE.md, docs/DEMO.md and docs/DIAGRAMS.md get updated only by the lead when merging to
main, so parallel branches don't conflict on them.

## No commands outside SETUP.md

The README, experiments/README.md, docs/TIMELINE.md and docs/DEMO.md never contain terminal
commands. Commands, install steps and troubleshooting go in SETUP.md, and the other docs link to
it. (The commands in "Video commands" below are for you, the agent, and never go in those files.)
Explain any acronym the first time it appears in each of them.

## Diagrams

Diagrams are SVGs in `docs/media/diagrams/`, in the style of `controllers_gamepad.svg`: cream cards with an
amber border, the cartoon duck and the gamepad with a small neural net, soft flat colors, big plain labels,
no hatching. All text sits on cream cards or pills, so they read on light and dark pages. No Mermaid.
- Each SVG has a `make_<name>.py` next to it, built from the shared `diagram_kit.py`. Change the script and
  rerun `make_all.py` (or that one script); never edit the SVG by hand.
- 4 to 6 elements per diagram, plenty of space, labels in plain words.
- Embed with a normal image link and alt text that says what the picture shows.
- Color by role where it helps: blue for what we train, green for frozen pretrained parts, cream for the
  simulator and reward.

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

### README.md

```markdown
# Microduck-CoPush

<one-line description, with the central vs decentralized angle>

<top GIF: central from scratch | decentralized (D2) from scratch | D2 distilled, same start, each
panel labeled, linked to its mp4>

<one caption line>

**How it works: see the diagrams → [docs/DIAGRAMS.md](docs/DIAGRAMS.md)** ·
**📈 [Progress timeline, with clips →](docs/TIMELINE.md)**

## Final goal

<2-3 sentences: two ducks starting anywhere within a set radius of the target, at any
angle, with the box anywhere and at any angle, learn to push it into the target together>

## Current status (<date>)

- **Current stage:** <stage, in plain words>
- **Last finished result:** <headline result in plain words, with eval size>
- **Still unsolved:** <one bullet>

## How it works

<one paragraph: frozen walking and pushing policies, the coordinator network we train, RL, the reward,
PPO; acronyms explained>

<system diagram image (docs/media/diagrams/system_loop.svg): what the ducks see -> coordinator (trained) ->
speed and turn -> frozen walking and pushing policies -> simulator -> reward -> PPO update, with an arrow
back to the coordinator; cards colored by role, with a legend>

## Central vs decentralized

<one plain sentence each: central, decentralized (D2; D1 without the partner), distilled, then the
controllers_gamepad.svg picture>

### Main result: trained from scratch, <N> seeds each

<small table: setup, test starts won (mean), range across seeds; one "no measurable difference" (or
not) sentence; one line on style differences; the learning-curve chart with a caption; link to the
experiment folder>

### Earlier result: <label it> (<what it was, e.g. distilled from central>)

<the earlier table, the caveat line (seeds, training budget), one clip, a link to its folder>

## Behaviors we're teaching

| behavior | status | where |
|---|---|---|
| **<behavior>.** <one line> | <done / in progress / planned, with the headline> | <link to experiment folder or ROADMAP.md section> |

## Next steps

The full plan, per track, is in [ROADMAP.md](ROADMAP.md).

<2-4 bullets, one per track>

## Progress

<GIFs in order, each with a one-line caption of the milestone; include notable bugs>

## The reward function

<formula with variable names>

| Symbol | Meaning | Current value |
|---|---|---|
| ... | ... | <from the current config> |

**What ends an episode:** <success, falls, box tipped / lost, timeout, with thresholds>

Why each value is what it is: [docs/REWARD_LOG.md](docs/REWARD_LOG.md).

## Links

ROADMAP.md · SETUP.md · AGENTS.md · docs/REWARD_LOG.md · docs/TIMELINE.md · docs/DIAGRAMS.md · experiments/README.md · docs/DEMO.md
```

### experiments/README.md

```markdown
# Experiments

<2 sentences: one folder per stage, each changing one thing; tested on fixed held-out starts>

<links: main README, docs/DIAGRAMS.md curriculum ladder, README reward function table>

## Finished stages

| clip | stage and the one change | result, in plain words |
|---|---|---|
| <a href="<stage>/"><img src="../docs/media/<clip>_thumb.gif" width="260" alt="<what the panels show>"></a> | **[<stage>](<stage>/).** <the one change> | <result with eval size; mean and range for several seeds> |

## What is in this folder, in plain words

<bullets: the index, test_sets, a stage folder's README / config / results, large outputs in runs>

How to run a stage: [SETUP.md](../SETUP.md#run-a-stage-experiment).

## Next

The plan for the next stages, per track, is in [ROADMAP.md](../ROADMAP.md).
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

Check the size with `ls -lh docs/media/`. Labeled thumbnails for experiments/README.md:
`scripts/make_stage_thumbs.sh` (see SETUP.md). The README's top GIF has a text label drawn
on each panel (ffmpeg drawtext); the recipe is in experiments/d2-from-scratch-comparison/make_gifs.sh.

## Git rules

- Commit only docs, README, experiments/README.md, ROADMAP.md, SETUP.md, and docs/media on the current branch.
- Use the user's git identity. No Claude co-author lines, no "Generated with" lines.
- Don't push or merge unless the user asks.
- notes/ and runs/ stay git-ignored.
