# Inha University & RODIX Inc, Anders Hwang
# 파일명: conftest.py
# 목적 및 역할:
# 테스트 실행 시 src 폴더를 import 경로에 추가한다.
# 작성자: RODIX Anders Hwang

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

