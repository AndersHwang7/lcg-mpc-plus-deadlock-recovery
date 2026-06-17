# Inha University & RODIX Inc, Anders Hwang
# 파일명: baselines.py
# 목적 및 역할:
# 외부 baseline 계열(ORCA, distributed MPC, IMPC-DR, MPC-CBF)을 동일 grid simulator에서
# 비교할 수 있도록 simulator-native surrogate와 adapter-friendly 클래스를 제공한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from math import hypot

from mr_deadlock.core.dynamics import KinematicSafetyConfig, cell_center, synchronous_segment_distance
from mr_deadlock.core.robot import Robot
from mr_deadlock.core.types import Cell, PlanResult
from mr_deadlock.planners.astar import AStar
from mr_deadlock.planners.base import Planner, PlannerContext
from mr_deadlock.planners.common import desired_next, resolve_vertex_edge_conflicts
from mr_deadlock.planners.whca import WHCAPlanner


def _active(ctx: PlannerContext) -> list[Robot]:
    return [r for r in ctx.robots if r.completed_at is None]


def _candidate_cells(grid, r: Robot) -> list[Cell]:
    cells = grid.neighbors4(r.pos, include_wait=True)
    nxt = desired_next(r)
    # path-following 후보를 앞에 두되, 모든 후보는 cost에서 다시 평가한다.
    cells = sorted(set(cells), key=lambda c: (c != nxt, grid.manhattan(c, r.goal), c))
    return cells


def _progress(grid, r: Robot, c: Cell) -> float:
    return float(grid.manhattan(r.pos, r.goal) - grid.manhattan(c, r.goal))


class ORCALitePlanner(Planner):
    """Grid-native ORCA/RVO-style reciprocal collision avoidance baseline.

    Full ORCA works in continuous velocity space. This lightweight version evaluates grid one-step
    velocity candidates and penalizes reciprocal closing motion and swept-footprint conflicts under
    the same simulator envelope, enabling fair paired experiments without an external dependency.
    """

    name = "orca_lite"

    def initialize(self, robots):
        astar = AStar(self.grid)
        for r in robots:
            r.path = astar.search(r.start, r.goal) or [r.start]
            r.nominal_path_length = max(0, len(r.path) - 1)

    def _orca_cost(self, r: Robot, target: Cell, robots: list[Robot], reserved: set[Cell]) -> float:
        cfg = KinematicSafetyConfig.from_config(self.config)
        min_sep = cfg.min_robot_separation
        p0, p1 = cell_center(r.pos), cell_center(target)
        vx, vy = p1[0] - p0[0], p1[1] - p0[1]
        cost = self.grid.manhattan(target, r.goal) - 0.45 * _progress(self.grid, r, target)
        if target == r.pos:
            cost += 0.35 + 0.08 * r.local_wait_streak
        if target in reserved:
            cost += 500.0
        for other in robots:
            if other.id == r.id:
                continue
            q0 = cell_center(other.pos)
            q1 = cell_center(desired_next(other))
            d_now = hypot(p0[0] - q0[0], p0[1] - q0[1])
            d_next = hypot(p1[0] - q1[0], p1[1] - q1[1])
            rel_vx = vx - (q1[0] - q0[0])
            rel_vy = vy - (q1[1] - q0[1])
            rel_px = p0[0] - q0[0]
            rel_py = p0[1] - q0[1]
            closing = -(rel_px * rel_vx + rel_py * rel_vy)
            if closing > 0:
                cost += 0.02 * closing / max(1e-6, d_now)
            swept = synchronous_segment_distance(p0, p1, q0, q1)
            if d_next < min_sep:
                cost += 800.0 + 100.0 * (min_sep - d_next)
            if swept < min_sep:
                cost += 400.0 + 80.0 * (min_sep - swept)
        return float(cost)

    def plan(self, ctx: PlannerContext) -> PlanResult:
        robots = _active(ctx)
        order = sorted(robots, key=lambda r: (-r.wait_time - r.fairness_debt, r.remaining_distance_estimate(), r.id))
        moves: dict[int, Cell] = {}
        reserved: set[Cell] = set()
        for r in order:
            candidates = _candidate_cells(self.grid, r)
            best = min(candidates, key=lambda c: self._orca_cost(r, c, robots, reserved))
            moves[r.id] = best
            reserved.add(best)
        for r in ctx.robots:
            moves.setdefault(r.id, r.pos)
        moves, fixed = resolve_vertex_edge_conflicts(ctx.robots, moves)
        return PlanResult(moves, {"baseline_family": "orca_lite", "fixed_conflicts": fixed})


