# Inha University & RODIX Inc, Anders Hwang
from mr_deadlock.experiments.runner import run_experiment


def _cfg(algorithm: str):
    return {
        "experiment": {
            "name": f"round2_toggle_{algorithm}",
            "output_dir": "results/test_round2_toggles/raw",
            "algorithms": [algorithm],
        },
        "scenario": {
            "width": 30,
            "height": 30,
            "obstacle_density": 0.05,
            "n_robots": 12,
            "map_type": "ring",
            "density": 0.05,
            "max_steps": 20,
            "start_goal_mode": "cross_traffic",
        },
        "planner": {
            "whca_window": 8,
            "whca_strong_window": 32,
            "enable_continuous_dynamics": True,
            "enable_mpc": True,
            "max_game_agents": 5,
            "game_max_profiles": 64,
            "mpc_horizon": 3,
        },
        "runtime": {"resume_existing": False},
    }


def test_lcg_without_game_disables_game_counts():
    s = run_experiment(_cfg("lcg_mpc_plus_without_game"), "lcg_mpc_plus_without_game", 0)
    assert s["enable_game"] == 0
    assert s["exact_game_count"] == 0
    assert s["partitioned_exact_count"] == 0
    assert s["greedy_fallback_count"] == 0


def test_lcg_without_mpc_disables_mpc_refinements():
    s = run_experiment(_cfg("lcg_mpc_plus_without_mpc"), "lcg_mpc_plus_without_mpc", 0)
    assert s["enable_mpc"] == 0
    assert s["mpc_refinements"] == 0


def test_lcg_without_cbf_disables_cbf_flag():
    s = run_experiment(_cfg("lcg_mpc_plus_without_cbf"), "lcg_mpc_plus_without_cbf", 0)
    assert s["enable_cbf"] == 0


def test_lcg_without_stagnation_repair_disables_calls():
    s = run_experiment(
        _cfg("lcg_mpc_plus_without_stagnation_repair"),
        "lcg_mpc_plus_without_stagnation_repair",
        0,
    )
    assert s["enable_stagnation_repair"] == 0
    assert s["stagnation_repair_calls"] == 0


def test_lcg_without_robust_nominal_disables_robust_count():
    s = run_experiment(
        _cfg("lcg_mpc_plus_without_robust_nominal"),
        "lcg_mpc_plus_without_robust_nominal",
        0,
    )
    assert s["enable_robust_nominal"] == 0
    assert s["robust_nominal_repairs"] == 0


def test_whca_window_and_goal_reservation_metadata():
    h8 = run_experiment(_cfg("whca_default"), "whca_default", 0)
    h32 = run_experiment(_cfg("whca_h32"), "whca_h32", 0)
    goal = run_experiment(_cfg("whca_strong_goal"), "whca_strong_goal", 0)
    assert h8["actual_window"] == 8
    assert h32["actual_window"] == 32
    assert goal["actual_window"] == 32
    assert goal["goal_reservation_enabled"] == 1


def test_v3_aliases_expose_expected_runtime_metadata():
    best = run_experiment(_cfg("whca_best_preregistered"), "whca_best_preregistered", 1)
    lcg = run_experiment(_cfg("lcg_mpc_plus_full_v3"), "lcg_mpc_plus_full_v3", 1)
    assert best["actual_window"] == 16
    assert "planner_plan_time_ms" in lcg
    assert "timeout_fallback_count" in lcg
    assert "capped_game_count" in lcg

