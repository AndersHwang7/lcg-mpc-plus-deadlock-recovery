# Inha University & RODIX Inc, Anders Hwang
# 파일명: warehouse.py
# 목적 및 역할:
# 물류창고형 통로와 선반 구조를 가진 지도를 생성한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import random
from mr_deadlock.core.grid import GridMap


def make_warehouse_map(width: int, height: int, obstacle_density: float, rng: random.Random) -> GridMap:
    obs = set()
    aisle_gap = max(6, width // 12)
    shelf_w = max(2, width // 45)
    cross_gap = max(8, height // 8)
    for y in range(2, height - 2):
        for x in range(2, width - 2):
            # 선반은 세로 장애물로 두고 일정 간격마다 가로 통로를 남긴다.
            in_shelf_col = (x % aisle_gap) < shelf_w
            in_cross_aisle = (y % cross_gap) < 3
            if in_shelf_col and not in_cross_aisle:
                obs.add((x, y))
    # 중앙의 가로 세로 주 통로는 항상 비워 둔다.
    cx, cy = width // 2, height // 2
    for y in range(height):
        for dx in range(-2, 3):
            obs.discard((cx + dx, y))
    for x in range(width):
        for dy in range(-2, 3):
            obs.discard((x, cy + dy))
    return GridMap(width, height, obs, name="warehouse")

