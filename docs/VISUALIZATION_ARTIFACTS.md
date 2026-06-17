# Inha University & RODIX Inc, Anders Hwang

# Visualization Artifacts Guide

This document describes the visualization materials included in the GitHub repository and how they should be used in a paper, presentation, or reproduction package.

## Included Materials

The repository contains a curated `visualizations/` directory with three artifact groups:

| Path | Purpose |
| --- | --- |
| `visualizations/interactive_4way_html/` | Browser-based four-way behavior comparisons for representative traffic scenarios. |
| `visualizations/paper_figures_1000seed/` | Publication-oriented PNG/PDF figures from the completed 1000-seed paired experiment. |
| `visualizations/captions/` | Draft captions for figures and tables. |

## Interactive Behavior Comparisons

The HTML visualizations compare four planners under identical map, seed, robot count, and start-goal assignments:

1. WHCA best preregistered
2. IMPC-DR-lite
3. MPC-CBF-lite
4. LCG-MPC+

The five included cases cover ring crossing, intersection crossing, bottleneck swap, warehouse aisles, and corridor opposing-flow scenarios. These animations are useful for inspecting qualitative behavior such as local congestion, waiting patterns, safety-supervisor corrections, and recovery behavior after potential deadlock formation.

To view them locally, open:

```text
visualizations/interactive_4way_html/index.html
```

No web server is required because each HTML file is self-contained.

## Paper Figure Set

The `paper_figures_1000seed/` directory contains both `.png` and `.pdf` versions of the manuscript figures. The current set covers:

- success rate,
- mean wait time,
- throughput per step,
- average step runtime,
- supervisor interventions,
- Jain wait fairness.

Each metric is separated into 56-robot and 100-robot figures. Error bars represent bootstrap 95% confidence intervals.

## Interpretation Notes

The HTML animations are qualitative demonstrations. Manuscript claims should rely on the final CSV summaries, paired statistical tests, and paper figures generated from the completed 1000-seed experiment.

The `fairness_jain_wait` metric should be interpreted carefully because a high fairness score can indicate uniformly low waits or uniformly high waits. It should be read together with mean wait time, throughput, and success rate.

Supervisor intervention counts indicate how often candidate planner actions required safety correction or recovery assistance. They should not be interpreted as final collision counts. The final `collision_count` metric reports residual executed collisions after supervision.

The `planner_native_conflict_reduction_rate` metric is excluded from the core manuscript interpretation because the current before/after logging path is not reliable enough for a primary result claim.

## Regeneration Commands

Regenerate the four-way HTML suite:

```bash
python scripts/visualize_suite.py --config configs/visual_4way_5cases.yaml
```

Regenerate paper-ready figures and captions from existing final result CSV files:

```bash
python scripts/prepare_paper_ready_1000seed.py
```

The 1000-seed experiment itself has already been completed for this package. Do not rerun the 1000-seed sweep unless a new experimental design or corrected logging pipeline is intentionally introduced.
