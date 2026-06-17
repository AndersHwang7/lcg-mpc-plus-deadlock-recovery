# Inha University & RODIX Inc, Anders Hwang
# 파일명: test_deadlock_detector.py
# 목적 및 역할:
# 서로 자리 교환을 시도하는 상황에서 교착 후보가 검출되는지 확인한다.
# 작성자: RODIX Anders Hwang

from mr_deadlock.core.robot import Robot
from mr_deadlock.deadlock.detector import DeadlockDetector


def test_swap_dependency_scc():
    robots = [Robot(0, (0, 0), (1, 0), (0, 0)), Robot(1, (1, 0), (0, 0), (1, 0))]
    moves = {0: (1, 0), 1: (0, 0)}
    det = DeadlockDetector(threshold=1)
    comps, meta = det.detect(0, robots, moves)
    assert any(set(c) == {0, 1} for c in comps)

