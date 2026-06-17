# Inha University & RODIX Inc, Anders Hwang
# 파일명: generator.py
# 목적 및 역할:
# 설정 이름에 맞는 지도 생성 함수를 선택한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import random
from mr_deadlock.core.grid import GridMap
from .random_map import make_random_map
from .intersection import make_intersection_map
from .corridor import make_corridor_map
from .warehouse import make_warehouse_map
from .bottleneck import make_bottleneck_map
from .ring import make_ring_map


def make_map(map_type: str, width: int, height: int, obstacle_density: float, rng: random.Random) -> GridMap:
    map_type = map_type.lower()
    if map_type == "random":
        return make_random_map(width, height, obstacle_density, rng)
    if map_type == "intersection":
        return make_intersection_map(width, height, obstacle_density, rng)
    if map_type == "corridor":
        return make_corridor_map(width, height, obstacle_density, rng)
    if map_type == "warehouse":
        return make_warehouse_map(width, height, obstacle_density, rng)
    if map_type == "bottleneck":
        return make_bottleneck_map(width, height, obstacle_density, rng)
    if map_type == "ring":
        return make_ring_map(width, height, obstacle_density, rng)
    raise ValueError(f"Unknown map_type: {map_type}")

