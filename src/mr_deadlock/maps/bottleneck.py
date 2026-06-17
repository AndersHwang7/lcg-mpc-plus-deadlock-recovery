# Inha University & RODIX Inc, Anders Hwang
# 파일명: bottleneck.py
# 목적 및 역할:
# 좁은 병목 통로 지도를 생성하여 교착 해소 성능을 확인한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import random
from mr_deadlock.core.grid import GridMap


def make_bottleneck_map(width: int, height: int, obstacle_density: float, rng: random.Random) -> GridMap:
    obs = set()
    wall_x = width // 2
    gap_y = height // 2
    gap_h = max(2, height // 20)
    for y in range(height):
        if abs(y - gap_y) > gap_h:
            obs.add((wall_x, y))
            if wall_x + 1 < width:
                obs.add((wall_x + 1, y))
    return GridMap(width, height, obs, name="bottleneck")

