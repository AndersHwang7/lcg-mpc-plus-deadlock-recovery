# Inha University & RODIX Inc, Anders Hwang
from __future__ import annotations

import argparse
import csv
import json
import os
import signal
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mr_deadlock.experiments.runner import raw_summary_path, run_experiment
from mr_deadlock.experiments.seeds import expand_seeds
from mr_deadlock.utils.io import ensure_dir, read_yaml

STOP_REQUESTED = False


def _handle_stop(signum, frame) -> None:  # noqa: ARG001
    global STOP_REQUESTED
    STOP_REQUESTED = True
    print("\nGraceful shutdown requested. No new run batches will be started.", flush=True)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def scenario_overrides(config: dict[str, Any]) -> list[dict[str, Any]]:
    sweep = config.get("sweep", {})
    keys = list(sweep.keys())
    vals = [sweep[k] for k in keys]
    out = []
    for combo in product(*vals):
        row = dict(zip(keys, combo))
        if "density" in row:
            row["obstacle_density"] = row["density"]
        out.append(row)
    return out or [{}]


def all_jobs(config: dict[str, Any]) -> list[dict[str, Any]]:
    exp = config.get("experiment", {})
    jobs = []
    for override, alg, seed in product(scenario_overrides(config), exp.get("algorithms", []), expand_seeds(exp)):
        row = {
            "algorithm": alg,
            "seed": int(seed),
            "map_type": override.get("map_type", config.get("scenario", {}).get("map_type")),
            "n_robots": int(override.get("n_robots", config.get("scenario", {}).get("n_robots", 0))),
            "density": float(override.get("density", override.get("obstacle_density", config.get("scenario", {}).get("obstacle_density", 0.0)))),
            "scenario_override": override,
        }
        row["raw_path"] = str(raw_summary_path(config, alg, int(seed), override))
        jobs.append(row)
    return jobs


def job_key(row: dict[str, Any]) -> tuple:
    return (row["map_type"], int(row["n_robots"]), float(row["density"]), row["algorithm"], int(row["seed"]))


