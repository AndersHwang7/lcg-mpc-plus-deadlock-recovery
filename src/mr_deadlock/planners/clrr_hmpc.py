# Inha University & RODIX Inc, Anders Hwang
# 파일명: clrr_hmpc.py
# 목적 및 역할:
# 교착 SCC를 감지하고 CLRR, 잠재게임, 국소 MPC를 결합해 이동을 결정한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from collections import deque
import time
from mr_deadlock.core.types import Cell, PlanResult
from mr_deadlock.core.robot import Robot
from mr_deadlock.planners.base import Planner, PlannerContext
from mr_deadlock.planners.astar import AStar
from mr_deadlock.planners.pibt import PIBTPlanner
from mr_deadlock.planners.whca import WHCAPlanner
from mr_deadlock.planners.prioritized import PrioritizedPlanner
from mr_deadlock.planners.common import resolve_vertex_edge_conflicts, desired_next
from mr_deadlock.deadlock.detector import DeadlockDetector
from mr_deadlock.game.potential_game import PotentialGameSelector, PotentialGameConfig
from mr_deadlock.mpc.local_qp import LocalMPCRefiner, LocalMPCConfig
from mr_deadlock.core.dynamics import KinematicSafetyConfig, cell_center, synchronous_segment_distance


# CLRR의 규칙 기반 핵심 계층이다.
# 순환 의존성을 찾고 후퇴할 로봇과 임시 pocket을 정해 SCC를 끊는다.
class CLRRPlanner(Planner):

    name = "clrr"

    def __init__(self, grid, config=None):
        super().__init__(grid, config)
        nominal_name = str(self.config.get("clrr_nominal", "whca")).lower()
        if nominal_name == "whca":
            self.nominal = WHCAPlanner(grid, config)
        elif nominal_name == "prioritized":
            self.nominal = PrioritizedPlanner(grid, config)
        else:
            self.nominal = PIBTPlanner(grid, config)
        activation_mode = str(self.config.get("activation_mode", "candidate")).lower()
        proactive = bool(self.config.get("proactive_clrr", activation_mode == "candidate"))
        self.detector = DeadlockDetector(
            threshold=int(self.config.get("deadlock_threshold", 6)),
            proactive=proactive,
        )
        self.astar = AStar(grid)

    def initialize(self, robots):
        self.nominal.initialize(robots)

    def _first_step_toward(self, start: Cell, goal: Cell, blocked: set[Cell]) -> Cell | None:
        path = self.astar.search(start, goal, blocked=blocked, max_expansions=int(self.config.get("repair_astar_expansions", 2000)))
        if len(path) >= 2 and path[1] in self.grid.neighbors4(start):
            return path[1]
        return None

    def _retreat_step(
        self,
        r: Robot,
        occupied: set[Cell],
        conflict_cells: set[Cell],
        radius: int,
    ) -> Cell | None:
        # 여러 칸 떨어진 pocket을 바로 지정하면 실제 로봇은 한 step에 갈 수 없다.
        # 그래서 pocket을 찾은 뒤 현재 위치에서 그 pocket으로 가는 첫 칸만 반환한다.
        q = deque([r.pos])
        parent: dict[Cell, Cell | None] = {r.pos: None}
        dist = {r.pos: 0}
        best: Cell | None = None
        best_key = None
        while q:
            c = q.popleft()
            d = dist[c]
            if d > radius:
                continue
            if c != r.pos and c not in occupied and c not in conflict_cells and self.grid.passable(c):
                sep = min((self.grid.manhattan(c, z) for z in conflict_cells), default=0)
                key = (sep, self.grid.degree(c), -self.grid.manhattan(c, r.goal), -d)
                if best is None or key > best_key:
                    best = c
                    best_key = key
            for nb in self.grid.neighbors4(c):
                if nb in parent:
                    continue
                if nb in occupied and nb != r.pos:
                    continue
                parent[nb] = c
                dist[nb] = d + 1
                q.append(nb)
        if best is None:
            return None
        cur = best
        while parent[cur] is not None and parent[cur] != r.pos:
            cur = parent[cur]
        if cur != r.pos and cur in self.grid.neighbors4(r.pos):
            return cur
        return None

    def _choose_retreat_robot(self, robots: list[Robot], conflict_cells: set[Cell], occupied: set[Cell], radius: int) -> tuple[Robot, Cell | None]:
        # 오래 기다린 로봇은 가능하면 통과시키고, 후퇴 여지가 큰 로봇이 양보하게 한다.
        candidates: list[tuple[tuple[float, int, int, int], Robot, Cell | None]] = []
        for r in robots:
            step = self._retreat_step(r, occupied - {r.pos}, conflict_cells, radius)
            local_exits = sum(1 for nb in self.grid.neighbors4(r.pos) if nb not in conflict_cells)
            has_step = 0 if step is not None else 1
            key = (r.wait_time + r.fairness_debt, has_step, -local_exits, r.remaining_distance_estimate())
            candidates.append((key, r, step))
        _, robot, step = min(candidates, key=lambda x: x[0])
        return robot, step

    def _leader_repair_move(self, leader: Robot, occupied: set[Cell], conflict_cells: set[Cell], reserved: set[Cell]) -> Cell:
        # SCC 안에서 가장 오래 기다린 로봇은 nominal move가 막혔을 때도 짧은 재탐색으로 통과시킨다.
        blocked = set(occupied) | set(reserved)
        blocked.discard(leader.pos)
        blocked.discard(leader.goal)
        step = self._first_step_toward(leader.pos, leader.goal, blocked)
        if step is not None and step not in reserved:
            return step
        nxt = leader.next_on_path()
        if nxt in self.grid.neighbors4(leader.pos) and nxt not in reserved and nxt not in occupied:
            return nxt
        return leader.pos


    def _move_conflict_groups(self, robots: list[Robot], moves: dict[int, Cell]) -> list[list[int]]:
        # nominal planner가 만든 실제 한 step 이동에서 충돌에 관여한 로봇만 뽑는다.
        # 의도 그래프의 후보 SCC를 모두 건드리면 정상적인 교차 흐름까지 과하게 막을 수 있다.
        # 1000대 규모를 위해 정점 충돌과 자리교환 충돌을 해시맵 기반으로 찾는다.
        active = [r for r in robots if r.completed_at is None]
        pos = {r.id: r.pos for r in active}
        parent = {r.id: r.id for r in active}

        def find(a: int) -> int:
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        by_target: dict[Cell, list[int]] = {}
        for r in active:
            by_target.setdefault(moves.get(r.id, r.pos), []).append(r.id)
        for ids in by_target.values():
            if len(ids) > 1:
                first = ids[0]
                for rid in ids[1:]:
                    union(first, rid)
        edge_owner: dict[tuple[Cell, Cell], int] = {}
        for rid, old in pos.items():
            new_pos = moves.get(rid, old)
            if new_pos == old:
                continue
            other = edge_owner.get((new_pos, old))
            if other is not None:
                union(rid, other)
            edge_owner[(old, new_pos)] = rid
        groups: dict[int, list[int]] = {}
        for rid in pos:
            root = find(rid)
            groups.setdefault(root, []).append(rid)
        return [sorted(g) for g in groups.values() if len(g) >= 2]

    def _move_conflict_count(self, robots: list[Robot], moves: dict[int, Cell]) -> int:
        return sum(len(g) - 1 for g in self._move_conflict_groups(robots, moves))

    def _select_repair_components(self, all_comps: list[list[int]], base_groups: list[list[int]]) -> list[list[int]]:
        # 실제 충돌 그룹은 바로 보정하고, 후보 SCC는 오래 지속된 경우에만 보정한다.
        # 이렇게 해야 WHCA 같은 강한 nominal planner의 정상 흐름을 불필요하게 방해하지 않는다.
        selected: list[list[int]] = []
        seen: set[tuple[int, ...]] = set()
        base_ids = {rid for g in base_groups for rid in g}
        for comp in all_comps:
            key = tuple(sorted(comp))
            no_progress = all(self.detector.no_progress_counter.get(rid, 0) >= self.detector.threshold for rid in key)
            if base_ids.intersection(key) or no_progress:
                if key not in seen:
                    selected.append(list(key))
                    seen.add(key)
        for group in base_groups:
            key = tuple(sorted(group))
            if key not in seen:
                selected.append(list(key))
                seen.add(key)
        return selected

    # 검출된 SCC마다 후퇴, 양보, 통과 중 하나를 정해 순환 대기를 끊는다.
    def _apply_clrr(self, ctx: PlannerContext, moves: dict[int, Cell], comps: list[list[int]]) -> tuple[dict[int, Cell], int, dict]:
        robot_map = {r.id: r for r in ctx.robots}
        occupied = {r.pos for r in ctx.robots if r.completed_at is None}
        retreat_radius = int(ctx.config.get("retreat_radius", self.config.get("retreat_radius", 4)))
        retreat_actions = 0
        new_moves = dict(moves)
        details = {"retreat_assignments": [], "leader_repairs": 0}
        reserved: set[Cell] = set()
        for comp in comps:
            robots = [robot_map[rid] for rid in comp if rid in robot_map and robot_map[rid].completed_at is None]
            if len(robots) < 2:
                continue
            conflict_cells = {r.pos for r in robots} | {desired_next(r) for r in robots} | {new_moves.get(r.id, r.pos) for r in robots}
            retreat_robot, retreat_step = self._choose_retreat_robot(robots, conflict_cells, occupied, retreat_radius)
            if retreat_step is not None and retreat_step not in reserved:
                new_moves[retreat_robot.id] = retreat_step
                retreat_robot.retreat_count += 1
                retreat_actions += 1
                reserved.add(retreat_step)
                details["retreat_assignments"].append((retreat_robot.id, retreat_step))
            else:
                new_moves[retreat_robot.id] = retreat_robot.pos

            leader = max(robots, key=lambda r: (r.wait_time + r.fairness_debt, -r.remaining_distance_estimate(), -r.id))
            if leader.id != retreat_robot.id:
                repaired = self._leader_repair_move(leader, occupied - {leader.pos}, conflict_cells, reserved)
                if repaired != leader.pos:
                    new_moves[leader.id] = repaired
                    reserved.add(repaired)
                    details["leader_repairs"] += 1

            # 같은 SCC의 나머지 로봇은 한 step 양보시켜 순환 대기를 끊는다.
            # 오래 기다린 로봇을 모두 묶어 두지 않도록 fairness debt가 큰 경우에는 기존 이동을 남긴다.
            for r in robots:
                if r.id in {leader.id, retreat_robot.id}:
                    continue
                target = new_moves.get(r.id, r.pos)
                if target in conflict_cells and r.fairness_debt < leader.fairness_debt:
                    new_moves[r.id] = r.pos
        return new_moves, retreat_actions, details

    # nominal planner의 이동 의도를 먼저 만들고, 교착 후보만 CLRR 계층으로 보정한다.
    def plan(self, ctx: PlannerContext) -> PlanResult:
        base = self.nominal.plan(ctx)
        # 이미 보정된 결과가 아니라 각 로봇의 원래 이동 의도로 wait for graph를 만든다.
        # 이 방식이 논문 수식의 의존 그래프 정의와 맞다.
        intent_moves = {r.id: desired_next(r) for r in ctx.robots}
        comps, meta = self.detector.detect(ctx.t, ctx.robots, intent_moves)
        moves = base.moves
        base_groups = self._move_conflict_groups(ctx.robots, moves)
        repair_comps = self._select_repair_components(comps, base_groups)
        retreat_actions = 0
        extra = {}
        if repair_comps:
            moves, retreat_actions, extra = self._apply_clrr(ctx, moves, repair_comps)
        moves, fixed_conflicts = resolve_vertex_edge_conflicts(ctx.robots, moves)
        self.detector.update_progress(ctx.robots, moves)
        meta.update(base.metadata)
        meta.update(extra)
        meta.update({"retreat_actions": retreat_actions, "fixed_conflicts": fixed_conflicts, "repair_components": [list(c) for c in repair_comps]})
        meta["closed_recovery_durations"] = self.detector.closed_event_durations()
        return PlanResult(moves, meta)


