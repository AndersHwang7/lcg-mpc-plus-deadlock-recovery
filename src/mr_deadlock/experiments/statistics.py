# Inha University & RODIX Inc, Anders Hwang
# 파일명: statistics.py
# 목적 및 역할:
# 논문용 paired 통계 비교를 계산한다. 동일 seed/start-goal set 조건에서 WHCA 등
# baseline 대비 제안 알고리즘의 평균 차이, 상대 변화, Wilcoxon p, Holm 보정,
# Vargha-Delaney A12, Cliff's delta, bootstrap CI를 제공한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

try:  # pragma: no cover - scipy availability may vary.
    from scipy.stats import wilcoxon
except Exception:  # pragma: no cover
    wilcoxon = None


DEFAULT_METRICS = [
    "success_rate",
    "mean_wait_time",
    "max_wait_time",
    "mean_travel_time",
    "makespan",
    "throughput_per_step",
    "fairness_jain_wait",
    "fixed_conflicts",
    "collision_count",
    "avg_step_runtime_ms",
    "p95_step_runtime_ms",
    "p99_step_runtime_ms",
    "max_step_runtime_ms",
    "raw_vertex_conflicts",
    "raw_edge_swap_conflicts",
    "final_vertex_conflicts",
    "final_edge_swap_conflicts",
    "supervisor_interventions",
    "supervisor_interventions_per_step",
    "supervisor_interventions_per_robot",
    "raw_conflicts_per_step",
    "final_conflicts_per_step",
    "planner_level_repairs",
    "footprint_conflicts",
    "swept_conflicts",
    "obstacle_envelope_conflicts",
    "acceleration_clips",
    "speed_clips",
    "sensing_risk_events",
    "continuous_min_clearance",
    "exact_game_count",
    "partitioned_exact_count",
    "greedy_fallback_count",
    "cbf_filter_calls",
    "stagnation_repair_calls",
    "robust_nominal_repairs",
    "timeout_count",
    "timeout_fallback_count",
    "capped_game_count",
    "capped_mpc_count",
    "capped_cbf_count",
    "game_profiles_evaluated_per_step",
    "mpc_refinements_per_step",
    "cbf_calls_per_step",
    "planner_plan_time_ms",
    "safety_supervisor_time_ms",
    "dynamics_envelope_time_ms",
    "reservation_table_time_ms",
    "astar_or_bfs_time_ms",
    "local_game_time_ms",
    "mpc_qp_refinement_time_ms",
    "cbf_robust_filter_time_ms",
    "planner_native_conflict_reduction_rate",
]


@dataclass(frozen=True)
class MetricDirection:
    higher_is_better: bool


METRIC_DIRECTIONS = {
    "success_rate": MetricDirection(True),
    "throughput_per_step": MetricDirection(True),
    "throughput_wallclock": MetricDirection(True),
    "fairness_jain_wait": MetricDirection(True),
    "mean_wait_time": MetricDirection(False),
    "max_wait_time": MetricDirection(False),
    "mean_travel_time": MetricDirection(False),
    "makespan": MetricDirection(False),
    "deadlock_rate_per_step": MetricDirection(False),
    "persistent_deadlock_steps": MetricDirection(False),
    "fixed_conflicts": MetricDirection(False),
    "collision_count": MetricDirection(False),
    "avg_step_runtime_ms": MetricDirection(False),
    "p95_step_runtime_ms": MetricDirection(False),
    "p99_step_runtime_ms": MetricDirection(False),
    "max_step_runtime_ms": MetricDirection(False),
    "raw_vertex_conflicts": MetricDirection(False),
    "raw_edge_swap_conflicts": MetricDirection(False),
    "final_vertex_conflicts": MetricDirection(False),
    "final_edge_swap_conflicts": MetricDirection(False),
    "supervisor_interventions": MetricDirection(False),
    "supervisor_interventions_per_step": MetricDirection(False),
    "supervisor_interventions_per_robot": MetricDirection(False),
    "raw_conflicts_per_step": MetricDirection(False),
    "final_conflicts_per_step": MetricDirection(False),
    "planner_level_repairs": MetricDirection(False),
    "footprint_conflicts": MetricDirection(False),
    "swept_conflicts": MetricDirection(False),
    "obstacle_envelope_conflicts": MetricDirection(False),
    "acceleration_clips": MetricDirection(False),
    "speed_clips": MetricDirection(False),
    "sensing_risk_events": MetricDirection(False),
    "continuous_min_clearance": MetricDirection(True),
    "exact_game_count": MetricDirection(False),
    "partitioned_exact_count": MetricDirection(False),
    "greedy_fallback_count": MetricDirection(False),
    "cbf_filter_calls": MetricDirection(False),
    "stagnation_repair_calls": MetricDirection(False),
    "robust_nominal_repairs": MetricDirection(False),
    "timeout_count": MetricDirection(False),
    "timeout_fallback_count": MetricDirection(False),
    "capped_game_count": MetricDirection(False),
    "capped_mpc_count": MetricDirection(False),
    "capped_cbf_count": MetricDirection(False),
    "game_profiles_evaluated_per_step": MetricDirection(False),
    "mpc_refinements_per_step": MetricDirection(False),
    "cbf_calls_per_step": MetricDirection(False),
    "planner_plan_time_ms": MetricDirection(False),
    "safety_supervisor_time_ms": MetricDirection(False),
    "dynamics_envelope_time_ms": MetricDirection(False),
    "reservation_table_time_ms": MetricDirection(False),
    "astar_or_bfs_time_ms": MetricDirection(False),
    "local_game_time_ms": MetricDirection(False),
    "mpc_qp_refinement_time_ms": MetricDirection(False),
    "cbf_robust_filter_time_ms": MetricDirection(False),
    "planner_native_conflict_reduction_rate": MetricDirection(True),
}


