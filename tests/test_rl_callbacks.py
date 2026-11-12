"""copush.rl_callbacks: video-on-change decisions, and a tiny real PPO run (seconds, not training)."""
from __future__ import annotations

import json
import os

import pytest

pytest.importorskip("stable_baselines3")
pytest.importorskip("mujoco")

from copush.config import load_config, policy_path  # noqa: E402

if not all(os.path.exists(policy_path(load_config(), n)) for n in ("velstand", "shoepush")):
    pytest.skip("policies missing (scripts/fetch_policies.sh)", allow_module_level=True)

from copush.rl_callbacks import VideoEvalCallback, behaviors, decide  # noqa: E402


def stats(ret, reason="timeout", flags=()):
    return {"return": ret, "reason": reason, "flags": list(flags)}


def test_decide_baseline_improved_new_behavior_none():
    s = stats(-5.0)
    assert decide(s, best=float("-inf"), seen=set(), margin=2.0, first=True) == "baseline"
    seen = behaviors(s)
    assert decide(stats(-2.9), best=-5.0, seen=seen, margin=2.0, first=False) == "improved"
    assert decide(stats(-3.5), best=-5.0, seen=seen, margin=2.0, first=False) is None          # +1.5 < margin
    assert decide(stats(-6.0, "fall"), best=-5.0, seen=seen, margin=2.0, first=False) == "new_behavior"
    assert decide(stats(-6.0, flags=["spin: box turned"]), best=-5.0, seen=seen, margin=2.0,
                  first=False) == "new_behavior"


def test_callback_on_a_tiny_ppo_run(tmp_path):
    from stable_baselines3 import PPO
    from copush.env import CoPushEnv

    cfg = load_config()
    cfg["env"]["max_steps"] = 5                      # 1 s episodes: this tests plumbing, not learning
    env = CoPushEnv(cfg)
    model = PPO("MlpPolicy", env, n_steps=16, batch_size=16, n_epochs=1, seed=0, verbose=0)
    cb = VideoEvalCallback(cfg, str(tmp_path), every=16)
    model.learn(total_timesteps=48, callback=cb)

    vids = tmp_path / "videos"
    names = sorted(p.name for p in vids.glob("*.mp4"))
    assert names[0].startswith("step_16_baseline") and any(n.endswith("_final.mp4") for n in names)
    evals = [json.loads(line) for line in open(vids / "evals.jsonl")]
    assert len(evals) == cb.n_evals >= 4                         # 16, 32, 48 + final
    index = (vids / "index.md").read_text()
    assert all(n in index for n in names)
