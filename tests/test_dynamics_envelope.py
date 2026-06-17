# Inha University & RODIX Inc, Anders Hwang
from mr_deadlock.core.dynamics import (
    KinematicSafetyConfig,
    cell_center,
    synchronous_segment_distance,
    validate_kinematic_envelope,
)
from mr_deadlock.core.grid import GridMap
from mr_deadlock.core.robot import Robot


def test_synchronous_segment_distance_allows_safe_following():
    # Robot B follows into A's previous cell while A moves forward; synchronous distance stays 1.
    a0, a1 = cell_center((1, 0)), cell_center((2, 0))
    b0, b1 = cell_center((0, 0)), cell_center((1, 0))
    assert synchronous_segment_distance(a0, a1, b0, b1) == 1.0


def test_kinematic_envelope_prevents_same_target():
    grid = GridMap(5, 5, set())
    robots = [Robot(0, (1, 2), (4, 2), (1, 2)), Robot(1, (2, 2), (0, 2), (2, 2))]
    cfg = KinematicSafetyConfig(enabled=True, footprint_radius=0.35, safety_margin=0.05, sensing_sigma=0.03)
    moves = {0: (2, 2), 1: (2, 2)}
    fixed, diag = validate_kinematic_envelope(robots, moves, grid, cfg)
    assert len(set(fixed.values())) == 2
    assert diag.footprint_conflicts + diag.swept_conflicts > 0

