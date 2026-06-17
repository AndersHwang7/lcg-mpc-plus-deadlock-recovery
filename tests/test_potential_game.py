# Inha University & RODIX Inc, Anders Hwang
# 파일명: test_potential_game.py
# 목적 및 역할:
# 국소 잠재게임의 exact potential 성질과 충돌 없는 선택 결과를 확인한다.
# 작성자: RODIX Anders Hwang

from mr_deadlock.core.grid import GridMap
from mr_deadlock.core.robot import Robot
from mr_deadlock.game.potential_game import PotentialGameSelector


def test_potential_game_exact_property():
    grid = GridMap(5, 5, set())
    robots = [
        Robot(0, (1, 2), (4, 2), (1, 2), path=[(1, 2), (2, 2), (3, 2), (4, 2)]),
        Robot(1, (3, 2), (0, 2), (3, 2), path=[(3, 2), (2, 2), (1, 2), (0, 2)]),
    ]
    game = PotentialGameSelector(grid)
    assert game.verify_exact_potential(robots, {r.pos for r in robots})


def test_potential_game_selects_collision_safe_profile_when_available():
    grid = GridMap(5, 5, set())
    robots = [
        Robot(0, (1, 2), (4, 2), (1, 2), path=[(1, 2), (2, 2), (3, 2), (4, 2)]),
        Robot(1, (2, 2), (0, 2), (2, 2), path=[(2, 2), (1, 2), (0, 2)]),
    ]
    game = PotentialGameSelector(grid)
    chosen = game.select(robots, {r.pos for r in robots})
    targets = [a.target for a in chosen.values()]
    assert len(targets) == len(set(targets))

