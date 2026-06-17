# Inha University & RODIX Inc, Anders Hwang
# 파일명: runner.py
# 목적 및 역할:
# 지도 생성부터 로봇 배치, planner 생성, 결과 저장까지 한 실험을 관리한다.
# 100/1000 seed 반복 실험을 위해 동일 seed/동일 scenario 재사용과 resume을 지원한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from pathlib import Path
import csv
import hashlib
from typing import Any

import pandas as pd

from mr_deadlock.core.robot import Robot
from mr_deadlock.core.simulator import Simulator
from mr_deadlock.maps.generator import make_map
from mr_deadlock.maps.tasks import sample_start_goals
from mr_deadlock.planners.factory import make_planner
from mr_deadlock.utils.random import seed_all
from mr_deadlock.utils.io import ensure_dir


def scenario_hash(scenario: dict[str, Any]) -> str:
    text = repr(sorted(scenario.items())).encode("utf-8")
    return hashlib.md5(text).hexdigest()[:8]


def stable_hash(value: Any) -> str:
    return hashlib.md5(repr(value).encode("utf-8")).hexdigest()[:12]


def build_scenario(config: dict[str, Any], scenario_override: dict[str, Any] | None = None) -> dict[str, Any]:
    scenario = dict(config.get("scenario", {}))
    if scenario_override:
        scenario.update(scenario_override)
    if "density" in scenario and "obstacle_density" not in scenario:
        scenario["obstacle_density"] = scenario["density"]
    return scenario


def raw_summary_path(
    config: dict[str, Any], algorithm: str, seed: int, scenario_override: dict[str, Any] | None = None
) -> Path:
    scenario = build_scenario(config, scenario_override)
    out_dir = ensure_dir(config.get("experiment", {}).get("output_dir", "results/raw"))
    exp_name = config.get("experiment", {}).get("name", "experiment")
    sid = scenario_hash({**scenario, "algorithm": algorithm, "seed": seed})
    return Path(out_dir) / f"{exp_name}_{algorithm}_seed{seed}_{sid}.csv"


# 시작점과 목표점 쌍을 Robot 객체로 바꾼다.
def build_robots(pairs):
    robots = []
    for i, (s, g) in enumerate(pairs):
        robots.append(Robot(id=i, start=s, goal=g, pos=s))
    return robots


def _read_existing_summary(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
        if df.empty:
            return None
        return df.iloc[0].to_dict()
    except Exception:
        return None


# 한 번의 실험을 구성하고 결과 CSV까지 저장한다.
def run_experiment(
    config: dict[str, Any],
    algorithm: str,
    seed: int,
    scenario_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scenario = build_scenario(config, scenario_override)
    planner_cfg = dict(config.get("planner", {}))
    runtime_cfg = dict(config.get("runtime", {}))
    raw_path = raw_summary_path(config, algorithm, seed, scenario_override)
    if bool(runtime_cfg.get("resume_existing", False)):
        existing = _read_existing_summary(raw_path)
        if existing is not None:
            return existing

    rng = seed_all(seed)
    width = int(scenario.get("width", 80))
    height = int(scenario.get("height", 80))
    map_type = scenario.get("map_type", "intersection")
    obstacle_density = float(scenario.get("obstacle_density", scenario.get("density", 0.05)))
    n_robots = int(scenario.get("n_robots", 100))
    grid = make_map(map_type, width, height, obstacle_density, rng)
    pairs = sample_start_goals(grid, n_robots, scenario.get("start_goal_mode", "cross_traffic"), rng)
    robots = build_robots(pairs)
    merged_cfg = {**scenario, **planner_cfg, **runtime_cfg}
    planner = make_planner(algorithm, grid, merged_cfg)
    sim = Simulator(grid, robots, planner, merged_cfg)
    result = sim.run(scenario, algorithm, seed)
    result.summary.update(
        {
            "map_hash": stable_hash(sorted(grid.obstacles)),
            "obstacle_hash": stable_hash(sorted(grid.obstacles)),
            "start_goal_hash": stable_hash(pairs),
            "robot_order_hash": stable_hash([(r.id, r.start, r.goal) for r in robots]),
            "scenario_instance_hash": stable_hash(
                {
                    "scenario": scenario,
                    "map_hash": stable_hash(sorted(grid.obstacles)),
                    "start_goal_hash": stable_hash(pairs),
                }
            ),
        }
    )
    write_summary_csv(raw_path, result.summary)
    if runtime_cfg.get("save_step_log", False):
        step_path = raw_path.with_name(raw_path.stem + "_steps.csv")
        write_steps_csv(step_path, result.step_records)
    return result.summary


def write_summary_csv(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)


def write_steps_csv(path: Path, records) -> None:
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        fields = list(records[0].__dict__.keys())
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in records:
            writer.writerow(r.__dict__)

