# Inha University & RODIX Inc, Anders Hwang
# 파일명: robot.py
# 목적 및 역할:
# 로봇의 위치, 목표, 대기 시간, 진행도, 공정성 부채를 저장하고 갱신한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from dataclasses import dataclass, field
from .types import Cell


@dataclass
class Robot:
    id: int
    start: Cell
    goal: Cell
    pos: Cell
    path: list[Cell] = field(default_factory=list)
    path_index: int = 0
    active: bool = True
    wait_time: int = 0
    local_wait_streak: int = 0
    travel_time: int = 0
    completed_at: int | None = None
    priority: float = 0.0
    fairness_debt: float = 0.0
    retreat_count: int = 0
    total_distance: int = 0
    nominal_path_length: int = 0
    last_goal_distance: int | None = None
    no_progress_streak: int = 0
    # 연속 AMR envelope 검증을 위한 최근 grid-cell velocity/acceleration 상태이다.
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    accel_x: float = 0.0
    accel_y: float = 0.0

    @property
    def reached(self) -> bool:
        return self.pos == self.goal

    def next_on_path(self) -> Cell:
        if not self.path:
            return self.pos
        if self.path_index + 1 < len(self.path):
            return self.path[self.path_index + 1]
        return self.pos

    def remaining_distance_estimate(self) -> int:
        if not self.path:
            return 0 if self.reached else 10**9
        return max(0, len(self.path) - self.path_index - 1)

    def goal_distance_on_grid(self) -> int:
        # 온라인 진행도 기록에만 쓰는 맨해튼 거리이다.
        # 논문 수식의 최단거리 정의를 대신하지 않는다.
        return abs(self.pos[0] - self.goal[0]) + abs(self.pos[1] - self.goal[1])

    def apply_move(self, new_pos: Cell, t: int) -> None:
        if self.completed_at is not None:
            return
        old = self.pos
        old_goal_dist = self.goal_distance_on_grid()
        self.pos = new_pos
        if new_pos == old:
            self.wait_time += 1
            self.local_wait_streak += 1
            self.fairness_debt += 1.0
        else:
            self.local_wait_streak = 0
            self.total_distance += 1
            self.fairness_debt = max(0.0, self.fairness_debt - 0.5)
            if self.path and self.path_index + 1 < len(self.path) and self.path[self.path_index + 1] == new_pos:
                self.path_index += 1
            else:
                # 후퇴나 복구 동작으로 nominal path를 벗어나면 가능한 위치에서 path index를 다시 맞춘다.
                try:
                    idx = self.path.index(new_pos)
                    if idx >= self.path_index:
                        self.path_index = idx
                except ValueError:
                    pass
        new_goal_dist = self.goal_distance_on_grid()
        if new_goal_dist >= old_goal_dist:
            self.no_progress_streak += 1
        else:
            self.no_progress_streak = 0
        self.last_goal_distance = new_goal_dist
        self.travel_time += 1
        if self.reached:
            self.completed_at = t
            self.active = False
            self.no_progress_streak = 0
            self.local_wait_streak = 0

