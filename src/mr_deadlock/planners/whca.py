# Inha University & RODIX Inc, Anders Hwang
# 파일명: whca.py
# 목적 및 역할:
# 짧은 시간창의 공간 시간 예약 탐색을 수행하는 WHCA 계열 baseline이다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import heapq
import time
from mr_deadlock.core.types import Cell, PlanResult
from mr_deadlock.planners.base import Planner, PlannerContext
from mr_deadlock.planners.astar import AStar


# 짧은 시간창에서 정점과 간선 예약을 사용해 이동을 정한다.
# RHCR과 WMAPF 계열 비교를 위한 가벼운 baseline이다.
class WHCAPlanner(Planner):

    name = "whca"

    def initialize(self, robots):
        astar = AStar(self.grid)
        for r in robots:
            r.path = astar.search(r.start, r.goal) or [r.start]
            r.nominal_path_length = max(0, len(r.path) - 1)

    def _space_time_search(self, start: Cell, goal: Cell, window: int, vertex_res, edge_res) -> list[Cell]:
        start_state = (start, 0)
        pq = [(self.grid.manhattan(start, goal), 0, start, 0)]
        came = {start_state: None}
        cost = {start_state: 0}
        best_state = start_state
        while pq:
            _, g, cell, tau = heapq.heappop(pq)
            if self.grid.manhattan(cell, goal) < self.grid.manhattan(best_state[0], goal):
                best_state = (cell, tau)
            if cell == goal or tau >= window:
                best_state = (cell, tau)
                break
            for nb in self.grid.neighbors4(cell, include_wait=True):
                nt = tau + 1
                if (nt, nb) in vertex_res:
                    continue
                if (nt, nb, cell) in edge_res:
                    continue
                st = (nb, nt)
                ng = g + 1
                if st not in cost or ng < cost[st]:
                    cost[st] = ng
                    pri = ng + self.grid.manhattan(nb, goal)
                    heapq.heappush(pq, (pri, ng, nb, nt))
                    came[st] = (cell, tau)
        path = []
        cur = best_state
        while cur is not None:
            path.append(cur[0])
            cur = came.get(cur)
        path.reverse()
        return path

    def plan(self, ctx: PlannerContext) -> PlanResult:
        window = int(ctx.config.get("whca_window", self.config.get("whca_window", 8)))
        reserve_goal = bool(ctx.config.get("whca_goal_reservation", self.config.get("whca_goal_reservation", False)))
        vertex_res = set()
        edge_res = set()
        moves = {}
        planned_lengths = []
        astar_time_ms = 0.0
        reservation_time_ms = 0.0
        order = sorted(
            [r for r in ctx.robots if r.completed_at is None],
            key=lambda r: (-r.wait_time, r.remaining_distance_estimate(), r.id),
        )
        for r in order:
            search_tic = time.perf_counter()
            st_path = self._space_time_search(r.pos, r.goal, window, vertex_res, edge_res)
            astar_time_ms += (time.perf_counter() - search_tic) * 1000.0
            planned_lengths.append(len(st_path))
            nxt = st_path[1] if len(st_path) > 1 else r.pos
            moves[r.id] = nxt
            # 이번 시간창에서 찾은 경로를 예약표에 반영한다.
            reservation_tic = time.perf_counter()
            for tau, c in enumerate(st_path[: window + 1]):
                vertex_res.add((tau, c))
                if tau > 0:
                    edge_res.add((tau, st_path[tau - 1], c))
            if reserve_goal and st_path:
                final = st_path[-1]
                if final == r.goal:
                    for tau in range(len(st_path), window + 1):
                        vertex_res.add((tau, final))
            reservation_time_ms += (time.perf_counter() - reservation_tic) * 1000.0
        for r in ctx.robots:
            moves.setdefault(r.id, r.pos)
        return PlanResult(
            moves,
            {
                "window": window,
                "actual_window": window,
                "reservation_horizon": window,
                "goal_reservation": reserve_goal,
                "goal_reservation_enabled": reserve_goal,
                "replanning_interval": 1,
                "tie_breaking_policy": "wait_desc_distance_asc_id_asc",
                "planned_path_length_mean": sum(planned_lengths) / max(1, len(planned_lengths)),
                "reservation_table_size_mean": len(vertex_res) + len(edge_res),
                "reservation_table_time_ms": reservation_time_ms,
                "astar_or_bfs_time_ms": astar_time_ms,
            },
        )

