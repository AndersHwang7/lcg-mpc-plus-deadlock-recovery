# Inha University & RODIX Inc, Anders Hwang
# 파일명: stackelberg.py
# 목적 및 역할:
# Stackelberg 방식의 순서 결정 baseline을 간단히 제공한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from dataclasses import dataclass
from mr_deadlock.core.robot import Robot


@dataclass(frozen=True)
class StackelbergOrder:
    leaders_first: tuple[int, ...]


# ablation용 순서 결정 함수이다.
# 오래 기다린 로봇을 leader로 두어 단순한 Stackelberg 기준선을 만든다.
def simple_stackelberg_order(robots: list[Robot]) -> StackelbergOrder:
    return StackelbergOrder(
        leaders_first=tuple(r.id for r in sorted(robots, key=lambda r: (-r.wait_time, -r.fairness_debt, r.id)))
    )

