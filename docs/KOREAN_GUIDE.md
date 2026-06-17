# 한국어 사용 가이드

이 프로젝트는 다중 로봇 교착상태 박사논문 실험을 위한 Python 연구용 코드입니다.

## 핵심 실행 순서

```bash
python -m venv .venv
source .venv/bin/activate      # Windows는 .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q
python scripts/run_single.py --config configs/quick_100.yaml --algorithm clrr_hmpc --seed 0
python scripts/run_batch.py --config configs/batch_scale.yaml
python scripts/analyze_results.py --input results/raw --output results/summary
python scripts/make_figures.py --input results/summary/summary.csv --output results/figures
```

## 논문용 추천 실험 순서

1. `astar_wait`, `prioritized`, `pibt`, `whca` baseline 동작 확인
2. `clrr`로 SCC 기반 교착 해소 성능 확인
3. `clrr_game`으로 Potential Game tie-breaker의 효과 확인
4. `clrr_hmpc`로 MPC hook 포함 결과 확인
5. 100, 250, 500, 750, 1000대 규모로 확장

## 주요 지표

- success_rate
- deadlock_events
- persistent_deadlock_steps
- retreat_actions
- mean_wait_time
- throughput
- runtime_sec
- p95_step_runtime_ms

## 코드 구조

- `src/mr_deadlock/core`: 격자, 로봇, 시뮬레이터, 예약 테이블
- `src/mr_deadlock/maps`: 실험 환경 생성
- `src/mr_deadlock/planners`: 비교 알고리즘과 제안 알고리즘
- `src/mr_deadlock/deadlock`: dependency graph, SCC, deadlock detector
- `src/mr_deadlock/game`: Potential game, Stackelberg 확장 모듈
- `src/mr_deadlock/mpc`: CVXPY/OSQP 기반 local QP-MPC hook
- `src/mr_deadlock/experiments`: batch 실험과 분석
- `src/mr_deadlock/visualization`: 논문용 그래프 생성

## 주의

이 코드는 ROS2/Gazebo 시뮬레이터가 아니라, 논문 아이디어 검증을 위한 경량 연구 플랫폼입니다. 실제 논문 제출 전에는 baseline 구현의 범위, 실험 seed 수, 통계 검정, figure 생성 방식을 고정하고 결과를 재현해야 합니다.
