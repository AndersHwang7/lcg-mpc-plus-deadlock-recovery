# Inha University & RODIX Inc, Anders Hwang
# 파일명: ring.py
# 목적 및 역할:
# 순환형 교착을 시험하기 위한 ring map을 생성한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import random
from mr_deadlock.core.grid import GridMap


# 순환형 병목과 roundabout 상황을 보기 위한 지도를 만든다.
def make_ring_map(width: int, height: int, obstacle_density: float, rng: random.Random) -> GridMap:
    obs = {(x, y) for y in range(height) for x in range(width)}
    cx, cy = width // 2, height // 2
    outer_rx = max(8, width // 3)
    outer_ry = max(8, height // 3)
    inner_rx = max(4, width // 6)
    inner_ry = max(4, height // 6)
    lane_w = max(2, min(width, height) // 30)

    def ellipse_value(x: int, y: int, rx: int, ry: int) -> float:
        return ((x - cx) / max(1, rx)) ** 2 + ((y - cy) / max(1, ry)) ** 2

    for y in range(height):
        for x in range(width):
            v_outer = ellipse_value(x, y, outer_rx, outer_ry)
            v_inner = ellipse_value(x, y, inner_rx, inner_ry)
            # 통과 가능한 고리 영역을 만든다.
            if v_outer <= 1.0 and v_inner >= 1.0:
                obs.discard((x, y))

    # 네 방향에서 ring으로 들어오는 접근 통로를 뚫는다.
    for x in range(width):
        for dy in range(-lane_w, lane_w + 1):
            obs.discard((x, cy + dy))
    for y in range(height):
        for dx in range(-lane_w, lane_w + 1):
            obs.discard((cx + dx, y))

    # 주요 축은 유지하면서 ring 주변에 약한 혼잡을 넣는다.
    for y in range(height):
        for x in range(width):
            if (x, y) not in obs and abs(x - cx) > lane_w and abs(y - cy) > lane_w:
                if rng.random() < obstacle_density * 0.05:
                    obs.add((x, y))
    return GridMap(width, height, obs, name="ring")

