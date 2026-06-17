# Inha University & RODIX Inc, Anders Hwang
# 파일명: aggregate.py
# 목적 및 역할:
# 여러 실험 CSV를 하나로 모으고 논문 표에 들어갈 요약 통계를 만든다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from pathlib import Path
import pandas as pd


def load_raw(input_dir: str | Path) -> pd.DataFrame:
    files = sorted(Path(input_dir).glob("*.csv"))
    files = [p for p in files if not p.name.endswith("_steps.csv") and not p.name.endswith("combined.csv")]
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_csv(p) for p in files], ignore_index=True)


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    group_cols = [c for c in ["algorithm", "map_type", "n_robots", "density"] if c in df.columns]
    metric_cols = [
        "success_rate",
        "deadlock_candidate_steps",
        "persistent_deadlock_steps",
        "deadlock_rate_per_step",
        "local_conflict_sets_total",
        "retreat_actions",
        "fixed_conflicts",
        "game_profiles_evaluated",
        "mpc_refinements",
        "mean_travel_time",
        "mean_wait_time",
        "max_wait_time",
        "makespan",
        "throughput_per_step",
        "throughput_wallclock",
        "runtime_sec",
        "avg_step_runtime_ms",
        "p95_step_runtime_ms",
        "p99_step_runtime_ms",
        "max_step_runtime_ms",
        "collision_count",
        "raw_vertex_conflicts",
        "raw_edge_swap_conflicts",
        "final_vertex_conflicts",
        "final_edge_swap_conflicts",
        "supervisor_interventions",
        "supervisor_interventions_per_step",
        "supervisor_interventions_per_robot",
        "raw_conflicts_per_step",
        "final_conflicts_per_step",
        "planner_level_repairs",
        "footprint_conflicts",
        "swept_conflicts",
        "obstacle_envelope_conflicts",
        "acceleration_clips",
        "speed_clips",
        "sensing_risk_events",
        "continuous_min_clearance",
        "exact_game_count",
        "partitioned_exact_count",
        "greedy_fallback_count",
        "cbf_filter_calls",
        "stagnation_repair_calls",
        "robust_nominal_repairs",
        "timeout_count",
        "timeout_fallback_count",
        "capped_game_count",
        "capped_mpc_count",
        "capped_cbf_count",
        "game_profiles_evaluated_per_step",
        "mpc_refinements_per_step",
        "cbf_calls_per_step",
        "planner_plan_time_ms",
        "safety_supervisor_time_ms",
        "dynamics_envelope_time_ms",
        "reservation_table_time_ms",
        "astar_or_bfs_time_ms",
        "local_game_time_ms",
        "mpc_qp_refinement_time_ms",
        "cbf_robust_filter_time_ms",
        "logging_csv_overhead_ms",
        "planner_native_conflict_reduction_rate",
        "raw_conflicts_before_repair",
        "raw_conflicts_after_planner_repair",
        "enable_game",
        "enable_mpc",
        "enable_cbf",
        "enable_stagnation_repair",
        "enable_robust_nominal",
        "enable_safety_envelope_logging",
        "actual_window",
        "reservation_horizon",
        "goal_reservation_enabled",
        "planned_path_length_mean",
        "reservation_table_size_mean",
        "fairness_jain_wait",
        "average_path_stretch",
    ]
    metric_cols = [c for c in metric_cols if c in df.columns]
    out = df.groupby(group_cols, dropna=False)[metric_cols].agg(["mean", "std", "count"]).reset_index()
    out.columns = ["_".join([str(x) for x in col if x]) for col in out.columns.to_flat_index()]
    return out

