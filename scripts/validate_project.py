# Inha University & RODIX Inc, Anders Hwang
# 파일명: validate_project.py
# 목적 및 역할:
# 수식과 코드가 맞는지 확인하기 위한 잠재게임 검증과 짧은 실행 검사를 수행한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import argparse
import json
from mr_deadlock.core.grid import GridMap
from mr_deadlock.core.robot import Robot
from mr_deadlock.game.potential_game import PotentialGameSelector
from mr_deadlock.utils.io import read_yaml
from mr_deadlock.experiments.runner import run_experiment


# 작은 충돌 상황을 만들어 potential game 수식이 코드와 맞는지 본다.
def validate_exact_potential() -> bool:
    grid = GridMap(7, 7, set())
    robots = [
        Robot(0, (1, 3), (5, 3), (1, 3), path=[(1, 3), (2, 3), (3, 3), (4, 3), (5, 3)]),
        Robot(1, (3, 3), (0, 3), (3, 3), path=[(3, 3), (2, 3), (1, 3), (0, 3)]),
        Robot(2, (2, 2), (2, 5), (2, 2), path=[(2, 2), (2, 3), (2, 4), (2, 5)]),
    ]
    return PotentialGameSelector(grid).verify_exact_potential(robots, {r.pos for r in robots})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/quick_100.yaml")
    ap.add_argument("--algorithm", default="clrr_hmpc")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-robots", type=int, default=100)
    ap.add_argument("--max-steps", type=int, default=500)
    args = ap.parse_args()

    cfg = read_yaml(args.config)
    override = {"n_robots": args.n_robots, "max_steps": args.max_steps}
    exact_ok = validate_exact_potential()
    summary = run_experiment(cfg, args.algorithm, args.seed, override)
    mpc_ok = True
    if args.algorithm == "clrr_hmpc":
        mpc_ok = summary.get("mpc_refinements", 0) > 0
    report = {
        "exact_potential_check": exact_ok,
        "smoke_summary": summary,
        "collision_free_check": summary.get("collision_count", 1) == 0,
        "mpc_activation_check": mpc_ok,
        "passed": bool(exact_ok and summary.get("collision_count", 1) == 0 and mpc_ok),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

