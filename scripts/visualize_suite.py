# Inha University & RODIX Inc, Anders Hwang
# 파일명: visualize_suite.py
# 목적 및 역할:
# visual_5cases.yaml에 정의된 다섯 개 이상의 case를 읽어 multi-panel HTML과 index를 만든다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mr_deadlock.utils.io import read_yaml, ensure_dir
from mr_deadlock.visualization.compare_viewer import save_comparison_html


DISPLAY_NAMES = {"lcg_mpc_plus_full_v3": "lcg_mpc_plus"}


def _safe_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)


def _display_name(config: dict, algorithm: str) -> str:
    labels = {**DISPLAY_NAMES, **dict(config.get("experiment", {}).get("algorithm_labels", {}))}
    return labels.get(algorithm, algorithm)


def write_index(paths: list[Path], output_dir: Path, title: str) -> Path:
    items = "\n".join(
        f'<li><a href="{p.name}">{p.stem}</a></li>' for p in paths
    )
    html = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:system-ui,sans-serif;margin:32px;line-height:1.55}} code{{background:#f1f5f9;padding:2px 5px;border-radius:4px}}</style>
</head><body>
<h1>{title}</h1>
<p>동일 start-goal set에서 여러 알고리즘을 다중 패널로 비교하는 HTML Canvas 시뮬레이션 모음입니다.</p>
<ol>{items}</ol>
<p>각 파일에서 space 키로 재생/일시정지, 좌우 화살표로 step 이동, checkbox로 path/intent/tail 표시를 제어할 수 있습니다.</p>
</body></html>"""
    out = output_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/visual_5cases.yaml")
    ap.add_argument("--algorithms", nargs="+", default=None, metavar="ALGORITHM")
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--path-horizon", type=int, default=10)
    args = ap.parse_args()

    cfg = read_yaml(args.config)
    exp = cfg.get("experiment", {})
    algorithms = args.algorithms or exp.get("algorithms", ["whca", "lcg_mpc_plus"])
    if not 2 <= len(algorithms) <= 4:
        raise SystemExit("visualize_suite requires 2 to 4 algorithms")
    display_algorithms = [_display_name(cfg, alg) for alg in algorithms]
    output_dir = ensure_dir(exp.get("output_dir", "results/visualizations"))
    paths: list[Path] = []
    for i, case in enumerate(cfg.get("cases", []), start=1):
        name = _safe_name(str(case.get("name", f"case_{i}")))
        seed = int(case.get("seed", exp.get("seeds", [0])[0]))
        scenario = dict(case.get("scenario", {}))
        out = Path(output_dir) / f"{i:02d}_{name}_{'_vs_'.join(display_algorithms)}.html"
        path = save_comparison_html(
            cfg,
            algorithms=list(algorithms),
            seed=seed,
            output_path=out,
            scenario_override=scenario,
            max_frames=args.max_frames,
            stride=args.stride,
            path_horizon=args.path_horizon,
        )
        paths.append(Path(path))
        print(f"Saved {path}")
    if not paths:
        raise SystemExit("No cases found in visualization config")
    index = write_index(paths, Path(output_dir), exp.get("name", "visual_suite"))
    print(f"Saved index {index}")


if __name__ == "__main__":
    main()

