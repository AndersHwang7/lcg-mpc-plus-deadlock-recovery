# Inha University & RODIX Inc, Anders Hwang
# 파일명: metrics.py
# 목적 및 역할:
# 성공률, 교착률, 대기시간, 처리량, 공정성 등 논문 지표를 계산한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import mean
from mr_deadlock.core.robot import Robot


@dataclass
class StepRecord:
    t: int
    active: int
    completed: int
    deadlock_candidates: int
    persistent_deadlocks: int
    local_conflict_sets: int
    retreat_actions: int
    fixed_conflicts: int
    game_profiles: int
    mpc_refinements: int
    step_runtime_ms: float
    footprint_conflicts: int = 0
    swept_conflicts: int = 0
    obstacle_envelope_conflicts: int = 0
    acceleration_clips: int = 0
    speed_clips: int = 0
    sensing_risk_events: int = 0
    continuous_min_clearance: float = math.nan
    raw_vertex_conflicts: int = 0
    raw_edge_swap_conflicts: int = 0
    final_vertex_conflicts: int = 0
    final_edge_swap_conflicts: int = 0
    supervisor_interventions: int = 0
    planner_level_repairs: int = 0
    exact_game_count: int = 0
    partitioned_exact_count: int = 0
    greedy_fallback_count: int = 0
    cbf_filter_calls: int = 0
    stagnation_repair_calls: int = 0
    robust_nominal_repairs: int = 0
    timeout_count: int = 0
    raw_conflicts_before_repair: int = 0
    raw_conflicts_after_planner_repair: int = 0
    enable_game: int = 0
    enable_mpc: int = 0
    enable_cbf: int = 0
    enable_stagnation_repair: int = 0
    enable_robust_nominal: int = 0
    enable_safety_envelope_logging: int = 0
    actual_window: int = 0
    reservation_horizon: int = 0
    goal_reservation_enabled: int = 0
    planned_path_length_mean: float = 0.0
    reservation_table_size_mean: float = 0.0
    timeout_fallback_count: int = 0
    capped_game_count: int = 0
    capped_mpc_count: int = 0
    capped_cbf_count: int = 0
    mpc_refinements_per_step: float = 0.0
    cbf_calls_per_step: float = 0.0
    planner_plan_time_ms: float = 0.0
    safety_supervisor_time_ms: float = 0.0
    dynamics_envelope_time_ms: float = 0.0
    reservation_table_time_ms: float = 0.0
    astar_or_bfs_time_ms: float = 0.0
    local_game_time_ms: float = 0.0
    mpc_qp_refinement_time_ms: float = 0.0
    cbf_robust_filter_time_ms: float = 0.0
    logging_csv_overhead_ms: float = 0.0


