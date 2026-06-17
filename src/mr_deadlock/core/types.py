# Inha University & RODIX Inc, Anders Hwang
# 파일명: types.py
# 목적 및 역할:
# 공통 타입과 planner 결과, 국소 충돌 집합 자료구조를 정의한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypeAlias

Cell: TypeAlias = tuple[int, int]
MoveDict: TypeAlias = dict[int, Cell]


@dataclass(slots=True)
# receding horizon 구조에서는 매 step 첫 이동만 실행한다.
# metadata는 ablation과 결과 분석에 사용한다.
class PlanResult:

    moves: MoveDict
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
# 교착 후보가 된 국소 충돌 집합을 보관한다.
# robot_ids는 SCC에 속한 로봇이고 cells는 현재 위치와 목표 칸을 함께 담는다.
class ConflictSet:

    robot_ids: tuple[int, ...]
    cells: frozenset[Cell]
    persistent: bool = False
    age: int = 1

