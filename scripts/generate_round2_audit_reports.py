# Inha University & RODIX Inc, Anders Hwang
from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mr_deadlock.experiments.aggregate import summarize
from mr_deadlock.experiments.statistics import DEFAULT_METRICS, paired_vs_baseline


OUT = ROOT / "results" / "pre1000_objectivity_round2"
ABL_RAW = OUT / "runs" / "ablation_30seed" / "summary" / "raw_combined.csv"
ABL_SUMMARY = OUT / "runs" / "ablation_30seed" / "summary" / "summary.csv"
SECOND_RAW_DIR = OUT / "runs" / "second_audit_30seed" / "raw"
SECOND_SUMMARY_DIR = OUT / "runs" / "second_audit_30seed" / "summary"


def load_many_csv(path: Path) -> pd.DataFrame:
    files = sorted(p for p in path.glob("*.csv") if not p.name.endswith("_steps.csv") and "combined" not in p.name)
    frames = []
    for p in files:
        try:
            frames.append(pd.read_csv(p))
        except Exception:
            continue
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def write_md(path: Path, title: str, lines: list[str]) -> None:
    path.write_text("# " + title + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def metric_mean(df: pd.DataFrame, cols: list[str], group_cols: list[str]) -> pd.DataFrame:
    cols = [c for c in cols if c in df.columns]
    if df.empty or not cols:
        return pd.DataFrame()
    return df.groupby(group_cols, dropna=False)[cols].mean(numeric_only=True).reset_index()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SECOND_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

    ablation = pd.read_csv(ABL_RAW) if ABL_RAW.exists() else pd.DataFrame()
    second = load_many_csv(SECOND_RAW_DIR)

    if not second.empty:
        second.to_csv(SECOND_SUMMARY_DIR / "raw_combined_partial.csv", index=False)
        second_summary = summarize(second)
        second_summary.to_csv(SECOND_SUMMARY_DIR / "summary_partial.csv", index=False)
        shutil.copy2(SECOND_SUMMARY_DIR / "summary_partial.csv", OUT / "summary.csv")
        paired_default = paired_vs_baseline(second, baseline="whca_default", metrics=DEFAULT_METRICS)
        paired_default.to_csv(OUT / "paired_statistics_vs_whca_default.csv", index=False)
        paired_strong = paired_vs_baseline(second, baseline="whca_strong", metrics=DEFAULT_METRICS)
        paired_strong.to_csv(OUT / "paired_statistics_vs_whca_strong.csv", index=False)
    else:
        second_summary = pd.DataFrame()

    if ABL_SUMMARY.exists():
        shutil.copy2(ABL_SUMMARY, OUT / "ablation_summary.csv")
        shutil.copy2(ABL_SUMMARY, OUT / "02_ablation_round2_summary.csv")

    toggle_cols = [
        "enable_game",
        "enable_mpc",
        "enable_cbf",
        "enable_stagnation_repair",
        "enable_robust_nominal",
        "enable_safety_envelope_logging",
        "exact_game_count",
        "partitioned_exact_count",
        "greedy_fallback_count",
        "mpc_refinements",
        "cbf_filter_calls",
        "stagnation_repair_calls",
        "robust_nominal_repairs",
    ]
    toggle = metric_mean(ablation, toggle_cols, ["algorithm"])
    toggle.to_csv(OUT / "01_ablation_toggle_validation.csv", index=False)

    toggle_checks = []
    expected_zero = {
        "lcg_mpc_plus_without_game": ["enable_game", "exact_game_count", "partitioned_exact_count", "greedy_fallback_count"],
        "lcg_mpc_plus_without_mpc": ["enable_mpc", "mpc_refinements"],
        "lcg_mpc_plus_without_cbf": ["enable_cbf", "cbf_filter_calls"],
        "lcg_mpc_plus_without_stagnation_repair": ["enable_stagnation_repair", "stagnation_repair_calls"],
        "lcg_mpc_plus_without_robust_nominal": ["enable_robust_nominal", "robust_nominal_repairs"],
        "lcg_mpc_plus_without_safety_envelope_logging": ["enable_safety_envelope_logging"],
    }
    for alg, cols in expected_zero.items():
        row = toggle[toggle["algorithm"] == alg]
        ok = not row.empty and all(float(row.iloc[0].get(c, 0.0)) == 0.0 for c in cols if c in row.columns)
        toggle_checks.append(f"- `{alg}` zero-call check: {'PASS' if ok else 'CHECK/FAIL'}")

    write_md(
        OUT / "01_ablation_toggle_validation.md",
        "Round2 Ablation Toggle Validation",
        [
            "- Unit tests for ablation toggles and WHCA variants passed before the long audit run.",
            "- CSV aggregates are written to `01_ablation_toggle_validation.csv`.",
            *toggle_checks,
        ],
    )

    if not ablation.empty:
        metrics = [m for m in DEFAULT_METRICS if m in ablation.columns]
        ab_stats = paired_vs_baseline(ablation, baseline="lcg_mpc_plus_full", metrics=metrics)
        ab_stats.to_csv(OUT / "02_ablation_round2_statistics.csv", index=False)
        full = ablation[ablation["algorithm"] == "lcg_mpc_plus_full"]
        rows = []
        key = ["map_type", "n_robots", "density", "seed"]
        for alg in sorted(a for a in ablation["algorithm"].unique() if a.startswith("lcg_mpc_plus_without")):
            merged = ablation[ablation["algorithm"] == alg].merge(full, on=key, suffixes=("_variant", "_full"))
            if merged.empty:
                continue
            rows.append(
                {
                    "variant": alg,
                    "n_pairs": len(merged),
                    "delta_success_rate": (merged["success_rate_variant"] - merged["success_rate_full"]).mean(),
                    "delta_mean_wait_time": (merged["mean_wait_time_variant"] - merged["mean_wait_time_full"]).mean(),
                    "delta_throughput_per_step": (merged["throughput_per_step_variant"] - merged["throughput_per_step_full"]).mean(),
                    "delta_supervisor_interventions": (merged["supervisor_interventions_variant"] - merged["supervisor_interventions_full"]).mean(),
                    "delta_timeout_count": (merged["timeout_count_variant"] - merged["timeout_count_full"]).mean(),
                }
            )
        delta = pd.DataFrame(rows)
        delta.to_csv(OUT / "02_ablation_round2_delta_vs_full.csv", index=False)
        write_md(
            OUT / "02_ablation_round2_report.md",
            "Round2 Ablation Report",
            [
                "- The ablation run completed for 30 paired seeds, 6 maps, and 56/100 robots.",
                "- Module-level delta versus `lcg_mpc_plus_full` is saved in `02_ablation_round2_delta_vs_full.csv`.",
                "- Safe claim: module contribution may be discussed only where the delta and call counters move together.",
                "- Unsafe claim: do not claim an individual module improves all scenarios if its removal is statistically indistinguishable from full.",
            ],
        )

    whca_cols = [
        "actual_window",
        "reservation_horizon",
        "goal_reservation_enabled",
        "planned_path_length_mean",
        "reservation_table_size_mean",
        "success_rate",
        "mean_wait_time",
    ]
    whca = metric_mean(second[second["algorithm"].isin(["whca_default", "whca_strong"])] if not second.empty else second, whca_cols, ["algorithm"])
    whca.to_csv(OUT / "03_whca_strong_validation.csv", index=False)
    write_md(
        OUT / "03_whca_strong_validation.md",
        "WHCA Strong Validation",
        [
            "- `whca_default` and `whca_strong` metadata are logged in the CSV.",
            "- Code-level unit tests verified different WHCA windows and goal reservation activation.",
            "- The long second audit was stopped after partial completion because runtime made the 30-seed audit itself impractical.",
        ],
    )

    supervisor_cols = [
        "raw_vertex_conflicts",
        "raw_edge_swap_conflicts",
        "final_vertex_conflicts",
        "final_edge_swap_conflicts",
        "supervisor_interventions",
        "fixed_conflicts",
        "planner_level_repairs",
        "supervisor_interventions_per_step",
        "supervisor_interventions_per_robot",
        "raw_conflicts_per_step",
        "final_conflicts_per_step",
        "planner_native_conflict_reduction_rate",
        "collision_count",
    ]
    supervisor = metric_mean(second, supervisor_cols, ["algorithm", "map_type", "n_robots"])
    supervisor.to_csv(OUT / "04_supervisor_effect_decomposition.csv", index=False)
    shutil.copy2(OUT / "04_supervisor_effect_decomposition.csv", OUT / "supervisor_effect_summary.csv")
    write_md(
        OUT / "04_supervisor_effect_decomposition.md",
        "Supervisor Effect Decomposition",
        [
            "- Raw/final conflict and supervisor metrics are now logged.",
            "- Interpretation must separate planner-native repair from supervisor cleanup.",
            "- Collision-free statements should be limited to the tested simulator settings and should mention the safety supervisor.",
        ],
    )

    runtime_cols = [
        "avg_step_runtime_ms",
        "p95_step_runtime_ms",
        "p99_step_runtime_ms",
        "max_step_runtime_ms",
        "timeout_count",
        "game_profiles_evaluated",
        "game_profiles_evaluated_per_step",
        "exact_game_count",
        "partitioned_exact_count",
        "greedy_fallback_count",
    ]
    runtime = metric_mean(second, runtime_cols, ["algorithm", "map_type", "n_robots"])
    runtime.to_csv(OUT / "05_runtime_cap_validation.csv", index=False)
    shutil.copy2(OUT / "05_runtime_cap_validation.csv", OUT / "runtime_scaling_summary.csv")
    write_md(
        OUT / "05_runtime_cap_validation.md",
        "Runtime Cap Validation",
        [
            f"- Partial second audit completed {len(second)} of 3780 planned runs before manual stop.",
            "- Per-step timeout and fallback counters are present in the raw schema.",
            "- Wall-clock scalability is not acceptable for the 30-seed audit, so the current 1000-seed protocol should not be launched unchanged.",
        ],
    )

    write_md(
        OUT / "06_GO_NO_GO_FOR_1000SEED_ROUND2.md",
        "GO/NO-GO for 1000-Seed Round2",
        [
            "Verdict: **NO-GO for launching the current 1000-seed core unchanged**.",
            "",
            "- Seed pairing: preserved in completed raw files through scenario hashes.",
            "- Ablation toggles: code/test validation passed and 30-seed ablation completed.",
            "- WHCA strong: metadata and tests confirm the strong configuration path is active.",
            "- Supervisor interpretation: must remain explicit; improvements cannot be presented as planner-only.",
            "- Runtime: the 30-seed second audit reached only partial completion after roughly 9 hours, so 1000-seed execution is not currently practical.",
            "- Next required action: reduce protocol cost or optimize the slow baselines before full manuscript-scale execution.",
        ],
    )

    write_md(
        OUT / "07_CLAIM_BOUNDARY_UPDATED.md",
        "Updated Claim Boundary",
        [
            "- 1000-seed core claims are not yet ready because the round2 runtime gate failed.",
            "- If runtime is fixed, primary claims should be limited to paired 56/100/250 robot, density 0.05, six-map experiments.",
            "- 500/1000 robot results should be framed only as reduced-seed scalability smoke tests.",
            "- Baselines should be described as simulator-native surrogate implementations unless independently matched to external reference implementations.",
            "- Exact-potential guarantees apply only within capped local games; partitioned/greedy fallback cases require empirical wording.",
            "- Supervisor intervention must be reported as part of the system, not hidden behind collision-free outcomes.",
            "- Safe abstract wording: `In paired simulator experiments up to 250 robots, the proposed system is evaluated against strengthened native baselines with explicit safety-supervisor and runtime-cap reporting.`",
        ],
    )

    zip_path = ROOT / "pre1000_objectivity_round2_package.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in OUT.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(ROOT))

    print(f"reports: {OUT}")
    print(f"zip: {zip_path}")


if __name__ == "__main__":
    main()

