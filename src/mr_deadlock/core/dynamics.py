# Inha University & RODIX Inc, Anders Hwang
# 파일명: dynamics.py
# 목적 및 역할:
# grid one-step simulator 위에 AMR 연속 footprint, swept-volume, acceleration bound,
# sensing uncertainty를 반영하는 보수적 safety envelope를 제공한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, hypot, isfinite
from typing import Iterable

from mr_deadlock.core.grid import GridMap
from mr_deadlock.core.robot import Robot
from mr_deadlock.core.types import Cell, MoveDict


@dataclass(frozen=True)
class KinematicSafetyConfig:
    enabled: bool = True
    footprint_radius: float = 0.35
    safety_margin: float = 0.05
    sensing_sigma: float = 0.05
    uncertainty_k: float = 2.0
    dt: float = 1.0
    max_speed: float = 1.25
    max_accel: float = 1.50
    enforce_acceleration_bound: bool = True
    enforce_footprint_clearance: bool = True
    enforce_swept_clearance: bool = True
    enforce_obstacle_clearance: bool = True

    @property
    def uncertainty_buffer(self) -> float:
        return max(0.0, self.uncertainty_k * self.sensing_sigma)

    @property
    def robot_radius(self) -> float:
        return max(0.0, self.footprint_radius + self.safety_margin + self.uncertainty_buffer)

    @property
    def min_robot_separation(self) -> float:
        return 2.0 * self.robot_radius

    @classmethod
    def from_config(cls, cfg: dict) -> "KinematicSafetyConfig":
        # enable_continuous_dynamics가 명시되지 않아도 footprint 관련 값이 있으면 활성화한다.
        has_envelope_key = any(
            k in cfg
            for k in [
                "footprint_radius",
                "safety_margin",
                "sensing_sigma",
                "max_accel",
                "max_speed",
                "uncertainty_k",
            ]
        )
        enabled = bool(cfg.get("enable_continuous_dynamics", has_envelope_key))
        return cls(
            enabled=enabled,
            footprint_radius=float(cfg.get("footprint_radius", cls.footprint_radius)),
            safety_margin=float(cfg.get("safety_margin", cls.safety_margin)),
            sensing_sigma=float(cfg.get("sensing_sigma", cls.sensing_sigma)),
            uncertainty_k=float(cfg.get("uncertainty_k", cls.uncertainty_k)),
            dt=max(1e-9, float(cfg.get("dt", cls.dt))),
            max_speed=max(1e-9, float(cfg.get("max_speed", cls.max_speed))),
            max_accel=max(1e-9, float(cfg.get("max_accel", cls.max_accel))),
            enforce_acceleration_bound=bool(
                cfg.get("enforce_acceleration_bound", cls.enforce_acceleration_bound)
            ),
            enforce_footprint_clearance=bool(
                cfg.get("enforce_footprint_clearance", cls.enforce_footprint_clearance)
            ),
            enforce_swept_clearance=bool(
                cfg.get("enforce_swept_clearance", cls.enforce_swept_clearance)
            ),
            enforce_obstacle_clearance=bool(
                cfg.get("enforce_obstacle_clearance", cls.enforce_obstacle_clearance)
            ),
        )


@dataclass
class KinematicDiagnostics:
    footprint_conflicts: int = 0
    swept_conflicts: int = 0
    obstacle_envelope_conflicts: int = 0
    acceleration_clips: int = 0
    speed_clips: int = 0
    sensing_risk_events: int = 0
    min_clearance: float = float("inf")

    def update_clearance(self, distance: float, required: float) -> None:
        if isfinite(distance):
            self.min_clearance = min(self.min_clearance, float(distance - required))

    def as_record_values(self) -> dict[str, float | int]:
        return {
            "footprint_conflicts": int(self.footprint_conflicts),
            "swept_conflicts": int(self.swept_conflicts),
            "obstacle_envelope_conflicts": int(self.obstacle_envelope_conflicts),
            "acceleration_clips": int(self.acceleration_clips),
            "speed_clips": int(self.speed_clips),
            "sensing_risk_events": int(self.sensing_risk_events),
            "continuous_min_clearance": (
                float(self.min_clearance) if isfinite(self.min_clearance) else float("nan")
            ),
        }


