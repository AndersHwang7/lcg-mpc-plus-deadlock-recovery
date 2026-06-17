# Inha University & RODIX Inc, Anders Hwang
# 파일명: base.py
# 목적 및 역할:
# 모든 planner가 공유하는 context와 기본 interface를 정의한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from mr_deadlock.core.types import PlanResult


@dataclass
class PlannerContext:
    grid: Any
    robots: list[Any]
    t: int
    config: dict[str, Any]


class Planner(ABC):
    name: str = "base"

    def __init__(self, grid, config: dict[str, Any] | None = None):
        self.grid = grid
        self.config = config or {}

    def initialize(self, robots: list[Any]) -> None:
        pass

    @abstractmethod
    def plan(self, ctx: PlannerContext) -> PlanResult:
        raise NotImplementedError

