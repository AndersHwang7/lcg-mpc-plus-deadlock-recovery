# Table Captions

## Table Caption Drafts

1. Core paired comparison of LCG-MPC+ against baselines. Rows summarize metric-specific paired differences against WHCA best, IMPC-DR-lite, and MPC-CBF-lite. Direction columns indicate whether higher or lower values are preferable.
2. Detailed map-wise paired statistics. For each map and robot scale, the table reports mean differences, relative change, win/loss/tie rates, Holm-adjusted p-values, and bootstrap 95% confidence intervals.
3. Timeout distribution. The table summarizes all 500 timeout rows by algorithm, map type, and robot scale. Timeout rows are retained in the analysis and are interpreted as runtime-budget/fallback events.
4. Metric uncertainty summary. The table reports mean, standard error, and bootstrap 95% confidence intervals for each algorithm, map type, robot scale, and main metric.
5. Supervisor and final-collision accounting. The table should be read as system-level supervised outcomes after common move validation, not as planner-only safety proof.