def cell_center(c: Cell) -> tuple[float, float]:
    return (float(c[0]) + 0.5, float(c[1]) + 0.5)


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def _point_segment_distance(
    p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    vx, vy = b[0] - a[0], b[1] - a[1]
    wx, wy = p[0] - a[0], p[1] - a[1]
    denom = vx * vx + vy * vy
    if denom <= 1e-12:
        return _dist(p, a)
    t = max(0.0, min(1.0, (wx * vx + wy * vy) / denom))
    proj = (a[0] + t * vx, a[1] + t * vy)
    return _dist(p, proj)


def segment_distance(
    a0: tuple[float, float],
    a1: tuple[float, float],
    b0: tuple[float, float],
    b1: tuple[float, float],
) -> float:
    # 한 step grid move에서는 선분 길이가 짧으므로 endpoint-to-segment 최소거리로 충분하다.
    return min(
        _point_segment_distance(a0, b0, b1),
        _point_segment_distance(a1, b0, b1),
        _point_segment_distance(b0, a0, a1),
        _point_segment_distance(b1, a0, a1),
    )




def synchronous_segment_distance(
    a0: tuple[float, float],
    a1: tuple[float, float],
    b0: tuple[float, float],
    b1: tuple[float, float],
) -> float:
    """Minimum distance between two constant-velocity segments at the same time parameter."""
    rx, ry = a0[0] - b0[0], a0[1] - b0[1]
    vx, vy = (a1[0] - a0[0]) - (b1[0] - b0[0]), (a1[1] - a0[1]) - (b1[1] - b0[1])
    denom = vx * vx + vy * vy
    if denom <= 1e-12:
        t = 0.0
    else:
        t = max(0.0, min(1.0, -(rx * vx + ry * vy) / denom))
    dx = rx + t * vx
    dy = ry + t * vy
    return hypot(dx, dy)

def _priority_key(r: Robot) -> tuple[float, int, int]:
    # 큰 값이 우선권이다. 오래 기다리고 목표가 가까운 로봇을 통과시킨다.
    return (r.wait_time + r.fairness_debt, -r.remaining_distance_estimate(), -r.id)


def _spatial_pairs(items: list[tuple[int, Cell]], radius: float) -> Iterable[tuple[int, int]]:
    # target cell 기준의 hash bin으로 근접 pair만 뽑는다. radius가 1 안팎이면 O(N)에 가깝다.
    reach = max(1, int(ceil(radius)) + 1)
    bins: dict[tuple[int, int], list[tuple[int, Cell]]] = {}
    for rid, cell in items:
        bins.setdefault(cell, []).append((rid, cell))
    emitted: set[tuple[int, int]] = set()
    for (x, y), bucket in bins.items():
        candidates: list[tuple[int, Cell]] = []
        for dx in range(-reach, reach + 1):
            for dy in range(-reach, reach + 1):
                candidates.extend(bins.get((x + dx, y + dy), []))
        for rid, cell in bucket:
            for oid, other_cell in candidates:
                if oid <= rid:
                    continue
                if abs(cell[0] - other_cell[0]) > reach or abs(cell[1] - other_cell[1]) > reach:
                    continue
                key = (rid, oid)
                if key not in emitted:
                    emitted.add(key)
                    yield key


def _nearby_obstacles(grid: GridMap, c: Cell, reach: int) -> Iterable[Cell]:
    x, y = c
    for ox in range(x - reach, x + reach + 1):
        for oy in range(y - reach, y + reach + 1):
            z = (ox, oy)
            if z in grid.obstacles:
                yield z


def validate_kinematic_envelope(
    robots: list[Robot],
    moves: MoveDict,
    grid: GridMap,
    cfg: KinematicSafetyConfig,
) -> tuple[MoveDict, KinematicDiagnostics]:
    """Apply continuous AMR safety envelope to already grid-valid one-step moves.

    The simulator still advances on a grid, but this filter prevents moves whose cell-center
    targets or swept segments would violate a circular AMR footprint inflated by sensing
    uncertainty. It also enforces a simple acceleration/speed bound by forcing a robot to wait
    when the commanded velocity change is outside the bound.
    """
    diag = KinematicDiagnostics()
    fixed: MoveDict = {r.id: moves.get(r.id, r.pos) for r in robots}
    if not cfg.enabled or not robots:
        return fixed, diag

    by_id = {r.id: r for r in robots}
    dt = cfg.dt
    min_sep = cfg.min_robot_separation
    obstacle_required = cfg.robot_radius

    # 1) acceleration and speed bound: abrupt reversals are converted to wait actions.
    for r in robots:
        target = fixed.get(r.id, r.pos)
        cmd_vx = (target[0] - r.pos[0]) / dt
        cmd_vy = (target[1] - r.pos[1]) / dt
        speed = hypot(cmd_vx, cmd_vy)
        accel = hypot(cmd_vx - r.velocity_x, cmd_vy - r.velocity_y) / dt
        if cfg.enforce_acceleration_bound and accel > cfg.max_accel + 1e-12:
            if target != r.pos:
                fixed[r.id] = r.pos
                diag.acceleration_clips += 1
                diag.sensing_risk_events += int(cfg.sensing_sigma > 0)
        elif speed > cfg.max_speed + 1e-12:
            if target != r.pos:
                fixed[r.id] = r.pos
                diag.speed_clips += 1
                diag.sensing_risk_events += int(cfg.sensing_sigma > 0)

    # 2) obstacle inflated footprint check near target cell centers.
    if cfg.enforce_obstacle_clearance and obstacle_required > 0.0:
        reach_obs = max(1, int(ceil(obstacle_required)) + 1)
        for r in robots:
            target = fixed.get(r.id, r.pos)
            p = cell_center(target)
            for obs in _nearby_obstacles(grid, target, reach_obs):
                d = _dist(p, cell_center(obs))
                diag.update_clearance(d, obstacle_required)
                if d < obstacle_required - 1e-12:
                    if target != r.pos:
                        fixed[r.id] = r.pos
                    diag.obstacle_envelope_conflicts += 1
                    diag.sensing_risk_events += int(cfg.sensing_sigma > 0)
                    break

    # 3) pairwise footprint and swept-volume conflict check. Repeat because making one robot wait
    # can introduce a new close approach with another moving robot's swept segment.
    changed = True
    while changed:
        changed = False
        target_items = [(r.id, fixed.get(r.id, r.pos)) for r in robots]
        for a, b in _spatial_pairs(target_items, min_sep):
            ra, rb = by_id[a], by_id[b]
            ta, tb = fixed.get(a, ra.pos), fixed.get(b, rb.pos)
            pa0, pa1 = cell_center(ra.pos), cell_center(ta)
            pb0, pb1 = cell_center(rb.pos), cell_center(tb)
            d_target = _dist(pa1, pb1)
            diag.update_clearance(d_target, min_sep)
            conflict = False
            reason = ""
            if cfg.enforce_footprint_clearance and d_target < min_sep - 1e-12:
                conflict = True
                reason = "footprint"
            d_swept = synchronous_segment_distance(pa0, pa1, pb0, pb1)
            diag.update_clearance(d_swept, min_sep)
            if cfg.enforce_swept_clearance and d_swept < min_sep - 1e-12:
                conflict = True
                reason = "swept" if reason == "" else reason
            if not conflict:
                continue
            loser = min((ra, rb), key=_priority_key)
            winner = rb if loser.id == ra.id else ra
            # If the lower-priority robot is already waiting, stopping it cannot clear a target
            # occupied by that robot. In that case stop the moving counterpart.
            chosen_loser = loser
            if fixed.get(loser.id, loser.pos) == loser.pos and fixed.get(winner.id, winner.pos) != winner.pos:
                chosen_loser = winner
            if fixed.get(chosen_loser.id, chosen_loser.pos) != chosen_loser.pos:
                fixed[chosen_loser.id] = chosen_loser.pos
                changed = True
            if reason == "footprint":
                diag.footprint_conflicts += 1
            else:
                diag.swept_conflicts += 1
            diag.sensing_risk_events += int(cfg.sensing_sigma > 0)

    # Report the final executed-profile clearance rather than the rejected candidate clearance.
    final_min = float("inf")
    target_items = [(r.id, fixed.get(r.id, r.pos)) for r in robots]
    for a, b in _spatial_pairs(target_items, min_sep):
        ra, rb = by_id[a], by_id[b]
        ta, tb = fixed.get(a, ra.pos), fixed.get(b, rb.pos)
        pa0, pa1 = cell_center(ra.pos), cell_center(ta)
        pb0, pb1 = cell_center(rb.pos), cell_center(tb)
        final_min = min(final_min, _dist(pa1, pb1) - min_sep)
        final_min = min(final_min, synchronous_segment_distance(pa0, pa1, pb0, pb1) - min_sep)
    if cfg.enforce_obstacle_clearance and obstacle_required > 0.0:
        reach_obs = max(1, int(ceil(obstacle_required)) + 1)
        for r in robots:
            target = fixed.get(r.id, r.pos)
            p = cell_center(target)
            for obs in _nearby_obstacles(grid, target, reach_obs):
                final_min = min(final_min, _dist(p, cell_center(obs)) - obstacle_required)
    diag.min_clearance = final_min
    return fixed, diag


def update_robot_velocity_state(robots: list[Robot], moves: MoveDict, dt: float = 1.0) -> None:
    dt = max(1e-9, dt)
    for r in robots:
        target = moves.get(r.id, r.pos)
        r.accel_x = ((target[0] - r.pos[0]) / dt - r.velocity_x) / dt
        r.accel_y = ((target[1] - r.pos[1]) / dt - r.velocity_y) / dt
        r.velocity_x = (target[0] - r.pos[0]) / dt
        r.velocity_y = (target[1] - r.pos[1]) / dt

