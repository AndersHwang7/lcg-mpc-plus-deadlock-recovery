# Inha University & RODIX Inc, Anders Hwang
from mr_deadlock.experiments.runner import run_experiment


def _cfg():
    return {
        "experiment": {"name": "planner_smoke", "output_dir": "results/test_raw", "seeds": [0]},
        "scenario": {
            "map_type": "intersection",
            "width": 28,
            "height": 28,
            "obstacle_density": 0.03,
            "n_robots": 12,
            "max_steps": 80,
            "start_goal_mode": "cross_traffic",
        },
        "planner": {
            "horizon": 6,
            "whca_window": 6,
            "deadlock_threshold": 4,
            "enable_continuous_dynamics": True,
            "footprint_radius": 0.35,
            "safety_margin": 0.05,
            "sensing_sigma": 0.02,
            "max_accel": 1.5,
            "max_speed": 1.25,
        },
        "runtime": {"resume_existing": False},
    }


def test_lcg_mpc_plus_smoke_runs_with_continuous_metrics():
    summary = run_experiment(_cfg(), "lcg_mpc_plus", 0)
    assert summary["algorithm"] == "lcg_mpc_plus"
    assert "continuous_min_clearance" in summary
    assert summary["collision_count"] == 0


def test_lite_baselines_smoke():
    for alg in ["orca_lite", "dmpc_lite", "mpc_cbf_lite", "impc_dr_lite"]:
        summary = run_experiment(_cfg(), alg, 1)
        assert summary["algorithm"] == alg
        assert summary["collision_count"] == 0

