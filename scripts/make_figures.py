# Inha University & RODIX Inc, Anders Hwang
# 파일명: make_figures.py
# 목적 및 역할:
# 요약 CSV를 읽어 논문에 사용할 성능 그래프를 생성한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


import argparse
from mr_deadlock.visualization.plot_results import make_figures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="results/summary/summary.csv")
    ap.add_argument("--output", default="results/figures")
    args = ap.parse_args()
    make_figures(args.input, args.output)
    print(f"Saved figures to {args.output}")


if __name__ == "__main__":
    main()