class DMPCLitePlanner(Planner):
    """Distributed MPC-style finite-action local horizon baseline."""

    name = "dmpc_lite"

    def initialize(self, robots):
        astar = AStar(self.grid)
        for r in robots:
            r.path = astar.search(r.start, r.goal) or [r.start]
            r.nominal_path_length = max(0, len(r.path) - 1)

    def _rollout_cost(self, r: Robot, first: Cell, robots: list[Robot], reserved: set[Cell]) -> float:
        horizon = int(self.config.get("dmpc_horizon", self.config.get("mpc_horizon", 6)))
        target = first
        cost = 0.0
        cur = target
        # one-step control plus a greedy nominal rollout gives a comparable MPC surrogate.
        for tau in range(1, horizon + 1):
            goal_d = self.grid.manhattan(cur, r.goal)
            cost += goal_d / tau
            if tau == 1 and cur == r.pos:
                cost += 0.4 + 0.12 * r.local_wait_streak
            if cur in reserved:
                cost += 400.0 / tau
            for other in robots:
                if other.id == r.id:
                    continue
                pred_other = desired_next(other) if tau == 1 else other.goal
                d = self.grid.manhattan(cur, pred_other)
                if d == 0:
                    cost += 900.0 / tau
                elif d == 1:
                    cost += 2.5 / tau
            if cur == r.goal:
                break
            # nominal rollout step after the first action.
            nbs = self.grid.neighbors4(cur, include_wait=True)
            cur = min(nbs, key=lambda c: (self.grid.manhattan(c, r.goal), c == cur, c))
        ax = (first[0] - r.pos[0]) - r.velocity_x
        ay = (first[1] - r.pos[1]) - r.velocity_y
        cost += float(self.config.get("dmpc_w_accel", 0.05)) * (ax * ax + ay * ay)
        cost -= 0.18 * r.fairness_debt * max(0.0, _progress(self.grid, r, first))
        return float(cost)

    def plan(self, ctx: PlannerContext) -> PlanResult:
        robots = _active(ctx)
        order = sorted(robots, key=lambda r: (-r.wait_time - r.fairness_debt, r.remaining_distance_estimate(), r.id))
        moves: dict[int, Cell] = {}
        reserved: set[Cell] = set()
        for r in order:
            best = min(_candidate_cells(self.grid, r), key=lambda c: self._rollout_cost(r, c, robots, reserved))
            moves[r.id] = best
            reserved.add(best)
        for r in ctx.robots:
            moves.setdefault(r.id, r.pos)
        moves, fixed = resolve_vertex_edge_conflicts(ctx.robots, moves)
        return PlanResult(moves, {"baseline_family": "dmpc_lite", "fixed_conflicts": fixed})


class MPCCBFLitePlanner(Planner):
    """WHCA nominal + CBF-like one-step safety filter baseline."""

    name = "mpc_cbf_lite"

    def __init__(self, grid, config=None):
        super().__init__(grid, config)
        self.nominal = WHCAPlanner(grid, config)

    def initialize(self, robots):
        self.nominal.initialize(robots)

    def _barrier_safe(
        self,
        r: Robot,
        target: Cell,
        chosen: dict[int, Cell],
        robots: list[Robot],
        risk_scale: float = 1.0,
    ) -> bool:
        cfg = KinematicSafetyConfig.from_config({**self.config, "uncertainty_k": float(self.config.get("uncertainty_k", 2.0)) * risk_scale})
        min_sep = cfg.min_robot_separation
        p0, p1 = cell_center(r.pos), cell_center(target)
        for other in robots:
            if other.id == r.id:
                continue
            ot = chosen.get(other.id, other.pos)
            q0, q1 = cell_center(other.pos), cell_center(ot)
            if hypot(p1[0] - q1[0], p1[1] - q1[1]) < min_sep - 1e-12:
                return False
            if synchronous_segment_distance(p0, p1, q0, q1) < min_sep - 1e-12:
                return False
        return True

    def plan(self, ctx: PlannerContext) -> PlanResult:
        base = self.nominal.plan(ctx)
        robots = _active(ctx)
        order = sorted(robots, key=lambda r: (-r.wait_time - r.fairness_debt, r.id))
        chosen: dict[int, Cell] = {}
        clips = 0
        for r in order:
            target = base.moves.get(r.id, r.pos)
            if self._barrier_safe(r, target, chosen, robots, risk_scale=1.0):
                chosen[r.id] = target
            else:
                chosen[r.id] = r.pos
                clips += int(target != r.pos)
        for r in ctx.robots:
            chosen.setdefault(r.id, r.pos)
        chosen, fixed = resolve_vertex_edge_conflicts(ctx.robots, chosen)
        return PlanResult(
            chosen,
            {"baseline_family": "mpc_cbf_lite", "cbf_clips": clips, "fixed_conflicts": fixed},
        )


class IMPCDRLitePlanner(MPCCBFLitePlanner):
    """Distributionally robust IMPC-style baseline using an inflated uncertainty buffer."""

    name = "impc_dr_lite"

    def plan(self, ctx: PlannerContext) -> PlanResult:
        base = self.nominal.plan(ctx)
        robots = _active(ctx)
        # 가장 오래 기다린 로봇부터 robust safety filter를 통과시켜 보수성으로 인한 starve를 줄인다.
        order = sorted(robots, key=lambda r: (-r.wait_time - 1.5 * r.fairness_debt, r.remaining_distance_estimate(), r.id))
        chosen: dict[int, Cell] = {}
        clips = 0
        risk_scale = float(ctx.config.get("impc_dr_risk_scale", self.config.get("impc_dr_risk_scale", 1.45)))
        for r in order:
            target = base.moves.get(r.id, r.pos)
            if self._barrier_safe(r, target, chosen, robots, risk_scale=risk_scale):
                chosen[r.id] = target
            else:
                # robust filter가 너무 보수적인 경우에는 더 작은 local action 중 가장 안전한 후보를 선택한다.
                alternatives = _candidate_cells(self.grid, r)
                safe_alt = next(
                    (c for c in alternatives if c != target and self._barrier_safe(r, c, chosen, robots, risk_scale=risk_scale)),
                    r.pos,
                )
                chosen[r.id] = safe_alt
                clips += int(target != safe_alt)
        for r in ctx.robots:
            chosen.setdefault(r.id, r.pos)
        chosen, fixed = resolve_vertex_edge_conflicts(ctx.robots, chosen)
        return PlanResult(
            chosen,
            {"baseline_family": "impc_dr_lite", "robust_clips": clips, "fixed_conflicts": fixed},
        )