def _holm_adjust(p_values: list[float]) -> list[float]:
    n = len(p_values)
    order = np.argsort([1.0 if np.isnan(p) else p for p in p_values])
    adjusted = [float("nan")] * n
    running_max = 0.0
    for rank, idx in enumerate(order):
        p = p_values[idx]
        if np.isnan(p):
            adjusted[idx] = float("nan")
            continue
        adj = min(1.0, (n - rank) * p)
        running_max = max(running_max, adj)
        adjusted[idx] = running_max
    return adjusted


def _a12_and_cliff(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    if len(x) == 0 or len(y) == 0:
        return float("nan"), float("nan")
    greater = 0
    lesser = 0
    equal = 0
    for xv in x:
        greater += int(np.sum(xv > y))
        lesser += int(np.sum(xv < y))
        equal += int(np.sum(xv == y))
    total = len(x) * len(y)
    a12 = (greater + 0.5 * equal) / total
    cliff = (greater - lesser) / total
    return float(a12), float(cliff)


def _bootstrap_mean_diff_ci(diff: np.ndarray, n_boot: int = 2000, seed: int = 12345) -> tuple[float, float]:
    diff = diff[np.isfinite(diff)]
    if len(diff) == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(diff), size=(n_boot, len(diff)))
    means = diff[idx].mean(axis=1)
    lo, hi = np.quantile(means, [0.025, 0.975])
    return float(lo), float(hi)


def paired_vs_baseline(
    df: pd.DataFrame,
    baseline: str = "whca",
    metrics: Iterable[str] | None = None,
    group_cols: Iterable[str] = ("map_type", "n_robots", "density"),
) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    metrics = [m for m in (metrics or DEFAULT_METRICS) if m in df.columns]
    group_cols = [c for c in group_cols if c in df.columns]
    required = set(group_cols) | {"algorithm", "seed"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns for paired statistics: {sorted(missing)}")
    out: list[dict] = []
    for group_key, g in df.groupby(group_cols, dropna=False):
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        base = g[g["algorithm"] == baseline]
        if base.empty:
            continue
        for alg in sorted(a for a in g["algorithm"].dropna().unique() if a != baseline):
            cur = g[g["algorithm"] == alg]
            merged = cur.merge(base, on=[*group_cols, "seed"], suffixes=("_alg", "_base"))
            if merged.empty:
                continue
            for metric in metrics:
                a = pd.to_numeric(merged[f"{metric}_alg"], errors="coerce").to_numpy(dtype=float)
                b = pd.to_numeric(merged[f"{metric}_base"], errors="coerce").to_numpy(dtype=float)
                mask = np.isfinite(a) & np.isfinite(b)
                a = a[mask]
                b = b[mask]
                if len(a) == 0:
                    continue
                diff = a - b
                mean_alg = float(np.mean(a))
                mean_base = float(np.mean(b))
                rel = float((mean_alg - mean_base) / abs(mean_base) * 100.0) if abs(mean_base) > 1e-12 else float("nan")
                p = float("nan")
                if wilcoxon is not None and len(diff) >= 2 and np.any(np.abs(diff) > 1e-12):
                    try:
                        p = float(wilcoxon(a, b, zero_method="wilcox").pvalue)
                    except Exception:
                        p = float("nan")
                a12, cliff = _a12_and_cliff(a, b)
                ci_lo, ci_hi = _bootstrap_mean_diff_ci(diff)
                direction = METRIC_DIRECTIONS.get(metric, MetricDirection(True)).higher_is_better
                improvement = diff if direction else -diff
                win_rate = float(np.mean(improvement > 0))
                loss_rate = float(np.mean(improvement < 0))
                tie_rate = float(np.mean(np.abs(improvement) <= 1e-12))
                row = {col: val for col, val in zip(group_cols, group_key)}
                row.update(
                    {
                        "algorithm": alg,
                        "baseline": baseline,
                        "metric": metric,
                        "n_pairs": int(len(a)),
                        "mean_algorithm": mean_alg,
                        "mean_baseline": mean_base,
                        "mean_diff": float(np.mean(diff)),
                        "relative_change_pct": rel,
                        "win_rate": win_rate,
                        "loss_rate": loss_rate,
                        "tie_rate": tie_rate,
                        "wilcoxon_p": p,
                        "holm_p": float("nan"),
                        "a12_algorithm_gt_baseline": a12,
                        "cliffs_delta": cliff,
                        "bootstrap_diff_ci95_low": ci_lo,
                        "bootstrap_diff_ci95_high": ci_hi,
                    }
                )
                out.append(row)
    result = pd.DataFrame(out)
    if result.empty:
        return result
    # 각 scenario group 안에서 여러 알고리즘/metric 비교에 대해 Holm 보정을 수행한다.
    adj_values = []
    for _, sub in result.groupby(group_cols, dropna=False):
        adjusted = _holm_adjust(sub["wilcoxon_p"].to_list())
        adj_values.extend(zip(sub.index, adjusted))
    for idx, adj in adj_values:
        result.loc[idx, "holm_p"] = adj
    return result.sort_values([*group_cols, "metric", "algorithm"]).reset_index(drop=True)

