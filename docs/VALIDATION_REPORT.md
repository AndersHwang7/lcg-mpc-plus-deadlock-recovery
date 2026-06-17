# Validation Report for MR Deadlock Thesis Code v2

This report summarizes the code-level corrections made after aligning the source code with the formula-strengthened second manuscript draft.

## Main corrections

1. **Throughput metric corrected**
   - Before: throughput was computed as completed tasks per wall-clock second.
   - After: `throughput_per_step` is computed as completed tasks per simulated step, while `throughput_wallclock` is retained separately.

2. **Persistent SCC deadlock detector strengthened**
   - Added no-progress counters.
   - Added SCC age tracking.
   - Added explicit `ConflictSet` records.
   - Added event duration support.

3. **Exact-potential game made verifiable**
   - Added `PotentialGameSelector.verify_exact_potential`.
   - Added unit test for the exact-potential property.
   - The game is implemented as an identical-interest exact-potential game for mathematical safety.

4. **Safety supervisor corrected**
   - Completed robots are not treated as active blockers in one-shot experiments.
   - Vertex and edge-swap conflicts are repaired iteratively to avoid secondary conflicts.

5. **LCG-MPC / CLRR-HMPC aligned with Draft 2.0**
   - Added activation mode: `persistent` or `candidate`.
   - Added configurable nominal layer: `pibt`, `whca`, or `prioritized`.
   - Added localized game profile counting and MPC status logging.

6. **Local MPC/QP made non-destructive**
   - If the game profile is already one-step feasible, local MPC certifies it instead of unnecessarily suppressing motions.
   - QP/OSQP is used only when there is a local profile conflict or when an explicit extension is needed.

## Validation commands

```bash
PYTHONPATH=src pytest -q
PYTHONPATH=src python -m compileall -q src scripts tests
PYTHONPATH=src python scripts/validate_project.py --config configs/quick_100.yaml --algorithm clrr_hmpc
```

Expected checks:

- Unit tests pass.
- Exact-potential property returns true.
- Single-run smoke experiment produces a valid CSV summary.

## SCI paper usage note

The current project is suitable as a reproducible research-code foundation. Before using the output in the final paper, run large-scale experiments with at least 20-30 seeds per scenario and report confidence intervals and statistical tests.
