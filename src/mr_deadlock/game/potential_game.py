# Inha University & RODIX Inc, Anders Hwang
# 파일명: potential_game.py
# 목적 및 역할:
# 국소 충돌 집합에서 전진, 양보, 후퇴 행동을 고르는 exact potential game을 구현한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from math import isclose
from mr_deadlock.core.grid import GridMap
from mr_deadlock.core.robot import Robot
from mr_deadlock.core.types import Cell


@dataclass(frozen=True)
class LocalAction:
    robot_id: int
    target: Cell
    label: str  # 대기, 전진, 양보, 후퇴 중 하나를 기록한다


@dataclass
# 국소 exact potential game의 비용 가중치를 모아 둔다.
class PotentialGameConfig:

    w_delay: float = 1.0
    w_retreat: float = 2.0
    w_collision: float = 1000.0
    w_edge_swap: float = 1000.0
    w_fairness: float = 1.20
    w_progress: float = 1.0
    w_congestion: float = 0.1
    w_goal_block: float = 0.4
    max_agents: int = 5
    max_actions_per_robot: int = 3
    max_profiles: int = 512


# 전진, 양보, 후퇴 중 하나를 고르는 국소 잠재게임 선택기이다.
# 모든 로봇의 효용을 같은 potential의 음수로 두어 exact potential 성질을 보장한다.
class PotentialGameSelector:

    def __init__(self, grid: GridMap, config: PotentialGameConfig | None = None):
        self.grid = grid
        self.config = config or PotentialGameConfig()
        self.last_profile_count = 0
        self.last_best_potential = 0.0
        self.last_selection_mode = "not_run"
        self.last_exact_components = 0
        self.last_greedy_components = 0

    def _outside_occupied(self, robots: list[Robot], occupied_all: set[Cell]) -> set[Cell]:
        own = {r.pos for r in robots}
        return set(occupied_all) - own

    def _actions_for(self, r: Robot, outside_occupied: set[Cell], conflict_cells: set[Cell]) -> list[LocalAction]:
        acts = [LocalAction(r.id, r.pos, "wait")]
        nxt = r.next_on_path()
        if nxt != r.pos and self.grid.passable(nxt) and nxt not in outside_occupied:
            acts.append(LocalAction(r.id, nxt, "advance"))
        # 양보는 대기와 비슷하지만 비용 계산과 로그에서 의미가 다르다.
        if r.local_wait_streak == 0:
            acts.append(LocalAction(r.id, r.pos, "yield"))
        # 후퇴 후보는 현재 충돌 칸을 벗어나는 이웃 칸에서 찾는다.
        retreat_candidates = []
        for nb in self.grid.neighbors4(r.pos):
            if nb == nxt:
                continue
            if nb in outside_occupied:
                continue
            old_min = min((self.grid.manhattan(r.pos, c) for c in conflict_cells), default=0)
            new_min = min((self.grid.manhattan(nb, c) for c in conflict_cells), default=0)
            if nb not in conflict_cells or new_min > old_min:
                retreat_candidates.append(nb)
        retreat_candidates.sort(key=lambda c: (-min((self.grid.manhattan(c, z) for z in conflict_cells), default=0), c))
        for nb in retreat_candidates[: max(0, self.config.max_actions_per_robot - len(acts))]:
            acts.append(LocalAction(r.id, nb, "retreat"))
        # 같은 목표와 행동이 중복되지 않도록 정리한다.
        unique: list[LocalAction] = []
        seen = set()
        for a in acts:
            key = (a.target, a.label)
            if key not in seen:
                seen.add(key)
                unique.append(a)
        return unique[: self.config.max_actions_per_robot]

    def action_lists(self, robots: list[Robot], occupied_all: set[Cell]) -> list[list[LocalAction]]:
        conflict_cells = {r.pos for r in robots} | {r.next_on_path() for r in robots}
        outside = self._outside_occupied(robots, occupied_all)
        return [self._actions_for(r, outside, conflict_cells) for r in robots]

    # 논문 수식의 전역 potential Phi를 코드로 계산한다.
    def potential(self, profile: tuple[LocalAction, ...], robots: dict[int, Robot]) -> float:
        cfg = self.config
        pos = {rid: r.pos for rid, r in robots.items()}
        phi = 0.0
        targets: dict[Cell, int] = {}
        for a in profile:
            if a.target in targets:
                phi += cfg.w_collision
            targets[a.target] = a.robot_id
        for i, a in enumerate(profile):
            for b in profile[i + 1:]:
                if a.target == pos[b.robot_id] and b.target == pos[a.robot_id] and pos[a.robot_id] != pos[b.robot_id]:
                    phi += cfg.w_edge_swap
        # 행동 profile별 국소 비용 항을 계산한다.
        target_counts: dict[Cell, int] = {}
        for a in profile:
            target_counts[a.target] = target_counts.get(a.target, 0) + 1
        for a in profile:
            r = robots[a.robot_id]
            old_d = self.grid.manhattan(r.pos, r.goal)
            new_d = self.grid.manhattan(a.target, r.goal)
            progress = old_d - new_d
            # 공정성 부채는 행동과 무관한 상수로 넣으면 선택에 영향을 주지 않는다.
            # 오래 기다린 로봇이 다시 기다리거나 후퇴할 때 비용을 더 주어 통과 기회를 보장한다.
            debt = max(0.0, r.fairness_debt)
            if a.label in {"wait", "yield"}:
                phi += cfg.w_delay * (1.0 + r.local_wait_streak)
                phi += cfg.w_fairness * (1.0 + debt)
            if a.label == "retreat":
                phi += cfg.w_retreat * (1.0 + 0.25 * debt)
            if progress > 0:
                phi -= (cfg.w_progress + 0.25 * cfg.w_fairness * debt) * progress
            else:
                phi -= cfg.w_progress * progress
                phi += cfg.w_goal_block * abs(progress)
            phi += cfg.w_congestion * max(0, target_counts[a.target] - 1)
        return float(phi)

    def utility(self, robot_id: int, profile: tuple[LocalAction, ...], robots: dict[int, Robot]) -> float:
        # 동일 interest 구조이므로 한 로봇의 효용 변화가 potential 변화와 정확히 대응한다.
        return -self.potential(profile, robots)

    # 한 로봇만 행동을 바꿀 때 exact potential 성질이 유지되는지 확인한다.
    def verify_exact_potential(
        self,
        robots: list[Robot],
        occupied_all: set[Cell],
        tol: float = 1e-9,
    ) -> bool:
        if not robots or len(robots) > self.config.max_agents:
            return True
        robot_map = {r.id: r for r in robots}
        action_lists = self.action_lists(robots, occupied_all)
        for profile in product(*action_lists):
            for idx, r in enumerate(robots):
                old_phi = self.potential(profile, robot_map)
                old_u = self.utility(r.id, profile, robot_map)
                for alt in action_lists[idx]:
                    if alt == profile[idx]:
                        continue
                    new_profile = tuple(alt if j == idx else a for j, a in enumerate(profile))
                    new_phi = self.potential(new_profile, robot_map)
                    new_u = self.utility(r.id, new_profile, robot_map)
                    if not isclose(new_u - old_u, -(new_phi - old_phi), rel_tol=tol, abs_tol=tol):
                        return False
        return True

    def _profile_count(self, action_lists: list[list[LocalAction]]) -> int:
        profile_count = 1
        for acts in action_lists:
            profile_count *= max(1, len(acts))
        return profile_count

    def _select_exact(self, robots: list[Robot], occupied_all: set[Cell]) -> dict[int, LocalAction]:
        action_lists = self.action_lists(robots, occupied_all)
        robot_map = {r.id: r for r in robots}
        best_cost = float("inf")
        best_profile: tuple[LocalAction, ...] | None = None
        count = 0
        for profile in product(*action_lists):
            count += 1
            cost = self.potential(profile, robot_map)
            if cost < best_cost:
                best_cost = cost
                best_profile = profile
        self.last_profile_count += count
        self.last_best_potential += best_cost if best_cost < float("inf") else 0.0
        self.last_exact_components += 1
        assert best_profile is not None
        return {a.robot_id: a for a in best_profile}

    def _partition_large_component(self, robots: list[Robot], occupied_all: set[Cell]) -> list[list[Robot]]:
        """Split a large component into bounded local games.

        This deliberately avoids presenting a greedy action profile as an exact-potential
        equilibrium. Each returned block has at most max_agents and can be enumerated exactly;
        the guarantee is therefore local-to-block, which is the claim recorded in metadata.
        """
        if len(robots) <= self.config.max_agents:
            return [robots]
        conflict_cells = {r.pos for r in robots} | {r.next_on_path() for r in robots}
        remaining = sorted(
            robots,
            key=lambda r: (-r.local_wait_streak, -r.fairness_debt, r.remaining_distance_estimate(), r.id),
        )
        blocks: list[list[Robot]] = []
        while remaining:
            seed = remaining.pop(0)
            block = [seed]
            # nearby robots with overlapping current/next cells are put in the same bounded game.
            remaining.sort(
                key=lambda r: (
                    min(self.grid.manhattan(r.pos, z) for z in {seed.pos, seed.next_on_path()} | conflict_cells),
                    -r.local_wait_streak,
                    r.id,
                )
            )
            while remaining and len(block) < self.config.max_agents:
                block.append(remaining.pop(0))
            blocks.append(block)
        return blocks

    def select(self, robots: list[Robot], occupied_all: set[Cell]) -> dict[int, LocalAction]:
        if not robots:
            self.last_selection_mode = "empty"
            return {}
        self.last_profile_count = 0
        self.last_best_potential = 0.0
        self.last_exact_components = 0
        self.last_greedy_components = 0
        action_lists = self.action_lists(robots, occupied_all)
        profile_count = self._profile_count(action_lists)
        if len(robots) <= self.config.max_agents and profile_count <= self.config.max_profiles:
            self.last_selection_mode = "exact_enumeration"
            return self._select_exact(robots, occupied_all)

        selected: dict[int, LocalAction] = {}
        occupied_dynamic = set(occupied_all)
        blocks = self._partition_large_component(robots, occupied_all)
        for block in blocks:
            block_actions = self.action_lists(block, occupied_dynamic)
            if self._profile_count(block_actions) <= self.config.max_profiles:
                chosen = self._select_exact(block, occupied_dynamic)
            else:
                # 이 경우는 한 bounded block 안에서도 행동 수가 너무 많을 때만 발생한다.
                # max_actions_per_robot를 줄이면 보통 exact path로 들어간다. metadata로 별도 표시한다.
                chosen = self._greedy_select(block, occupied_dynamic)
                self.last_greedy_components += 1
            selected.update(chosen)
            for rid, action in chosen.items():
                # 다음 block은 이전 block의 선택 target을 외부 예약으로 본다.
                robot = next(r for r in block if r.id == rid)
                occupied_dynamic.discard(robot.pos)
                occupied_dynamic.add(action.target)
        self.last_selection_mode = (
            "partitioned_exact" if self.last_greedy_components == 0 else "partitioned_mixed"
        )
        return selected

    def _greedy_select(self, robots: list[Robot], occupied_all: set[Cell]) -> dict[int, LocalAction]:
        selected: dict[int, LocalAction] = {}
        reserved: set[Cell] = set()
        conflict_cells = {r.pos for r in robots} | {r.next_on_path() for r in robots}
        outside = self._outside_occupied(robots, occupied_all)
        order = sorted(robots, key=lambda r: (-r.local_wait_streak, -r.fairness_debt, r.id))
        robot_map = {r.id: r for r in robots}
        for r in order:
            acts = self._actions_for(r, outside, conflict_cells)
            acts = sorted(
                acts,
                key=lambda a: (
                    a.target in reserved,
                    self.potential(tuple([*selected.values(), a]), robot_map),
                    self.grid.manhattan(a.target, r.goal),
                    0 if a.label == "advance" else 1,
                ),
            )
            chosen = next((a for a in acts if a.target not in reserved), acts[0])
            selected[r.id] = chosen
            reserved.add(chosen.target)
        self.last_profile_count += len(order)
        return selected

