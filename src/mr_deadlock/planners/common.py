# Inha University & RODIX Inc, Anders Hwang
# 파일명: common.py
# 목적 및 역할:
# planner들이 함께 쓰는 활성 로봇 추출, 이동 정리, 충돌 보정 함수를 제공한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from collections import defaultdict
from mr_deadlock.core.types import Cell, MoveDict
from mr_deadlock.core.robot import Robot


def desired_next(robot: Robot) -> Cell:
    if robot.completed_at is not None:
        return robot.pos
    return robot.next_on_path()


def active_robots(robots: list[Robot]) -> list[Robot]:
    return [r for r in robots if r.completed_at is None]


def sanitize_moves(robots: list[Robot], moves: MoveDict) -> MoveDict:
    return {r.id: moves.get(r.id, r.pos) for r in active_robots(robots)}


def _edge_swaps(pos: dict[int, Cell], moves: MoveDict) -> list[tuple[int, int]]:
    """Find pairwise edge swaps in O(N) expected time instead of O(N^2)."""
    owner: dict[tuple[Cell, Cell], int] = {}
    swaps: list[tuple[int, int]] = []
    for rid, old in pos.items():
        new = moves.get(rid, old)
        if new == old:
            continue
        other = owner.get((new, old))
        if other is not None:
            swaps.append((other, rid))
        owner[(old, new)] = rid
    return swaps


def count_vertex_edge_conflicts(robots: list[Robot], moves: MoveDict) -> int:
    act = active_robots(robots)
    pos = {r.id: r.pos for r in act}
    moves = sanitize_moves(act, moves)
    conflicts = 0
    by_target: dict[Cell, list[int]] = defaultdict(list)
    for rid, target in moves.items():
        by_target[target].append(rid)
    conflicts += sum(max(0, len(ids) - 1) for ids in by_target.values())
    conflicts += len(_edge_swaps(pos, moves))
    return conflicts


# 모든 알고리즘에 공통으로 쓰는 보수적 충돌 보정 함수이다.
# 제안기법의 기여가 아니라 baseline 공정성을 위한 안전장치이다.
def resolve_vertex_edge_conflicts(robots: list[Robot], moves: MoveDict) -> tuple[MoveDict, int]:
    act = active_robots(robots)
    pos = {r.id: r.pos for r in act}
    by_id = {r.id: r for r in act}
    moves = sanitize_moves(act, moves)
    wait: set[int] = set()
    by_target: dict[Cell, list[int]] = defaultdict(list)
    for rid, target in moves.items():
        by_target[target].append(rid)
    for _, ids in by_target.items():
        if len(ids) > 1:
            keep = max(ids, key=lambda rid: (by_id[rid].wait_time + by_id[rid].fairness_debt, -rid))
            wait.update(rid for rid in ids if rid != keep)
    for a, b in _edge_swaps(pos, moves):
        loser = min((a, b), key=lambda rid: (by_id[rid].wait_time + by_id[rid].fairness_debt, -rid))
        wait.add(loser)
    fixed = dict(moves)
    for rid in wait:
        fixed[rid] = pos[rid]
    return fixed, len(wait)