def existing_completed(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in jobs:
        path = Path(row["raw_path"])
        if path.exists() and path.stat().st_size > 0:
            done = dict(row)
            done["status"] = "completed"
            done["path"] = str(path)
            out.append(done)
    return out


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({k for row in rows for k in row.keys() if k != "scenario_override"})
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def current_seed_range(completed: list[dict[str, Any]]) -> str:
    if not completed:
        return "none"
    seeds = sorted({int(r["seed"]) for r in completed})
    return f"{seeds[0]}-{seeds[-1]} ({len(seeds)} distinct seeds with at least one completed run)"


def next_job(missing: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not missing:
        return None
    return sorted(missing, key=job_key)[0]


def read_timeout_rows(completed: list[dict[str, Any]]) -> int:
    count = 0
    for row in completed:
        try:
            df = pd.read_csv(row["raw_path"])
            if not df.empty and "timeout_count" in df.columns:
                count += int((pd.to_numeric(df["timeout_count"], errors="coerce").fillna(0) > 0).any())
        except Exception:
            continue
    return count


def parse_stop_at(value: str | None) -> float | None:
    if not value:
        return None
    return datetime.fromisoformat(value).timestamp()


def write_state(
    *,
    state_dir: Path,
    config_path: str,
    jobs: list[dict[str, Any]],
    completed: list[dict[str, Any]],
    failed: list[dict[str, Any]],
    start_time: float,
    start_iso: str,
    stop_reason: str,
    args,
) -> None:
    completed_keys = {job_key(r) for r in completed}
    failed_keys = {job_key(r) for r in failed}
    missing = [r for r in jobs if job_key(r) not in completed_keys and job_key(r) not in failed_keys]
    planned = len(jobs)
    coverage = len(completed) / max(1, planned) * 100.0
    elapsed = time.time() - start_time
    stop_iso = now_iso()
    timeout_rows = read_timeout_rows(completed)
    nxt = next_job(missing)
    stop_at_arg = f' --stop-at "{args.stop_at}"' if args.stop_at else ""
    resume_cmd = (
        f".\\.venv\\Scripts\\python.exe scripts\\run_resumable_1000seed_core.py "
        f"--config {config_path} --jobs {args.jobs} --max-hours {args.max_hours}"
        f"{stop_at_arg} --resume"
    )
    state_dir.mkdir(parents=True, exist_ok=True)
    write_csv(state_dir / "completed_runs.csv", completed)
    write_csv(state_dir / "missing_runs.csv", missing)
    write_csv(state_dir / "failed_runs.csv", failed)
    (state_dir / "NEXT_RUN_COMMAND.txt").write_text(resume_cmd + "\n", encoding="utf-8")
    state = {
        "start_time": start_iso,
        "stop_time": stop_iso,
        "elapsed_sec": elapsed,
        "planned_runs": planned,
        "completed_runs": len(completed),
        "coverage_percentage": coverage,
        "missing_runs": len(missing),
        "failed_runs": len(failed),
        "timeout_rows": timeout_rows,
        "current_seed_range_completed": current_seed_range(completed),
        "next_job": nxt,
        "selected_jobs": args.jobs,
        "max_hours": args.max_hours,
        "stop_reason": stop_reason,
        "current_time": stop_iso,
        "current_processing_block": "between batches",
        "safe_to_shut_down": True,
        "resume_command": resume_cmd,
    }
    (state_dir / "run_state.json").write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    next_line = "none" if nxt is None else f"{nxt['algorithm']} seed={nxt['seed']} map={nxt['map_type']} robots={nxt['n_robots']}"
    checkpoint = [
        "# Last Checkpoint",
        "",
        f"- start time: {start_iso}",
        f"- stop time: {stop_iso}",
        f"- current time: {stop_iso}",
        f"- elapsed time: {elapsed / 3600.0:.3f} hours",
        f"- planned runs: {planned}",
        f"- completed runs: {len(completed)}",
        f"- coverage percentage: {coverage:.2f}%",
        f"- missing runs: {len(missing)}",
        f"- failed runs: {len(failed)}",
        f"- timeout rows: {timeout_rows}",
        f"- current seed range completed: {current_seed_range(completed)}",
        "- current processing block: between batches",
        f"- next seed/scenario to run: {next_line}",
        f"- exact command to resume: `{resume_cmd}`",
        "- safe to shut down: YES",
        f"- stop reason: {stop_reason}",
    ]
    (state_dir / "last_checkpoint.md").write_text("\n".join(checkpoint) + "\n", encoding="utf-8")


def _run_one(payload: tuple[dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
    config, job = payload
    try:
        summary = run_experiment(config, job["algorithm"], int(job["seed"]), job["scenario_override"])
        out = dict(job)
        out.pop("scenario_override", None)
        out["status"] = "completed"
        out["path"] = job["raw_path"]
        out["runtime_sec"] = summary.get("runtime_sec", "")
        out["timeout_count"] = summary.get("timeout_count", 0)
        return out
    except Exception as exc:
        out = dict(job)
        out.pop("scenario_override", None)
        out["status"] = "failed"
        out["error"] = repr(exc)
        out["traceback"] = traceback.format_exc()
        return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--jobs", type=int, default=max(1, min(max((os.cpu_count() or 6) - 2, 4), 10)))
    parser.add_argument("--max-hours", type=float, default=13.5)
    parser.add_argument("--stop-at", default=None, help="Absolute ISO cutoff, e.g. 2026-06-17T14:30:00+09:00")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _handle_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_stop)

    config = read_yaml(args.config)
    config.setdefault("runtime", {})["resume_existing"] = True
    raw_dir = ensure_dir(config.get("experiment", {}).get("output_dir", "results/raw"))
    root = Path(raw_dir).parent if Path(raw_dir).name == "raw" else Path(raw_dir)
    state_dir = ensure_dir(root / "state")
    jobs = all_jobs(config)
    start_time = time.time()
    start_iso = now_iso()
    max_sec = max(0.0, args.max_hours) * 3600.0
    stop_at_ts = parse_stop_at(args.stop_at)

    completed = existing_completed(jobs)
    failed: list[dict[str, Any]] = []
    write_state(
        state_dir=state_dir,
        config_path=args.config,
        jobs=jobs,
        completed=completed,
        failed=failed,
        start_time=start_time,
        start_iso=start_iso,
        stop_reason="initialized",
        args=args,
    )

    flush_every = int(config.get("runtime", {}).get("flush_every_n_runs", 20))
    checkpoint_every = int(config.get("runtime", {}).get("checkpoint_every_n_runs", 20))
    done_keys = {job_key(r) for r in completed}
    pending = [j for j in jobs if job_key(j) not in done_keys]
    submitted_since_checkpoint = 0
    last_checkpoint_time = time.time()
    stop_reason = "completed"

    while pending and not STOP_REQUESTED:
        if max_sec and (time.time() - start_time) >= max_sec:
            stop_reason = "max-hours reached before starting next batch"
            break
        if stop_at_ts is not None and time.time() >= stop_at_ts:
            stop_reason = "stop-at reached before starting next batch"
            break
        batch = pending[: max(1, args.jobs)]
        pending = pending[len(batch):]
        with ProcessPoolExecutor(max_workers=max(1, args.jobs)) as ex:
            futures = [ex.submit(_run_one, (config, job)) for job in batch]
            for fut in as_completed(futures):
                row = fut.result()
                if row.get("status") == "completed":
                    completed.append(row)
                else:
                    failed.append(row)
                submitted_since_checkpoint += 1
                checkpoint_due = submitted_since_checkpoint % max(1, flush_every) == 0 or (time.time() - last_checkpoint_time) >= 600.0
                if checkpoint_due:
                    write_state(
                        state_dir=state_dir,
                        config_path=args.config,
                        jobs=jobs,
                        completed=completed,
                        failed=failed,
                        start_time=start_time,
                        start_iso=start_iso,
                        stop_reason="running checkpoint",
                        args=args,
                    )
                    last_checkpoint_time = time.time()
                if submitted_since_checkpoint % max(1, checkpoint_every) == 0:
                    print(f"checkpoint: completed={len(completed)} failed={len(failed)} planned={len(jobs)}", flush=True)
        if STOP_REQUESTED:
            stop_reason = "Ctrl+C or termination signal"
            break

    if STOP_REQUESTED and stop_reason == "completed":
        stop_reason = "Ctrl+C or termination signal"
    if pending and stop_reason == "completed":
        stop_reason = "stopped with pending jobs"
    write_state(
        state_dir=state_dir,
        config_path=args.config,
        jobs=jobs,
        completed=existing_completed(jobs),
        failed=failed,
        start_time=start_time,
        start_iso=start_iso,
        stop_reason=stop_reason,
        args=args,
    )
    print(f"stop_reason={stop_reason}")
    print(f"state={state_dir}")
    print((state_dir / "NEXT_RUN_COMMAND.txt").read_text(encoding="utf-8").strip())


if __name__ == "__main__":
    main()

