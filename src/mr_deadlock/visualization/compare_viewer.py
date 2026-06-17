# Inha University & RODIX Inc, Anders Hwang
# 파일명: compare_viewer.py
# 목적 및 역할:
# 그래프가 아닌 "동작 시각화"를 만든다. 동일 seed/start-goal set에서 여러 알고리즘을
# 나란히 실행하고, 로봇 도형/경로 시도선/실행 이동/핵심 값을 HTML Canvas로 재생한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mr_deadlock.core.robot import Robot
from mr_deadlock.core.simulator import Simulator
from mr_deadlock.experiments.runner import build_robots, build_scenario
from mr_deadlock.maps.generator import make_map
from mr_deadlock.maps.tasks import sample_start_goals
from mr_deadlock.planners.factory import make_planner
from mr_deadlock.utils.io import ensure_dir
from mr_deadlock.utils.random import seed_all


DEFAULT_DISPLAY_NAMES = {"lcg_mpc_plus_full_v3": "lcg_mpc_plus"}


def _cell(c) -> list[int]:
    return [int(c[0]), int(c[1])]


def _robot_state(r: Robot) -> dict[str, Any]:
    return {
        "id": int(r.id),
        "x": int(r.pos[0]),
        "y": int(r.pos[1]),
        "done": bool(r.completed_at is not None),
        "wait": int(r.wait_time),
        "debt": float(round(r.fairness_debt, 3)),
    }


def _path_segment(r: Robot, horizon: int) -> list[list[int]]:
    if not r.path:
        return [_cell(r.pos), _cell(r.goal)]
    lo = max(0, r.path_index)
    hi = min(len(r.path), lo + max(2, horizon))
    segment = r.path[lo:hi]
    if segment and segment[0] != r.pos:
        segment = [r.pos] + segment
    if not segment:
        segment = [r.pos]
    return [_cell(c) for c in segment]


