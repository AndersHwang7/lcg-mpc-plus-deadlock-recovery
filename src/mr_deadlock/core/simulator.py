# Inha University & RODIX Inc, Anders Hwang
# 파일명: simulator.py
# 목적 및 역할:
# planner가 제안한 이동을 안전 감독기로 보정하고 step 단위 실험을 실행한다.
# 100/1000 seed 대규모 실험을 위해 충돌 검사는 O(N) 중심으로 최적화하고,
# 비교 시각화를 위해 각 step의 raw/validated move 정보를 반환한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from mr_deadlock.core.grid import GridMap
from mr_deadlock.core.robot import Robot
from mr_deadlock.core.types import Cell, MoveDict
from mr_deadlock.planners.base import PlannerContext
from mr_deadlock.experiments.metrics import MetricsCollector, StepRecord
from mr_deadlock.planners.common import sanitize_moves
from mr_deadlock.core.dynamics import KinematicSafetyConfig, validate_kinematic_envelope, update_robot_velocity_state


@dataclass
class SimulationResult:
    summary: dict
    step_records: list[StepRecord]
    robots: list[Robot]


class Simulator:
    def __init__(self, grid: GridMap, robots: list[Robot], planner, config: dict):
        self.grid = grid
        self.robots = robots
        self.planner = planner
        self.config = config
        self.metrics = MetricsCollector()
        self.t = 0
        self.max_steps = int(config.get("max_steps", 1000))
        self.kinematic_cfg = KinematicSafetyConfig.from_config(config)
        self.last_kinematic_diagnostics = None
        self.last_dynamics_envelope_time_ms = 0.0
        self.planner.initialize(self.robots)

    def _edge_swaps(self, old_pos: dict[int, Cell], moves: MoveDict) -> list[tuple[int, int]]:
        owner: dict[tuple[Cell, Cell], int] = {}
        swaps: list[tuple[int, int]] = []
        for rid, old in old_pos.items():
            new = moves.get(rid, old)
            if new == old:
                continue
            other = owner.get((new, old))
            if other is not None:
                swaps.append((other, rid))
            owner[(old, new)] = rid
        return swaps

    # 모든 planner가 같은 안전 감독기를 거치도록 한 step 이동을 다시 확인한다.
    # 충돌 후보는 보수적으로 대기 처리해서 실험 비교 조건을 맞춘다.
    def _validate_moves(self, moves):
        active_robots = [r for r in self.robots if r.completed_at is None]
        fixed = sanitize_moves(active_robots, moves)
        old_pos = {r.id: r.pos for r in active_robots}
        invalid = 0

        # 지도 밖 이동, 장애물 이동, 한 칸을 넘는 이동은 대기로 바꾼다.
        for r in active_robots:
            target = fixed.get(r.id, r.pos)
            if target != r.pos and target not in self.grid.neighbors4(r.pos):
                fixed[r.id] = r.pos
                invalid += 1
            elif not self.grid.passable(target):
                fixed[r.id] = r.pos
                invalid += 1

        # 정점 충돌과 자리교환 충돌은 새 충돌이 생기지 않을 때까지 반복 보정한다.
        # 각 반복의 충돌 탐지는 해시맵 기반으로 수행하여 1000대 규모에서도 안정적이다.
        changed = True
        while changed:
            changed = False
            by_target: dict[Cell, list[int]] = {}
            for rid, target in fixed.items():
                by_target.setdefault(target, []).append(rid)
            for target, ids in by_target.items():
                if len(ids) > 1:
                    ids_sorted = sorted(ids)
                    keep = min(ids_sorted, key=lambda rid: (old_pos[rid] != target, rid))
                    for rid in ids_sorted:
                        if rid != keep and fixed[rid] != old_pos[rid]:
                            fixed[rid] = old_pos[rid]
                            invalid += 1
                            changed = True
            for a, b in self._edge_swaps(old_pos, fixed):
                loser = max(a, b)
                if fixed[loser] != old_pos[loser]:
                    fixed[loser] = old_pos[loser]
                    invalid += 1
                    changed = True
        # Grid-level supervisor 이후 AMR 연속 footprint/swept-volume/acceleration envelope를 적용한다.
        dyn_tic = time.perf_counter()
        fixed, kin_diag = validate_kinematic_envelope(active_robots, fixed, self.grid, self.kinematic_cfg)
        self.last_dynamics_envelope_time_ms = (time.perf_counter() - dyn_tic) * 1000.0
        self.last_kinematic_diagnostics = kin_diag

        # invalid는 실제 충돌이 아니라 안전 감독기가 보정한 횟수이다.
        # 논문 지표의 collision_count는 최종 실행 이동에서 실제 충돌이 남았는지만 센다.
        actual_collision = self._count_remaining_collisions(active_robots, fixed)
        self.metrics.collision_count += actual_collision
        return fixed, invalid

    def _count_remaining_collisions(self, robots, moves) -> int:
        vertex, edge = self._count_vertex_edge_collisions(robots, moves)
        return vertex + edge

    def _count_vertex_edge_collisions(self, robots, moves) -> tuple[int, int]:
        old_pos = {r.id: r.pos for r in robots}
        seen: dict[Cell, int] = {}
        vertex_collisions = 0
        for r in robots:
            target = moves.get(r.id, r.pos)
            if target in seen:
                vertex_collisions += 1
            else:
                seen[target] = r.id
        edge_collisions = len(self._edge_swaps(old_pos, moves))
        return vertex_collisions, edge_collisions

    def step(self) -> dict[str, Any]:
        ctx = PlannerContext(self.grid, self.robots, self.t, self.config)
        active_before_apply = [r for r in self.robots if r.completed_at is None]
        old_positions = {r.id: r.pos for r in active_before_apply}
        tic = time.perf_counter()
        plan_tic = time.perf_counter()
        result = self.planner.plan(ctx)
        planner_plan_time_ms = (time.perf_counter() - plan_tic) * 1000.0
        raw_moves = dict(result.moves)
        raw_vertex, raw_edge = self._count_vertex_edge_collisions(active_before_apply, raw_moves)
        supervisor_tic = time.perf_counter()
        moves, invalid = self._validate_moves(result.moves)
        safety_supervisor_time_ms = (time.perf_counter() - supervisor_tic) * 1000.0
        final_vertex, final_edge = self._count_vertex_edge_collisions(active_before_apply, moves)
        elapsed_ms = (time.perf_counter() - tic) * 1000.0
        timeout_limit = float(self.config.get("planner_step_timeout_ms", 0.0) or 0.0)
        timeout_count = int(timeout_limit > 0.0 and elapsed_ms > timeout_limit)
        timeout_fallback_count = 0
        if timeout_count:
            moves = {r.id: r.pos for r in active_before_apply}
            final_vertex, final_edge = self._count_vertex_edge_collisions(active_before_apply, moves)
            timeout_fallback_count = int(bool(self.config.get("safe_fallback_on_timeout", True)))
        update_robot_velocity_state(active_before_apply, moves, dt=self.kinematic_cfg.dt)
        for r in self.robots:
            r.apply_move(moves.get(r.id, r.pos), self.t + 1)
        meta = result.metadata
        active = sum(1 for r in self.robots if r.completed_at is None)
        completed = len(self.robots) - active
        kin_vals = (self.last_kinematic_diagnostics.as_record_values() if self.last_kinematic_diagnostics is not None else {})
        record = StepRecord(
            t=self.t,
            active=active,
            completed=completed,
            deadlock_candidates=len(meta.get("sccs", [])),
            persistent_deadlocks=len(meta.get("persistent_sccs", [])),
            local_conflict_sets=len(meta.get("conflict_sets", [])),
            retreat_actions=int(meta.get("retreat_actions", 0)),
            fixed_conflicts=int(meta.get("fixed_conflicts", 0)) + invalid,
            game_profiles=int(meta.get("game_profiles", 0)),
            mpc_refinements=int(meta.get("mpc_refinements", 0)),
            step_runtime_ms=elapsed_ms,
            footprint_conflicts=int(kin_vals.get("footprint_conflicts", 0)),
            swept_conflicts=int(kin_vals.get("swept_conflicts", 0)),
            obstacle_envelope_conflicts=int(kin_vals.get("obstacle_envelope_conflicts", 0)),
            acceleration_clips=int(kin_vals.get("acceleration_clips", 0)),
            speed_clips=int(kin_vals.get("speed_clips", 0)),
            sensing_risk_events=int(kin_vals.get("sensing_risk_events", 0)),
            continuous_min_clearance=float(kin_vals.get("continuous_min_clearance", float("nan"))),
            raw_vertex_conflicts=int(raw_vertex),
            raw_edge_swap_conflicts=int(raw_edge),
            final_vertex_conflicts=int(final_vertex),
            final_edge_swap_conflicts=int(final_edge),
            supervisor_interventions=int(invalid),
            planner_level_repairs=int(meta.get("retreat_actions", 0)) + int(meta.get("adaptive_cbf_clips", 0)) + int(meta.get("cbf_clips", 0)) + int(meta.get("robust_clips", 0)),
            exact_game_count=int(meta.get("game_exact_components", 0)),
            partitioned_exact_count=int(meta.get("game_exact_components", 0)) if str(meta.get("game_selection_mode", "")) == "partitioned_exact" else 0,
            greedy_fallback_count=int(meta.get("game_greedy_components", 0)),
            cbf_filter_calls=int(meta.get("adaptive_cbf_clips", 0) > 0 or meta.get("cbf_clips", 0) or meta.get("robust_clips", 0)),
            stagnation_repair_calls=int(len(meta.get("stagnation_components", []))),
            robust_nominal_repairs=int(meta.get("robust_nominal_repairs", 0)),
            timeout_count=timeout_count,
            raw_conflicts_before_repair=int(meta.get("raw_conflicts_before_repair", raw_vertex + raw_edge)),
            raw_conflicts_after_planner_repair=int(raw_vertex + raw_edge),
            enable_game=int(bool(meta.get("enable_game", False))),
            enable_mpc=int(bool(meta.get("enable_mpc", False))),
            enable_cbf=int(bool(meta.get("enable_cbf", False))),
            enable_stagnation_repair=int(bool(meta.get("enable_stagnation_repair", False))),
            enable_robust_nominal=int(bool(meta.get("enable_robust_nominal", False))),
            enable_safety_envelope_logging=int(bool(meta.get("enable_safety_envelope_logging", self.kinematic_cfg.enabled))),
            actual_window=int(meta.get("actual_window", meta.get("window", 0))),
            reservation_horizon=int(meta.get("reservation_horizon", meta.get("window", 0))),
            goal_reservation_enabled=int(bool(meta.get("goal_reservation_enabled", meta.get("goal_reservation", False)))),
            planned_path_length_mean=float(meta.get("planned_path_length_mean", 0.0)),
            reservation_table_size_mean=float(meta.get("reservation_table_size_mean", 0.0)),
            timeout_fallback_count=timeout_fallback_count,
            capped_game_count=int(meta.get("capped_game_count", 0)),
            capped_mpc_count=int(meta.get("capped_mpc_count", 0)),
            capped_cbf_count=int(meta.get("capped_cbf_count", 0)),
            mpc_refinements_per_step=float(meta.get("mpc_refinements", 0)),
            cbf_calls_per_step=float(meta.get("adaptive_cbf_clips", 0) > 0 or meta.get("cbf_clips", 0) or meta.get("robust_clips", 0)),
            planner_plan_time_ms=planner_plan_time_ms,
            safety_supervisor_time_ms=safety_supervisor_time_ms,
            dynamics_envelope_time_ms=self.last_dynamics_envelope_time_ms,
            reservation_table_time_ms=float(meta.get("reservation_table_time_ms", 0.0)),
            astar_or_bfs_time_ms=float(meta.get("astar_or_bfs_time_ms", 0.0)),
            local_game_time_ms=float(meta.get("local_game_time_ms", 0.0)),
            mpc_qp_refinement_time_ms=float(meta.get("mpc_qp_refinement_time_ms", 0.0)),
            cbf_robust_filter_time_ms=float(meta.get("cbf_robust_filter_time_ms", 0.0)),
            logging_csv_overhead_ms=0.0,
        )
        self.metrics.log_step(record)
        self.t += 1
        return {
            "t": record.t,
            "old_positions": old_positions,
            "raw_moves": raw_moves,
            "validated_moves": dict(moves),
            "metadata": meta,
            "record": record,
        }

    # 전체 실험 루프이다. 매 step마다 계획, 안전 보정, 실행, 기록 순서로 진행한다.
    def run(self, scenario: dict, algorithm: str, seed: int) -> SimulationResult:
        tic = time.perf_counter()
        while self.t < self.max_steps and any(r.completed_at is None for r in self.robots):
            self.step()
        runtime_sec = time.perf_counter() - tic
        summary = self.metrics.summary(
            self.robots,
            max_steps=self.max_steps,
            executed_steps=self.t,
            runtime_sec=runtime_sec,
            scenario=scenario,
            algorithm=algorithm,
            seed=seed,
        )
        return SimulationResult(summary, self.metrics.step_records, self.robots)

