# Inha University & RODIX Inc, Anders Hwang
# 파일명: io.py
# 목적 및 역할:
# YAML과 JSONL 입출력, 폴더 생성을 담당하는 작은 유틸리티다.
# 작성자: RODIX Anders Hwang

from __future__ import annotations

from pathlib import Path
from typing import Any
import yaml


def read_yaml(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

