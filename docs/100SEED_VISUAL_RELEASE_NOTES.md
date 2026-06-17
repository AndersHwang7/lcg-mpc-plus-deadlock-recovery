# 100-seed 및 시각화 추가 릴리스 노트

## 변경 목적

업로드된 20-seed 최적화 패키지를 논문용 100-seed 반복 실험과 최종 1000-seed 목표에 맞게 확장하고, 그래프가 아닌 실제 동작 시각화가 가능한 경량 비교 시뮬레이터를 추가했다.

## 추가/수정 파일

- `configs/optimized_100seed.yaml`: 100-seed paired 실험 설정.
- `configs/paper_1000seed_final.yaml`: 최종 1000-seed 목표 설정.
- `configs/visual_compare.yaml`: WHCA vs CLRR-HMPC 분할 화면 동작 시각화 설정.
- `src/mr_deadlock/experiments/seeds.py`: `seed_range` 파서.
- `src/mr_deadlock/experiments/statistics.py`: paired Wilcoxon, Holm correction, 효과크기, bootstrap CI.
- `scripts/statistical_compare.py`: 통계 비교 CSV 생성 CLI.
- `src/mr_deadlock/visualization/compare_viewer.py`: HTML Canvas 기반 동작 시각화 생성기.
- `scripts/visualize_compare.py`: 시각화 HTML 생성 CLI.
- `docs/100SEED_AND_VISUALIZATION_GUIDE.md`: 실행 가이드.
- `results/visualizations/ring_whca_vs_clrr_hmpc_seed0_sample.html`: 샘플 동작 시각화.

## 성능/확장성 개선

1000대 및 1000-seed 실험을 감안하여 다음 O(N^2) pairwise 탐색을 해시맵 기반 탐색으로 교체했다.

- simulator 최종 안전 감독기의 자리교환 충돌 검사.
- planner 공통 충돌 보정 함수.
- dependency graph의 edge-swap 의존성 검출.
- CLRR repair component 추출 과정.

이는 알고리즘의 본질을 바꾸는 꼼수가 아니라 동일한 충돌 정의를 더 빠르게 계산하는 구현 최적화이다.

## 검증 결과

현재 패키지에서 다음 검증을 재실행했다.

```text
pytest -q                       -> 10 passed
python -m compileall -q src scripts tests -> passed
scripts/validate_project.py quick_100 clrr_hmpc seed0 -> passed
```

`validate_project.py` smoke 결과 핵심값:

- `exact_potential_check=true`
- `collision_free_check=true`
- `mpc_activation_check=true`
- `success_rate=1.0`
- `collision_count=0`
- `mpc_refinements=7`

## 사용 순서

100-seed 실험:

```bash
PYTHONPATH=src python scripts/run_batch.py --config configs/optimized_100seed.yaml --jobs 4 --resume
PYTHONPATH=src python scripts/analyze_results.py --input results/raw --output results/summary
PYTHONPATH=src python scripts/statistical_compare.py --input results/raw --output results/summary --baseline whca
```

동작 시각화:

```bash
PYTHONPATH=src python scripts/visualize_compare.py --config configs/visual_compare.yaml
```

최종 1000-seed 목표:

```bash
PYTHONPATH=src python scripts/run_batch.py --config configs/paper_1000seed_final.yaml --jobs 8 --resume
```
