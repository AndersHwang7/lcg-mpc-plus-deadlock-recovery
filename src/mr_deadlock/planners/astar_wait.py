# Inha University & RODIX Inc, Anders Hwang
# 파일명: astar_wait.py
# 목적 및 역할:
# A* 경로를 따라가되 막히면 대기하는 가장 단순한 baseline이다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from mr_deadlock.core.types import PlanResult
from mr_deadlock.planners.base import Planner, PlannerContext
from mr_deadlock.planners.astar import AStar
from mr_deadlock.planners.common import desired_next, resolve_vertex_edge_conflicts


class AStarWaitPlanner(Planner):
    name = "astar_wait"

    def initialize(self, robots):
        astar = AStar(self.grid)
        occupied = {r.start for r in robots}
        for r in robots:
            path = astar.search(r.start, r.goal, blocked=occupied - {r.start, r.goal})
            if not path:
                path = astar.search(r.start, r.goal)
            r.path = path or [r.start]
            r.nominal_path_length = max(0, len(r.path) - 1)

    def plan(self, ctx: PlannerContext) -> PlanResult:
        moves = {r.id: desired_next(r) for r in ctx.robots}
        moves, conflicts = resolve_vertex_edge_conflicts(ctx.robots, moves)
        return PlanResult(moves, {"conflicts_resolved": conflicts})

