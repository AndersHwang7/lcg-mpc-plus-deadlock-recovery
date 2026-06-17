# Inha University & RODIX Inc, Anders Hwang
# 파일명: astar.py
# 목적 및 역할:
# 단일 로봇의 최단 경로를 찾는 A* 탐색기를 제공한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import heapq
from typing import Optional
from mr_deadlock.core.grid import GridMap
from mr_deadlock.core.types import Cell


class AStar:
    def __init__(self, grid: GridMap):
        self.grid = grid

    # 시작점에서 목표점까지 장애물을 피해 최단 격자 경로를 찾는다.
    def search(
        self,
        start: Cell,
        goal: Cell,
        blocked: set[Cell] | None = None,
        max_expansions: int | None = None,
    ) -> list[Cell]:
        if start == goal:
            return [start]
        if not self.grid.passable(start) or not self.grid.passable(goal):
            return []
        blocked = blocked or set()
        frontier: list[tuple[int, int, Cell]] = []
        counter = 0
        heapq.heappush(frontier, (0, counter, start))
        came_from: dict[Cell, Optional[Cell]] = {start: None}
        cost_so_far: dict[Cell, int] = {start: 0}
        expansions = 0
        while frontier:
            _, _, current = heapq.heappop(frontier)
            expansions += 1
            if max_expansions is not None and expansions > max_expansions:
                break
            if current == goal:
                break
            for nxt in self.grid.neighbors4(current):
                if nxt in blocked and nxt != goal:
                    continue
                new_cost = cost_so_far[current] + 1
                if nxt not in cost_so_far or new_cost < cost_so_far[nxt]:
                    cost_so_far[nxt] = new_cost
                    priority = new_cost + self.grid.manhattan(nxt, goal)
                    counter += 1
                    heapq.heappush(frontier, (priority, counter, nxt))
                    came_from[nxt] = current
        if goal not in came_from:
            return []
        path = []
        cur: Cell | None = goal
        while cur is not None:
            path.append(cur)
            cur = came_from[cur]
        path.reverse()
        return path

