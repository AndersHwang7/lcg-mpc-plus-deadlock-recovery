# Inha University & RODIX Inc, Anders Hwang
# 파일명: statistical_compare.py
# 목적 및 역할:
# raw 결과 CSV에서 paired 통계 검정, Holm 보정, 효과크기, bootstrap CI를 계산한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import argparse
from mr_deadlock.experiments.aggregate import load_raw
from mr_deadlock.experiments.statistics import DEFAULT_METRICS, paired_vs_baseline
from mr_deadlock.utils.io import ensure_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="results/raw")
    ap.add_argument("--output", default="results/summary")
    ap.add_argument("--baseline", default="whca")
    ap.add_argument("--metrics", nargs="*", default=None)
    args = ap.parse_args()
    df = load_raw(args.input)
    if df.empty:
        print("No raw CSV files found.")
        return
    metrics = args.metrics or DEFAULT_METRICS
    out = paired_vs_baseline(df, baseline=args.baseline, metrics=metrics)
    out_dir = ensure_dir(args.output)
    path = Path(out_dir) / f"paired_vs_{args.baseline}.csv"
    out.to_csv(path, index=False)
    print(f"Saved {path}")


if __name__ == "__main__":
    main()

