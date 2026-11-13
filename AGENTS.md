# AGENTS.md

Shared context and rules for every AI coding agent (Codex, Claude Code, or any other) working in
this repo. These rules are stable; the plan changes in [ROADMAP.md](ROADMAP.md).

## The project

Microduck-CoPush is a Cornell Generative AI club project (fall 2026). Two simulated MicroDuck robots
learn to push a box into a target together, in MuJoCo. Each duck walks and pushes with frozen,
pretrained ONNX policies from Pollen Robotics; we train, with PPO, the controller on top that picks
each duck's forward speed and turn rate every 0.2 s.

**Final goal:** both ducks and the box start anywhere within a set radius of the target, at any
angle, and the ducks walk to the box and push it into the target together.

## Controllers

- **Central:** one controller sees the whole scene and commands both ducks. This is the default
  (`controller: {mode: central}` in [configs/copush.yaml](configs/copush.yaml)).
- **Decentralized D2:** each duck runs the same network on its own view plus its partner's position
  and heading (`controller: {mode: decentral, include_partner: true}`). D1 is own view only.
- **Plan:** improve the central controller first, distill it into per-duck controllers at the end,
  and compare that with D2 trained from scratch.

## Tracks

| owner | track | controller | branch | folder |
|---|---|---|---|---|
| Anmol | steering: turn the box on hard starts, then wider box angles | central | `steering` | `experiments/steering/` |
| Winston | rendezvous: ducks start apart and come together at the box | central | `rendezvous` | `experiments/rendezvous/` |
| Ashwin | decentralized from scratch, compared with distilled D2 | D2 | `d2-from-scratch` | `experiments/d2-from-scratch-comparison/` |

## Read first

1. [ROADMAP.md](ROADMAP.md): the plan, each track's status and next steps, decisions so far
2. [README.md](README.md): current status and results
3. [SETUP.md](SETUP.md): every command (install, sim, training, tests, policies)
4. [experiments/README.md](experiments/README.md) and the latest stage READMEs under `experiments/`
5. [docs/REWARD_LOG.md](docs/REWARD_LOG.md): every reward version and why
6. [configs/copush.yaml](configs/copush.yaml): all settings

## Rules for experiments

- **One change per run,** compared with a named previous policy.
- **Every change is a config setting.** New behavior goes behind a setting whose default keeps the
  old behavior, so earlier configs reproduce.
- **Warm start from the released policies:** `scripts/get_policies.sh` puts them in `runs/` where
  the configs expect them.
- **Test on the shared 50-start test sets** in `experiments/test_sets/` (never trained on). Training
  checks and early stopping use the separate check sets (`*_checks.json`), never the test set.
- **Report success overall and per difficulty** (for example the box angle sides), with the number
  of episodes and seeds.
- **Never overstate.** One seed is preliminary; a difference inside the spread across seeds is "no
  measurable effect"; compare by success rate, not return, when rewards differ.

## Where to write

- Results only in your own `experiments/<track>/` folder. Large outputs (checkpoints, videos,
  logs) go in the git-ignored `runs/`, linked from your README.
- Edit only your own track section of [ROADMAP.md](ROADMAP.md).
- README.md, docs/TIMELINE.md and docs/DEMO.md change only when merging to main.
- Keep the number of .md files small: add to an existing file rather than starting a new one.

## Git

- Commit under the teammate's own name and email only.
- No AI tool as author or co-author. No `Co-authored-by` or "Generated with" lines, and no mention
  of Codex, Claude or any AI in commits or PRs.
- Before pushing, run `git log --format="%h %an <%ae> %s"` and check every commit.
- Work on your track's branch and open a PR. Only the lead merges.

## Report after each run

1. Test-set success against the previous policy, overall and per difficulty.
2. Forgetting check: the new policy on earlier stages' test sets (at least stage 1).
3. Falls, box lost, overshoots, and push share (is one duck doing all the work?).
4. One success video and one failure video (paths).
5. What it means, in plain words, and the proposed next step.
