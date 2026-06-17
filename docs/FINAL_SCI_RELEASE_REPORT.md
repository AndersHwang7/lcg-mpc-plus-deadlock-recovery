# Final SCI release report

이 문서는 사용자가 지적한 미완성 요소를 코드/실험/시각화 파이프라인으로 닫기 위해 추가한 내용의 요약이다.

## 1. 핵심 변경점

### 1.1 보강 알고리즘: `lcg_mpc_plus`

새 planner `lcg_mpc_plus`를 추가했다. 기존 `clrr_hmpc`의 localized conflict game + MPC 구조를 유지하면서 다음을 보강했다.

- continuous-envelope 조건에서는 WHCA 단독 nominal 대신 robust `impc_dr_lite` nominal을 사용한다.
- 지속 정체 robot cluster를 별도 repair component로 추가한다.
- exact-potential game은 큰 component를 `max_game_agents` 이하 bounded local blocks로 분할해 enumerated exact game을 수행한다.
- greedy fallback은 metadata에서 `partitioned_mixed`로 분리 표기하며, exact-potential 보장은 `exact_enumeration` 또는 `partitioned_exact` block에만 적용되도록 claim 범위를 명확히 했다.
- optional `lcg_strict_cbf_filter`를 제공해 최종 후보를 CBF-like filter로 한 번 더 조일 수 있다.

### 1.2 AMR 연속 footprint / acceleration / sensing uncertainty 반영

새 모듈 `src/mr_deadlock/core/dynamics.py`를 추가했다.

- circular footprint radius: `footprint_radius`
- safety margin: `safety_margin`
- sensing uncertainty buffer: `uncertainty_k * sensing_sigma`
- acceleration/speed bound: `max_accel`, `max_speed`
- synchronous swept-volume clearance check
- obstacle inflated-envelope check
- 관련 통계: `footprint_conflicts`, `swept_conflicts`, `obstacle_envelope_conflicts`, `acceleration_clips`, `speed_clips`, `sensing_risk_events`, `continuous_min_clearance`

모든 planner는 동일한 final safety supervisor를 통과하므로 baseline과 proposed method 비교 조건이 같다.

### 1.3 simulator-native external baseline 계열

외부 공개 코드가 없어도 동일 simulator에서 비교할 수 있도록 다음 baseline을 추가했다.

- `orca_lite`: ORCA/RVO-style reciprocal collision avoidance surrogate
- `dmpc_lite`: distributed MPC-style finite-action local horizon surrogate
- `mpc_cbf_lite`: WHCA nominal + CBF-like one-step safety filter
- `impc_dr_lite`: uncertainty-inflated robust MPC/CBF surrogate

이 구현은 논문에 “official third-party implementation”이라고 쓰면 안 된다. 동일 simulator 비교용 구현 baseline이며, 외부 공개 코드 연결 시에는 동일 `Planner` API로 adapter를 추가하면 된다.

### 1.4 5개 split-screen 동작 시각화

`configs/visual_5cases.yaml`와 `scripts/visualize_suite.py`를 추가했다.

생성된 파일:

- `results/visualizations/index.html`
- `results/visualizations/01_ring_cross_56robots_seed0_whca_vs_lcg_mpc_plus.html`
- `results/visualizations/02_intersection_cross_72robots_seed7_whca_vs_lcg_mpc_plus.html`
- `results/visualizations/03_bottleneck_swap_80robots_seed13_whca_vs_lcg_mpc_plus.html`
- `results/visualizations/04_warehouse_aisles_90robots_seed21_whca_vs_lcg_mpc_plus.html`
- `results/visualizations/05_corridor_opposing_60robots_seed42_whca_vs_lcg_mpc_plus.html`

각 HTML은 path attempts, raw move, safety-supervised move, completion/wait/game/MPC/continuous-safety counters를 함께 보여준다.

### 1.5 통계/그래프/표 자동 생성

새 스크립트:

```bash
python scripts/run_paper_pipeline.py --config configs/paper_fast_1000seed_core.yaml --jobs 8 --resume
python scripts/run_paper_pipeline.py --config configs/paper_1000seed_final.yaml --jobs 8 --resume
```

생성물:

- raw CSV
- `summary/summary.csv`
- `summary/paired_vs_whca.csv`
- figure PNG/PDF
- `tables/main_metrics_table.csv/.tex`
- `tables/best_algorithm_by_metric.csv/.tex`
- pipeline manifest

## 2. 포함된 빠른 검증 결과

배포본에는 full 1000-seed 결과 대신 `configs/final_validation_3seed_quick.yaml`로 재현한 경량 paired validation 결과를 포함했다.

경로:

- `results/final_validation_quick/raw`
- `results/final_validation_quick/summary/summary.csv`
- `results/final_validation_quick/summary/paired_vs_whca.csv`
- `results/final_validation_quick/figures`
- `results/final_validation_quick/tables`

이 결과는 코드와 파이프라인 검증용이다. 본문 SCI 정량 claim에는 반드시 1000-seed 또는 최소 100-seed sweep을 재실행한 뒤 표와 통계 절을 갱신해야 한다.

## 3. 최종 논문용 실행 순서

### 빠른 1000-seed core stress claim

```bash
python scripts/run_paper_pipeline.py --config configs/paper_fast_1000seed_core.yaml --jobs 8 --resume
```

### 완전한 large-scale 1000-seed final sweep

```bash
python scripts/run_paper_pipeline.py --config configs/paper_1000seed_final.yaml --jobs 8 --resume
```

### 5개 동작 시각화 재생성

```bash
python scripts/visualize_suite.py --config configs/visual_5cases.yaml --max-frames 160
```

### 단일 case 실험

```bash
python scripts/run_single.py --config configs/visual_compare.yaml --algorithm lcg_mpc_plus --seed 0
```

## 4. 논문 문구 주의사항

- `orca_lite`, `dmpc_lite`, `mpc_cbf_lite`, `impc_dr_lite`는 simulator-native baseline이다. 외부 저자 공식 코드를 그대로 사용한 것이 아니다.
- exact-potential equilibrium claim은 bounded local enumerated games 또는 partitioned exact blocks에 대해서만 기술해야 한다.
- full 1000-seed 결과를 생성하지 않은 상태에서는 `results/final_validation_quick` 수치를 본문 최종 claim으로 사용하지 말고 “pipeline validation” 또는 “small paired validation”으로만 써야 한다.
- continuous footprint 통계에서 `footprint_conflicts`와 `swept_conflicts`는 최종 충돌이 아니라 safety supervisor 또는 planner가 보정한 위험 이벤트 수이다. 최종 실행 후 실제 grid collision은 `collision_count`로 별도 기록된다.
