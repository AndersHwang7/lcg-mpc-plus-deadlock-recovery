# Inha University & RODIX Inc, Anders Hwang
# 파일명: seeds.py
# 목적 및 역할:
# 100-seed, 1000-seed 실험을 설정 파일에서 간결하고 재현 가능하게 지정한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def expand_seeds(experiment_cfg: dict[str, Any] | None) -> list[int]:
    """Return an explicit deterministic seed list from experiment config.

    Supported forms:
      seeds: [0, 1, 2]
      seed_range: {start: 0, stop: 99}
      seed_range: {start: 0, count: 100}
      seed_range: {start: 0, stop: 999, step: 1}

    The stop value is inclusive because seed sweeps are usually described as
    "0-99" or "0-999" in experiment notes.
    """
    cfg = experiment_cfg or {}
    if "seeds" in cfg and cfg["seeds"] is not None:
        seeds = cfg["seeds"]
        if isinstance(seeds, int):
            return [int(seeds)]
        if not isinstance(seeds, Iterable) or isinstance(seeds, (str, bytes)):
            raise TypeError("experiment.seeds must be an integer or a list of integers")
        out = [int(s) for s in seeds]
        if not out:
            raise ValueError("experiment.seeds must not be empty")
        return out

    seed_range = cfg.get("seed_range")
    if seed_range is None:
        return [0]
    if not isinstance(seed_range, dict):
        raise TypeError("experiment.seed_range must be a dictionary")

    start = int(seed_range.get("start", 0))
    step = int(seed_range.get("step", 1))
    if step <= 0:
        raise ValueError("experiment.seed_range.step must be positive")

    if "count" in seed_range and seed_range["count"] is not None:
        count = int(seed_range["count"])
        if count <= 0:
            raise ValueError("experiment.seed_range.count must be positive")
        return [start + i * step for i in range(count)]

    stop = int(seed_range.get("stop", start))
    if stop < start:
        raise ValueError("experiment.seed_range.stop must be >= start")
    return list(range(start, stop + 1, step))

