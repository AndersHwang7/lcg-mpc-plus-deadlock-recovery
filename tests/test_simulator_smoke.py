# Inha University & RODIX Inc, Anders Hwang
# 파일명: test_simulator_smoke.py
# 목적 및 역할:
# 작은 교차로 환경에서 시뮬레이터와 제안 계열 planner가 끝까지 실행되는지 확인한다.
# 작성자: RODIX Anders Hwang

from mr_deadlock.maps.generator import make_map
from mr_deadlock.maps.tasks import sample_start_goals
from mr_deadlock.core.robot import Robot
from mr_deadlock.core.simulator import Simulator
from mr_deadlock.planners.factory import make_planner
import random


def test_simulator_smoke():
    rng = random.Random(0)
    grid = make_map("intersection", 30, 30, 0.02, rng)
    pairs = sample_start_goals(grid, 10, "cross_traffic", rng)
    robots = [Robot(i, s, g, s) for i, (s, g) in enumerate(pairs)]
    planner = make_planner("clrr_game", grid, {"max_steps": 100, "deadlock_threshold": 3})
    sim = Simulator(grid, robots, planner, {"max_steps": 100, "deadlock_threshold": 3})
    result = sim.run({"map_type": "intersection", "n_robots": 10}, "clrr_game", 0)
    assert "success_rate" in result.summary
    assert result.summary["collision_count"] >= 0

