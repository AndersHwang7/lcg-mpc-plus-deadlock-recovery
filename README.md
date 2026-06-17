# MR Deadlock Thesis Simulator

A reproducible Python research platform for the doctoral/Sci-level topic:

**Localized Conflict-Game Model Predictive Control for Deadlock-Free Large-Scale Multi-Robot Traffic**

This repository provides a complete experimental scaffold, not a one-file demo. It includes:

- grid-based large-scale multi-robot simulator,
- map generators for corridor, intersection, warehouse, bottleneck, random maps,
- baseline planners: A*+wait, prioritized planning, simplified PIBT, simplified WHCA*,
- proposed planners: CLRR, CLRR+Potential Game, CLRR-HMPC,
- SCC-based deadlock detector,
- potential-game tie-breaking module,
- optional local MPC/QP refinement hook using CVXPY/OSQP,
- batch experiment runner,
- metrics, statistical summaries, and paper-style plotting scripts,
- pytest tests.

The implementation is intentionally lightweight so that 100--1000 robot experiments can be run without ROS2/Gazebo.

---

## 1. Recommended environment

### Windows recommendation

Use **WSL2 Ubuntu + VSCode**.

### Python recommendation

Python 3.11 or 3.12.

### Option A: uv

```bash
cd mr_deadlock_thesis
uv venv
uv pip install -e ".[dev]"
```

### Option B: venv + pip

```bash
cd mr_deadlock_thesis
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows
pip install -e ".[dev]"
```

---

## 2. Quick start

Run a single experiment:

```bash
python scripts/run_single.py --config configs/quick_100.yaml
```

Run a scale batch:

```bash
python scripts/run_batch.py --config configs/batch_scale.yaml
```

Summarize results:

```bash
python scripts/analyze_results.py --input results/raw --output results/summary
```

Create paper figures:

```bash
python scripts/make_figures.py --input results/summary/summary.csv --output results/figures
```

Run tests:

```bash
pytest -q
```

---

## 3. Algorithms

Available algorithm names:

```text
astar_wait
prioritized
pibt
whca
orca_lite
dmpc_lite
mpc_cbf_lite
impc_dr_lite
clrr
clrr_game
clrr_hmpc
lcg_mpc_plus
```

Recommended first paper comparison:

```text
astar_wait, prioritized, pibt, whca, clrr, clrr_game, clrr_hmpc
```

`clrr_hmpc` uses the CLRR + game layer and attempts optional local MPC/QP refinement when CVXPY is available. `lcg_mpc_plus` is the recommended final proposed algorithm: it adds robust continuous-envelope nominal control, bounded/partitioned exact local games, stagnation repair, and optional strict CBF filtering. The `*_lite` baselines are simulator-native ORCA/DMPC/MPC-CBF/IMPC-DR surrogates for identical-simulator comparison, not official third-party code ports.

---

## 4. Metrics

The runner logs:

- success_rate
- completed
- deadlock_events
- unresolved_deadlocks
- mean_travel_time
- mean_wait_time
- makespan
- throughput
- runtime_sec
- avg_step_runtime_ms
- p95_step_runtime_ms
- collision_count
- retreat_actions
- fairness_jain
- average_path_stretch

---

## 5. Thesis workflow

1. Verify baseline behavior on `quick_100.yaml`.
2. Run `batch_scale.yaml` with 100, 250, 500, 750, 1000 robots.
3. Inspect `results/raw` and `results/summary`.
4. Use `results/figures` for paper plots.
5. Add additional ablation configs:
   - no game layer,
   - no retreat,
   - no deadlock detector,
   - different horizon length,
   - different conflict radius.

---

## 6. Notes

This code is a research simulator. It is designed for algorithmic validation and reproducible experiments, not direct deployment on physical robots. For future ROS2/Gazebo integration, keep the `planners`, `deadlock`, `game`, and `mpc` modules and replace only the simulator/executor layer.
---

## 7. 100-seed / 1000-seed experiments

This version supports compact seed ranges for large paired experiments. For a 100-seed paper-ready sweep:

```bash
python scripts/run_batch.py --config configs/optimized_100seed.yaml --jobs 4 --resume
python scripts/analyze_results.py --input results/raw --output results/summary
python scripts/statistical_compare.py --input results/raw --output results/summary --baseline whca
```

For the final 1000-seed target, use the full paper pipeline so raw data, statistics, figures, and tables are regenerated together:

```bash
python scripts/run_paper_pipeline.py --config configs/paper_fast_1000seed_core.yaml --jobs 8 --resume
python scripts/run_paper_pipeline.py --config configs/paper_1000seed_final.yaml --jobs 8 --resume
```

The same seed is reused across algorithms, maps, and start-goal generation, enabling paired statistical tests. See `docs/100SEED_AND_VISUALIZATION_GUIDE.md`.

---

## 8. Split-screen behavior visualization, not plots

Create a lightweight HTML Canvas simulator that compares two algorithms side-by-side:

```bash
python scripts/visualize_compare.py --config configs/visual_compare.yaml
```

The output HTML shows moving circles/squares as robots, faint route-attempt lines, raw versus safety-supervised one-step decisions, and live values such as completion, waiting, fixed conflicts, retreat actions, game profiles, and MPC checks.



---

## 9. Final SCI package additions

This release includes the following completion-oriented additions:

- `lcg_mpc_plus`: recommended final proposed planner.
- Continuous AMR safety envelope: circular footprint, swept-volume, acceleration/speed bounds, and sensing uncertainty.
- Simulator-native baseline family: `orca_lite`, `dmpc_lite`, `mpc_cbf_lite`, `impc_dr_lite`.
- 5-case split-screen HTML animation suite:

```bash
python scripts/visualize_suite.py --config configs/visual_5cases.yaml --max-frames 160
```

- End-to-end paper artifact pipeline:

```bash
python scripts/run_paper_pipeline.py --config configs/paper_fast_1000seed_core.yaml --jobs 8 --resume
```

A compact included validation run is stored under `results/final_validation_quick`. It verifies the pipeline and produces figures/tables, but the final manuscript claim should be regenerated from a 100-seed or 1000-seed sweep. See `docs/FINAL_SCI_RELEASE_REPORT.md`.