# CLRR에 잠재게임 기반 tie breaker를 붙인 planner이다.
class CLRRGamePlanner(CLRRPlanner):

    name = "clrr_game"

    def __init__(self, grid, config=None):
        super().__init__(grid, config)
        game_cfg = PotentialGameConfig(
            max_agents=int(self.config.get("max_game_agents", 5)),
            w_delay=float(self.config.get("game_w_delay", 1.0)),
            w_retreat=float(self.config.get("game_w_retreat", 2.0)),
            w_collision=float(self.config.get("game_w_collision", 1000.0)),
            w_fairness=float(self.config.get("game_w_fairness", 1.20)),
            w_progress=float(self.config.get("game_w_progress", 1.0)),
            max_profiles=int(self.config.get("max_game_profiles_per_component", self.config.get("game_max_profiles", 512))),
        )
        self.game = PotentialGameSelector(grid, game_cfg)

    # CLRR의 후퇴 후보 대신 잠재게임이 고른 행동 profile을 적용한다.
    def _apply_clrr(self, ctx: PlannerContext, moves: dict[int, Cell], comps: list[list[int]]) -> tuple[dict[int, Cell], int, dict]:
        robot_map = {r.id: r for r in ctx.robots}
        occupied_all = {r.pos for r in ctx.robots if r.completed_at is None}
        new_moves = dict(moves)
        retreat_actions = 0
        game_profiles = 0
        potential_values: list[float] = []
        exact_potential_verified = True
        capped_game_count = 0
        local_game_time_ms = 0.0
        max_total_profiles = int(ctx.config.get("max_total_game_profiles_per_step", self.config.get("max_total_game_profiles_per_step", 10**9)))
        for comp in comps:
            if game_profiles >= max_total_profiles:
                capped_game_count += 1
                continue
            robots = [robot_map[rid] for rid in comp if rid in robot_map and robot_map[rid].completed_at is None]
            if len(robots) < 2:
                continue
            if bool(ctx.config.get("verify_potential_online", False)) and len(robots) <= self.game.config.max_agents:
                exact_potential_verified = exact_potential_verified and self.game.verify_exact_potential(robots, occupied_all)
            tic = time.perf_counter()
            chosen = self.game.select(robots, occupied_all)
            local_game_time_ms += (time.perf_counter() - tic) * 1000.0
            game_profiles += self.game.last_profile_count
            if game_profiles > max_total_profiles:
                capped_game_count += 1
            potential_values.append(self.game.last_best_potential)
            for rid, action in chosen.items():
                new_moves[rid] = action.target
                if action.label == "retreat":
                    robot_map[rid].retreat_count += 1
                    retreat_actions += 1
        details = {
            "game_profiles": game_profiles,
            "game_best_potential_sum": sum(potential_values) if potential_values else 0.0,
            "exact_potential_verified": exact_potential_verified,
            "game_selection_mode": getattr(self.game, "last_selection_mode", "unknown"),
            "game_exact_components": int(getattr(self.game, "last_exact_components", 0)),
            "game_greedy_components": int(getattr(self.game, "last_greedy_components", 0)),
            "capped_game_count": capped_game_count,
            "local_game_time_ms": local_game_time_ms,
        }
        return new_moves, retreat_actions, details


