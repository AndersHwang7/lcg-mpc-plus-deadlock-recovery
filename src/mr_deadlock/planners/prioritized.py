# Inha University & RODIX Inc, Anders Hwang
# 파일명: prioritized.py
# 목적 및 역할:
# 대기시간과 남은 거리 기반의 동적 우선순위 baseline을 구현한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from mr_deadlock.core.types import PlanResult
from mr_deadlock.planners.base import Planner, PlannerContext
from mr_deadlock.planners.astar import AStar
from mr_deadlock.planners.common import desired_next


class PrioritizedPlanner(Planner):
    name = "prioritized"

    def initialize(self, robots):
        astar = AStar(self.grid)
        for r in robots:
            r.path = astar.search(r.start, r.goal) or [r.start]
            r.nominal_path_length = max(0, len(r.path) - 1)

    def plan(self, ctx: PlannerContext) -> PlanResult:
        occupied_now = {r.pos: r.id for r in ctx.robots if r.completed_at is None}
        reserved_targets = set()
        reserved_edges = set()
        moves = {}
        # 오래 기다린 로봇을 먼저 처리하고, 남은 거리가 짧은 로봇을 다음 기준으로 둔다.
        order = sorted(
            [r for r in ctx.robots if r.completed_at is None],
            key=lambda r: (-r.wait_time, r.remaining_distance_estimate(), r.id),
        )
        for r in order:
            nxt = desired_next(r)
            edge = (r.pos, nxt)
            rev = (nxt, r.pos)
            if nxt in reserved_targets or rev in reserved_edges:
                moves[r.id] = r.pos
                continue
            owner = occupied_now.get(nxt)
            if owner is not None and owner != r.id:
                # 상대가 비켜나는 경우가 아니면 현재 점유된 칸으로 들어가지 않는다.
                if owner not in moves or moves.get(owner) == nxt:
                    moves[r.id] = r.pos
                    continue
            moves[r.id] = nxt
            reserved_targets.add(nxt)
            reserved_edges.add(edge)
        for r in ctx.robots:
            moves.setdefault(r.id, r.pos)
        return PlanResult(moves, {"priority_order": [r.id for r in order]})

