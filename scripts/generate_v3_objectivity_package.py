# Inha University & RODIX Inc, Anders Hwang
from __future__ import annotations

import csv
import sys
import zipfile
from itertools import product
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mr_deadlock.experiments.aggregate import load_raw, summarize
from mr_deadlock.experiments.seeds import expand_seeds
from mr_deadlock.experiments.statistics import DEFAULT_METRICS, paired_vs_baseline
from mr_deadlock.utils.io import read_yaml

OUT = ROOT / "results" / "pre1000_objectivity_v3"
REHEARSAL = OUT / "rehearsal_200seed"
PAPER_READY = OUT / "paper_ready"
ROUND2 = ROOT / "results" / "pre1000_objectivity_round2"


def write_md(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# " + title + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def copy_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def expected_jobs(config_path: Path) -> pd.DataFrame:
    cfg = read_yaml(config_path)
    exp = cfg.get("experiment", {})
    sweep = cfg.get("sweep", {})
    rows = []
    for map_type, n_robots, density, alg, seed in product(
        sweep.get("map_type", [cfg.get("scenario", {}).get("map_type")]),
        sweep.get("n_robots", [cfg.get("scenario", {}).get("n_robots")]),
        sweep.get("density", [cfg.get("scenario", {}).get("density", cfg.get("scenario", {}).get("obstacle_density"))]),
        exp.get("algorithms", []),
        expand_seeds(exp),
    ):
        rows.append({"map_type": map_type, "n_robots": n_robots, "density": density, "algorithm": alg, "seed": seed})
    return pd.DataFrame(rows)


def coverage(raw: pd.DataFrame, expected: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    key = ["map_type", "n_robots", "density", "algorithm", "seed"]
    if raw.empty:
        done = pd.DataFrame(columns=[*key, "done_count"])
    else:
        done = raw.groupby(key, dropna=False).size().reset_index(name="done_count")
    merged = expected.merge(done, on=key, how="left")
    merged["completed"] = merged["done_count"].fillna(0).astype(int) > 0
    missing = merged[~merged["completed"]][key].copy()
    failed = raw[raw.get("timeout_count", pd.Series(dtype=float)).fillna(0).astype(float) > 0].copy() if not raw.empty and "timeout_count" in raw else pd.DataFrame()
    summary = merged.groupby(["algorithm", "map_type", "n_robots"], dropna=False)["completed"].agg(["sum", "count"]).reset_index()
    summary["coverage_pct"] = summary["sum"] / summary["count"] * 100.0
    return summary, missing, failed


def make_figures(summary: pd.DataFrame, raw: pd.DataFrame) -> None:
    PAPER_READY.mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib.pyplot as plt
    except Exception:
        write_md(PAPER_READY / "FIGURE_GENERATION_SKIPPED.md", "Figure Generation Skipped", ["- matplotlib is unavailable."])
        return

    if summary.empty:
        return
    plots = [
        ("success_rate_by_map_algorithm", "success_rate_mean", "Success rate"),
        ("mean_wait_time_by_map_algorithm", "mean_wait_time_mean", "Mean wait time"),
        ("throughput_by_map_algorithm", "throughput_per_step_mean", "Throughput per step"),
        ("fairness_by_map_algorithm", "fairness_jain_wait_mean", "Jain fairness wait"),
        ("runtime_by_map_algorithm", "avg_step_runtime_ms_mean", "Avg step runtime ms"),
        ("supervisor_intervention_by_map_algorithm", "supervisor_interventions_mean", "Supervisor interventions"),
    ]
    for name, col, ylabel in plots:
        if col not in summary.columns:
            continue
        pivot = summary.groupby(["map_type", "algorithm"], dropna=False)[col].mean().unstack("algorithm")
        ax = pivot.plot(kind="bar", figsize=(10, 5))
        ax.set_ylabel(ylabel)
        ax.set_xlabel("map")
        ax.legend(fontsize=7)
        plt.tight_layout()
        for ext in ["png", "pdf"]:
            plt.savefig(PAPER_READY / f"{name}.{ext}")
        plt.close()

    if not raw.empty and {"algorithm", "raw_conflicts_per_step", "final_conflicts_per_step"}.issubset(raw.columns):
        conflict = raw.groupby("algorithm")[["raw_conflicts_per_step", "final_conflicts_per_step"]].mean()
        ax = conflict.plot(kind="bar", figsize=(10, 5))
        ax.set_ylabel("conflicts per step")
        plt.tight_layout()
        for ext in ["png", "pdf"]:
            plt.savefig(PAPER_READY / f"raw_vs_final_conflict_by_algorithm.{ext}")
        plt.close()

    if not raw.empty and {"map_type", "algorithm", "success_rate"}.issubset(raw.columns):
        stress = raw.copy()
        stress["stress_group"] = stress["map_type"].isin(["ring", "bottleneck"]).map({True: "stress", False: "nonstress"})
        pivot = stress.groupby(["stress_group", "algorithm"])["success_rate"].mean().unstack("algorithm")
        ax = pivot.plot(kind="bar", figsize=(10, 5))
        ax.set_ylabel("success rate")
        plt.tight_layout()
        for ext in ["png", "pdf"]:
            plt.savefig(PAPER_READY / f"stress_vs_nonstress_success.{ext}")
        plt.close()


def table_to_tex(csv_path: Path) -> None:
    if not csv_path.exists():
        return
    df = pd.read_csv(csv_path)
    tex_path = csv_path.with_suffix(".tex")
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(df.head(80).to_latex(index=False, escape=True))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    PAPER_READY.mkdir(parents=True, exist_ok=True)
    raw_dir = REHEARSAL / "raw"
    raw = load_raw(raw_dir) if raw_dir.exists() else pd.DataFrame()
    dedupe_key = ["map_type", "n_robots", "density", "algorithm", "seed"]
    if not raw.empty and set(dedupe_key).issubset(raw.columns):
        raw = raw.sort_values(dedupe_key).drop_duplicates(dedupe_key, keep="last").reset_index(drop=True)
    expected = expected_jobs(ROOT / "configs" / "pre1000_v3_rehearsal_200seed.yaml")
    cov, missing, failed = coverage(raw, expected)

    raw_path = REHEARSAL / "raw_combined.csv"
    summary_path = REHEARSAL / "summary.csv"
    copy_csv(raw, raw_path)
    summary = summarize(raw) if not raw.empty else pd.DataFrame()
    copy_csv(summary, summary_path)
    copy_csv(cov, REHEARSAL / "experiment_coverage.csv")
    copy_csv(missing, REHEARSAL / "missing_runs.csv")
    copy_csv(failed, REHEARSAL / "failed_runs.csv")

    for baseline, filename in [
        ("whca_best_preregistered", "paired_statistics_vs_whca_best.csv"),
        ("mpc_cbf_lite", "paired_statistics_vs_mpc_cbf_lite.csv"),
        ("impc_dr_lite", "paired_statistics_vs_impc_dr_lite.csv"),
    ]:
        paired = paired_vs_baseline(raw, baseline=baseline, metrics=DEFAULT_METRICS) if not raw.empty else pd.DataFrame()
        copy_csv(paired, REHEARSAL / filename)
        copy_csv(paired, PAPER_READY / filename)
        table_to_tex(PAPER_READY / filename)

    completed = len(raw)
    expected_count = len(expected)
    coverage_pct = completed / max(1, expected_count) * 100.0
    runtime_sec = float(raw["runtime_sec"].sum()) if not raw.empty and "runtime_sec" in raw else 0.0
    sec_per_run = runtime_sec / max(1, completed)
    est_200_hours = sec_per_run * expected_count / 3600.0
    est_1000_jobs = 1000 * 2 * 6 * 7
    est_1000_hours = sec_per_run * est_1000_jobs / 3600.0
    est_1000_hours_jobs6 = est_1000_hours / 6.0

    write_md(
        REHEARSAL / "runtime_budget_estimate.md",
        "Runtime Budget Estimate",
        [
            f"- Completed rehearsal runs: {completed} / {expected_count} ({coverage_pct:.2f}%).",
            f"- Observed wall-clock runtime in raw summaries: {runtime_sec:.1f} sec.",
            f"- Mean runtime per completed run: {sec_per_run:.3f} sec.",
            f"- Estimated 200-seed rehearsal runtime at this rate: {est_200_hours:.2f} hours serial.",
            f"- Estimated 1000-seed manuscript-core runtime at this rate: {est_1000_hours:.2f} hours serial before parallel speedup.",
            f"- Estimated 1000-seed manuscript-core runtime with jobs=6: {est_1000_hours_jobs6:.2f} hours.",
            "- This estimate is optimistic if slow cases are not yet represented.",
        ],
    )

    profile_cols = [
        "algorithm", "map_type", "n_robots", "density", "seed", "runtime_sec", "avg_step_runtime_ms",
        "p95_step_runtime_ms", "p99_step_runtime_ms", "max_step_runtime_ms", "timeout_count",
        "executed_steps", "planner_plan_time_ms", "safety_supervisor_time_ms",
        "dynamics_envelope_time_ms", "reservation_table_time_ms", "astar_or_bfs_time_ms",
        "local_game_time_ms", "mpc_qp_refinement_time_ms", "cbf_robust_filter_time_ms",
        "logging_csv_overhead_ms",
    ]
    profile = raw[[c for c in profile_cols if c in raw.columns]].copy() if not raw.empty else pd.DataFrame(columns=profile_cols)
    copy_csv(profile, OUT / "01_runtime_profile.csv")
    slow = profile.sort_values("runtime_sec", ascending=False).head(10) if not profile.empty and "runtime_sec" in profile else pd.DataFrame()
    slow_lines = ["- No v3 raw profile rows are available."] if slow.empty else [
        "- Slowest observed v3 pilot rows:",
        *[
            f"  - {r.algorithm} {r.map_type} robots={int(r.n_robots)} seed={int(r.seed)} runtime={float(r.runtime_sec):.2f}s p99={float(getattr(r, 'p99_step_runtime_ms', 0.0)):.2f}ms"
            for r in slow.itertuples()
        ],
    ]
    write_md(OUT / "01_runtime_profile_report.md", "Runtime Profile Report", slow_lines)

    whca = raw[raw["algorithm"].isin(["whca_default_h8", "whca_best_preregistered", "whca_h16", "whca_h32", "whca_h32_goal"])] if not raw.empty and "algorithm" in raw else pd.DataFrame()
    whca_summary = whca.groupby(["algorithm", "map_type", "n_robots"], dropna=False)[[
        c for c in ["success_rate", "mean_wait_time", "fairness_jain_wait", "avg_step_runtime_ms", "actual_window", "goal_reservation_enabled"] if c in whca.columns
    ]].mean(numeric_only=True).reset_index() if not whca.empty else pd.DataFrame()
    copy_csv(whca_summary, OUT / "02_whca_runtime_fairness.csv")
    write_md(
        OUT / "02_whca_runtime_fairness_report.md",
        "WHCA Runtime Fairness Report",
        [
            "- `whca_best_preregistered` is fixed to h16 before the main experiment; it is not chosen per seed.",
            "- h32 remains available for sensitivity analysis but is not selected as the main strong baseline because round2 exposed high wall-clock cost.",
            "- goal reservation is kept out of the preregistered baseline unless a separate pilot proves a net benefit.",
        ],
    )

    lcg = raw[raw["algorithm"] == "lcg_mpc_plus_full_v3"] if not raw.empty and "algorithm" in raw else pd.DataFrame()
    lcg_cols = [
        "algorithm", "map_type", "n_robots", "seed", "runtime_sec", "timeout_count",
        "timeout_fallback_count", "capped_game_count", "capped_mpc_count", "capped_cbf_count",
        "game_profiles_evaluated_per_step", "mpc_refinements_per_step", "cbf_calls_per_step",
    ]
    copy_csv(lcg[[c for c in lcg_cols if c in lcg.columns]] if not lcg.empty else pd.DataFrame(columns=lcg_cols), OUT / "03_lcg_runtime_optimization.csv")
    write_md(
        OUT / "03_lcg_runtime_optimization_report.md",
        "LCG-MPC+ Runtime Optimization Report",
        [
            "- Added v3 caps: max_game_profiles_per_component, max_total_game_profiles_per_step, max_mpc_refinements_per_step, max_cbf_filter_calls_per_step.",
            "- Added metrics: timeout_fallback_count, capped_game_count, capped_mpc_count, capped_cbf_count, mpc_refinements_per_step, cbf_calls_per_step.",
            "- `lcg_mpc_plus_full_v3` skips the extra WHCA probe used only for robust-nominal difference logging.",
        ],
    )

    ablation_stats = ROUND2 / "02_ablation_round2_statistics.csv"
    ablation_delta = ROUND2 / "02_ablation_round2_delta_vs_full.csv"
    claim_rows = []
    if ablation_delta.exists():
        delta = pd.read_csv(ablation_delta)
        for row in delta.to_dict("records"):
            variant = row.get("variant", "")
            if "robust_nominal" in variant:
                category = "Core performance driver"
            elif "safety_envelope_logging" in variant:
                category = "Engineering/logging component"
            elif "cbf" in variant:
                category = "Safety/interpretability component"
            elif "game" in variant or "mpc" in variant or "stagnation" in variant:
                category = "Secondary stabilizer"
            else:
                category = "Not supported by current ablation"
            claim_rows.append({**row, "claim_category": category})
    claim = pd.DataFrame(claim_rows)
    copy_csv(claim, OUT / "04_ablation_claim_table.csv")
    write_md(
        OUT / "04_ablation_claim_report.md",
        "Ablation Claim Report",
        [
            "- Round2 supports robust nominal as the clearest performance driver.",
            "- Game/MPC/CBF/stagnation effects should be framed as secondary or safety/stabilization modules unless the v3 ablation shows larger deltas.",
            "- Safety-envelope logging is an engineering/interpretability component, not a performance driver.",
        ],
    )

    verdict = "NO-GO"
    if coverage_pct >= 99.9 and est_1000_hours <= 24 and (failed.empty or len(failed) < 0.01 * completed):
        verdict = "GO"
    elif coverage_pct >= 99.9 and missing.empty and failed.empty and est_1000_hours_jobs6 <= 24:
        verdict = "CONDITIONAL GO"
    write_md(
        OUT / "05_GO_NO_GO_FOR_1000SEED_V3.md",
        "GO/NO-GO for 1000-Seed V3",
        [
            f"Verdict: **{verdict}**.",
            f"- 200-seed rehearsal coverage: {completed} / {expected_count} ({coverage_pct:.2f}%).",
            f"- Estimated 1000-seed core runtime: {est_1000_hours:.2f} serial hours before parallel speedup.",
            f"- Estimated 1000-seed core runtime with jobs=6: {est_1000_hours_jobs6:.2f} hours.",
            f"- Missing runs: {len(missing)}.",
            f"- Timeout/failed rows: {len(failed)}.",
            "- Full GO would require a shorter runtime budget or stronger evidence that the full 1000-seed run can complete comfortably under the available wall-clock window.",
        ],
    )

    write_md(
        OUT / "06_CLAIM_BOUNDARY_V3.md",
        "Claim Boundary V3",
        [
            "- 1000-seed core: paired 56/100 robots, six maps, density 0.05 only.",
            "- 250 robots: reduced-seed scalability validation only.",
            "- 500/1000 robots: smoke feasibility only.",
            "- WHCA best baseline: preregistered h16 baseline selected before the main 1000-seed run.",
            "- IMPC-DR-lite and MPC-CBF-lite: simulator-native surrogate baselines.",
            "- Exact-potential guarantee: bounded exact or partitioned-exact local games only.",
            "- Safety: collision_count=0 is a system-level result after the common safety supervisor.",
            "- Module contribution: robust nominal can be stated as core driver; other modules require cautious secondary/safety wording.",
            "- Runtime scalability: claim only within the configured caps and reported timeout/fallback rates.",
            "",
            "Safe abstract sentences:",
            "1. We evaluate a capped local-game MPC architecture in paired simulator-native experiments.",
            "2. Safety outcomes are reported after a common supervisory validation layer applied to every planner.",
            "3. Large-scale experiments are presented as reduced-seed scalability evidence rather than full statistical claims.",
            "",
            "Do not write:",
            "1. LCG-MPC+ is collision-free by planner design alone.",
            "2. The exact-potential guarantee applies to every global multi-robot interaction.",
            "3. The surrogate baselines are official implementations of the cited algorithms.",
            "4. 500/1000 robot results are full 1000-seed statistical evidence.",
            "5. Every module independently improves performance in all maps.",
        ],
    )

    main_table = summary.copy()
    copy_csv(main_table, PAPER_READY / "main_result_table.csv")
    table_to_tex(PAPER_READY / "main_result_table.csv")
    copy_csv(claim, PAPER_READY / "ablation_claim_table.csv")
    table_to_tex(PAPER_READY / "ablation_claim_table.csv")
    runtime_table = profile.groupby(["algorithm", "map_type", "n_robots"], dropna=False).mean(numeric_only=True).reset_index() if not profile.empty else pd.DataFrame()
    copy_csv(runtime_table, PAPER_READY / "runtime_budget_table.csv")
    table_to_tex(PAPER_READY / "runtime_budget_table.csv")
    supervisor_cols = [c for c in ["algorithm", "map_type", "n_robots", "supervisor_interventions", "raw_conflicts_per_step", "final_conflicts_per_step"] if c in raw.columns]
    supervisor_table = raw[supervisor_cols].groupby(["algorithm", "map_type", "n_robots"], dropna=False).mean(numeric_only=True).reset_index() if supervisor_cols and not raw.empty else pd.DataFrame()
    copy_csv(supervisor_table, PAPER_READY / "supervisor_effect_table.csv")
    table_to_tex(PAPER_READY / "supervisor_effect_table.csv")
    make_figures(summary, raw)

    with open(OUT / "V3_PACKAGE_MANIFEST.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["path", "bytes"])
        for p in sorted(OUT.rglob("*")):
            if p.is_file():
                writer.writerow([str(p.relative_to(ROOT)), p.stat().st_size])

    zip_path = ROOT / "pre1000_objectivity_v3_package.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in OUT.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(ROOT))

    print(f"verdict={verdict}")
    print(f"completed={completed}/{expected_count}")
    print(f"estimated_1000seed_serial_hours={est_1000_hours:.2f}")
    print(f"zip={zip_path}")


if __name__ == "__main__":
    main()