# 논문에서 제안하는 전체 LCG-MPC 계층이다.
# 잠재게임으로 비대칭 행동을 고르고, 국소 MPC가 즉시 실행 여부를 보정한다.
class CLRRHMPCPlanner(CLRRGamePlanner):

    name = "clrr_hmpc"

    def __init__(self, grid, config=None):
        super().__init__(grid, config)
        mpc_cfg = LocalMPCConfig(
            horizon=int(self.config.get("mpc_horizon", 6)),
            enabled=bool(self.config.get("enable_mpc", True)),
            w_progress=float(self.config.get("mpc_w_progress", 1.0)),
            w_wait=float(self.config.get("mpc_w_wait", 0.2)),
            w_accel=float(self.config.get("mpc_w_accel", 0.05)),
            max_simultaneous_go_ratio=float(self.config.get("mpc_go_ratio", 0.65)),
        )
        self.mpc = LocalMPCRefiner(mpc_cfg)

    # 잠재게임 결과를 받은 뒤 국소 MPC가 즉시 실행 여부를 한 번 더 조정한다.
    def _apply_clrr(self, ctx: PlannerContext, moves: dict[int, Cell], comps: list[list[int]]) -> tuple[dict[int, Cell], int, dict]:
        robot_map = {r.id: r for r in ctx.robots}
        new_moves, retreat_actions, details = super()._apply_clrr(ctx, moves, comps)
        mpc_refinements = 0
        capped_mpc_count = 0
        mpc_time_ms = 0.0
        mpc_statuses: list[str] = []
        max_mpc = int(ctx.config.get("max_mpc_refinements_per_step", self.config.get("max_mpc_refinements_per_step", 10**9)))
        for comp in comps:
            if mpc_refinements >= max_mpc:
                capped_mpc_count += 1
                continue
            robots = [robot_map[rid] for rid in comp if rid in robot_map and robot_map[rid].completed_at is None]
            if len(robots) >= 2:
                local_candidates = {r.id: new_moves.get(r.id, r.pos) for r in robots}
                tic = time.perf_counter()
                refined = self.mpc.refine(robots, local_candidates)
                mpc_time_ms += (time.perf_counter() - tic) * 1000.0
                if self.mpc.last_status not in {"disabled", "not_run"}:
                    mpc_refinements += 1
                mpc_statuses.append(self.mpc.last_status)
                new_moves.update(refined)
        details.update({"mpc_refinements": mpc_refinements, "mpc_statuses": mpc_statuses, "capped_mpc_count": capped_mpc_count, "mpc_qp_refinement_time_ms": mpc_time_ms})
        return new_moves, retreat_actions, details


