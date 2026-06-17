# 100-seed / 1000-seed 실험 및 동작 시각화 가이드

## 1. 핵심 변경점

이번 버전은 20-seed pilot 패키지를 다음 방향으로 확장한다.

1. `experiment.seed_range`를 지원해 100개 또는 1000개 seed를 긴 YAML 리스트 없이 지정한다.
2. `scripts/run_batch.py --jobs N --resume`를 지원해 대규모 seed sweep을 병렬 실행하고 중단 후 재시작할 수 있다.
3. 충돌 검사에서 O(N^2) pairwise 자리교환 탐색을 해시맵 기반 O(N) 탐색으로 바꾸어 1000대/1000-seed 실험의 병목을 줄였다.
4. `scripts/statistical_compare.py`를 추가해 WHCA 등 baseline 대비 paired Wilcoxon, Holm 보정 p-value, 효과크기, bootstrap CI를 계산한다.
5. `scripts/visualize_compare.py`를 추가해 그래프가 아닌 HTML Canvas 기반 분할 화면 동작 시뮬레이터를 생성한다.

## 2. 100-seed 실행

```bash
PYTHONPATH=src python scripts/run_batch.py --config configs/optimized_100seed.yaml --jobs 4 --resume
PYTHONPATH=src python scripts/analyze_results.py --input results/raw --output results/summary
PYTHONPATH=src python scripts/statistical_compare.py --input results/raw --output results/summary --baseline whca
```

`configs/optimized_100seed.yaml`은 `seed_range: {start: 0, stop: 99}`를 사용한다. 같은 seed는 모든 알고리즘에서 같은 지도, 시작점, 목표점을 사용하므로 paired comparison이 가능하다.

## 3. 최종 1000-seed 목표

```bash
PYTHONPATH=src python scripts/run_batch.py --config configs/paper_1000seed_final.yaml --jobs 8 --resume
PYTHONPATH=src python scripts/analyze_results.py --input results/raw --output results/summary
PYTHONPATH=src python scripts/statistical_compare.py --input results/raw --output results/summary --baseline whca
```

1000-seed sweep은 매우 크다. 실험 환경에 맞게 `--jobs`를 조정하고, 중단 가능성을 고려하여 항상 `--resume`을 붙인다. 최종 논문용으로는 전체 sweep을 한 번에 돌리기보다 map type 또는 robot count 단위로 config를 복제해 나누어 실행하는 것이 안전하다.

## 4. 동작 시각화 생성

```bash
PYTHONPATH=src python scripts/visualize_compare.py --config configs/visual_compare.yaml
```

출력 예시는 다음 위치에 저장된다.

```text
results/visualizations/ring_whca_vs_clrr_hmpc_seed0.html
```

브라우저에서 HTML 파일을 열면 화면이 좌우로 분할된다. 왼쪽은 baseline, 오른쪽은 제안 알고리즘이다. 원/네모는 이동체, 옅은 선은 nominal path attempt, 짧은 선은 planner의 raw one-step decision과 safety-supervised executed decision을 의미한다. 하단에는 완료율, 평균 대기, 충돌 보정 수, retreat/game/MPC 활성값이 실시간으로 표시된다.

다른 환경을 보고 싶으면 다음처럼 실행한다.

```bash
PYTHONPATH=src python scripts/visualize_compare.py \
  --config configs/visual_compare.yaml \
  --algorithms whca clrr_hmpc \
  --map-type intersection \
  --n-robots 64 \
  --seed 3 \
  --max-frames 120 \
  --output results/visualizations/intersection_seed3.html
```

## 5. 논문 반영 시 주의점

- 100-seed 또는 1000-seed 결과가 나오기 전까지는 기존 20-seed 수치를 최종 성능 주장으로 쓰면 안 된다.
- `collision_count`는 최종 실행 이동에 남은 실제 충돌 수이고, `fixed_conflicts`는 안전 감독기가 보정한 후보 위반 수이다.
- `mpc_refinements`는 실제 이동 변경 횟수라기보다 local MPC/QP check 또는 refinement activation count로 해석해야 한다.
- greedy fallback이 작동한 큰 충돌 집합에는 exact-potential equilibrium 보장을 직접 주장하지 말고 scalable heuristic으로 설명해야 한다.
