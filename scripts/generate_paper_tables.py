# Inha University & RODIX Inc, Anders Hwang
# 파일명: generate_paper_tables.py
# 목적 및 역할:
# raw/summary/statistics CSV를 논문 본문·부록용 표 CSV/LaTeX로 변환한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pandas as pd

from mr_deadlock.experiments.aggregate import load_raw, summarize
from mr_deadlock.utils.io import ensure_dir


KEY_METRICS = [
    "success_rate",
    "mean_wait_time",
    "throughput_per_step",
    "fairness_jain_wait",
    "collision_count",
    "footprint_conflicts",
    "swept_conflicts",
    "continuous_min_clearance",
    "avg_step_runtime_ms",
]


def _flat_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = summarize(df)
    return out


def _best_by_metric(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    group_cols = [c for c in ["map_type", "n_robots", "density"] if c in df.columns]
    rows = []
    directions = {
        "success_rate": False,
        "throughput_per_step": False,
        "fairness_jain_wait": False,
        "continuous_min_clearance": False,
        "mean_wait_time": True,
        "collision_count": True,
        "footprint_conflicts": True,
        "swept_conflicts": True,
        "avg_step_runtime_ms": True,
    }
    # directions value means ascending=True if lower is better.
    for keys, g in df.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row_base = {c: v for c, v in zip(group_cols, keys)}
        for metric in KEY_METRICS:
            col = f"{metric}_mean"
            if col not in g.columns:
                continue
            sorted_g = g.sort_values(col, ascending=directions.get(metric, True))
            winner = sorted_g.iloc[0]
            rows.append(
                {
                    **row_base,
                    "metric": metric,
                    "best_algorithm": winner.get("algorithm"),
                    "best_mean": winner.get(col),
                    "n": winner.get(f"{metric}_count"),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="results/raw")
    ap.add_argument("--summary", default=None, help="Optional precomputed summary.csv")
    ap.add_argument("--paired", default=None, help="Optional paired_vs_whca.csv")
    ap.add_argument("--output", default="results/tables")
    args = ap.parse_args()

    out_dir = ensure_dir(args.output)
    if args.summary and Path(args.summary).exists():
        summary = pd.read_csv(args.summary)
        raw = load_raw(args.raw)
    else:
        raw = load_raw(args.raw)
        summary = _flat_summary(raw)

    if summary.empty:
        print("No summary data available.")
        return

    metric_cols = [c for c in summary.columns if any(c.startswith(m + "_") for m in KEY_METRICS)]
    keep = [c for c in ["algorithm", "map_type", "n_robots", "density"] if c in summary.columns] + metric_cols
    main_table = summary[keep].copy()
    main_csv = Path(out_dir) / "main_metrics_table.csv"
    main_tex = Path(out_dir) / "main_metrics_table.tex"
    main_table.to_csv(main_csv, index=False)
    main_table.to_latex(main_tex, index=False, float_format="%.4g")

    winners = _best_by_metric(summary)
    winners_csv = Path(out_dir) / "best_algorithm_by_metric.csv"
    winners_tex = Path(out_dir) / "best_algorithm_by_metric.tex"
    winners.to_csv(winners_csv, index=False)
    if not winners.empty:
        winners.to_latex(winners_tex, index=False, float_format="%.4g")

    paired_path = Path(args.paired) if args.paired else None
    if paired_path and paired_path.exists():
        paired = pd.read_csv(paired_path)
        sig = paired[(paired.get("holm_p", 1.0) <= 0.05) & (paired.get("n_pairs", 0) >= 20)]
        sig_csv = Path(out_dir) / "significant_paired_tests.csv"
        sig_tex = Path(out_dir) / "significant_paired_tests.tex"
        sig.to_csv(sig_csv, index=False)
        if not sig.empty:
            sig.to_latex(sig_tex, index=False, float_format="%.4g")

    manifest = Path(out_dir) / "TABLE_MANIFEST.md"
    manifest.write_text(
        "# Paper table manifest\n\n"
        f"- main metrics: `{main_csv.name}`, `{main_tex.name}`\n"
        f"- best algorithm by metric: `{winners_csv.name}`, `{winners_tex.name}`\n"
        + (f"- significant paired tests generated from `{paired_path}`\n" if paired_path else ""),
        encoding="utf-8",
    )
    print(f"Saved tables to {out_dir}")


if __name__ == "__main__":
    main()

