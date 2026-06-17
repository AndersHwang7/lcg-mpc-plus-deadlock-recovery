# Inha University & RODIX Inc, Anders Hwang
# 파일명: grid.py
# 목적 및 역할:
# 격자 지도와 이동 가능 셀, 이웃 셀, 거리 계산을 담당한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from dataclasses import dataclass
from .types import Cell


@dataclass
class GridMap:
    width: int
    height: int
    obstacles: set[Cell]
    name: str = "grid"

    def in_bounds(self, c: Cell) -> bool:
        x, y = c
        return 0 <= x < self.width and 0 <= y < self.height

    def passable(self, c: Cell) -> bool:
        return self.in_bounds(c) and c not in self.obstacles

    # 상하좌우 네 방향을 기본 이동으로 사용한다. 필요할 때 제자리 대기도 이웃으로 포함한다.
    def neighbors4(self, c: Cell, include_wait: bool = False) -> list[Cell]:
        x, y = c
        nb = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        if include_wait:
            nb.append(c)
        return [p for p in nb if self.passable(p)]

    def manhattan(self, a: Cell, b: Cell) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def free_cells(self) -> list[Cell]:
        return [(x, y) for y in range(self.height) for x in range(self.width) if self.passable((x, y))]

    def obstacle_ratio(self) -> float:
        return len(self.obstacles) / max(1, self.width * self.height)

    def degree(self, c: Cell) -> int:
        return len(self.neighbors4(c))

