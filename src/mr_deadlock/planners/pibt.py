# Inha University & RODIX Inc, Anders Hwang
# 파일명: pibt.py
# 목적 및 역할:
# 대규모 비교를 위한 간소화된 priority inheritance with backtracking planner이다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from mr_deadlock.core.types import Cell, PlanResult
from mr_deadlock.planners.base import Planner, PlannerContext
from mr_deadlock.planners.astar import AStar


# 논문 비교를 위한 간소화된 PIBT 계열 planner이다.
# 원 논문의 세부 구현을 그대로 복제하기보다 공통 API에 맞춘 baseline으로 둔다.
class PIBTPlanner(Planner):

    name = "pibt"

    def initialize(self, robots):
        astar = AStar(self.grid)
        for r in robots:
            r.path = astar.search(r.start, r.goal) or [r.start]
            r.nominal_path_length = max(0, len(r.path) - 1)

    def plan(self, ctx: PlannerContext) -> PlanResult:
        robots = [r for r in ctx.robots if r.completed_at is None]
        occ = {r.pos: r.id for r in robots}
        by_id = {r.id: r for r in robots}
        decided: dict[int, Cell] = {}
        reserved: set[Cell] = set()
        reserved_edges: set[tuple[Cell, Cell]] = set()

        def candidates(r):
            nb = self.grid.neighbors4(r.pos, include_wait=True)
            return sorted(nb, key=lambda c: (self.grid.manhattan(c, r.goal), c != r.pos))

        # 한 로봇이 목표 칸으로 가려 할 때 막고 있는 로봇을 재귀적으로 밀어낸다.
        def assign(rid: int, stack: set[int]) -> bool:
            if rid in decided:
                return True
            if rid in stack:
                return False
            r = by_id[rid]
            stack.add(rid)
            for c in candidates(r):
                if c in reserved:
                    continue
                if (c, r.pos) in reserved_edges:
                    continue
                blocker = occ.get(c)
                if blocker is not None and blocker != rid:
                    # 막고 있는 로봇에게 우선순위를 넘겨 재귀적으로 이동을 시도한다.
                    if not assign(blocker, stack):
                        continue
                    if decided.get(blocker, c) == c:
                        continue
                decided[rid] = c
                reserved.add(c)
                reserved_edges.add((r.pos, c))
                stack.remove(rid)
                return True
            decided[rid] = r.pos
            reserved.add(r.pos)
            stack.remove(rid)
            return True

        order = sorted(robots, key=lambda r: (-r.wait_time, r.remaining_distance_estimate(), r.id))
        for r in order:
            assign(r.id, set())
        for r in ctx.robots:
            decided.setdefault(r.id, r.pos)
        return PlanResult(decided, {"priority_order": [r.id for r in order]})

