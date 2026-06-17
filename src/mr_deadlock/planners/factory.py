# Inha University & RODIX Inc, Anders Hwang
# 파일명: factory.py
# 목적 및 역할:
# 문자열 이름으로 planner 객체를 생성한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from mr_deadlock.planners.astar_wait import AStarWaitPlanner
from mr_deadlock.planners.prioritized import PrioritizedPlanner
from mr_deadlock.planners.pibt import PIBTPlanner
from mr_deadlock.planners.whca import WHCAPlanner
from mr_deadlock.planners.clrr_hmpc import CLRRPlanner, CLRRGamePlanner, CLRRHMPCPlanner, LCGMPCPlusPlanner
from mr_deadlock.planners.baselines import ORCALitePlanner, DMPCLitePlanner, MPCCBFLitePlanner, IMPCDRLitePlanner


def make_planner(name: str, grid, config: dict | None = None):
    name = name.lower()
    config = config if config is not None else {}
    if name in {"whca_default", "whca_default_h8"}:
        name = "whca"
    elif name == "whca_h8":
        config["whca_window"] = 8
        name = "whca"
    elif name == "whca_h16":
        config["whca_window"] = 16
        name = "whca"
    elif name == "whca_h32":
        config["whca_window"] = 32
        name = "whca"
    elif name in {"whca_strong", "whca_strong_goal", "whca_strong_with_goal_reservation"}:
        config["whca_window"] = int(config.get("whca_strong_window", 32))
        config["whca_goal_reservation"] = name in {"whca_strong_goal", "whca_strong_with_goal_reservation"}
        name = "whca"
    elif name in {"whca_h32_goal", "whca_best", "whca_best_preregistered"}:
        config["whca_window"] = 16 if name in {"whca_best", "whca_best_preregistered"} else 32
        config["whca_goal_reservation"] = name == "whca_h32_goal"
        config["whca_preregistered_baseline"] = name in {"whca_best", "whca_best_preregistered"}
        name = "whca"
    elif name == "clrr_only":
        name = "clrr"
    elif name == "lcg_mpc_plus_without_game":
        config["lcg_disable_game"] = True
        name = "lcg_mpc_plus"
    elif name == "lcg_mpc_plus_without_mpc":
        config["enable_mpc"] = False
        name = "lcg_mpc_plus"
    elif name == "lcg_mpc_plus_without_cbf":
        config["lcg_strict_cbf_filter"] = False
        name = "lcg_mpc_plus"
    elif name == "lcg_mpc_plus_without_stagnation_repair":
        config["lcg_disable_stagnation_repair"] = True
        name = "lcg_mpc_plus"
    elif name == "lcg_mpc_plus_without_robust_nominal":
        config["lcg_disable_robust_nominal"] = True
        name = "lcg_mpc_plus"
    elif name == "lcg_mpc_plus_without_safety_envelope_logging":
        config["lcg_disable_safety_envelope_logging"] = True
        name = "lcg_mpc_plus"
    elif name == "lcg_mpc_plus_full_v3":
        config["lcg_strict_cbf_filter"] = True
        config.setdefault("max_game_profiles_per_component", 128)
        config.setdefault("max_total_game_profiles_per_step", 512)
        config.setdefault("max_mpc_refinements_per_step", 4)
        config.setdefault("max_cbf_filter_calls_per_step", 1)
        config.setdefault("planner_step_timeout_ms", 250.0)
        config.setdefault("safe_fallback_on_timeout", True)
        config.setdefault("lcg_skip_whca_probe", True)
        name = "lcg_mpc_plus"
    elif name == "lcg_mpc_plus_full":
        config["lcg_strict_cbf_filter"] = True
        name = "lcg_mpc_plus"
    cls = {
        "astar_wait": AStarWaitPlanner,
        "prioritized": PrioritizedPlanner,
        "pibt": PIBTPlanner,
        "whca": WHCAPlanner,
        "clrr": CLRRPlanner,
        "clrr_game": CLRRGamePlanner,
        "clrr_hmpc": CLRRHMPCPlanner,
        "lcg_mpc_plus": LCGMPCPlusPlanner,
        "orca_lite": ORCALitePlanner,
        "dmpc_lite": DMPCLitePlanner,
        "mpc_cbf_lite": MPCCBFLitePlanner,
        "impc_dr_lite": IMPCDRLitePlanner,
    }.get(name)
    if cls is None:
        raise ValueError(f"Unknown planner: {name}")
    return cls(grid, config)

