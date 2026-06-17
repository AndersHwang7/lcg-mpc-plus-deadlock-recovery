# 파일명: 20SEED_OPTIMIZATION_REPORT.md
# 목적 및 역할:
# 20회 반복 실험과 파라미터 조정 결과를 논문 실험 준비 관점에서 정리한다.
# 작성자: RODIX Anders Hwang

## 1. 검증 목적

v3 소스가 논문 초안의 주장과 맞게 동작하는지 확인하기 위해 20개 seed 반복 실험을 수행하였다. 이번 검증은 최종 논문 수치가 아니라, 논문에 넣을 만한 결과가 나올 가능성과 현재 코드의 약점을 판단하기 위한 중간 검증이다.

## 2. 실험 조건

비교 알고리즘은 pibt, whca, clrr, clrr_game, clrr_hmpc이다. 실험은 intersection_100과 ring_80에서 각각 20개 seed로 수행하였다. ring_80은 교착과 순환 대기가 강하게 나타나는 stress 환경으로 사용하였다.

## 3. 코드 수정 및 최적화 내용

잠재게임 단계에서 큰 conflict set을 전부 열거하면 실행 시간이 급격히 증가하였다. 이를 막기 위해 정확한 potential game은 작은 집합과 제한된 profile 수 안에서만 사용하고, 조합 수가 커질 경우 같은 potential 비용을 따르는 greedy selector로 전환하였다.

또한 local MPC가 이미 안전한 잠재게임 profile을 불필요하게 늦추는 문제가 있었다. 이 문제를 막기 위해 candidate profile에 정점 충돌이나 자리교환 충돌이 없으면 MPC가 이동을 보존하도록 수정하였다. 충돌이 남은 경우에만 국소 MPC 보정을 수행한다.

## 4. 20 seed 평균 결과 요약

자세한 수치는 results/optimization/summary/20seed_summary_mean.csv에 저장되어 있다.

### intersection_100

intersection_100에서는 whca와 CLRR 계열이 모두 성공률 1.0을 달성하였다. 이 환경은 기본 교차로 통과 능력을 보는 데는 유용하지만, whca가 이미 강하기 때문에 제안 방법의 deadlock 우위를 강하게 주장하기에는 부족하다. 다만 clrr_hmpc는 평균 step runtime과 p95 runtime에서 whca보다 낮게 나와 구현 효율성 주장을 보조할 수 있다.

### ring_80

ring_80에서는 제안 방법의 장점이 더 분명하다. whca는 평균 성공률 0.9862였고, clrr, clrr_game, clrr_hmpc는 모두 1.0이었다. clrr_hmpc는 whca 대비 평균 대기시간을 약 68.9퍼센트 줄였고, 처리량을 약 3.77퍼센트 높였으며, Jain wait fairness도 약 6.39퍼센트 개선하였다. 모든 제안 알고리즘의 collision_count는 0이었다.

## 5. 논문 사용 가능성 판단

현재 결과만 놓고 보면, 모든 환경에서 제안 방법이 압도적으로 우수하다고 주장하기는 어렵다. 특히 intersection_100은 whca가 이미 충분히 강하다. 그러나 교착 stress가 강한 ring_80에서는 제안 구조가 성공률, 대기시간, 처리량, 공정성에서 우수한 경향을 보였다. 따라서 논문에서는 일반 교차로 결과보다 교착이 강하게 발생하는 corridor, ring, bottleneck, warehouse crossing 환경을 중심으로 주장을 구성해야 한다.

## 6. 논문에 반영할 권장 문장 방향

본 방법은 모든 topology에서 전역 최적성을 보장하는 일반 MAPF solver가 아니라, 국소 순환 의존성이 반복되는 교착 환경에서 안전한 recovery와 bounded local progress를 제공하는 hybrid repair layer로 정의하는 것이 타당하다.

## 7. 추가로 필요한 최종 실험

최종 SCI 투고 전에는 100, 250, 500, 750, 1000대 조건에서 corridor, ring, bottleneck, warehouse crossing을 포함하여 seed 20회 이상 반복해야 한다. 이번 결과는 알고리즘 방향이 유효함을 보이는 중간 검증이며, 최종 논문 표에는 더 넓은 scale sweep 결과를 사용해야 한다.
