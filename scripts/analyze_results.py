# Inha University & RODIX Inc, Anders Hwang
# 파일명: analyze_results.py
# 목적 및 역할:
# 원자료 CSV를 모아 평균과 표준편차를 계산하고 요약 표를 저장한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


import argparse
from pathlib import Path
from mr_deadlock.utils.io import ensure_dir
from mr_deadlock.experiments.aggregate import load_raw, summarize


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="results/raw")
    ap.add_argument("--output", default="results/summary")
    args = ap.parse_args()
    out = ensure_dir(args.output)
    df = load_raw(args.input)
    if df.empty:
        print("No raw CSV files found.")
        return
    summary = summarize(df)
    raw_path = Path(out) / "raw_combined.csv"
    sum_path = Path(out) / "summary.csv"
    df.to_csv(raw_path, index=False)
    summary.to_csv(sum_path, index=False)
    print(f"Saved {raw_path}")
    print(f"Saved {sum_path}")


if __name__ == "__main__":
    main()

