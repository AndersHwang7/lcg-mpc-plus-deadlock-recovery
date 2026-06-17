# Inha University & RODIX Inc, Anders Hwang
# 파일명: test_metrics.py
# 목적 및 역할:
# 논문용 처리량 지표가 시뮬레이션 step 기준으로 계산되는지 확인한다.
# 작성자: RODIX Anders Hwang

from mr_deadlock.core.grid import GridMap
from mr_deadlock.core.robot import Robot
from mr_deadlock.core.simulator import Simulator
from mr_deadlock.planners.factory import make_planner


def test_throughput_per_step_is_simulated_not_wallclock():
    grid = GridMap(4, 1, set())
    robots = [Robot(0, (0, 0), (1, 0), (0, 0))]
    planner = make_planner("astar_wait", grid, {"max_steps": 10})
    sim = Simulator(grid, robots, planner, {"max_steps": 10})
    result = sim.run({"map_type": "line", "n_robots": 1}, "astar_wait", 0)
    assert result.summary["completed"] == 1
    assert result.summary["throughput_per_step"] <= 1.0
    assert "throughput_wallclock" in result.summary

