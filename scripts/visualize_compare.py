# Inha University & RODIX Inc, Anders Hwang
# 파일명: visualize_compare.py
# 목적 및 역할:
# 여러 알고리즘을 동일 seed/start-goal set에서 나란히 실행해 HTML Canvas 동작 시각화를 만든다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import argparse
from mr_deadlock.utils.io import read_yaml
from mr_deadlock.visualization.compare_viewer import save_comparison_html


DISPLAY_NAMES = {"lcg_mpc_plus_full_v3": "lcg_mpc_plus"}


def _display_name(config: dict, algorithm: str) -> str:
    labels = {**DISPLAY_NAMES, **dict(config.get("experiment", {}).get("algorithm_labels", {}))}
    return labels.get(algorithm, algorithm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/visual_compare.yaml")
    ap.add_argument("--algorithms", nargs="+", default=None, metavar="ALGORITHM")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--map-type", default=None)
    ap.add_argument("--n-robots", type=int, default=None)
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--height", type=int, default=None)
    ap.add_argument("--max-steps", type=int, default=None)
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--path-horizon", type=int, default=10)
    ap.add_argument("--output", default=None)
    args = ap.parse_args()

    cfg = read_yaml(args.config)
    exp = cfg.get("experiment", {})
    algs = args.algorithms or exp.get("algorithms", ["whca", "clrr_hmpc"])
    if not 2 <= len(algs) <= 4:
        raise SystemExit("visualize_compare requires 2 to 4 algorithms")
    seed = int(args.seed if args.seed is not None else exp.get("seeds", [0])[0])
    override = {}
    for key, value in {
        "map_type": args.map_type,
        "n_robots": args.n_robots,
        "width": args.width,
        "height": args.height,
        "max_steps": args.max_steps,
    }.items():
        if value is not None:
            override[key] = value
    scenario = cfg.get("scenario", {})
    out_algs = [_display_name(cfg, alg) for alg in algs]
    out = args.output or f"results/visualizations/{scenario.get('map_type', 'scenario')}_{'_vs_'.join(out_algs)}_seed{seed}.html"
    path = save_comparison_html(
        cfg,
        algorithms=list(algs),
        seed=seed,
        output_path=out,
        scenario_override=override or None,
        max_frames=args.max_frames,
        stride=args.stride,
        path_horizon=args.path_horizon,
    )
    print(f"Saved visual comparison to {path}")


if __name__ == "__main__":
    main()

