# Inha University & RODIX Inc, Anders Hwang
from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from itertools import product
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mr_deadlock.experiments.aggregate import load_raw, summarize
from mr_deadlock.experiments.seeds import expand_seeds
from mr_deadlock.experiments.statistics import DEFAULT_METRICS, paired_vs_baseline
from mr_deadlock.utils.io import read_yaml


BASELINES = ["whca_best_preregistered", "impc_dr_lite", "mpc_cbf_lite"]
ALGORITHMS = ["whca_best_preregistered", "impc_dr_lite", "mpc_cbf_lite", "lcg_mpc_plus_full_v3"]
DISPLAY_NAMES = {"lcg_mpc_plus_full_v3": "lcg_mpc_plus"}
PAIR_KEY = ["map_type", "n_robots", "density", "seed"]
RUN_KEY = ["map_type", "n_robots", "density", "algorithm", "seed"]


def write_md(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# " + title + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def display_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["algorithm", "baseline"]:
        if col in out.columns:
            out[col] = out[col].replace(DISPLAY_NAMES)
    return out


def expected(config: dict) -> pd.DataFrame:
    exp = config.get("experiment", {})
    sweep = config.get("sweep", {})
    rows = []
    for map_type, n_robots, density, alg, seed in product(
        sweep.get("map_type", []),
        sweep.get("n_robots", []),
        sweep.get("density", []),
        exp.get("algorithms", []),
        expand_seeds(exp),
    ):
        rows.append({"map_type": map_type, "n_robots": n_robots, "density": density, "algorithm": alg, "seed": int(seed)})
    return pd.DataFrame(rows)


def coverage(raw: pd.DataFrame, exp_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    done = raw.groupby(RUN_KEY, dropna=False).size().reset_index(name="done_count") if not raw.empty else pd.DataFrame(columns=[*RUN_KEY, "done_count"])
    merged = exp_df.merge(done, on=RUN_KEY, how="left")
    merged["completed"] = merged["done_count"].fillna(0).astype(int) > 0
    cov = merged.groupby(["algorithm", "map_type", "n_robots"], dropna=False)["completed"].agg(["sum", "count"]).reset_index()
    cov["coverage_pct"] = cov["sum"] / cov["count"] * 100.0
    missing = merged[~merged["completed"]][RUN_KEY].copy()
    timeout_rows = raw[pd.to_numeric(raw.get("timeout_count", 0), errors="coerce").fillna(0) > 0].copy() if not raw.empty else pd.DataFrame()
    return cov, missing, timeout_rows


def complete_pair_subset(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if raw.empty:
        return raw, pd.DataFrame(columns=PAIR_KEY)
    counts = raw.groupby(PAIR_KEY)["algorithm"].nunique().reset_index(name="algorithm_count")
    complete = counts[counts["algorithm_count"] == len(ALGORITHMS)][PAIR_KEY]
    excluded = counts[counts["algorithm_count"] < len(ALGORITHMS)][PAIR_KEY + ["algorithm_count"]]
    paired = raw.merge(complete, on=PAIR_KEY, how="inner")
    return paired, excluded


def to_tex(csv_path: Path) -> None:
    if not csv_path.exists():
        return
    df = pd.read_csv(csv_path)
    csv_path.with_suffix(".tex").write_text(df.head(120).to_latex(index=False, escape=True), encoding="utf-8")


def make_figures(summary: pd.DataFrame, raw: pd.DataFrame, fig_dir: Path) -> None:
    fig_dir.mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib.pyplot as plt
    except Exception:
        write_md(fig_dir / "FIGURES_SKIPPED.md", "Figures Skipped", ["matplotlib is unavailable."])
        return
    plots = [
        ("success_rate_by_map_algorithm", "success_rate_mean", "Success rate"),
        ("mean_wait_time_by_map_algorithm", "mean_wait_time_mean", "Mean wait time"),
        ("throughput_by_map_algorithm", "throughput_per_step_mean", "Throughput per step"),
        ("fairness_by_map_algorithm", "fairness_jain_wait_mean", "Jain fairness wait"),
        ("runtime_by_map_algorithm", "avg_step_runtime_ms_mean", "Average step runtime (ms)"),
        ("p99_runtime_by_map_algorithm", "p99_step_runtime_ms_mean", "P99 step runtime (ms)"),
        ("supervisor_intervention_by_map_algorithm", "supervisor_interventions_mean", "Supervisor interventions"),
    ]
    for name, col, ylabel in plots:
        if summary.empty or col not in summary.columns:
            continue
        ax = summary.groupby(["map_type", "algorithm"], dropna=False)[col].mean().unstack("algorithm").plot(kind="bar", figsize=(10, 5))
        ax.set_ylabel(ylabel)
        ax.set_xlabel("map")
        ax.legend(fontsize=7)
        plt.tight_layout()
        plt.savefig(fig_dir / f"{name}.png")
        plt.savefig(fig_dir / f"{name}.pdf")
        plt.close()
    if not raw.empty and {"algorithm", "raw_conflicts_per_step", "final_conflicts_per_step"}.issubset(raw.columns):
        ax = raw.groupby("algorithm")[["raw_conflicts_per_step", "final_conflicts_per_step"]].mean().plot(kind="bar", figsize=(10, 5))
        ax.set_ylabel("conflicts per step")
        plt.tight_layout()
        plt.savefig(fig_dir / "raw_vs_final_conflict_by_algorithm.png")
        plt.savefig(fig_dir / "raw_vs_final_conflict_by_algorithm.pdf")
        plt.close()
    if not raw.empty and {"algorithm", "footprint_conflicts", "swept_conflicts"}.issubset(raw.columns):
        ax = raw.groupby("algorithm")[["footprint_conflicts", "swept_conflicts"]].mean().plot(kind="bar", figsize=(10, 5))
        ax.set_ylabel("risk events")
        plt.tight_layout()
        plt.savefig(fig_dir / "footprint_swept_risk_by_algorithm.png")
        plt.savefig(fig_dir / "footprint_swept_risk_by_algorithm.pdf")
        plt.close()
    if not raw.empty:
        tmp = raw.copy()
        tmp["stress_group"] = tmp["map_type"].isin(["ring", "bottleneck"]).map({True: "stress", False: "nonstress"})
        ax = tmp.groupby(["stress_group", "algorithm"])["success_rate"].mean().unstack("algorithm").plot(kind="bar", figsize=(10, 5))
        ax.set_ylabel("success rate")
        plt.tight_layout()
        plt.savefig(fig_dir / "stress_vs_nonstress_success.png")
        plt.savefig(fig_dir / "stress_vs_nonstress_success.pdf")
        plt.close()


def claim_boundary(path: Path, full: bool) -> None:
    scope = "1000-seed paired evaluation" if full else "partial paired evaluation"
    write_md(
        path,
        "Claim Boundary After 1000-Seed Core",
        [
            f"- Current experimental status: {scope}.",
            "- Claims are limited to 56/100 robots, density 0.05, six simulator maps.",
            "- WHCA best comparison may be stated against the preregistered h16 native baseline.",
            "- IMPC-DR-lite and MPC-CBF-lite are simulator-native surrogate baselines, not official external implementations.",
            "- MPC-CBF-lite metrics where it outperforms LCG-MPC+ must be reported plainly.",
            "- Exact-potential equilibrium claims apply only to bounded exact or partitioned-exact local games.",
            "- Greedy fallback cases do not carry the same exact-potential guarantee.",
            "- collision_count=0 is a common safety-supervisor system-level outcome, not planner-only proof.",
            "",
            "Safe abstract sentences:",
            "1. We report paired simulator-native experiments with preregistered baselines and explicit safety-supervisor accounting.",
            "2. LCG-MPC+ improves localized deadlock recovery relative to WHCA best and IMPC-DR-lite in the tested core setting.",
            "3. MPC-CBF-lite is retained as a strong surrogate baseline, and metrics favoring it are reported without exclusion.",
            "",
            "Do not write:",
            "1. LCG-MPC+ dominates every baseline on every metric.",
            "2. MPC-CBF-lite was excluded because it performed too well.",
            "3. final collision_count=0 proves planner-only safety.",
            "4. Exact-potential guarantees apply to global multi-robot behavior.",
            "5. 250/500/1000 robot scalability is proven by this core experiment.",
        ],
    )


def manuscript(path: Path, full: bool) -> None:
    status = "1000-seed paired evaluation" if full else "partial paired evaluation"
    write_md(
        path,
        "LCG-MPC+ SCI Final Manuscript Draft",
        [
            "## 제목",
            "LCG-MPC+: Local Conflict-Game MPC for System-Level Deadlock Recovery in Multi-AMR Simulation",
            "",
            "## 초록",
            f"본 초안은 현재 `{status}` 결과만 반영한다. WHCA best와 IMPC-DR-lite 대비 개선은 metric별로 보고하며, MPC-CBF-lite가 더 우수한 항목은 그대로 제시한다.",
            "",
            "## Abstract",
            f"This draft reflects the current {status}. MPC-CBF-lite is retained as a strong simulator-native surrogate baseline.",
            "",
            "## Introduction",
            "Multi-AMR deadlock recovery requires both planner-level progress and system-level safety validation.",
            "",
            "## Related Work",
            "We compare against preregistered WHCA best, IMPC-DR-lite, and MPC-CBF-lite simulator-native baselines.",
            "",
            "## Problem Formulation",
            "The core experiment is limited to 56/100 robots, density 0.05, one-shot cross-traffic tasks.",
            "",
            "## Proposed Method: LCG-MPC+",
            "LCG-MPC+ combines bounded local conflict games, MPC-style refinement, robust nominal filtering, and a common safety supervisor.",
            "",
            "## Theoretical Scope and Claim Boundary",
            "Exact-potential claims apply only to bounded exact or partitioned-exact local games. Greedy fallback is empirical.",
            "",
            "## Experimental Protocol",
            "All runs are paired by seed, map, start-goal hash, robot count, density, and algorithm set.",
            "",
            "## 1000-Seed Core Results",
            "Populate from `final/summary.csv` only after coverage reaches 100%; otherwise label as partial.",
            "",
            "## Comparison with WHCA Best",
            "Report paired statistics versus `whca_best_preregistered`.",
            "",
            "## Comparison with IMPC-DR-lite",
            "Report metric-specific improvements and any losses.",
            "",
            "## Comparison with MPC-CBF-lite",
            "Do not hide MPC-CBF-lite advantages; frame LCG-MPC+ as complementary where appropriate.",
            "",
            "## Safety Supervisor and Raw/Final Conflict Analysis",
            "final collision_count is a system-level outcome after common safety supervision.",
            "",
            "## Runtime Analysis",
            "Report avg/p95/p99/max step runtime and timeout/fallback/cap counters.",
            "",
            "## Ablation Interpretation",
            "Use robust nominal as the clearest current core driver; other modules require cautious wording.",
            "",
            "## Visualization Cases",
            "Use figures generated in `final/figures` after completion.",
            "",
            "## Discussion",
            "LCG-MPC+ is a localized game-based repair framework, not a universal dominance result.",
            "",
            "## Limitations",
            "Simulator-native baselines, fixed density, 56/100 robot core scope, and common supervisor dependency.",
            "",
            "## Conclusion",
            "Claims must track actual coverage and paired statistics.",
            "",
            "## References",
            "To be synchronized with the existing manuscript bibliography.",
            "",
            "## Appendix",
            "Include resume protocol, configs, seed pairing, statistical tests, and raw/final metric definitions.",
        ],
    )


def supplementary(path: Path) -> None:
    write_md(
        path,
        "Supplementary Material",
        [
            "## Config",
            "Primary config: `configs/paper_1000seed_core_resumable.yaml`.",
            "## Seed Pairing",
            "Runs share seed, map, robot count, density, start-goal mode, and algorithm set.",
            "## Algorithms",
            "WHCA best, IMPC-DR-lite, MPC-CBF-lite, and LCG-MPC+ are included.",
            "## Raw/Final Conflict Metrics",
            "Raw conflicts are planner outputs before common validation; final conflicts are after supervisor correction.",
            "## Supervisor Intervention",
            "Counts common safety supervisor corrections.",
            "## Statistical Tests",
            "Paired statistics use complete seed/scenario sets only.",
            "## Bootstrap CI",
            "Mean-difference bootstrap intervals are produced by the statistics module.",
            "## Runtime Logging",
            "avg/p95/p99/max runtime, timeout, fallback, and cap counters are recorded.",
            "## Resume Protocol",
            "Use `state/NEXT_RUN_COMMAND.txt` after graceful shutdown.",
            "## Visualization Protocol",
            "Figures are regenerated from completed raw CSV files.",
            "## Reproduction Commands",
            "Run precheck, then `scripts/run_resumable_1000seed_core.py`, then this analyzer.",
        ],
    )


def claim_boundary_table(path: Path) -> None:
    rows = [
        {"claim": "1000-seed paired core", "allowed": "only when coverage is 100%", "scope": "56/100 robots, density 0.05"},
        {"claim": "WHCA best comparison", "allowed": "yes", "scope": "preregistered h16 simulator-native baseline"},
        {"claim": "IMPC-DR-lite comparison", "allowed": "metric-specific", "scope": "simulator-native surrogate"},
        {"claim": "MPC-CBF-lite comparison", "allowed": "metric-specific, include losses", "scope": "simulator-native surrogate"},
        {"claim": "planner-only safety", "allowed": "no", "scope": "collision_count is after common supervisor"},
        {"claim": "global exact-potential guarantee", "allowed": "no", "scope": "bounded local exact/partitioned exact only"},
    ]
    pd.DataFrame(rows).to_csv(path, index=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/paper_1000seed_core_resumable.yaml")
    args = ap.parse_args()
    cfg = read_yaml(args.config)
    root = PROJECT_ROOT / "results" / "paper_1000seed_core_resumable"
    raw_dir = root / "raw"
    progress = root / "progress"
    final = root / "final"
    state = root / "state"
    progress.mkdir(parents=True, exist_ok=True)
    final.mkdir(parents=True, exist_ok=True)

    raw = load_raw(raw_dir) if raw_dir.exists() else pd.DataFrame()
    if not raw.empty:
        raw = raw.drop_duplicates(RUN_KEY, keep="last").reset_index(drop=True)
    exp_df = expected(cfg)
    cov, missing, timeout_rows = coverage(raw, exp_df)
    paired_raw, excluded = complete_pair_subset(raw)
    full = len(raw) == len(exp_df) and missing.empty
    target = final if full else progress

    raw_display = display_df(raw)
    summary_display = display_df(summarize(raw))
    cov_display = display_df(cov)
    timeout_display = display_df(timeout_rows)

    raw_display.to_csv(progress / "raw_combined_current.csv", index=False)
    summary_display.to_csv(progress / "summary_current.csv", index=False)
    excluded.to_csv(progress / "excluded_incomplete_pairs.csv", index=False)
    cov_display.to_csv(progress / "experiment_coverage.csv", index=False)
    missing.to_csv(progress / "missing_runs.csv", index=False)
    timeout_display.to_csv(progress / "timeout_rows.csv", index=False)

    for baseline in BASELINES:
        paired = paired_vs_baseline(paired_raw, baseline=baseline, metrics=DEFAULT_METRICS) if not paired_raw.empty else pd.DataFrame()
        display_df(paired).to_csv(progress / f"paired_statistics_vs_{baseline.replace('whca_best_preregistered', 'whca_best')}_current.csv", index=False)

    write_md(
        progress / "PROGRESS_REPORT.md",
        "1000-Seed Core Progress Report",
        [
            f"- full 1000-seed completed: {'YES' if full else 'NO'}",
            f"- planned runs: {len(exp_df)}",
            f"- completed runs: {len(raw)}",
            f"- coverage percentage: {len(raw) / max(1, len(exp_df)) * 100.0:.2f}%",
            f"- missing runs: {len(missing)}",
            f"- timeout rows: {len(timeout_rows)}",
            f"- complete paired scenario sets used for paired stats: {0 if paired_raw.empty else paired_raw.groupby(PAIR_KEY).ngroups}",
            "- This is a progress report unless coverage is 100%.",
        ],
    )

    if full:
        raw_display.to_csv(final / "raw_combined.csv", index=False)
        summary = summarize(raw)
        summary_display = display_df(summary)
        summary_display.to_csv(final / "summary.csv", index=False)
        cov_display.to_csv(final / "experiment_coverage.csv", index=False)
        missing.to_csv(final / "missing_runs.csv", index=False)
        pd.DataFrame().to_csv(final / "failed_runs.csv", index=False)
        timeout_display.to_csv(final / "timeout_rows.csv", index=False)
        for baseline in BASELINES:
            paired = paired_vs_baseline(paired_raw, baseline=baseline, metrics=DEFAULT_METRICS)
            name = baseline.replace("whca_best_preregistered", "whca_best")
            display_df(paired).to_csv(final / f"paired_statistics_vs_{name}.csv", index=False)
        tables = final / "tables"
        figs = final / "figures"
        tables.mkdir(exist_ok=True)
        figs.mkdir(exist_ok=True)
        summary_display.to_csv(tables / "main_result_table.csv", index=False)
        for p in [tables / "main_result_table.csv"]:
            to_tex(p)
        for name in ["whca_best", "impc_dr_lite", "mpc_cbf_lite"]:
            src = final / f"paired_statistics_vs_{name}.csv"
            dst = tables / f"paired_statistics_vs_{name}.csv"
            if src.exists():
                shutil.copy2(src, dst)
                to_tex(dst)
        runtime_cols = [c for c in ["algorithm", "map_type", "n_robots", "avg_step_runtime_ms", "p95_step_runtime_ms", "p99_step_runtime_ms", "max_step_runtime_ms", "timeout_count"] if c in raw.columns]
        raw_display[runtime_cols].groupby(["algorithm", "map_type", "n_robots"], dropna=False).mean(numeric_only=True).reset_index().to_csv(tables / "runtime_table.csv", index=False)
        to_tex(tables / "runtime_table.csv")
        sup_cols = [c for c in ["algorithm", "map_type", "n_robots", "supervisor_interventions", "raw_conflicts_per_step", "final_conflicts_per_step"] if c in raw.columns]
        raw_display[sup_cols].groupby(["algorithm", "map_type", "n_robots"], dropna=False).mean(numeric_only=True).reset_index().to_csv(tables / "supervisor_effect_table.csv", index=False)
        to_tex(tables / "supervisor_effect_table.csv")
        claim_boundary_table(tables / "claim_boundary_table.csv")
        to_tex(tables / "claim_boundary_table.csv")
        claim_boundary(final / "CLAIM_BOUNDARY_AFTER_1000SEED.md", full)
        write_md(final / "FINAL_1000SEED_CORE_REPORT.md", "Final 1000-Seed Core Report", [f"- completed runs: {len(raw)} / {len(exp_df)}", "- Coverage is complete."])
        make_figures(summary_display, raw_display, figs)
        write_md(final / "FIGURE_CAPTIONS.md", "Figure Captions", ["- Captions should state that MPC-CBF-lite advantages are retained where observed."])
        manuscript(final / "manuscript" / "LCG_MPC_PLUS_SCI_Final_Manuscript_1000seed_KR.md", full)
        supplementary(final / "supplementary" / "SUPPLEMENTARY_MATERIAL.md")
    else:
        partial = root / "partial"
        partial.mkdir(exist_ok=True)
        raw_display.to_csv(partial / "raw_combined_partial.csv", index=False)
        summary_display.to_csv(partial / "summary_partial.csv", index=False)
        claim_boundary(partial / "CLAIM_BOUNDARY_PARTIAL.md", full)
        manuscript(partial / "manuscript" / "LCG_MPC_PLUS_SCI_Final_Manuscript_1000seed_KR.md", full)
        supplementary(partial / "supplementary" / "SUPPLEMENTARY_MATERIAL.md")

    zip_path = PROJECT_ROOT / "paper_1000seed_core_resumable_results_final.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder in [PROJECT_ROOT / "configs", state, root / "precheck", progress, final, root / "partial"]:
            if folder.exists():
                for p in folder.rglob("*"):
                    if p.is_file():
                        zf.write(p, p.relative_to(PROJECT_ROOT))
    print(f"full={full}")
    print(f"planned={len(exp_df)} completed={len(raw)} missing={len(missing)} timeout_rows={len(timeout_rows)}")
    print(f"zip={zip_path}")


if __name__ == "__main__":
    main()

