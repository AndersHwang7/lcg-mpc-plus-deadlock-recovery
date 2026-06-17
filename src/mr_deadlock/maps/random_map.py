# Inha University & RODIX Inc, Anders Hwang
# 파일명: random_map.py
# 목적 및 역할:
# 무작위 장애물 지도를 생성하되 시작점과 목표점 배치를 고려한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import random
from mr_deadlock.core.grid import GridMap


def make_random_map(width: int, height: int, obstacle_density: float, rng: random.Random) -> GridMap:
    obs = set()
    for y in range(height):
        for x in range(width):
            if rng.random() < obstacle_density:
                obs.add((x, y))
    # 시작점과 목표점 샘플링이 막히지 않도록 테두리는 충분히 비워 둔다.
    for x in range(width):
        obs.discard((x, 0)); obs.discard((x, height - 1))
    for y in range(height):
        obs.discard((0, y)); obs.discard((width - 1, y))
    return GridMap(width, height, obs, name="random")

