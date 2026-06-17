# Inha University & RODIX Inc, Anders Hwang
# 파일명: reservation.py
# 목적 및 역할:
# 시간별 정점과 간선 예약을 관리하여 충돌 없는 실행을 보조한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from dataclasses import dataclass, field
from .types import Cell


@dataclass
class ReservationTable:
    vertex: dict[tuple[int, Cell], int] = field(default_factory=dict)
    edge: dict[tuple[int, Cell, Cell], int] = field(default_factory=dict)

    def clear(self) -> None:
        self.vertex.clear()
        self.edge.clear()

    # 같은 시간에 같은 칸을 두 로봇이 예약하지 못하게 한다.
    def reserve_vertex(self, t: int, cell: Cell, robot_id: int) -> bool:
        key = (t, cell)
        owner = self.vertex.get(key)
        if owner is not None and owner != robot_id:
            return False
        self.vertex[key] = robot_id
        return True

    # 서로 반대 방향으로 같은 간선을 지나가는 자리교환도 막는다.
    def reserve_edge(self, t: int, u: Cell, v: Cell, robot_id: int) -> bool:
        key = (t, u, v)
        rev = (t, v, u)
        owner = self.edge.get(key)
        rev_owner = self.edge.get(rev)
        if owner is not None and owner != robot_id:
            return False
        if rev_owner is not None and rev_owner != robot_id:
            return False
        self.edge[key] = robot_id
        return True

    def vertex_owner(self, t: int, cell: Cell) -> int | None:
        return self.vertex.get((t, cell))

    def edge_owner(self, t: int, u: Cell, v: Cell) -> int | None:
        return self.edge.get((t, u, v))

    def is_vertex_free(self, t: int, cell: Cell, robot_id: int | None = None) -> bool:
        owner = self.vertex_owner(t, cell)
        return owner is None or owner == robot_id

    def is_edge_free(self, t: int, u: Cell, v: Cell, robot_id: int | None = None) -> bool:
        owner = self.edge_owner(t, u, v)
        rev_owner = self.edge_owner(t, v, u)
        ok1 = owner is None or owner == robot_id
        ok2 = rev_owner is None or rev_owner == robot_id
        return ok1 and ok2

