# Inha University & RODIX Inc, Anders Hwang
# 파일명: corridor.py
# 목적 및 역할:
# 양방향 복도와 passing bay가 있는 지도를 생성한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import random
from mr_deadlock.core.grid import GridMap


def make_corridor_map(width: int, height: int, obstacle_density: float, rng: random.Random) -> GridMap:
    cy = height // 2
    road_w = max(2, height // 20)
    obs = set()
    for y in range(height):
        for x in range(width):
            if abs(y - cy) > road_w:
                obs.add((x, y))
    # 서로 비켜 지나갈 수 있는 작은 대피 공간을 둔다.
    for x in range(width // 8, width, max(8, width // 8)):
        for yy in range(max(0, cy - road_w - 3), min(height, cy + road_w + 4)):
            for xx in range(max(0, x - 2), min(width, x + 3)):
                obs.discard((xx, yy))
    return GridMap(width, height, obs, name="corridor")

