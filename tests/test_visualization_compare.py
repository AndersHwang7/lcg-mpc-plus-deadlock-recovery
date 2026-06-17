# Inha University & RODIX Inc, Anders Hwang
from pathlib import Path

from mr_deadlock.visualization.compare_viewer import build_comparison_trace, render_comparison_html


def test_comparison_trace_and_html(tmp_path: Path):
    cfg = {
        "experiment": {"name": "visual_test", "algorithms": ["whca", "clrr_hmpc"], "seeds": [0]},
        "scenario": {
            "map_type": "intersection",
            "width": 24,
            "height": 24,
            "obstacle_density": 0.02,
            "n_robots": 8,
            "max_steps": 8,
            "start_goal_mode": "cross_traffic",
        },
        "planner": {
            "whca_window": 4,
            "activation_mode": "candidate",
            "deadlock_threshold": 3,
            "retreat_radius": 3,
            "max_game_agents": 4,
            "game_max_profiles": 128,
            "enable_mpc": True,
            "mpc_horizon": 4,
        },
        "runtime": {"save_step_log": False},
    }
    trace = build_comparison_trace(cfg, ["whca", "clrr_hmpc"], seed=0, max_frames=3, path_horizon=4)
    assert trace["frames"]
    assert len(trace["frames"][0]["panels"]) == 2
    out = render_comparison_html(trace, tmp_path / "compare.html")
    text = out.read_text(encoding="utf-8")
    assert "panelCount" in text
    assert "TRACE" in text


def test_comparison_trace_supports_four_panels(tmp_path: Path):
    cfg = {
        "experiment": {"name": "visual_test_4way", "algorithms": ["whca", "impc_dr_lite", "mpc_cbf_lite", "lcg_mpc_plus"], "seeds": [0]},
        "scenario": {
            "map_type": "ring",
            "width": 20,
            "height": 20,
            "obstacle_density": 0.02,
            "n_robots": 6,
            "max_steps": 5,
            "start_goal_mode": "cross_traffic",
        },
        "planner": {
            "whca_window": 4,
            "activation_mode": "candidate",
            "deadlock_threshold": 3,
            "retreat_radius": 3,
            "max_game_agents": 4,
            "game_max_profiles": 64,
            "enable_mpc": True,
            "mpc_horizon": 3,
        },
        "runtime": {"save_step_log": False},
    }
    trace = build_comparison_trace(
        cfg,
        ["whca", "impc_dr_lite", "mpc_cbf_lite", "lcg_mpc_plus"],
        seed=0,
        max_frames=2,
        path_horizon=3,
    )
    assert len(trace["frames"][0]["panels"]) == 4
    out = render_comparison_html(trace, tmp_path / "compare_4way.html")
    text = out.read_text(encoding="utf-8")
    assert "panelCount" in text