def _actions_from_step(step_info: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not step_info:
        return []
    old = step_info.get("old_positions", {})
    raw = step_info.get("raw_moves", {})
    valid = step_info.get("validated_moves", {})
    actions = []
    for rid, start in old.items():
        raw_target = raw.get(rid, start)
        final_target = valid.get(rid, start)
        actions.append(
            {
                "id": int(rid),
                "from": _cell(start),
                "raw": _cell(raw_target),
                "final": _cell(final_target),
                "changed": bool(raw_target != final_target),
            }
        )
    return actions


def _panel_state(algorithm: str, sim: Simulator, step_info: dict[str, Any] | None, path_horizon: int) -> dict[str, Any]:
    records = sim.metrics.step_records
    last = records[-1] if records else None
    n = max(1, len(sim.robots))
    completed = sum(1 for r in sim.robots if r.completed_at is not None)
    active = n - completed
    waits = [r.wait_time for r in sim.robots]
    cumulative = {
        "fixed": sum(r.fixed_conflicts for r in records),
        "retreat": sum(r.retreat_actions for r in records),
        "game": sum(r.game_profiles for r in records),
        "mpc": sum(r.mpc_refinements for r in records),
        "footprint": sum(r.footprint_conflicts for r in records),
        "swept": sum(r.swept_conflicts for r in records),
        "accel": sum(r.acceleration_clips for r in records),
    }
    metrics = {
        "t": int(sim.t),
        "completed": int(completed),
        "active": int(active),
        "success": round(completed / n, 4),
        "mean_wait": round(sum(waits) / n, 3),
        "max_wait": int(max(waits) if waits else 0),
        "fixed": int(cumulative["fixed"]),
        "collision": int(sim.metrics.collision_count),
        "retreat": int(cumulative["retreat"]),
        "game_profiles": int(cumulative["game"]),
        "mpc_checks": int(cumulative["mpc"]),
        "local_sets": int(last.local_conflict_sets if last else 0),
        "persistent": int(last.persistent_deadlocks if last else 0),
        "step_ms": round(float(last.step_runtime_ms), 3) if last else 0.0,
        "footprint": int(cumulative["footprint"]),
        "swept": int(cumulative["swept"]),
        "accel": int(cumulative["accel"]),
        "clearance": round(float(last.continuous_min_clearance), 3) if last and last.continuous_min_clearance == last.continuous_min_clearance else None,
    }
    return {
        "algorithm": algorithm,
        "metrics": metrics,
        "robots": [_robot_state(r) for r in sim.robots],
        "paths": {str(r.id): _path_segment(r, path_horizon) for r in sim.robots if r.completed_at is None},
        "actions": _actions_from_step(step_info),
    }


def build_comparison_trace(
    config: dict[str, Any],
    algorithms: list[str],
    seed: int,
    scenario_override: dict[str, Any] | None = None,
    max_frames: int | None = None,
    stride: int = 1,
    path_horizon: int = 10,
) -> dict[str, Any]:
    if not 2 <= len(algorithms) <= 4:
        raise ValueError("Comparison visualization expects 2 to 4 algorithms")
    scenario = build_scenario(config, scenario_override)
    exp_cfg = dict(config.get("experiment", {}))
    display_names = {**DEFAULT_DISPLAY_NAMES, **dict(exp_cfg.get("algorithm_labels", {}))}
    algorithm_labels = [display_names.get(alg, alg) for alg in algorithms]
    planner_cfg = dict(config.get("planner", {}))
    runtime_cfg = dict(config.get("runtime", {}))
    rng = seed_all(seed)
    width = int(scenario.get("width", 70))
    height = int(scenario.get("height", 70))
    map_type = str(scenario.get("map_type", "ring"))
    obstacle_density = float(scenario.get("obstacle_density", scenario.get("density", 0.05)))
    n_robots = int(scenario.get("n_robots", 60))
    grid = make_map(map_type, width, height, obstacle_density, rng)
    pairs = sample_start_goals(grid, n_robots, scenario.get("start_goal_mode", "cross_traffic"), rng)
    merged_cfg = {**scenario, **planner_cfg, **runtime_cfg}
    sims: list[Simulator] = []
    for alg in algorithms:
        robots = build_robots(pairs)
        sim_cfg = dict(merged_cfg)
        planner = make_planner(alg, grid, dict(merged_cfg))
        sims.append(Simulator(grid, robots, planner, sim_cfg))

    max_steps = int(merged_cfg.get("max_steps", 200))
    if max_frames is not None:
        max_steps = min(max_steps, int(max_frames))
    stride = max(1, int(stride))
    frames: list[dict[str, Any]] = [
        {
            "step": 0,
            "panels": [
                _panel_state(algorithm_labels[i], sims[i], None, path_horizon=path_horizon)
                for i in range(len(algorithms))
            ],
        }
    ]
    step_infos: list[dict[str, Any] | None] = [None for _ in algorithms]
    for step in range(max_steps):
        all_done_before = True
        for i, sim in enumerate(sims):
            if any(r.completed_at is None for r in sim.robots) and sim.t < sim.max_steps:
                all_done_before = False
                step_infos[i] = sim.step()
            else:
                step_infos[i] = None
        if all_done_before:
            break
        if (step + 1) % stride == 0:
            frames.append(
                {
                    "step": int(step + 1),
                    "panels": [
                        _panel_state(algorithm_labels[i], sims[i], step_infos[i], path_horizon=path_horizon)
                        for i in range(len(algorithms))
                    ],
                }
            )
    return {
        "meta": {
            "title": "LCG-MPC multi-panel simulator comparison",
            "seed": int(seed),
            "scenario": scenario,
            "algorithms": algorithm_labels,
            "stride": stride,
            "path_horizon": int(path_horizon),
            "note": "Canvas animation: shapes are robots, faint polylines are nominal path attempts, short segments are raw/final one-step decisions.",
        },
        "grid": {
            "width": int(grid.width),
            "height": int(grid.height),
            "name": grid.name,
            "obstacles": [_cell(c) for c in sorted(grid.obstacles)],
        },
        "tasks": [
            {"id": i, "start": _cell(s), "goal": _cell(g)} for i, (s, g) in enumerate(pairs)
        ],
        "frames": frames,
    }


HTML_TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>LCG-MPC 비교 시뮬레이터</title>
<style>
  :root { font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  body { margin: 0; background: #111827; color: #f9fafb; }
  header { padding: 12px 18px 8px; border-bottom: 1px solid #374151; }
  h1 { margin: 0 0 4px; font-size: 18px; }
  .sub { color: #cbd5e1; font-size: 13px; }
  .wrap { padding: 10px 14px 14px; }
  canvas { width: 100%; max-width: 1600px; height: auto; display: block; margin: 0 auto; background: #f8fafc; border-radius: 12px; box-shadow: 0 12px 40px rgba(0,0,0,.35); }
  .controls { max-width: 1600px; margin: 10px auto 0; display: grid; grid-template-columns: auto 1fr auto auto auto auto; gap: 10px; align-items: center; }
  button, select, label { font-size: 13px; }
  button, select { border: 1px solid #4b5563; background: #1f2937; color: #f9fafb; border-radius: 8px; padding: 7px 10px; }
  input[type="range"] { width: 100%; }
  label { color: #d1d5db; user-select: none; }
  .legend { max-width: 1600px; margin: 8px auto 0; color: #d1d5db; font-size: 12px; line-height: 1.45; }
  .pill { display: inline-block; padding: 2px 6px; margin-right: 5px; border-radius: 999px; background: #1f2937; border: 1px solid #4b5563; }
</style>
</head>
<body>
<header>
  <h1>LCG-MPC 다중 패널 비교 시뮬레이터</h1>
  <div class="sub" id="meta"></div>
</header>
<div class="wrap">
  <canvas id="sim" width="1600" height="1180"></canvas>
  <div class="controls">
    <button id="play">재생</button>
    <input id="slider" type="range" min="0" max="0" value="0" />
    <select id="speed">
      <option value="150">느림</option>
      <option value="80" selected>보통</option>
      <option value="35">빠름</option>
    </select>
    <label><input id="showPaths" type="checkbox" checked /> 경로 시도선</label>
    <label><input id="showTails" type="checkbox" checked /> 이동 꼬리</label>
    <label><input id="showIntent" type="checkbox" checked /> 원시/실행 이동</label>
  </div>
  <div class="legend">
    <span class="pill">원/네모: 이동체</span>
    <span class="pill">옅은 선: nominal path attempt</span>
    <span class="pill">짧은 선: planner raw move → safety-supervised executed move</span>
    <span class="pill">하단: 성공률·대기·충돌 보정·game/MPC 활성값</span>
  </div>
</div>
<script>
const TRACE = __TRACE_JSON__;
const canvas = document.getElementById('sim');
const ctx = canvas.getContext('2d');
const slider = document.getElementById('slider');
const playBtn = document.getElementById('play');
const speedSel = document.getElementById('speed');
const showPaths = document.getElementById('showPaths');
const showTails = document.getElementById('showTails');
const showIntent = document.getElementById('showIntent');
const frames = TRACE.frames;
const panelCount = TRACE.meta.algorithms.length;
slider.max = Math.max(0, frames.length - 1);
let frameIndex = 0;
let timer = null;
const palette = ['#2563eb','#dc2626','#16a34a','#9333ea','#ea580c','#0891b2','#be123c','#4f46e5','#65a30d','#7c2d12'];
document.getElementById('meta').textContent = `seed=${TRACE.meta.seed}, map=${TRACE.grid.name}, robots=${TRACE.tasks.length}, frames=${frames.length}, algorithms=${TRACE.meta.algorithms.join(' vs ')}`;

function colorFor(id) { return palette[id % palette.length]; }
function panelGeom(i) {
  const margin = 28;
  const gap = 24;
  const footer = 34;
  const cols = panelCount <= 2 ? panelCount : 2;
  const rows = Math.ceil(panelCount / cols);
  const panelW = (canvas.width - 2 * margin - gap * (cols - 1)) / cols;
  const panelH = (canvas.height - 2 * margin - footer - gap * (rows - 1)) / rows;
  const col = i % cols;
  const row = Math.floor(i / cols);
  const x = margin + col * (panelW + gap);
  const y = margin + row * (panelH + gap);
  const titleH = 34;
  const metricsH = 120;
  const mapHLimit = Math.max(80, panelH - titleH - metricsH - 18);
  const scale = Math.min(panelW / TRACE.grid.width, mapHLimit / TRACE.grid.height);
  const mapW = TRACE.grid.width * scale;
  const mapH = TRACE.grid.height * scale;
  return {x: x + (panelW - mapW)/2, y: y + titleH + (mapHLimit - mapH)/2, w: mapW, h: mapH, scale, panelW, panelH, rawX:x, rawY:y, metricsH};
}
function toPx(g, cell) { return [g.x + (cell[0] + 0.5) * g.scale, g.y + (cell[1] + 0.5) * g.scale]; }
function rectCell(g, cell) { return [g.x + cell[0] * g.scale, g.y + cell[1] * g.scale, g.scale, g.scale]; }
function drawLine(points, stroke, width, alpha=1, dash=[]) {
  if (!points || points.length < 2) return;
  ctx.save(); ctx.globalAlpha = alpha; ctx.strokeStyle = stroke; ctx.lineWidth = width; ctx.setLineDash(dash);
  ctx.beginPath(); ctx.moveTo(points[0][0], points[0][1]);
  for (let i=1; i<points.length; i++) ctx.lineTo(points[i][0], points[i][1]);
  ctx.stroke(); ctx.restore();
}
function drawMap(g) {
  ctx.save();
  ctx.fillStyle = '#ffffff'; ctx.fillRect(g.x, g.y, g.w, g.h);
  ctx.strokeStyle = '#334155'; ctx.lineWidth = 1.2; ctx.strokeRect(g.x, g.y, g.w, g.h);
  ctx.fillStyle = '#1f2937';
  for (const c of TRACE.grid.obstacles) { const r = rectCell(g, c); ctx.fillRect(r[0], r[1], Math.ceil(r[2]), Math.ceil(r[3])); }
  if (g.scale >= 8) {
    ctx.strokeStyle = 'rgba(15,23,42,.08)'; ctx.lineWidth = 1;
    for (let x=0; x<=TRACE.grid.width; x++) { ctx.beginPath(); ctx.moveTo(g.x+x*g.scale, g.y); ctx.lineTo(g.x+x*g.scale, g.y+g.h); ctx.stroke(); }
    for (let y=0; y<=TRACE.grid.height; y++) { ctx.beginPath(); ctx.moveTo(g.x, g.y+y*g.scale); ctx.lineTo(g.x+g.w, g.y+y*g.scale); ctx.stroke(); }
  }
  ctx.restore();
}
function drawTasks(g) {
  ctx.save();
  for (const t of TRACE.tasks) {
    const cs = toPx(g, t.start), cg = toPx(g, t.goal);
    ctx.globalAlpha = .18; ctx.fillStyle = colorFor(t.id);
    ctx.beginPath(); ctx.arc(cs[0], cs[1], Math.max(2, g.scale*.18), 0, Math.PI*2); ctx.fill();
    ctx.globalAlpha = .22; ctx.strokeStyle = colorFor(t.id); ctx.lineWidth = Math.max(1, g.scale*.10);
    ctx.beginPath(); ctx.moveTo(cg[0]-g.scale*.18, cg[1]-g.scale*.18); ctx.lineTo(cg[0]+g.scale*.18, cg[1]+g.scale*.18); ctx.moveTo(cg[0]+g.scale*.18, cg[1]-g.scale*.18); ctx.lineTo(cg[0]-g.scale*.18, cg[1]+g.scale*.18); ctx.stroke();
  }
  ctx.restore();
}
function drawTails(panelIndex, g, currentFrame) {
  if (!showTails.checked) return;
  const first = Math.max(0, currentFrame - 14);
  const tracks = new Map();
  for (let fi=first; fi<=currentFrame; fi++) {
    const panel = frames[fi].panels[panelIndex];
    for (const r of panel.robots) {
      if (!tracks.has(r.id)) tracks.set(r.id, []);
      tracks.get(r.id).push(toPx(g, [r.x, r.y]));
    }
  }
  for (const [id, pts] of tracks) drawLine(pts, colorFor(id), Math.max(1, g.scale*.08), .28);
}
function drawPaths(g, panel) {
  if (!showPaths.checked) return;
  for (const [rid, cells] of Object.entries(panel.paths)) {
    const pts = cells.map(c => toPx(g, c));
    drawLine(pts, colorFor(Number(rid)), Math.max(1, g.scale*.06), .18, [5, 5]);
  }
}
function drawActions(g, panel) {
  if (!showIntent.checked) return;
  for (const a of panel.actions) {
    const p0 = toPx(g, a.from);
    const praw = toPx(g, a.raw);
    const pfin = toPx(g, a.final);
    if (a.raw[0] !== a.from[0] || a.raw[1] !== a.from[1]) drawLine([p0, praw], '#f97316', Math.max(1, g.scale*.10), .55, [3, 4]);
    if (a.final[0] !== a.from[0] || a.final[1] !== a.from[1]) drawLine([p0, pfin], a.changed ? '#dc2626' : '#111827', Math.max(1.2, g.scale*.14), .65);
  }
}
function drawRobots(g, panel) {
  ctx.save();
  for (const r of panel.robots) {
    const [x, y] = toPx(g, [r.x, r.y]);
    const rad = Math.max(3.2, g.scale * .34);
    ctx.globalAlpha = r.done ? .35 : .95;
    ctx.fillStyle = colorFor(r.id); ctx.strokeStyle = '#0f172a'; ctx.lineWidth = Math.max(1, g.scale*.07);
    if (r.id % 2 === 0) { ctx.beginPath(); ctx.arc(x, y, rad, 0, Math.PI*2); ctx.fill(); ctx.stroke(); }
    else { ctx.fillRect(x-rad, y-rad, rad*2, rad*2); ctx.strokeRect(x-rad, y-rad, rad*2, rad*2); }
    if (g.scale > 10 && r.id < 100) { ctx.globalAlpha = .9; ctx.fillStyle = '#fff'; ctx.font = `${Math.max(7, g.scale*.38)}px sans-serif`; ctx.textAlign='center'; ctx.textBaseline='middle'; ctx.fillText(String(r.id), x, y); }
  }
  ctx.restore();
}
function metricText(m) {
  return [
    `t=${m.t}`, `완료=${m.completed}`, `활성=${m.active}`, `성공=${(m.success*100).toFixed(1)}%`,
    `평균대기=${m.mean_wait}`, `최대대기=${m.max_wait}`, `fixed=${m.fixed}`, `collision=${m.collision}`,
    `retreat=${m.retreat}`, `game=${m.game_profiles}`, `mpc=${m.mpc_checks}`, `local=${m.local_sets}`, `ms=${m.step_ms}`,
    `foot=${m.footprint}`, `swept=${m.swept}`, `accel=${m.accel}`, `clear=${m.clearance}`
  ];
}
function drawPanelTitle(g, panel) {
  ctx.save();
  ctx.fillStyle = '#e5e7eb'; ctx.fillRect(g.rawX, g.rawY, g.panelW, 32);
  ctx.fillStyle = '#111827'; ctx.font = 'bold 17px sans-serif'; ctx.textAlign='left'; ctx.textBaseline='middle';
  ctx.fillText(panel.algorithm, g.rawX + 10, g.rawY + 16);
  ctx.restore();
}
function drawMetrics(panelIndex, g, panel) {
  const baseY = g.rawY + g.panelH - g.metricsH;
  const x = g.rawX;
  const w = g.panelW;
  ctx.save();
  ctx.fillStyle = '#f1f5f9'; ctx.strokeStyle = '#cbd5e1'; ctx.lineWidth = 1;
  ctx.fillRect(x, baseY, w, g.metricsH); ctx.strokeRect(x, baseY, w, g.metricsH);
  ctx.fillStyle = '#0f172a'; ctx.font = '12px sans-serif'; ctx.textAlign='left'; ctx.textBaseline='top';
  const items = metricText(panel.metrics);
  const colW = w / 3;
  for (let i=0; i<items.length; i++) {
    const cx = x + 10 + (i % 3) * colW;
    const cy = baseY + 8 + Math.floor(i / 3) * 18;
    ctx.fillText(items[i], cx, cy);
  }
  ctx.restore();
}
function drawFrame(idx) {
  frameIndex = Math.max(0, Math.min(frames.length-1, idx));
  slider.value = frameIndex;
  ctx.clearRect(0,0,canvas.width,canvas.height);
  ctx.fillStyle = '#e2e8f0'; ctx.fillRect(0,0,canvas.width,canvas.height);
  const frame = frames[frameIndex];
  for (let i=0; i<frame.panels.length; i++) {
    const g = panelGeom(i); const panel = frame.panels[i];
    drawPanelTitle(g, panel); drawMap(g); drawTasks(g); drawTails(i, g, frameIndex); drawPaths(g, panel); drawActions(g, panel); drawRobots(g, panel); drawMetrics(i, g, panel);
  }
  ctx.save(); ctx.fillStyle = '#0f172a'; ctx.font = '14px sans-serif'; ctx.textAlign='center'; ctx.fillText(`frame ${frameIndex}/${frames.length-1} · simulation step ${frame.step}`, canvas.width/2, canvas.height-10); ctx.restore();
}
function play() {
  if (timer) { clearInterval(timer); timer=null; playBtn.textContent='재생'; return; }
  playBtn.textContent='일시정지';
  timer = setInterval(() => {
    if (frameIndex >= frames.length - 1) { clearInterval(timer); timer=null; playBtn.textContent='재생'; return; }
    drawFrame(frameIndex + 1);
  }, Number(speedSel.value));
}
playBtn.addEventListener('click', play);
slider.addEventListener('input', () => drawFrame(Number(slider.value)));
speedSel.addEventListener('change', () => { if (timer) { clearInterval(timer); timer=null; play(); } });
for (const el of [showPaths, showTails, showIntent]) el.addEventListener('change', () => drawFrame(frameIndex));
window.addEventListener('keydown', ev => { if (ev.key === ' ') { ev.preventDefault(); play(); } if (ev.key === 'ArrowRight') drawFrame(frameIndex+1); if (ev.key === 'ArrowLeft') drawFrame(frameIndex-1); });
drawFrame(0);
</script>
</body>
</html>
"""


def render_comparison_html(trace: dict[str, Any], output_path: str | Path) -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(trace, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    out.write_text(HTML_TEMPLATE.replace("__TRACE_JSON__", payload), encoding="utf-8")
    return out


def save_comparison_html(
    config: dict[str, Any],
    algorithms: list[str],
    seed: int,
    output_path: str | Path,
    scenario_override: dict[str, Any] | None = None,
    max_frames: int | None = None,
    stride: int = 1,
    path_horizon: int = 10,
) -> Path:
    trace = build_comparison_trace(
        config=config,
        algorithms=algorithms,
        seed=seed,
        scenario_override=scenario_override,
        max_frames=max_frames,
        stride=stride,
        path_horizon=path_horizon,
    )
    return render_comparison_html(trace, ensure_dir(Path(output_path).parent) / Path(output_path).name)

