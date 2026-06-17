# Inha University & RODIX Inc, Anders Hwang
# 파일명: run_paper_pipeline.py
# 목적 및 역할:
# batch 실행부터 raw 통합, paired 통계, 그림, 논문 표까지 한 번에 재현한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pandas as pd

from mr_deadlock.experiments.aggregate import load_raw, summarize
from mr_deadlock.experiments.batch import run_batch
from mr_deadlock.experiments.seeds import expand_seeds
from mr_deadlock.experiments.statistics import DEFAULT_METRICS, paired_vs_baseline
from mr_deadlock.utils.io import ensure_dir, read_yaml
from mr_deadlock.visualization.plot_results import make_figures


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/paper_fast_1000seed_core.yaml")
    ap.add_argument("--jobs", type=int, default=None)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--skip-run", action="store_true", help="Only re-analyze existing raw CSV files")
    ap.add_argument("--baseline", default="whca")
    args = ap.parse_args()

    cfg = read_yaml(args.config)
    exp = cfg.get("experiment", {})
    if args.resume:
        cfg.setdefault("runtime", {})["resume_existing"] = True
    raw_dir = ensure_dir(exp.get("output_dir", "results/raw"))
    root = Path(raw_dir).parent if Path(raw_dir).name == "raw" else Path(raw_dir)
    summary_dir = ensure_dir(root / "summary")
    fig_dir = ensure_dir(root / "figures")
    table_dir = ensure_dir(root / "tables")
    name = exp.get("name", "paper")
    seeds = expand_seeds(exp)

    if not args.skip_run:
        print(f"Experiment={name}, seeds={len(seeds)}, algorithms={exp.get('algorithms')}, raw={raw_dir}")
        summaries = run_batch(cfg, n_jobs=args.jobs)
        pd.DataFrame(summaries).to_csv(Path(raw_dir) / f"{name}_combined.csv", index=False)

    raw = load_raw(raw_dir)
    if raw.empty:
        raise SystemExit(f"No raw CSV files found in {raw_dir}")
    raw_combined = Path(summary_dir) / "raw_combined.csv"
    summary_csv = Path(summary_dir) / "summary.csv"
    raw.to_csv(raw_combined, index=False)
    summary = summarize(raw)
    summary.to_csv(summary_csv, index=False)

    paired = paired_vs_baseline(raw, baseline=args.baseline, metrics=DEFAULT_METRICS)
    paired_csv = Path(summary_dir) / f"paired_vs_{args.baseline}.csv"
    paired.to_csv(paired_csv, index=False)

    make_figures(summary_csv, fig_dir)

    subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "generate_paper_tables.py"),
            "--raw",
            str(raw_dir),
            "--summary",
            str(summary_csv),
            "--paired",
            str(paired_csv),
            "--output",
            str(table_dir),
        ],
        check=True,
    )

    manifest = root / "PIPELINE_MANIFEST.md"
    manifest.write_text(
        "# Reproducible paper pipeline output\n\n"
        f"- config: `{args.config}`\n"
        f"- raw directory: `{raw_dir}`\n"
        f"- combined raw: `{raw_combined}`\n"
        f"- summary: `{summary_csv}`\n"
        f"- paired statistics: `{paired_csv}`\n"
        f"- figures: `{fig_dir}`\n"
        f"- tables: `{table_dir}`\n"
        f"- rows analyzed: {len(raw)}\n"
        f"- seed count in config: {len(seeds)}\n",
        encoding="utf-8",
    )
    print(f"Pipeline completed. Manifest: {manifest}")


if __name__ == "__main__":
    main()

