# Inha University & RODIX Inc, Anders Hwang
# 파일명: intersection.py
# 목적 및 역할:
# 십자 교차로 형태의 지도를 생성한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import random
from mr_deadlock.core.grid import GridMap


def make_intersection_map(width: int, height: int, obstacle_density: float, rng: random.Random) -> GridMap:
    cx, cy = width // 2, height // 2
    road_w = max(3, min(width, height) // 12)
    obs = set()
    for y in range(height):
        for x in range(width):
            in_vertical = abs(x - cx) <= road_w
            in_horizontal = abs(y - cy) <= road_w
            if not (in_vertical or in_horizontal):
                obs.add((x, y))
    # 주 통행로를 막지 않는 범위에서만 약한 장애물을 넣는다.
    for y in range(height):
        for x in range(width):
            if (x, y) not in obs and rng.random() < obstacle_density * 0.1:
                obs.add((x, y))
    return GridMap(width, height, obs, name="intersection")

