# Inha University & RODIX Inc, Anders Hwang
# 파일명: run_batch.py
# 목적 및 역할:
# 여러 알고리즘과 여러 시드 조합을 순차 또는 병렬 실행하여 논문용 원자료를 만든다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import argparse
import pandas as pd
from mr_deadlock.utils.io import read_yaml, ensure_dir
from mr_deadlock.experiments.batch import run_batch
from mr_deadlock.experiments.seeds import expand_seeds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--jobs", type=int, default=None, help="Number of worker processes. Default: config experiment.n_jobs or 1")
    ap.add_argument("--resume", action="store_true", help="Reuse existing raw summary CSV files when present")
    args = ap.parse_args()
    cfg = read_yaml(args.config)
    if args.resume:
        cfg.setdefault("runtime", {})["resume_existing"] = True
    seeds = expand_seeds(cfg.get("experiment", {}))
    print(f"Experiment: {cfg.get('experiment', {}).get('name', 'batch')}")
    print(f"Seeds: {len(seeds)} values, first={seeds[0]}, last={seeds[-1]}")
    summaries = run_batch(cfg, n_jobs=args.jobs)
    out = ensure_dir(cfg.get("experiment", {}).get("output_dir", "results/raw"))
    name = cfg.get("experiment", {}).get("name", "batch")
    path = Path(out) / f"{name}_combined.csv"
    pd.DataFrame(summaries).to_csv(path, index=False)
    print(f"Saved combined results to {path}")


if __name__ == "__main__":
    main()

