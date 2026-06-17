# Inha University & RODIX Inc, Anders Hwang
# 파일명: scc.py
# 목적 및 역할:
# Tarjan 알고리즘으로 방향 그래프의 강연결성분을 계산한다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations


def tarjan_scc(edges: dict[int, set[int]]) -> list[list[int]]:
    index = 0
    stack: list[int] = []
    on_stack: set[int] = set()
    indices: dict[int, int] = {}
    lowlink: dict[int, int] = {}
    comps: list[list[int]] = []

    nodes = set(edges.keys())
    for vs in edges.values():
        nodes.update(vs)

    # 하나의 노드에서 시작해 도달 가능한 순환 묶음을 재귀적으로 찾는다.
    def strongconnect(v: int) -> None:
        nonlocal index
        indices[v] = index
        lowlink[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)
        for w in edges.get(v, set()):
            if w not in indices:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], indices[w])
        if lowlink[v] == indices[v]:
            comp = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                comp.append(w)
                if w == v:
                    break
            comps.append(comp)

    for v in nodes:
        if v not in indices:
            strongconnect(v)
    return comps

