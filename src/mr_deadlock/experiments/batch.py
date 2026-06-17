# Inha University & RODIX Inc, Anders Hwang
# 파일명: batch.py
# 목적 및 역할:
# 설정 파일의 sweep 조건을 펼쳐 반복 실험을 실행한다. 100/1000 seed 실험을 위해
# seed_range, 병렬 실행, 기존 결과 재사용을 지원한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product
from typing import Any

from tqdm import tqdm

from .runner import run_experiment
from .seeds import expand_seeds


def scenario_overrides_from_sweep(config: dict[str, Any]) -> list[dict[str, Any]]:
    sweep = config.get("sweep")
    if not sweep:
        return [{}]
    keys = list(sweep.keys())
    vals = [sweep[k] for k in keys]
    overrides: list[dict[str, Any]] = []
    for combo in product(*vals):
        d = dict(zip(keys, combo))
        # 설정 파일에서 쓰는 이름을 내부 변수명에 맞춘다.
        if "density" in d:
            d["obstacle_density"] = d["density"]
        overrides.append(d)
    return overrides


def _run_job(args: tuple[dict[str, Any], dict[str, Any], str, int]) -> dict[str, Any]:
    config, override, alg, seed = args
    return run_experiment(config, alg, int(seed), override)


def run_batch(config: dict[str, Any], n_jobs: int | None = None) -> list[dict[str, Any]]:
    exp = config.get("experiment", {})
    algs = exp.get("algorithms", ["clrr_hmpc"])
    seeds = expand_seeds(exp)
    overrides = scenario_overrides_from_sweep(config)
    jobs = [(config, override, alg, int(seed)) for override, alg, seed in product(overrides, algs, seeds)]
    workers = int(n_jobs if n_jobs is not None else exp.get("n_jobs", 1))
    workers = max(1, workers)
    summaries: list[dict[str, Any]] = []
    if workers == 1:
        for job in tqdm(jobs, desc="batch"):
            summaries.append(_run_job(job))
        return summaries

    # 각 실험은 독립적인 seed와 scenario를 사용하므로 프로세스 병렬화가 가능하다.
    # 반환 순서는 CSV 통합 시 재현성을 위해 마지막에 정렬한다.
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_run_job, job) for job in jobs]
        for fut in tqdm(as_completed(futures), total=len(futures), desc=f"batch x{workers}"):
            summaries.append(fut.result())
    sort_keys = ["map_type", "n_robots", "density", "algorithm", "seed"]
    summaries.sort(key=lambda row: tuple(row.get(k, "") for k in sort_keys))
    return summaries

