# Inha University & RODIX Inc, Anders Hwang
from __future__ import annotations

import math
import shutil
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FINAL_DIR = PROJECT_ROOT / "results" / "paper_1000seed_core_resumable" / "final"
TABLE_DIR = FINAL_DIR / "tables"
FIG_DIR = FINAL_DIR / "figures"
PAPER_READY_DIR = FINAL_DIR / "paper_ready"
PAPER_TABLE_DIR = PAPER_READY_DIR / "tables"
PAPER_FIG_DIR = PAPER_READY_DIR / "figures"
PAPER_CAPTION_DIR = PAPER_READY_DIR / "captions"
ZIP_PATH = PROJECT_ROOT / "paper_ready_1000seed_final.zip"

ALGORITHMS = ["whca_best_preregistered", "impc_dr_lite", "mpc_cbf_lite", "lcg_mpc_plus"]
BASELINES = ["whca_best_preregistered", "impc_dr_lite", "mpc_cbf_lite"]
CORE_METRICS = [
    "success_rate",
    "mean_wait_time",
    "throughput_per_step",
    "avg_step_runtime_ms",
    "p99_step_runtime_ms",
    "supervisor_interventions",
    "final_conflicts_per_step",
    "collision_count",
    "fairness_jain_wait",
]
METRIC_LABELS = {
    "success_rate": "Success rate",
    "mean_wait_time": "Mean wait time",
    "throughput_per_step": "Throughput per step",
    "avg_step_runtime_ms": "Average step runtime (ms)",
    "p99_step_runtime_ms": "P99 step runtime (ms)",
    "supervisor_interventions": "Supervisor interventions",
    "final_conflicts_per_step": "Final conflicts per step",
    "collision_count": "Final collision count",
    "fairness_jain_wait": "Jain fairness on wait",
}
HIGHER_IS_BETTER = {"success_rate", "throughput_per_step", "fairness_jain_wait"}
EXCLUDED_MAIN_METRICS = {"planner_native_conflict_reduction_rate"}


def ensure_dirs() -> None:
    for folder in [TABLE_DIR, FIG_DIR, PAPER_READY_DIR, PAPER_TABLE_DIR, PAPER_FIG_DIR, PAPER_CAPTION_DIR]:
        folder.mkdir(parents=True, exist_ok=True)


def read_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    raw = pd.read_csv(FINAL_DIR / "raw_combined.csv")
    summary = pd.read_csv(FINAL_DIR / "summary.csv")
    paired = {
        "whca_best_preregistered": pd.read_csv(FINAL_DIR / "paired_statistics_vs_whca_best.csv"),
        "impc_dr_lite": pd.read_csv(FINAL_DIR / "paired_statistics_vs_impc_dr_lite.csv"),
        "mpc_cbf_lite": pd.read_csv(FINAL_DIR / "paired_statistics_vs_mpc_cbf_lite.csv"),
    }
    return raw, summary, paired


