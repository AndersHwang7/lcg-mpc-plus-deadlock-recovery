# Inha University & RODIX Inc, Anders Hwang
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mr_deadlock.experiments.aggregate import load_raw


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/paper_1000seed_core_precheck_40run.yaml")
    ap.add_argument("--core-config", default="configs/paper_1000seed_core_resumable.yaml")
    ap.add_argument("--jobs", type=int, default=None)
    args = ap.parse_args()

    cpu = os.cpu_count() or 6
    jobs = args.jobs if args.jobs is not None else min(max(cpu - 2, 4), 10)
    jobs = max(1, int(jobs))
    out = PROJECT_ROOT / "results" / "paper_1000seed_core_resumable" / "precheck"
    out.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "run_paper_pipeline.py"),
        "--config",
        args.config,
        "--jobs",
        str(jobs),
        "--resume",
        "--baseline",
        "whca_best_preregistered",
    ]
    subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)

    raw = load_raw(out / "raw")
    raw.to_csv(out / "runtime_precheck.csv", index=False)
    runtimes = pd.to_numeric(raw.get("runtime_sec", pd.Series(dtype=float)), errors="coerce").dropna()
    mean = float(runtimes.mean()) if len(runtimes) else 0.0
    p95 = float(runtimes.quantile(0.95)) if len(runtimes) else 0.0
    sample_count = len(raw)
    planned_total = 1000 * 2 * 6 * 4
    est_serial_hours = mean * planned_total / 3600.0
    est_jobs_hours = est_serial_hours / max(1, jobs)
    within_14h = est_jobs_hours <= 14.0
    recommended_jobs = jobs
    if not within_14h and jobs < 10:
        recommended_jobs = min(10, max(jobs + 1, int(est_serial_hours / 13.5) + 1))
    recommended_max_hours = 13.5
    resume = (
        f".\\.venv\\Scripts\\python.exe scripts\\run_resumable_1000seed_core.py "
        f"--config {args.core_config} --jobs {recommended_jobs} --max-hours {recommended_max_hours} --resume"
    )
    lines = [
        "# Runtime Precheck",
        "",
        f"- detected cpu count: {cpu}",
        f"- selected jobs: {jobs}",
        f"- sample run count: {sample_count}",
        f"- mean runtime per run: {mean:.3f} sec",
        f"- p95 runtime per run: {p95:.3f} sec",
        f"- estimated total runtime: {est_serial_hours:.2f} serial hours",
        f"- estimated runtime with selected jobs: {est_jobs_hours:.2f} hours",
        f"- 14h 내 완료 가능 여부: {'YES' if within_14h else 'NO'}",
        f"- recommended jobs: {recommended_jobs}",
        f"- recommended max-hours: {recommended_max_hours}",
        f"- recommended resume command: `{resume}`",
        "",
        "Note: the instruction says 40-run dry timing, but the listed Cartesian product is 80 runs; this precheck uses all listed factors.",
    ]
    (out / "runtime_precheck.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

