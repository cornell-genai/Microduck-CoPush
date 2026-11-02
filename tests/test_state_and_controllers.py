"""State helpers, controllers, and the body-extension's pure parts — no simulator needed."""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest

from copush.controllers import Phase, SequenceController, m1_demo_phases
from copush.sim_client import SimClient, SimNotRunning, quat_to_yaw
from copush.state import STOP, Controller, StopController, validate_actions, wrap_angle

ROOT = Path(__file__).resolve().parents[1]


def test_wrap_angle():
    assert wrap_angle(3 * math.pi) == pytest.approx(math.pi)
    assert wrap_angle(-math.pi) == pytest.approx(math.pi)
    assert wrap_angle(0.5) == pytest.approx(0.5)


def test_validate_actions():
    ok = validate_actions({"duck_a": (0.3, 0, 0), "duck_b": [0, 0, 1]})
    assert ok == {"duck_a": (0.3, 0.0, 0.0), "duck_b": (0.0, 0.0, 1.0)}
    with pytest.raises(ValueError):
        validate_actions({"duck_a": (0, 0, 0)})
    with pytest.raises(ValueError):
        validate_actions({"duck_a": (0, 0), "duck_b": (0, 0, 0)})
    with pytest.raises(ValueError):
        validate_actions({"duck_a": (float("nan"), 0, 0), "duck_b": (0, 0, 0)})


def test_base_controller_is_abstract():
    with pytest.raises(NotImplementedError):
        Controller().get_actions({})  # type: ignore[arg-type]
    assert StopController().get_actions({}) == {"duck_a": STOP, "duck_b": STOP}  # type: ignore[arg-type]


def test_sequence_controller_schedule():
    c = SequenceController(m1_demo_phases(0.3, 1.2))
    assert c.total == pytest.approx(20.0)
    assert c.get_actions({"t": 0.0})["duck_a"] == (0.3, 0.0, 0.0)
    assert c.phase == "1_a_walks"
    acts = c.get_actions({"t": 8.0})
    assert acts["duck_a"] == STOP and acts["duck_b"] == (0.0, 0.0, 1.2)
    assert c.get_actions({"t": 17.0}) == {"duck_a": STOP, "duck_b": STOP}
    assert c.get_actions({"t": 25.0}) == {"duck_a": STOP, "duck_b": STOP}
    assert c.phase == "done"
    assert c.windows()["2_b_turns"] == (8.0, 16.0)


def test_quat_to_yaw():
    for yaw in (0.0, 0.7, -2.5, math.pi / 2):
        q = (math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2))
        assert quat_to_yaw(q) == pytest.approx(yaw)


def test_sim_client_clear_error_when_nothing_runs(tmp_path):
    sim = SimClient(state_dir=tmp_path, base_port=1)  # nothing there
    with pytest.raises(SimNotRunning) as err:
        sim.connect()
    text = str(err.value)
    assert "duck-a" in text and "duck-b" in text and "sim.sh up" in text


def _load_bodyext():
    spec = importlib.util.spec_from_file_location(
        "copush_bodyext_test", ROOT / "copush" / "_bodyext" / "sitecustomize.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # inert here: this process is not the body server
    return mod


def test_bodyext_is_inert_outside_body_server():
    import socketserver

    before = socketserver.BaseServer.__init__
    mod = _load_bodyext()
    assert not mod._is_body_server()
    assert socketserver.BaseServer.__init__ is before


def test_bodyext_placements(monkeypatch):
    mod = _load_bodyext()
    monkeypatch.setenv("COPUSH_PLACE", ";0,0.25,90")
    assert mod._placements() == {1: (0.0, 0.25, pytest.approx(math.pi / 2))}
    monkeypatch.setenv("COPUSH_PLACE", "")
    assert mod._placements() == {}


def test_bodyext_handler_extension_passes_other_ops_through():
    mod = _load_bodyext()

    class Handler:
        def dispatch(self, body, request):
            return {"echo": request["op"]}

    Extended = mod._extend(Handler)
    assert Extended.__name__ == "Handler"
    assert Extended().dispatch(None, {"op": "read"}) == {"echo": "read"}
    assert mod._extend(Extended) is Extended  # not wrapped twice