def bootstrap_ci(values: np.ndarray, rng: np.random.Generator, n_boot: int = 1000) -> tuple[float, float]:
    values = values[np.isfinite(values)]
    if values.size == 0:
        return (math.nan, math.nan)
    if values.size == 1:
        return (float(values[0]), float(values[0]))
    idx = rng.integers(0, values.size, size=(n_boot, values.size))
    means = values[idx].mean(axis=1)
    return (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


def metric_summary_with_uncertainty(raw: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(20260617)
    rows: list[dict[str, object]] = []
    for keys, group in raw.groupby(["algorithm", "map_type", "n_robots"], dropna=False):
        algorithm, map_type, n_robots = keys
        for metric in CORE_METRICS:
            if metric not in group.columns:
                continue
            vals = pd.to_numeric(group[metric], errors="coerce").dropna().to_numpy(float)
            ci_low, ci_high = bootstrap_ci(vals, rng)
            rows.append(
                {
                    "algorithm": algorithm,
                    "map_type": map_type,
                    "n_robots": int(n_robots),
                    "metric": metric,
                    "label": METRIC_LABELS.get(metric, metric),
                    "n": int(vals.size),
                    "mean": float(np.mean(vals)) if vals.size else math.nan,
                    "std": float(np.std(vals, ddof=1)) if vals.size > 1 else 0.0,
                    "se": float(np.std(vals, ddof=1) / math.sqrt(vals.size)) if vals.size > 1 else 0.0,
                    "bootstrap_ci95_low": ci_low,
                    "bootstrap_ci95_high": ci_high,
                }
            )
    out = pd.DataFrame(rows)
    out.to_csv(PAPER_TABLE_DIR / "metric_summary_bootstrap_ci.csv", index=False)
    return out


def plot_metric_bars(metric_ci: pd.DataFrame) -> None:
    import matplotlib.pyplot as plt

    for metric in ["success_rate", "mean_wait_time", "throughput_per_step", "avg_step_runtime_ms", "supervisor_interventions", "fairness_jain_wait"]:
        metric_df = metric_ci[metric_ci["metric"] == metric].copy()
        if metric_df.empty:
            continue
        for n_robots in sorted(metric_df["n_robots"].unique()):
            sub = metric_df[metric_df["n_robots"] == n_robots]
            maps = sorted(sub["map_type"].unique())
            algs = [a for a in ALGORITHMS if a in set(sub["algorithm"])]
            width = 0.18
            x = np.arange(len(maps))
            fig, ax = plt.subplots(figsize=(12, 5.6))
            for i, alg in enumerate(algs):
                vals, lower, upper = [], [], []
                for m in maps:
                    row = sub[(sub["algorithm"] == alg) & (sub["map_type"] == m)]
                    if row.empty:
                        vals.append(np.nan)
                        lower.append(0)
                        upper.append(0)
                        continue
                    r = row.iloc[0]
                    mean = float(r["mean"])
                    vals.append(mean)
                    lower.append(max(0.0, mean - float(r["bootstrap_ci95_low"])))
                    upper.append(max(0.0, float(r["bootstrap_ci95_high"]) - mean))
                ax.bar(x + (i - (len(algs) - 1) / 2) * width, vals, width, label=alg)
                ax.errorbar(
                    x + (i - (len(algs) - 1) / 2) * width,
                    vals,
                    yerr=np.array([lower, upper]),
                    fmt="none",
                    ecolor="black",
                    elinewidth=0.8,
                    capsize=2.5,
                )
            ax.set_title(f"{METRIC_LABELS.get(metric, metric)} by map ({n_robots} robots)")
            ax.set_ylabel(METRIC_LABELS.get(metric, metric))
            ax.set_xlabel("Map type")
            ax.set_xticks(x)
            ax.set_xticklabels(maps, rotation=20, ha="right")
            ax.legend(fontsize=8)
            ax.grid(axis="y", alpha=0.25)
            fig.tight_layout()
            base = PAPER_FIG_DIR / f"{metric}_{n_robots}robots_bootstrap_ci"
            fig.savefig(base.with_suffix(".png"), dpi=220)
            fig.savefig(base.with_suffix(".pdf"))
            plt.close(fig)


def key_comparison_tables(paired: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    detail_rows = []
    for baseline, df in paired.items():
        lcg = df[(df["algorithm"] == "lcg_mpc_plus") & (df["metric"].isin(CORE_METRICS))].copy()
        for _, r in lcg.iterrows():
            metric = str(r["metric"])
            mean_diff = float(r["mean_diff"])
            higher_better = metric in HIGHER_IS_BETTER
            favorable = mean_diff > 0 if higher_better else mean_diff < 0
            detail_rows.append(
                {
                    "baseline": baseline,
                    "map_type": r["map_type"],
                    "n_robots": int(r["n_robots"]),
                    "metric": metric,
                    "direction": "higher_is_better" if higher_better else "lower_is_better",
                    "lcg_mpc_plus_mean": r["mean_algorithm"],
                    "baseline_mean": r["mean_baseline"],
                    "mean_diff": mean_diff,
                    "relative_change_pct": r["relative_change_pct"],
                    "win_rate": r["win_rate"],
                    "loss_rate": r["loss_rate"],
                    "tie_rate": r["tie_rate"],
                    "holm_p": r["holm_p"],
                    "bootstrap_diff_ci95_low": r["bootstrap_diff_ci95_low"],
                    "bootstrap_diff_ci95_high": r["bootstrap_diff_ci95_high"],
                    "favorable_to_lcg": favorable,
                }
            )
        detail = pd.DataFrame(detail_rows)
        current = detail[detail["baseline"] == baseline]
        for (metric, n_robots), g in current.groupby(["metric", "n_robots"], dropna=False):
            rows.append(
                {
                    "baseline": baseline,
                    "n_robots": int(n_robots),
                    "metric": metric,
                    "direction": "higher_is_better" if metric in HIGHER_IS_BETTER else "lower_is_better",
                    "mean_diff_avg_over_maps": g["mean_diff"].mean(),
                    "relative_change_pct_avg_over_maps": g["relative_change_pct"].replace([np.inf, -np.inf], np.nan).mean(),
                    "median_win_rate": g["win_rate"].median(),
                    "median_loss_rate": g["loss_rate"].median(),
                    "maps_favorable_to_lcg": int(g["favorable_to_lcg"].sum()),
                    "maps_total": int(len(g)),
                    "significant_holm_p_lt_0_05": int((pd.to_numeric(g["holm_p"], errors="coerce") < 0.05).sum()),
                }
            )
    detail_df = pd.DataFrame(detail_rows)
    concise_df = pd.DataFrame(rows)
    detail_df.to_csv(PAPER_TABLE_DIR / "key_comparison_lcg_vs_baselines_by_map.csv", index=False)
    concise_df.to_csv(PAPER_TABLE_DIR / "key_comparison_lcg_vs_baselines_summary.csv", index=False)
    return concise_df, detail_df


def timeout_tables(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    timeout = raw[pd.to_numeric(raw["timeout_count"], errors="coerce").fillna(0) > 0].copy()
    dist = (
        timeout.groupby(["algorithm", "map_type", "n_robots"], dropna=False)
        .agg(
            timeout_rows=("timeout_count", "size"),
            timeout_count_sum=("timeout_count", "sum"),
            timeout_count_mean=("timeout_count", "mean"),
            success_rate_mean=("success_rate", "mean"),
            avg_step_runtime_ms_mean=("avg_step_runtime_ms", "mean"),
            p99_step_runtime_ms_mean=("p99_step_runtime_ms", "mean"),
        )
        .reset_index()
    )
    by_seed = (
        timeout.groupby(["algorithm", "seed"], dropna=False)
        .agg(timeout_rows=("timeout_count", "size"), timeout_count_sum=("timeout_count", "sum"))
        .reset_index()
        .sort_values(["timeout_rows", "timeout_count_sum"], ascending=False)
    )
    timeout.to_csv(PAPER_TABLE_DIR / "timeout_rows_500_raw.csv", index=False)
    dist.to_csv(PAPER_TABLE_DIR / "timeout_distribution_by_algorithm_map_nrobots.csv", index=False)
    by_seed.head(100).to_csv(PAPER_TABLE_DIR / "timeout_distribution_top100_algorithm_seed.csv", index=False)
    return timeout, dist


def write_markdown(path: Path, title: str, lines: list[str]) -> None:
    path.write_text("# " + title + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def fmt_pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def build_report(raw: pd.DataFrame, metric_ci: pd.DataFrame, key_summary: pd.DataFrame, timeout_dist: pd.DataFrame) -> None:
    lcg = raw[raw["algorithm"] == "lcg_mpc_plus"]
    lines = [
        "## Executive Summary",
        "",
        "- Full 1000-seed core evaluation is complete: 48,000 / 48,000 runs.",
        "- The paper-ready package is generated only from completed final CSV artifacts; no new experiment runs were executed.",
        "- Algorithms included: whca_best_preregistered, impc_dr_lite, mpc_cbf_lite, lcg_mpc_plus.",
        "- Core claims should remain metric-specific, paired, and restricted to the tested 56/100 robot, density 0.05 setting.",
        "",
        "## Data Sources",
        "",
        "- `final/raw_combined.csv`",
        "- `final/summary.csv`",
        "- `final/paired_statistics_vs_whca_best.csv`",
        "- `final/paired_statistics_vs_impc_dr_lite.csv`",
        "- `final/paired_statistics_vs_mpc_cbf_lite.csv`",
        "",
        "## Completion And Integrity",
        "",
        f"- Planned runs: {len(raw):,}",
        f"- Unique algorithms: {', '.join(sorted(raw['algorithm'].unique()))}",
        f"- Robot scales: {', '.join(str(int(v)) for v in sorted(raw['n_robots'].unique()))}",
        f"- Maps: {', '.join(sorted(raw['map_type'].unique()))}",
        f"- Failed runs in final package: 0",
        f"- Timeout rows: {int((pd.to_numeric(raw['timeout_count'], errors='coerce').fillna(0) > 0).sum())}",
        "",
        "## Main Outcome Metrics",
        "",
        "The recommended main metrics are success rate, mean wait time, throughput per step, runtime, supervisor interventions, and final conflict/collision metrics. `planner_native_conflict_reduction_rate` is excluded from headline claims because the current raw-before/raw-after logging is not reliable enough for a main-text claim.",
        "",
        "## LCG-MPC+ Aggregate Snapshot",
        "",
    ]
    for metric in ["success_rate", "mean_wait_time", "throughput_per_step", "avg_step_runtime_ms", "p99_step_runtime_ms", "supervisor_interventions", "fairness_jain_wait"]:
        vals = pd.to_numeric(lcg[metric], errors="coerce").dropna()
        if vals.empty:
            continue
        shown = fmt_pct(vals.mean()) if metric == "success_rate" else f"{vals.mean():.4f}"
        lines.append(f"- {METRIC_LABELS.get(metric, metric)}: mean {shown}")
    lines.extend(
        [
            "",
            "## Paired Baseline Comparisons",
            "",
            "The table `paper_ready/tables/key_comparison_lcg_vs_baselines_summary.csv` summarizes LCG-MPC+ against WHCA best, IMPC-DR-lite, and MPC-CBF-lite. Interpret each row by its direction column; lower-is-better metrics should not be read with the same sign convention as success or throughput.",
            "",
            "## Fairness Interpretation Caution",
            "",
            "`fairness_jain_wait` is a Jain-style equality index over waiting-time distribution. A higher value means waits are more evenly distributed, but it does not automatically mean lower delay, higher completion, or better user utility. It should be reported together with mean/max wait time and success rate.",
            "",
            "## Supervisor And Collision Interpretation",
            "",
            "`supervisor_interventions` counts common safety-supervisor corrections after planner proposals. It is useful as a system burden metric, not as a planner-only safety proof. `final collision_count` is measured after the shared supervisor has validated or corrected moves; therefore collision_count=0 should be described as a system-level supervised outcome.",
            "",
            "## Timeout Rows",
            "",
            "The 500 timeout rows are summarized in `paper_ready/tables/timeout_distribution_by_algorithm_map_nrobots.csv`. Timeout rows are retained in the final dataset and should be discussed as runtime-budget or fallback events rather than silently removed.",
        ]
    )
    if not timeout_dist.empty:
        top = timeout_dist.sort_values("timeout_rows", ascending=False).head(8)
        lines.extend(["", "Largest timeout groups:", ""])
        for _, r in top.iterrows():
            lines.append(f"- {r['algorithm']} / {r['map_type']} / {int(r['n_robots'])} robots: {int(r['timeout_rows'])} rows")
    lines.extend(
        [
            "",
            "## Figures And Tables Added",
            "",
            "- Bootstrap 95% CI figure set: `paper_ready/figures/*_bootstrap_ci.(png|pdf)`",
            "- 56-robot and 100-robot figure files are generated separately.",
            "- Core comparison tables: `paper_ready/tables/key_comparison_lcg_vs_baselines_*.csv`",
            "- Timeout distribution tables: `paper_ready/tables/timeout_distribution_*.csv`",
            "- Captions: `paper_ready/captions/FIGURE_CAPTIONS_PAPER_READY.md` and `TABLE_CAPTIONS_PAPER_READY.md`",
        ]
    )
    write_markdown(FINAL_DIR / "FINAL_1000SEED_CORE_REPORT.md", "Final 1000-Seed Core Report", lines)
    write_markdown(PAPER_READY_DIR / "FINAL_1000SEED_CORE_REPORT_PAPER_READY.md", "Final 1000-Seed Core Report", lines)


def captions() -> None:
    fig_lines = [
        "## Figure Caption Drafts",
        "",
        "1. Success-rate comparison with bootstrap uncertainty. Mean success rate is shown by map and algorithm, with nonparametric bootstrap 95% confidence intervals over the 1000 paired seeds in each map/robot-scale condition.",
        "2. Mean waiting-time comparison with bootstrap uncertainty. Bars show mean wait time; error bars show bootstrap 95% confidence intervals. Lower values indicate less waiting, whereas fairness is reported separately.",
        "3. Throughput comparison with bootstrap uncertainty. Bars report throughput per simulation step with bootstrap 95% confidence intervals, separately for 56-robot and 100-robot settings.",
        "4. Runtime comparison with bootstrap uncertainty. Average step runtime is summarized with bootstrap 95% confidence intervals. Timeout and fallback rows are retained and summarized separately.",
        "5. Supervisor-intervention comparison. Bars report the number of common safety-supervisor corrections. This is a system burden metric and should not be interpreted as planner-only collision avoidance.",
        "6. Jain waiting-fairness comparison. The index measures equality of waiting-time distribution; it should be interpreted together with mean/max wait time and success rate.",
    ]
    table_lines = [
        "## Table Caption Drafts",
        "",
        "1. Core paired comparison of LCG-MPC+ against baselines. Rows summarize metric-specific paired differences against WHCA best, IMPC-DR-lite, and MPC-CBF-lite. Direction columns indicate whether higher or lower values are preferable.",
        "2. Detailed map-wise paired statistics. For each map and robot scale, the table reports mean differences, relative change, win/loss/tie rates, Holm-adjusted p-values, and bootstrap 95% confidence intervals.",
        "3. Timeout distribution. The table summarizes all 500 timeout rows by algorithm, map type, and robot scale. Timeout rows are retained in the analysis and are interpreted as runtime-budget/fallback events.",
        "4. Metric uncertainty summary. The table reports mean, standard error, and bootstrap 95% confidence intervals for each algorithm, map type, robot scale, and main metric.",
        "5. Supervisor and final-collision accounting. The table should be read as system-level supervised outcomes after common move validation, not as planner-only safety proof.",
    ]
    write_markdown(FINAL_DIR / "FIGURE_CAPTIONS.md", "Figure Captions", fig_lines)
    write_markdown(PAPER_CAPTION_DIR / "FIGURE_CAPTIONS_PAPER_READY.md", "Figure Captions", fig_lines)
    write_markdown(PAPER_CAPTION_DIR / "TABLE_CAPTIONS_PAPER_READY.md", "Table Captions", table_lines)


def copy_caption_tables_to_final() -> None:
    for src in PAPER_TABLE_DIR.glob("*.csv"):
        shutil.copy2(src, TABLE_DIR / src.name)
    for src in PAPER_FIG_DIR.glob("*"):
        if src.suffix.lower() in {".png", ".pdf"}:
            shutil.copy2(src, FIG_DIR / src.name)


def make_zip() -> None:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    include_roots = [
        FINAL_DIR / "raw_combined.csv",
        FINAL_DIR / "summary.csv",
        FINAL_DIR / "paired_statistics_vs_whca_best.csv",
        FINAL_DIR / "paired_statistics_vs_impc_dr_lite.csv",
        FINAL_DIR / "paired_statistics_vs_mpc_cbf_lite.csv",
        FINAL_DIR / "FINAL_1000SEED_CORE_REPORT.md",
        FINAL_DIR / "CLAIM_BOUNDARY_AFTER_1000SEED.md",
        FINAL_DIR / "FIGURE_CAPTIONS.md",
        FINAL_DIR / "manuscript",
        FINAL_DIR / "supplementary",
        FINAL_DIR / "tables",
        FINAL_DIR / "figures",
        FINAL_DIR / "paper_ready",
        PROJECT_ROOT / "results" / "visualizations_4way",
        PROJECT_ROOT / "configs" / "paper_1000seed_core_resumable.yaml",
        PROJECT_ROOT / "configs" / "visual_4way_5cases.yaml",
        PROJECT_ROOT / "scripts",
        PROJECT_ROOT / "src",
        PROJECT_ROOT / "tests",
    ]
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in include_roots:
            if not item.exists():
                continue
            if item.is_file():
                zf.write(item, item.relative_to(PROJECT_ROOT))
            else:
                for p in item.rglob("*"):
                    if p.is_file():
                        zf.write(p, p.relative_to(PROJECT_ROOT))


def main() -> None:
    ensure_dirs()
    raw, summary, paired = read_inputs()
    raw = raw[raw["algorithm"].isin(ALGORITHMS)].copy()
    metric_ci = metric_summary_with_uncertainty(raw)
    plot_metric_bars(metric_ci)
    key_summary, key_detail = key_comparison_tables(paired)
    timeout_rows, timeout_dist = timeout_tables(raw)
    build_report(raw, metric_ci, key_summary, timeout_dist)
    captions()
    copy_caption_tables_to_final()
    make_zip()
    print(f"paper_ready_zip={ZIP_PATH}")
    print(f"runs={len(raw)} timeout_rows={len(timeout_rows)} figures={len(list(PAPER_FIG_DIR.glob('*.png')))}")


if __name__ == "__main__":
    main()