@dataclass
class MetricsCollector:
    step_records: list[StepRecord] = field(default_factory=list)
    collision_count: int = 0

    def log_step(self, rec: StepRecord) -> None:
        self.step_records.append(rec)

    def summary(
        self,
        robots: list[Robot],
        max_steps: int,
        executed_steps: int,
        runtime_sec: float,
        scenario: dict,
        algorithm: str,
        seed: int,
    ) -> dict:
        completed = [r for r in robots if r.completed_at is not None]
        active = [r for r in robots if r.completed_at is None]
        n = len(robots)
        waits = [r.wait_time for r in robots]
        travel = [r.travel_time for r in completed]
        step_rt = [r.step_runtime_ms for r in self.step_records]
        p95 = 0.0
        p99 = 0.0
        if step_rt:
            s = sorted(step_rt)
            p95 = s[int(0.95 * (len(s) - 1))]
            p99 = s[int(0.99 * (len(s) - 1))]
        sum_wait = sum(waits)
        sum_wait_sq = sum(w * w for w in waits)
        fairness = (sum_wait * sum_wait) / (n * sum_wait_sq) if sum_wait_sq > 0 else 1.0
        path_stretches = []
        for r in completed:
            if r.nominal_path_length > 0:
                path_stretches.append(r.total_distance / max(1, r.nominal_path_length))
        simulated_time = max(1, executed_steps)
        persistent_steps = [r for r in self.step_records if r.persistent_deadlocks > 0]
        candidate_steps = [r for r in self.step_records if r.deadlock_candidates > 0]
        return {
            "algorithm": algorithm,
            "seed": seed,
            "map_type": scenario.get("map_type"),
            "n_robots": n,
            "density": scenario.get("density", scenario.get("obstacle_density")),
            "max_steps": max_steps,
            "executed_steps": executed_steps,
            "success_rate": len(completed) / max(1, n),
            "completed": len(completed),
            "unfinished": len(active),
            "deadlock_candidate_steps": len(candidate_steps),
            "persistent_deadlock_steps": len(persistent_steps),
            "deadlock_rate_per_step": len(persistent_steps) / simulated_time,
            "local_conflict_sets_total": sum(r.local_conflict_sets for r in self.step_records),
            "retreat_actions": sum(r.retreat_actions for r in self.step_records),
            "fixed_conflicts": sum(r.fixed_conflicts for r in self.step_records),
            "game_profiles_evaluated": sum(r.game_profiles for r in self.step_records),
            "mpc_refinements": sum(r.mpc_refinements for r in self.step_records),
            "mean_travel_time": mean(travel) if travel else math.nan,
            "mean_wait_time": mean(waits) if waits else 0.0,
            "max_wait_time": max(waits) if waits else 0,
            "makespan": max((r.completed_at or max_steps) for r in robots),
            # 논문용 처리량은 시뮬레이션 step당 완료 작업 수로 계산한다.
            "throughput_per_step": len(completed) / simulated_time,
            # 구현 성능 확인용 처리량은 실제 실행 시간 기준으로 따로 둔다.
            "throughput_wallclock": len(completed) / max(1e-9, runtime_sec),
            "runtime_sec": runtime_sec,
            "avg_step_runtime_ms": mean(step_rt) if step_rt else 0.0,
            "p95_step_runtime_ms": p95,
            "p99_step_runtime_ms": p99,
            "max_step_runtime_ms": max(step_rt) if step_rt else 0.0,
            "collision_count": self.collision_count,
            "raw_vertex_conflicts": sum(r.raw_vertex_conflicts for r in self.step_records),
            "raw_edge_swap_conflicts": sum(r.raw_edge_swap_conflicts for r in self.step_records),
            "final_vertex_conflicts": sum(r.final_vertex_conflicts for r in self.step_records),
            "final_edge_swap_conflicts": sum(r.final_edge_swap_conflicts for r in self.step_records),
            "supervisor_interventions": sum(r.supervisor_interventions for r in self.step_records),
            "supervisor_interventions_per_step": sum(r.supervisor_interventions for r in self.step_records) / simulated_time,
            "supervisor_interventions_per_robot": sum(r.supervisor_interventions for r in self.step_records) / max(1, n),
            "raw_conflicts_per_step": (
                sum(r.raw_vertex_conflicts + r.raw_edge_swap_conflicts for r in self.step_records) / simulated_time
            ),
            "final_conflicts_per_step": (
                sum(r.final_vertex_conflicts + r.final_edge_swap_conflicts for r in self.step_records) / simulated_time
            ),
            "planner_level_repairs": sum(r.planner_level_repairs for r in self.step_records),
            "footprint_conflicts": sum(r.footprint_conflicts for r in self.step_records),
            "swept_conflicts": sum(r.swept_conflicts for r in self.step_records),
            "obstacle_envelope_conflicts": sum(r.obstacle_envelope_conflicts for r in self.step_records),
            "acceleration_clips": sum(r.acceleration_clips for r in self.step_records),
            "speed_clips": sum(r.speed_clips for r in self.step_records),
            "sensing_risk_events": sum(r.sensing_risk_events for r in self.step_records),
            "continuous_min_clearance": min((r.continuous_min_clearance for r in self.step_records if math.isfinite(r.continuous_min_clearance)), default=math.nan),
            "exact_game_count": sum(r.exact_game_count for r in self.step_records),
            "partitioned_exact_count": sum(r.partitioned_exact_count for r in self.step_records),
            "greedy_fallback_count": sum(r.greedy_fallback_count for r in self.step_records),
            "cbf_filter_calls": sum(r.cbf_filter_calls for r in self.step_records),
            "stagnation_repair_calls": sum(r.stagnation_repair_calls for r in self.step_records),
            "robust_nominal_repairs": sum(r.robust_nominal_repairs for r in self.step_records),
            "timeout_count": sum(r.timeout_count for r in self.step_records),
            "game_profiles_evaluated_per_step": sum(r.game_profiles for r in self.step_records) / simulated_time,
            "mpc_refinements_per_step": sum(r.mpc_refinements for r in self.step_records) / simulated_time,
            "cbf_calls_per_step": sum(r.cbf_filter_calls for r in self.step_records) / simulated_time,
            "timeout_fallback_count": sum(r.timeout_fallback_count for r in self.step_records),
            "capped_game_count": sum(r.capped_game_count for r in self.step_records),
            "capped_mpc_count": sum(r.capped_mpc_count for r in self.step_records),
            "capped_cbf_count": sum(r.capped_cbf_count for r in self.step_records),
            "planner_plan_time_ms": sum(r.planner_plan_time_ms for r in self.step_records),
            "safety_supervisor_time_ms": sum(r.safety_supervisor_time_ms for r in self.step_records),
            "dynamics_envelope_time_ms": sum(r.dynamics_envelope_time_ms for r in self.step_records),
            "reservation_table_time_ms": sum(r.reservation_table_time_ms for r in self.step_records),
            "astar_or_bfs_time_ms": sum(r.astar_or_bfs_time_ms for r in self.step_records),
            "local_game_time_ms": sum(r.local_game_time_ms for r in self.step_records),
            "mpc_qp_refinement_time_ms": sum(r.mpc_qp_refinement_time_ms for r in self.step_records),
            "cbf_robust_filter_time_ms": sum(r.cbf_robust_filter_time_ms for r in self.step_records),
            "logging_csv_overhead_ms": sum(r.logging_csv_overhead_ms for r in self.step_records),
            "planner_native_conflict_reduction_rate": (
                (
                    sum(r.raw_conflicts_before_repair for r in self.step_records)
                    - sum(r.raw_conflicts_after_planner_repair for r in self.step_records)
                )
                / max(1, sum(r.raw_conflicts_before_repair for r in self.step_records))
            ),
            "raw_conflicts_before_repair": sum(r.raw_conflicts_before_repair for r in self.step_records),
            "raw_conflicts_after_planner_repair": sum(r.raw_conflicts_after_planner_repair for r in self.step_records),
            "enable_game": int(max((r.enable_game for r in self.step_records), default=0)),
            "enable_mpc": int(max((r.enable_mpc for r in self.step_records), default=0)),
            "enable_cbf": int(max((r.enable_cbf for r in self.step_records), default=0)),
            "enable_stagnation_repair": int(max((r.enable_stagnation_repair for r in self.step_records), default=0)),
            "enable_robust_nominal": int(max((r.enable_robust_nominal for r in self.step_records), default=0)),
            "enable_safety_envelope_logging": int(max((r.enable_safety_envelope_logging for r in self.step_records), default=0)),
            "actual_window": max((r.actual_window for r in self.step_records), default=0),
            "reservation_horizon": max((r.reservation_horizon for r in self.step_records), default=0),
            "goal_reservation_enabled": int(max((r.goal_reservation_enabled for r in self.step_records), default=0)),
            "planned_path_length_mean": mean([r.planned_path_length_mean for r in self.step_records if r.planned_path_length_mean > 0]) if any(r.planned_path_length_mean > 0 for r in self.step_records) else 0.0,
            "reservation_table_size_mean": mean([r.reservation_table_size_mean for r in self.step_records if r.reservation_table_size_mean > 0]) if any(r.reservation_table_size_mean > 0 for r in self.step_records) else 0.0,
            "fairness_jain_wait": fairness,
            "average_path_stretch": mean(path_stretches) if path_stretches else math.nan,
        }

