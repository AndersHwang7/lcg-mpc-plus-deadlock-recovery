# Inha University & RODIX Inc, Anders Hwang
# 파일명: detector.py
# 목적 및 역할:
# 지속적인 무진전 SCC를 이용해 논문 정의에 맞는 교착 후보를 검출한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from mr_deadlock.core.robot import Robot
from mr_deadlock.core.types import MoveDict, ConflictSet
from .dependency_graph import build_dependency_graph
from .scc import tarjan_scc


@dataclass
class DeadlockEvent:
    t_start: int
    t_end: int | None
    robots: tuple[int, ...]
    reason: str

    @property
    def duration(self) -> int | None:
        if self.t_end is None:
            return None
        return self.t_end - self.t_start + 1


@dataclass
# 지속적인 무진전 SCC를 교착 후보로 검출한다.
# 같은 SCC가 오래 유지되거나 구성 로봇이 모두 진전하지 못하면 persistent deadlock으로 본다.
class DeadlockDetector:

    threshold: int = 6
    proactive: bool = True
    no_move_counter: dict[int, int] = field(default_factory=dict)
    no_progress_counter: dict[int, int] = field(default_factory=dict)
    scc_age: dict[tuple[int, ...], int] = field(default_factory=dict)
    active_events: dict[tuple[int, ...], DeadlockEvent] = field(default_factory=dict)
    events: list[DeadlockEvent] = field(default_factory=list)

    def update_progress(self, robots: list[Robot], moves: MoveDict) -> None:
        for r in robots:
            if r.completed_at is not None:
                self.no_move_counter[r.id] = 0
                self.no_progress_counter[r.id] = 0
                continue
            nxt = moves.get(r.id, r.pos)
            self.no_move_counter[r.id] = self.no_move_counter.get(r.id, 0) + 1 if nxt == r.pos else 0
            # apply_move는 실행 뒤에 진행도를 갱신하므로, 여기서는 실행 전 예측값을 따로 둔다.
            old_d = abs(r.pos[0] - r.goal[0]) + abs(r.pos[1] - r.goal[1])
            new_d = abs(nxt[0] - r.goal[0]) + abs(nxt[1] - r.goal[1])
            self.no_progress_counter[r.id] = (
                self.no_progress_counter.get(r.id, 0) + 1 if new_d >= old_d else 0
            )

    def detect(self, t: int, robots: list[Robot], proposed: MoveDict) -> tuple[list[list[int]], dict]:
        g = build_dependency_graph(robots, proposed)
        comps = [tuple(sorted(c)) for c in tarjan_scc(g.edges) if len(c) >= 2]
        current = set(comps)
        # SCC가 얼마나 오래 유지되는지 갱신하고 사라진 SCC는 정리한다.
        for comp in comps:
            self.scc_age[comp] = self.scc_age.get(comp, 0) + 1
        for comp in list(self.scc_age):
            if comp not in current:
                if comp in self.active_events:
                    ev = self.active_events.pop(comp)
                    ev.t_end = t - 1
                    self.events.append(ev)
                self.scc_age.pop(comp, None)

        persistent: list[tuple[int, ...]] = []
        conflict_sets: list[ConflictSet] = []
        by_id = {r.id: r for r in robots}
        for comp in comps:
            no_progress = all(self.no_progress_counter.get(rid, 0) >= self.threshold for rid in comp)
            old_scc = self.scc_age.get(comp, 0) >= self.threshold
            # 논문 정의는 오래 남은 SCC 자체가 아니라, 오래 남은 SCC와 무진전이 함께 있는 상태이다.
            # 정상 교차 흐름에서 반복적으로 보이는 의도 SCC는 persistent deadlock으로 세지 않는다.
            is_persistent = bool(no_progress and old_scc)
            if is_persistent:
                persistent.append(comp)
                if comp not in self.active_events:
                    self.active_events[comp] = DeadlockEvent(t, None, comp, "persistent_scc_no_progress")
            cells = set()
            for rid in comp:
                r = by_id.get(rid)
                if r is not None:
                    cells.add(r.pos)
                    cells.add(proposed.get(rid, r.pos))
            conflict_sets.append(
                ConflictSet(
                    robot_ids=comp,
                    cells=frozenset(cells),
                    persistent=is_persistent,
                    age=self.scc_age.get(comp, 1),
                )
            )
        candidates = comps if self.proactive else persistent
        meta = {
            "dependency_edges": {k: sorted(v) for k, v in g.edges.items()},
            "dependency_reasons": {f"{a}->{b}": r for (a, b), r in g.reasons.items()},
            "sccs": [list(c) for c in comps],
            "persistent_sccs": [list(c) for c in persistent],
            "conflict_sets": [asdict(cs) for cs in conflict_sets],
            "scc_age": {str(k): v for k, v in self.scc_age.items()},
        }
        return [list(c) for c in candidates], meta

    def closed_event_durations(self) -> list[int]:
        return [ev.duration for ev in self.events if ev.duration is not None]

