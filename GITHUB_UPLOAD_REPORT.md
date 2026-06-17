# Inha University & RODIX Inc, Anders Hwang

# GitHub Upload Readiness Report

## Recommendation

Do not upload the entire working directory exactly as-is. The current directory contains a local virtual environment, intermediate experiment states, raw/progress CSV files, old ZIP bundles, and generated HTML/figure artifacts. These are useful locally, but they will make the GitHub repository unnecessarily large and noisy.

Recommended GitHub strategy:

1. Upload the code, configs, tests, documentation, and this report to the GitHub repository.
2. Upload `paper_ready_1000seed_final.zip` as a GitHub Release asset, or keep it in the repository only if you intentionally want a self-contained package in Git history.
3. Do not upload `.venv/`, raw run directories, checkpoint state, progress folders, partial folders, or old pre-1000 ZIP files.

This folder has been initialized as a local Git repository on branch `main`, but no commit or remote upload has been performed yet. Create an empty GitHub repository first, then add the GitHub remote and commit/push the selected files.

## Suggested GitHub Repository Description

LCG-MPC+ multi-robot deadlock-recovery simulator and 1000-seed paired evaluation package, including WHCA best, IMPC-DR-lite, MPC-CBF-lite, bootstrap-CI paper figures, statistical comparison tables, and reproducible experiment scripts.

## Suggested GitHub Topics

`multi-robot-systems`, `deadlock-recovery`, `model-predictive-control`, `potential-game`, `robotics-simulation`, `path-planning`, `python`, `research-code`, `reproducible-research`

## Project Summary

This project is a Python research simulator for large-scale multi-AMR traffic and deadlock recovery. It implements grid-based multi-robot simulation, multiple baseline planners, the proposed LCG-MPC+ planner family, common safety-supervisor accounting, paired experiment runners, statistical analysis, paper-ready tables, bootstrap confidence interval figures, and HTML Canvas behavior visualizations.

The completed 1000-seed core package evaluates four simulator-native algorithms:

- `whca_best_preregistered`
- `impc_dr_lite`
- `mpc_cbf_lite`
- `lcg_mpc_plus`

The final paper-ready package is:

```text
paper_ready_1000seed_final.zip
```

## Current Completion State

- Full 1000-seed core experiment: complete
- Planned runs: 48,000
- Completed runs: 48,000
- Missing runs: 0
- Failed runs: 0
- Timeout rows retained and summarized: 500
- Paper-ready package generated: yes
- New experiments required before upload: no

## Development Environment

Recommended:

- Python 3.11 or 3.12
- Windows PowerShell, WSL2 Ubuntu, or Linux/macOS shell
- Git

Install from source:

```bash
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows PowerShell
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Core dependencies are declared in `pyproject.toml`:

- numpy
- scipy
- pandas
- matplotlib
- networkx
- pyyaml
- tqdm
- pytest/ruff/black for development
- optional cvxpy/osqp for MPC-related paths

## Important Commands

Run tests:

```bash
pytest -q
```

Run a quick single experiment:

```bash
python scripts/run_single.py --config configs/quick_100.yaml
```

Run a batch experiment:

```bash
python scripts/run_batch.py --config configs/batch_scale.yaml
```

Generate two-to-four algorithm HTML visualizations:

```bash
python scripts/visualize_suite.py --config configs/visual_4way_5cases.yaml --stride 1 --path-horizon 10
```

Regenerate the paper-ready package from completed final CSV files only:

```bash
python scripts/prepare_paper_ready_1000seed.py
```

Important: do not rerun the 1000-seed experiment unless intentionally starting a new study. The paper-ready package is built from:

```text
results/paper_1000seed_core_resumable/final/raw_combined.csv
results/paper_1000seed_core_resumable/final/summary.csv
results/paper_1000seed_core_resumable/final/paired_statistics_vs_whca_best.csv
results/paper_1000seed_core_resumable/final/paired_statistics_vs_impc_dr_lite.csv
results/paper_1000seed_core_resumable/final/paired_statistics_vs_mpc_cbf_lite.csv
```

## Folder Structure

```text
configs/
  Experiment and visualization YAML configurations.

docs/
  Validation notes, upgrade notes, experiment guides, and manuscript-support documents.

scripts/
  CLI entry points for running experiments, resumable 1000-seed execution, analysis, paper-ready packaging, plotting, and HTML visualization generation.

src/mr_deadlock/
  Main Python package.

src/mr_deadlock/core/
  Grid, robot, simulator, dynamics, and reservation-table logic.

src/mr_deadlock/planners/
  Baseline planners and LCG-MPC+ planner implementations.

src/mr_deadlock/deadlock/
  Dependency graph, SCC detection, and deadlock detection.

src/mr_deadlock/game/
  Local game and potential-game related logic.

src/mr_deadlock/mpc/
  Local QP/MPC refinement utilities.

src/mr_deadlock/experiments/
  Batch runner, metrics, aggregation, seed handling, and paired statistics.

src/mr_deadlock/visualization/
  HTML Canvas comparison viewer and result plotting helpers.

tests/
  Pytest tests for planners, simulator behavior, metrics, visualization traces, and validation toggles.

results/
  Generated results. Most raw/intermediate outputs should not be committed to GitHub. Use the paper-ready ZIP as the portable result artifact.
```

## Paper-Ready Result Package

`paper_ready_1000seed_final.zip` contains the key paper-ready artifacts, including:

- final raw/summary/paired statistics CSV files
- detailed `FINAL_1000SEED_CORE_REPORT.md`
- bootstrap 95% CI figures
- 56-robot and 100-robot separated figures
- key LCG-MPC+ vs baseline comparison tables
- timeout distribution tables for the 500 timeout rows
- figure and table caption drafts
- source code, configs, and tests with attribution headers

Recommended use:

- Put code and documentation in the GitHub repository.
- Attach `paper_ready_1000seed_final.zip` to a GitHub Release named something like `1000-seed paper-ready package`.

## Upload Checklist

Before first commit:

```bash
git status --short
git add README.md pyproject.toml .gitignore GITHUB_UPLOAD_REPORT.md configs docs scripts src tests
git add paper_ready_1000seed_final.zip
git status --short
```

If you prefer to keep the ZIP out of Git history, do not run `git add paper_ready_1000seed_final.zip`; upload it as a Release asset after pushing the repository.

Recommended validation before pushing:

```bash
python -m py_compile scripts/prepare_paper_ready_1000seed.py
pytest -q
```

## Files To Avoid Uploading

Avoid committing:

- `.venv/`
- `.pytest_cache/`
- `__pycache__/`
- old ZIP bundles such as `pre1000_objectivity_*_package.zip`
- intermediate `results/**/raw/`
- checkpoint `results/**/state/`
- progress and partial folders
- ad hoc combined raw CSV files unless explicitly needed for a release archive

## Notes For README Or GitHub Page

Recommended short README paragraph:

> This repository provides a reproducible Python simulator and paper artifact pipeline for LCG-MPC+, a localized conflict-game MPC approach for multi-robot deadlock recovery. The included paper-ready package summarizes a completed 48,000-run, 1000-seed paired evaluation against WHCA best, IMPC-DR-lite, and MPC-CBF-lite, with bootstrap confidence intervals, separated 56/100-robot figures, timeout accounting, and manuscript-ready captions.

## Caution About Claims

Use metric-specific wording. Do not claim universal dominance. MPC-CBF-lite advantages should remain visible where observed. `fairness_jain_wait` measures equality of waiting distribution, not lower waiting by itself. `final collision_count` is a supervised system-level outcome after common safety validation, not planner-only safety proof.
