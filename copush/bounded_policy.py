"""Bounded exploration for a Gaussian PPO policy (D2 steering, night 4).

The speed action is clipped to [-1, 1] by the env, but an unbounded policy mean can drift far outside (the night 2 and 3
policies had means of -1 to -8 at their stall states and a sampling std of 2.5 to 3). This policy class changes the action head:

    mean = raw                                              if |raw| <= 1   (identical to the unbounded head inside the action range)
         = sign(raw) * (1 + (bound - 1) * tanh((|raw| - 1) / (bound - 1)))   otherwise (bound 1.5: never leaves [-1.5, 1.5])
    std  = exp(min(log_std, log(std_cap)))   (std never above std_cap)

STATUS: tested and rejected in night 4 (experiments/d2-steering/night4/SUMMARY.md). Run E (this head, std cap 0.5, ent_coef 0) was
measurably worse than night 2's Run A (-17.2 points overall on the no-noise set, -26.5 on the noisy set) with about 3x the
both-idle stalls. Kept so the experiment reproduces.

Used only when a stage config has `bounded_action:` (scripts/rl/stage.py); nothing else changes. Models saved with this class
load with plain PPO.load as long as `copush` is importable.
"""
from __future__ import annotations

import json
import math
import os

import torch as th
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.distributions import DiagGaussianDistribution
from stable_baselines3.common.policies import ActorCriticPolicy


def soft_bound(raw, bound: float = 1.5):
    """Identity on [-1, 1], then a smooth tanh shoulder that approaches +-bound. Continuous, with slope 1 at +-1."""
    w = bound - 1.0
    over = th.clamp(raw.abs() - 1.0, min=0.0)
    return th.where(raw.abs() <= 1.0, raw, th.sign(raw) * (1.0 + w * th.tanh(over / w)))


class BoundedActorCriticPolicy(ActorCriticPolicy):
    def __init__(self, *args, mean_bound: float = 1.5, std_cap: float = 0.5, **kwargs):
        self.mean_bound, self.std_cap = float(mean_bound), float(std_cap)
        super().__init__(*args, **kwargs)

    def _get_action_dist_from_latent(self, latent_pi):
        raw = self.action_net(latent_pi)
        mean = soft_bound(raw, self.mean_bound)
        log_std = th.clamp(self.log_std, max=math.log(self.std_cap))
        assert isinstance(self.action_dist, DiagGaussianDistribution)
        return self.action_dist.proba_distribution(mean, log_std)

    def effective_std(self):
        return th.exp(th.clamp(self.log_std, max=math.log(self.std_cap))).detach().cpu().numpy()


def load_bounded(path: str, env=None, mean_bound: float = 1.5, std_cap: float = 0.5, init_std: float = 0.5,
                 ent_coef=None, device: str = "cpu", tensorboard_log=None):
    """The model at `path` with the bounded action head: same weights, log_std set to log(init_std), optionally ent_coef."""
    from stable_baselines3 import PPO
    kwargs = dict(PPO.load(path, device=device).policy_kwargs, mean_bound=mean_bound, std_cap=std_cap)
    model = PPO.load(path, env=env, device=device, tensorboard_log=tensorboard_log,
                     custom_objects={"policy_class": BoundedActorCriticPolicy, "policy_kwargs": kwargs})
    with th.no_grad():
        model.policy.log_std.fill_(math.log(init_std))
    if ent_coef is not None:
        model.ent_coef = float(ent_coef)
    return model


class StdCapCallback(BaseCallback):
    """After every rollout: clamp the stored log_std to the cap, and log the effective std, the fraction of speed outputs with |raw| > 3 and with raw below the hold cutoff (tensorboard and <path> as jsonl)."""

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def _on_step(self) -> bool:
        return True

    def _on_rollout_end(self) -> None:
        pol = self.model.policy
        with th.no_grad():
            pol.log_std.clamp_(max=math.log(pol.std_cap))
        std = pol.effective_std().tolist()
        obs = th.as_tensor(self.model.rollout_buffer.observations.reshape(-1, self.model.rollout_buffer.observations.shape[-1]))
        with th.no_grad():                                        # raw (unbounded) speed output on this rollout's observations
            raw = pol.action_net(pol.mlp_extractor.forward_actor(pol.extract_features(obs, pol.pi_features_extractor)))
        raw_vx = raw[:, 0]
        frac3, frac_hold = float((raw_vx.abs() > 3).float().mean()), float((raw_vx < 2 * 0.02 / 0.30 - 1).float().mean())
        self.logger.record("bounded/std_vx", std[0])
        self.logger.record("bounded/std_vyaw", std[1])
        self.logger.record("bounded/frac_raw_vx_gt3", frac3)
        with open(self.path, "a") as f:
            f.write(json.dumps({"step": self.num_timesteps, "std_vx": std[0], "std_vyaw": std[1], "cap": pol.std_cap,
                                "frac_raw_vx_abs_gt3": frac3, "frac_raw_vx_below_hold": frac_hold}) + "\n")
