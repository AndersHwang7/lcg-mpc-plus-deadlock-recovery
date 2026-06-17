# Inha University & RODIX Inc, Anders Hwang
# 파일명: test_scc.py
# 목적 및 역할:
# Tarjan SCC 구현이 순환 의존 관계를 정확히 찾는지 확인한다.
# 작성자: RODIX Anders Hwang

from mr_deadlock.deadlock.scc import tarjan_scc


def test_tarjan_cycle():
    comps = tarjan_scc({1: {2}, 2: {3}, 3: {1}, 4: set()})
    assert any(set(c) == {1, 2, 3} for c in comps)

