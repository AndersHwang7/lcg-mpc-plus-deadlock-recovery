# Inha University & RODIX Inc, Anders Hwang
# 파일명: run_single.py
# 목적 및 역할:
# 단일 설정 파일을 읽어 한 번의 실험을 실행하고 주요 결과를 터미널에 출력한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


import argparse
from mr_deadlock.utils.io import read_yaml
from mr_deadlock.experiments.runner import run_experiment


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--algorithm", default=None)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()
    cfg = read_yaml(args.config)
    alg = args.algorithm or cfg.get("experiment", {}).get("algorithms", ["clrr_hmpc"])[0]
    seed = args.seed if args.seed is not None else cfg.get("experiment", {}).get("seeds", [0])[0]
    summary = run_experiment(cfg, alg, int(seed))
    for k, v in summary.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()

