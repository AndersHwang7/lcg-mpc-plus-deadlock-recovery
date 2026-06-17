# Inha University & RODIX Inc, Anders Hwang
# 파일명: tasks.py
# 목적 및 역할:
# 지도 유형에 맞게 시작점과 목표점 쌍을 샘플링한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import random
from mr_deadlock.core.grid import GridMap
from mr_deadlock.core.types import Cell


def _sample_from(cells: list[Cell], rng: random.Random, used: set[Cell]) -> Cell:
    for _ in range(10000):
        c = rng.choice(cells)
        if c not in used:
            used.add(c)
            return c
    raise RuntimeError("Could not sample a unique cell")


def sample_start_goals(grid: GridMap, n: int, mode: str, rng: random.Random) -> list[tuple[Cell, Cell]]:
    free = grid.free_cells()
    if len(free) < 2 * n:
        raise ValueError(f"Not enough free cells for {n} robots: {len(free)} free cells")
    mode = mode.lower()
    used: set[Cell] = set()
    pairs = []
    if mode == "cross_traffic":
        left = [c for c in free if c[0] < grid.width // 4]
        right = [c for c in free if c[0] > 3 * grid.width // 4]
        top = [c for c in free if c[1] < grid.height // 4]
        bottom = [c for c in free if c[1] > 3 * grid.height // 4]
        groups = [(left, right), (right, left), (top, bottom), (bottom, top)]
        for i in range(n):
            a, b = groups[i % len(groups)]
            if not a or not b:
                a = b = free
            s = _sample_from(a, rng, used)
            g = _sample_from(b, rng, used)
            pairs.append((s, g))
        return pairs
    if mode == "random":
        for _ in range(n):
            s = _sample_from(free, rng, used)
            g = _sample_from(free, rng, used)
            pairs.append((s, g))
        return pairs
    raise ValueError(f"Unknown start_goal_mode: {mode}")

