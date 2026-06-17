# Inha University & RODIX Inc, Anders Hwang
# 파일명: plot_results.py
# 목적 및 역할:
# 요약 결과를 읽어 논문용 성능 그래프를 저장한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


def _normalize_summary(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    keep = []
    for c in df.columns:
        if c.endswith("_mean"):
            rename[c] = c[:-5]
            keep.append(c)
        elif not c.endswith(("_std", "_count")):
            keep.append(c)
    if rename:
        df = df[keep].rename(columns=rename)
    return df


def _plot_metric(df: pd.DataFrame, metric: str, out_dir: Path) -> None:
    if metric not in df.columns or "n_robots" not in df.columns:
        return
    fig = plt.figure(figsize=(7, 4.5))
    for alg, sub in df.groupby("algorithm"):
        sub = sub.sort_values("n_robots")
        y = pd.to_numeric(sub[metric], errors="coerce")
        plt.plot(sub["n_robots"], y, marker="o", label=str(alg))
    plt.xlabel("Number of robots")
    plt.ylabel(metric.replace("_", " "))
    plt.grid(True, alpha=0.3)
    plt.legend(fontsize=8)
    plt.tight_layout()
    fig.savefig(out_dir / f"{metric}.png", dpi=300)
    fig.savefig(out_dir / f"{metric}.pdf")
    plt.close(fig)


# 논문 그림으로 쓸 주요 지표를 한 번에 저장한다.
def make_figures(summary_csv: str | Path, output_dir: str | Path) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    df = _normalize_summary(pd.read_csv(summary_csv))
    for metric in [
        "success_rate",
        "deadlock_rate_per_step",
        "persistent_deadlock_steps",
        "throughput_per_step",
        "mean_wait_time",
        "mean_travel_time",
        "avg_step_runtime_ms",
        "p95_step_runtime_ms",
        "retreat_actions",
        "fairness_jain_wait",
        "average_path_stretch",
        "collision_count",
        "footprint_conflicts",
        "swept_conflicts",
        "acceleration_clips",
        "sensing_risk_events",
        "continuous_min_clearance",
    ]:
        _plot_metric(df, metric, out)

