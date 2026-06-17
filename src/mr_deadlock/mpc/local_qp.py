# Inha University & RODIX Inc, Anders Hwang
# 파일명: local_qp.py
# 목적 및 역할:
# 국소 충돌 집합에 대해 path index 기반의 가벼운 MPC 보정 단계를 수행한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from dataclasses import dataclass
from mr_deadlock.core.robot import Robot
from mr_deadlock.core.types import Cell


@dataclass
class LocalMPCConfig:
    horizon: int = 6
    w_progress: float = 1.0
    w_wait: float = 0.2
    w_accel: float = 0.05
    w_fairness: float = 0.05
    enabled: bool = True
    max_simultaneous_go_ratio: float = 0.65


# path index 상태를 가정한 가벼운 국소 MPC 보정기이다.
# 전체 로봇을 푸는 대신 충돌 집합 내부의 즉시 실행 여부만 작은 QP로 조정한다.
class LocalMPCRefiner:

    def __init__(self, config: LocalMPCConfig | None = None):
        self.config = config or LocalMPCConfig()
        try:
            import cvxpy as cp  # type: ignore
            self.cp = cp
            self.available = True
        except Exception:
            self.cp = None
            self.available = False
        self.last_status = "not_run"
        self.last_objective = None

    # game layer의 후보 이동을 받아 이번 step에서 바로 실행할 로봇을 고른다.
    def refine(self, robots: list[Robot], candidate_moves: dict[int, Cell]) -> dict[int, Cell]:
        if not self.config.enabled or len(robots) <= 1:
            self.last_status = "disabled"
            return candidate_moves
        # 잠재게임 결과가 이미 국소 충돌을 없앤 경우에는 MPC가 흐름을 과하게 늦추면 안 된다.
        # 그래서 먼저 안전한 후보인지 확인하고, 실제 충돌이 없으면 후보 이동을 보존한다.
        if not self._has_profile_conflict(robots, candidate_moves):
            self.last_status = "checked_safe"
            return dict(candidate_moves)
        if self.available:
            out = self._refine_qp(robots, candidate_moves)
            if out is not None:
                return out
        return self._refine_heuristic(robots, candidate_moves)


    def _make_safe_profile(self, robots: list[Robot], moves: dict[int, Cell]) -> dict[int, Cell]:
        # MPC가 고른 실행 집합 안에서도 같은 칸 진입과 자리교환을 한 번 더 정리한다.
        # 최종 안전 감독기 전에 국소 단계에서 최대한 충돌 수정을 끝내기 위한 절차이다.
        pos = {r.id: r.pos for r in robots}
        by_id = {r.id: r for r in robots}
        out = dict(moves)
        changed = True
        while changed:
            changed = False
            by_target: dict[Cell, list[int]] = {}
            for r in robots:
                by_target.setdefault(out.get(r.id, r.pos), []).append(r.id)
            for ids in by_target.values():
                if len(ids) <= 1:
                    continue
                keep = max(ids, key=lambda rid: (by_id[rid].local_wait_streak + by_id[rid].fairness_debt, self._progress_score(by_id[rid], out.get(rid, by_id[rid].pos)), -rid))
                for rid in ids:
                    if rid != keep and out.get(rid, pos[rid]) != pos[rid]:
                        out[rid] = pos[rid]
                        changed = True
            ids = [r.id for r in robots]
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    if out.get(a, pos[a]) == pos[b] and out.get(b, pos[b]) == pos[a] and pos[a] != pos[b]:
                        loser = min((a, b), key=lambda rid: (by_id[rid].local_wait_streak + by_id[rid].fairness_debt, self._progress_score(by_id[rid], out.get(rid, by_id[rid].pos))))
                        if out.get(loser, pos[loser]) != pos[loser]:
                            out[loser] = pos[loser]
                            changed = True
        return out

    def _has_profile_conflict(self, robots: list[Robot], candidate_moves: dict[int, Cell]) -> bool:
        pos = {r.id: r.pos for r in robots}
        targets: dict[Cell, int] = {}
        for r in robots:
            target = candidate_moves.get(r.id, r.pos)
            if target in targets:
                return True
            targets[target] = r.id
        ids = [r.id for r in robots]
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                if candidate_moves.get(a, pos[a]) == pos[b] and candidate_moves.get(b, pos[b]) == pos[a] and pos[a] != pos[b]:
                    return True
        return False

    def _progress_score(self, r: Robot, target: Cell) -> float:
        old_d = abs(r.pos[0] - r.goal[0]) + abs(r.pos[1] - r.goal[1])
        new_d = abs(target[0] - r.goal[0]) + abs(target[1] - r.goal[1])
        return float(old_d - new_d)

    def _refine_qp(self, robots: list[Robot], candidate_moves: dict[int, Cell]) -> dict[int, Cell] | None:
        try:
            cp = self.cp
            n = len(robots)
            z = cp.Variable(n)  # 완화된 실행 변수이다. 1이면 후보 이동을 실행하고 0이면 대기한다.
            progress = [self._progress_score(r, candidate_moves.get(r.id, r.pos)) for r in robots]
            wait_credit = [1.0 + r.local_wait_streak + self.config.w_fairness * r.fairness_debt for r in robots]
            # 진행도와 긴 대기를 함께 반영하고, 작은 이차항으로 극단적인 진동을 줄인다.
            objective = cp.Maximize(
                sum((self.config.w_progress * progress[i] + self.config.w_wait * wait_credit[i]) * z[i] for i in range(n))
                - self.config.w_accel * cp.sum_squares(z[1:] - z[:-1])
            )
            constraints = [z >= 0, z <= 1]
            max_go = max(1, min(n, int(round(self.config.max_simultaneous_go_ratio * n))))
            constraints.append(cp.sum(z) <= max_go)
            prob = cp.Problem(objective, constraints)
            prob.solve(solver="OSQP", warm_start=True, verbose=False)
            if z.value is None:
                self.last_status = "infeasible_or_no_value"
                return None
            self.last_status = str(prob.status)
            self.last_objective = float(prob.value) if prob.value is not None else None
            out = dict(candidate_moves)
            for i, r in enumerate(robots):
                # 완화 QP가 충분히 지지한 로봇만 이번 step에서 이동시킨다.
                if float(z.value[i]) < 0.45:
                    out[r.id] = r.pos
            # 완화 QP가 모두 이동을 허용하면 국소 용량 제한이 드러나지 않는다.
            # 이 경우에도 낮은 점수의 일부 로봇은 한 step 양보시켜 ablation 차이를 명확히 한다.
            moving = [r for r in robots if out.get(r.id, r.pos) != r.pos]
            if len(moving) > max_go:
                ranked = sorted(moving, key=lambda rr: (self._progress_score(rr, candidate_moves.get(rr.id, rr.pos)) + 0.2 * rr.local_wait_streak + 0.08 * rr.fairness_debt, -rr.id), reverse=True)
                allow = {r.id for r in ranked[:max_go]}
                for r in moving:
                    if r.id not in allow:
                        out[r.id] = r.pos
            return self._make_safe_profile(robots, out)
        except Exception as exc:  # pragma: no cover - solver availability varies.
            self.last_status = f"qp_failed:{type(exc).__name__}"
            return None

    def _refine_heuristic(self, robots: list[Robot], candidate_moves: dict[int, Cell]) -> dict[int, Cell]:
        n = len(robots)
        max_go = max(1, min(n, int(round(self.config.max_simultaneous_go_ratio * n))))
        scores = []
        for r in robots:
            target = candidate_moves.get(r.id, r.pos)
            score = self._progress_score(r, target) + 0.2 * r.local_wait_streak + 0.08 * r.fairness_debt
            scores.append((score, r.id))
        go_ids = {rid for _, rid in sorted(scores, reverse=True)[:max_go]}
        out = dict(candidate_moves)
        for r in robots:
            if r.id not in go_ids:
                out[r.id] = r.pos
        self.last_status = "heuristic"
        return self._make_safe_profile(robots, out)

