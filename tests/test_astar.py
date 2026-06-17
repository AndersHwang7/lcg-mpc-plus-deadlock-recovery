# Inha University & RODIX Inc, Anders Hwang
# 파일명: test_astar.py
# 목적 및 역할:
# A* 경로 탐색이 장애물을 피하고 목표까지 도달하는지 확인한다.
# 작성자: RODIX Anders Hwang

from mr_deadlock.core.grid import GridMap
from mr_deadlock.planners.astar import AStar


def test_astar_basic():
    grid = GridMap(5, 5, {(2, 2)})
    path = AStar(grid).search((0, 0), (4, 4))
    assert path[0] == (0, 0)
    assert path[-1] == (4, 4)
    assert (2, 2) not in path

