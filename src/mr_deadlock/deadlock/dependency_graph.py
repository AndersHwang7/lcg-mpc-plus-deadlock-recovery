# Inha University & RODIX Inc, Anders Hwang
# 파일명: dependency_graph.py
# 목적 및 역할:
# 로봇의 이동 의도를 wait for graph로 바꾸어 순환 의존성을 표현한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict
from mr_deadlock.core.robot import Robot
from mr_deadlock.core.types import Cell, MoveDict


@dataclass
# 논문 수식의 wait for graph를 코드로 표현한다.
# i에서 j로 가는 간선은 i의 이동 의도가 j의 점유 때문에 막혔다는 뜻이다.
class DependencyGraph:

    edges: dict[int, set[int]] = field(default_factory=lambda: defaultdict(set))
    reasons: dict[tuple[int, int], str] = field(default_factory=dict)

    def add_edge(self, a: int, b: int, reason: str) -> None:
        if a != b:
            self.edges[a].add(b)
            self.reasons[(a, b)] = reason

    def nodes(self) -> set[int]:
        out = set(self.edges.keys())
        for vs in self.edges.values():
            out.update(vs)
        return out


def build_dependency_graph(robots: list[Robot], proposed: MoveDict) -> DependencyGraph:
    active = [r for r in robots if r.completed_at is None]
    pos_owner: dict[Cell, int] = {r.pos: r.id for r in active}
    g = DependencyGraph()
    by_target: dict[Cell, list[int]] = defaultdict(list)
    moves: dict[int, Cell] = {}
    pos: dict[int, Cell] = {}
    for r in active:
        nxt = proposed.get(r.id, r.pos)
        moves[r.id] = nxt
        pos[r.id] = r.pos
        by_target[nxt].append(r.id)
        owner = pos_owner.get(nxt)
        if owner is not None and owner != r.id:
            g.add_edge(r.id, owner, "target_occupied")
    # 여러 로봇이 같은 빈 칸을 동시에 원하면 실제 점유자는 없어도 충돌 의존성이 생긴다.
    # 이 간선을 넣어야 교차로 중앙에서 생기는 선점 경쟁을 조기에 잡을 수 있다.
    for _target, ids_same in by_target.items():
        if len(ids_same) > 1:
            for a in ids_same:
                for b in ids_same:
                    if a != b:
                        g.add_edge(a, b, "same_target_intent")
    # 자리교환은 두 로봇이 서로를 기다리는 상호 의존으로 본다.
    # 해시맵으로 reverse edge를 찾기 때문에 pairwise O(N^2) 탐색을 피한다.
    edge_owner: dict[tuple[Cell, Cell], int] = {}
    for rid, old in pos.items():
        new = moves.get(rid, old)
        if new == old:
            continue
        other = edge_owner.get((new, old))
        if other is not None:
            g.add_edge(rid, other, "edge_swap")
            g.add_edge(other, rid, "edge_swap")
        edge_owner[(old, new)] = rid
    return g