class LCGMPCPlusPlanner(CLRRHMPCPlanner):

    name = "lcg_mpc_plus"

    def __init__(self, grid, config=None):
        super().__init__(grid, config)
        # Continuous-envelope experiments benefit from a robust CBF/MPC nominal controller.
        # Import locally to keep the baseline module independent of the proposed planner.
        from mr_deadlock.planners.baselines import IMPCDRLitePlanner

        self.robust_nominal = IMPCDRLitePlanner(grid, config)

    def initialize(self, robots):
        self.nominal.initialize(robots)
        self.robust_nominal.initialize(robots)

    def _cluster_waiting_robots(self, ctx: PlannerContext, moves: dict[int, Cell]) -> list[list[int]]:
        threshold = int(ctx.config.get("deadlock_threshold", self.config.get("deadlock_threshold", 6)))
        radius = int(ctx.config.get("stagnation_cluster_radius", 3))
        robots = [
            r
            for r in ctx.robots
            if r.completed_at is None
            and (
                r.local_wait_streak >= threshold
                or r.no_progress_streak >= threshold
                or self.detector.no_progress_counter.get(r.id, 0) >= threshold
            )
        ]
        if not robots:
            return []
        parent = {r.id: r.id for r in robots}
        by_id = {r.id: r for r in robots}

        def find(a: int) -> int:
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        ids = [r.id for r in robots]
        for i, a in enumerate(ids):
            ra = by_id[a]
            cells_a = {ra.pos, desired_next(ra), moves.get(ra.id, ra.pos)}
            for b in ids[i + 1 :]:
                rb = by_id[b]
                cells_b = {rb.pos, desired_next(rb), moves.get(rb.id, rb.pos)}
                d = min(self.grid.manhattan(ca, cb) for ca in cells_a for cb in cells_b)
                if d <= radius:
                    union(a, b)
        groups: dict[int, list[int]] = {}
        for rid in ids:
            groups.setdefault(find(rid), []).append(rid)
        return [sorted(g) for g in groups.values() if len(g) >= 2]

    def _quality(self, ctx: PlannerContext, moves: dict[int, Cell], fixed_conflicts: int = 0) -> float:
        score = 1000.0 * fixed_conflicts
        for r in ctx.robots:
            if r.completed_at is not None:
                continue
            target = moves.get(r.id, r.pos)
            old_d = self.grid.manhattan(r.pos, r.goal)
            new_d = self.grid.manhattan(target, r.goal)
            progress = old_d - new_d
            wait = target == r.pos
            debt = r.local_wait_streak + r.fairness_debt
            score += new_d
            if wait:
                score += 0.75 + 0.22 * debt
            if progress < 0:
                score += 2.5 * abs(progress)
            if target != r.pos and r.local_wait_streak > 0:
                score -= 0.12 * r.local_wait_streak
        return score

    def _accept_repair(
        self,
        ctx: PlannerContext,
        base_moves: dict[int, Cell],
        cand_moves: dict[int, Cell],
        base_fixed: int,
        cand_fixed: int,
        repair_comps: list[list[int]],
    ) -> bool:
        if not repair_comps:
            return False
        if cand_fixed < base_fixed:
            return True
        persistent = False
        for comp in repair_comps:
            if all(
                self.detector.no_progress_counter.get(rid, 0) >= self.detector.threshold
                for rid in comp
            ):
                persistent = True
                break
        base_q = self._quality(ctx, base_moves, base_fixed)
        cand_q = self._quality(ctx, cand_moves, cand_fixed)
        margin = float(ctx.config.get("repair_acceptance_margin", self.config.get("repair_acceptance_margin", 0.05)))
        return cand_q <= base_q * (1.0 + margin) or persistent

    def _candidate_moves_for_filter(self, r: Robot, preferred: Cell) -> list[Cell]:
        cells = [preferred, desired_next(r), *self.grid.neighbors4(r.pos, include_wait=True)]
        unique: list[Cell] = []
        seen: set[Cell] = set()
        for c in cells:
            if c in seen or not self.grid.passable(c):
                continue
            if c != r.pos and c not in self.grid.neighbors4(r.pos):
                continue
            seen.add(c)
            unique.append(c)
        return sorted(
            unique,
            key=lambda c: (
                c != preferred,
                self.grid.manhattan(c, r.goal),
                c == r.pos,
                c,
            ),
        )

    def _cbf_safe_against_selected(
        self,
        r: Robot,
        target: Cell,
        selected: dict[int, Cell],
        robot_map: dict[int, Robot],
        kin: KinematicSafetyConfig,
    ) -> bool:
        if target in selected.values():
            return False
        p0, p1 = cell_center(r.pos), cell_center(target)
        min_sep = kin.min_robot_separation
        for oid, ot in selected.items():
            other = robot_map[oid]
            q0, q1 = cell_center(other.pos), cell_center(ot)
            # target footprint and synchronous swept-volume barrier.
            if ((p1[0] - q1[0]) ** 2 + (p1[1] - q1[1]) ** 2) ** 0.5 < min_sep - 1e-12:
                return False
            if synchronous_segment_distance(p0, p1, q0, q1) < min_sep - 1e-12:
                return False
        vx = target[0] - r.pos[0]
        vy = target[1] - r.pos[1]
        accel = ((vx - r.velocity_x) ** 2 + (vy - r.velocity_y) ** 2) ** 0.5 / max(1e-9, kin.dt)
        speed = (vx * vx + vy * vy) ** 0.5 / max(1e-9, kin.dt)
        if kin.enforce_acceleration_bound and accel > kin.max_accel + 1e-12:
            return target == r.pos
        if speed > kin.max_speed + 1e-12:
            return target == r.pos
        return True

    def _adaptive_cbf_filter(self, ctx: PlannerContext, moves: dict[int, Cell]) -> tuple[dict[int, Cell], int]:
        kin = KinematicSafetyConfig.from_config(ctx.config)
        if not kin.enabled:
            return moves, 0
        robots = [r for r in ctx.robots if r.completed_at is None]
        robot_map = {r.id: r for r in robots}
        order = sorted(
            robots,
            key=lambda r: (-r.wait_time - r.fairness_debt, r.remaining_distance_estimate(), r.id),
        )
        selected: dict[int, Cell] = {}
        clips = 0
        for r in order:
            preferred = moves.get(r.id, r.pos)
            chosen = None
            for c in self._candidate_moves_for_filter(r, preferred):
                if self._cbf_safe_against_selected(r, c, selected, robot_map, kin):
                    chosen = c
                    break
            if chosen is None:
                chosen = r.pos
            selected[r.id] = chosen
            clips += int(chosen != preferred)
        for r in ctx.robots:
            selected.setdefault(r.id, r.pos)
        return selected, clips

    def plan(self, ctx: PlannerContext) -> PlanResult:
        # 1) grid-only 실험에서는 WHCA nominal을, continuous-envelope 실험에서는 robust IMPC-DR
        # nominal을 사용한다. 제안 계층은 실제 충돌·지속 정체가 있을 때만 개입한다.
        enable_robust_nominal = bool(ctx.config.get("enable_continuous_dynamics", False)) and not bool(ctx.config.get("lcg_disable_robust_nominal", False))
        robust_nominal_repairs = 0
        if enable_robust_nominal:
            base = self.robust_nominal.plan(ctx)
            nominal_family = "impc_dr_lite"
            if bool(ctx.config.get("lcg_skip_whca_probe", False)):
                robust_nominal_repairs = int(base.metadata.get("robust_clips", 0))
            else:
                whca_probe = self.nominal.plan(ctx)
                robust_nominal_repairs = sum(
                    1
                    for r in ctx.robots
                    if base.moves.get(r.id, r.pos) != whca_probe.moves.get(r.id, r.pos)
                )
        else:
            base = self.nominal.plan(ctx)
            nominal_family = "whca"
        base_moves, base_fixed = resolve_vertex_edge_conflicts(ctx.robots, base.moves)
        raw_before = self._move_conflict_count(ctx.robots, base.moves)

        # 2) 의존 그래프와 실제 one-step 충돌, 그리고 지속 정체 그룹을 모두 repair 후보로 만든다.
        intent_moves = {r.id: desired_next(r) for r in ctx.robots}
        comps, meta = self.detector.detect(ctx.t, ctx.robots, intent_moves)
        base_groups = self._move_conflict_groups(ctx.robots, base_moves)
        wait_groups = [] if bool(ctx.config.get("lcg_disable_stagnation_repair", False)) else self._cluster_waiting_robots(ctx, base_moves)
        repair_comps = self._select_repair_components(comps, base_groups + wait_groups)
        for group in wait_groups:
            key = tuple(sorted(group))
            if key not in {tuple(sorted(c)) for c in repair_comps}:
                repair_comps.append(group)

        chosen_moves = base_moves
        accepted = False
        retreat_actions = 0
        extra: dict = {}
        cand_fixed = base_fixed
        enable_game = not bool(ctx.config.get("lcg_disable_game", False))
        enable_mpc = bool(ctx.config.get("enable_mpc", True))
        enable_cbf = bool(ctx.config.get("lcg_strict_cbf_filter", False))
        enable_stagnation = not bool(ctx.config.get("lcg_disable_stagnation_repair", False))
        if repair_comps:
            if not enable_game:
                candidate, retreat_actions, extra = CLRRPlanner._apply_clrr(self, ctx, base_moves, repair_comps)
                extra.update({"game_selection_mode": "disabled", "game_exact_components": 0, "game_greedy_components": 0})
            else:
                candidate, retreat_actions, extra = self._apply_clrr(ctx, base_moves, repair_comps)
            candidate, cand_fixed = resolve_vertex_edge_conflicts(ctx.robots, candidate)
            accepted = self._accept_repair(ctx, base_moves, candidate, base_fixed, cand_fixed, repair_comps)
            if accepted:
                chosen_moves = candidate
            else:
                retreat_actions = 0
                # 실행하지 않은 game/MPC 검사는 metadata에 남기되 action count는 올리지 않는다.
                extra["discarded_repair"] = True

        cbf_clips = 0
        cbf_time_ms = 0.0
        capped_cbf_count = 0
        if bool(ctx.config.get("lcg_strict_cbf_filter", False)):
            max_cbf = int(ctx.config.get("max_cbf_filter_calls_per_step", self.config.get("max_cbf_filter_calls_per_step", 1)))
            if max_cbf <= 0:
                capped_cbf_count = 1
            else:
                cbf_tic = time.perf_counter()
                filtered_moves, cbf_clips = self._adaptive_cbf_filter(ctx, chosen_moves)
                cbf_time_ms = (time.perf_counter() - cbf_tic) * 1000.0
                filtered_moves, filtered_fixed = resolve_vertex_edge_conflicts(ctx.robots, filtered_moves)
                if cbf_clips or filtered_fixed:
                    chosen_moves = filtered_moves

        self.detector.update_progress(ctx.robots, chosen_moves)
        meta.update(base.metadata)
        meta.update(extra)
        meta.update(
            {
                "retreat_actions": retreat_actions,
                "fixed_conflicts": cand_fixed if accepted else base_fixed,
                "repair_components": [list(c) for c in repair_comps],
                "stagnation_components": [list(c) for c in wait_groups],
                "accepted_repair": bool(accepted),
                "nominal_family": nominal_family,
                "enable_game": enable_game,
                "enable_mpc": enable_mpc,
                "enable_cbf": enable_cbf,
                "enable_stagnation_repair": enable_stagnation,
                "enable_robust_nominal": enable_robust_nominal,
                "enable_safety_envelope_logging": not bool(ctx.config.get("lcg_disable_safety_envelope_logging", False)),
                "robust_nominal_repairs": robust_nominal_repairs,
                "raw_conflicts_before_repair": raw_before,
                "base_quality": self._quality(ctx, base_moves, base_fixed),
                "candidate_quality": self._quality(ctx, chosen_moves, cand_fixed if accepted else base_fixed),
                "adaptive_cbf_clips": int(locals().get("cbf_clips", 0)),
                "capped_cbf_count": capped_cbf_count,
                "cbf_robust_filter_time_ms": cbf_time_ms,
            }
        )
        meta["closed_recovery_durations"] = self.detector.closed_event_durations()
        return PlanResult(chosen_moves, meta)

