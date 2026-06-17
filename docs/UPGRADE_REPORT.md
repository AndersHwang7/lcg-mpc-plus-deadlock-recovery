# 성능 보강 작업 보고서

본 문서는 논문 2차 초안의 수식 구조와 실험 요구사항을 기준으로 소스 코드를 보강한 내용을 정리한다.

## 보강 목표

1. 제안 알고리즘에서 실제 실행 후 충돌 수가 0이 되도록 안전 감독기와 지표 계산을 분리하였다.
2. HMPC 계층이 실제 국소 충돌 집합에서 활성화되도록 MPC 호출 조건을 수정하였다.
3. CLRR, CLRR-Game, CLRR-HMPC의 역할이 분리되도록 후보 SCC와 실제 이동 충돌 그룹을 구분하였다.
4. 후퇴 pocket을 여러 칸 목표로 직접 지정하던 문제를 수정하여 실제 한 step 이동이 가능한 후퇴 동작으로 바꾸었다.
5. 공정성 부채가 행동 선택에 실제로 영향을 주도록 potential 함수와 MPC 점수식을 수정하였다.

## 주요 수정 파일

- src/mr_deadlock/core/simulator.py
- src/mr_deadlock/deadlock/dependency_graph.py
- src/mr_deadlock/deadlock/detector.py
- src/mr_deadlock/planners/clrr_hmpc.py
- src/mr_deadlock/game/potential_game.py
- src/mr_deadlock/mpc/local_qp.py
- configs/quick_100.yaml
- configs/stress_deadlock.yaml
- configs/batch_scale.yaml
- configs/paper_scale.yaml
- scripts/validate_project.py

## 검증 결과

- pytest 통과
- compileall 통과
- exact potential 검증 통과
- clrr_hmpc smoke 실행 통과
- collision_count 0 확인
- mpc_refinements 활성화 확인

검증 세부 결과는 docs/UPGRADE_VALIDATION_RESULTS.json 파일에 저장하였다.

## 빠른 비교 확인

stress_deadlock 설정에서 seed 0을 기준으로 확인한 결과는 다음과 같다. 이 값은 논문 최종 수치가 아니라 코드 수정 후 동작 확인용이다.

| 알고리즘 | success_rate | makespan | throughput_per_step | collision_count | fairness_jain_wait | mpc_refinements |
|---|---:|---:|---:|---:|---:|---:|
| whca | 1.0 | 66 | 1.2121 | 0 | 0.7879 | 0 |
| clrr_hmpc | 1.0 | 65 | 1.2308 | 0 | 0.8074 | 34 |

최종 논문에는 seed 20회 이상 반복 실험 후 평균, 표준편차, 신뢰구간을 넣어야 한다.
