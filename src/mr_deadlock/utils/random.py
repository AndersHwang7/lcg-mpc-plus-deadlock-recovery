# Inha University & RODIX Inc, Anders Hwang
# 파일명: random.py
# 목적 및 역할:
# 재현 가능한 실험을 위해 난수 생성기를 통일해서 만든다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

import random
import numpy as np


def seed_all(seed: int) -> random.Random:
    random.seed(seed)
    np.random.seed(seed)
    return random.Random(seed)

