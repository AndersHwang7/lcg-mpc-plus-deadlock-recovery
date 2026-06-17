# Formula-to-Code Alignment for Draft 2.0

This document maps the formula-strengthened manuscript to the Python research code.

## 1. Workspace and robot state

Manuscript notation:

```latex
G=(V,E), \quad \mathcal R=\{1,\dots,N\}, \quad p_i(t)\in V
```

Code:

- `core/grid.py::GridMap`
- `core/robot.py::Robot.pos`
- `maps/*` for corridor, intersection, warehouse, bottleneck, ring, and random maps.

## 2. Nominal path and admissible move set

Manuscript notation:

```latex
P_i=(v_{i,0},\dots,v_{i,L_i}), \qquad
\mathcal A_i(t)=\{p_i(t)\}\cup\mathcal N_4(p_i(t))
```

Code:

- `planners/astar.py::AStar.search`
- `core/grid.py::GridMap.neighbors4`
- `core/robot.py::Robot.next_on_path`

## 3. Vertex and edge conflict

Manuscript notation:

```latex
p_i(t+1)=p_j(t+1), \qquad
p_i(t)=p_j(t+1) \land p_j(t)=p_i(t+1)
```

Code:

- `planners/common.py::resolve_vertex_edge_conflicts`
- `core/simulator.py::Simulator._validate_moves`

The simulator uses the same safety supervisor for all algorithms to ensure fair comparison.

## 4. Dependency graph and persistent SCC deadlock

Manuscript notation:

```latex
D_t=(\mathcal R,E_D(t)),\quad i\to j
```

and persistent no-progress SCC condition:

```latex
C\in\operatorname{SCC}(D_t),\quad
\Delta_i(t,t+\tau)\le\epsilon,\ \forall i\in C
```

Code:

- `deadlock/dependency_graph.py::build_dependency_graph`
- `deadlock/scc.py::tarjan_scc`
- `deadlock/detector.py::DeadlockDetector`

## 5. Exact-potential conflict game

Manuscript notation:

```latex
\Phi(a)=\sum_i J_i(a_i,a_{-i}) + J_{\mathrm{shared}}(a)
```

with exact-potential property:

```latex
U_i(a_i',a_{-i})-U_i(a_i,a_{-i})
= -\left[\Phi(a_i',a_{-i})-\Phi(a_i,a_{-i})\right].
```

Code:

- `game/potential_game.py::PotentialGameSelector.potential`
- `game/potential_game.py::PotentialGameSelector.utility`
- `game/potential_game.py::PotentialGameSelector.verify_exact_potential`
- `tests/test_potential_game.py`

The implementation uses an identical-interest exact-potential game, which is mathematically conservative and appropriate for a cooperative fleet.

## 6. Local path-index MPC/QP

Manuscript notation:

```latex
x_i=[s_i,v_i]^\top,\quad
s_{i,k+1}=s_{i,k}+v_{i,k}\Delta t + \frac12 a_{i,k}\Delta t^2.
```

Code:

- `mpc/local_qp.py::LocalMPCRefiner`

The code implements a lightweight timing-refinement QP over relaxed immediate execution variables. It is intentionally localized and optional. If CVXPY/OSQP is unavailable, it uses a deterministic heuristic fallback.

## 7. Metrics

Manuscript metrics:

- success rate
- deadlock rate
- resolution/recovery behavior
- throughput
- waiting time
- runtime
- fairness

Code:

- `experiments/metrics.py::MetricsCollector.summary`
- `experiments/aggregate.py`
- `visualization/plot_results.py`

The code distinguishes paper-level throughput `throughput_per_step` from engineering runtime throughput `throughput_wallclock`.
