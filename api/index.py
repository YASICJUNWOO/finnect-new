"""Vercel Python Function 진입점 — 제품 API 를 그대로 얹는다.

**여기 로직을 두지 않는다.** `src/finnect/api/app.py` 가 정본이고 이 파일은 경로만 잇는다.
로컬에서는 이 파일 없이 uvicorn 으로 같은 앱을 띄운다.

    uv run uvicorn finnect.api.app:app --port 8100
"""

import sys
from pathlib import Path

# 저장소가 src 레이아웃이라 패키지가 `src/` 아래 있다. Vercel 은 프로젝트 루트에서
# 함수를 실행하므로 여기를 직접 얹는다. vercel.json 의 includeFiles 가 짝이다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finnect.api.app import app  # noqa: E402

__all__ = ["app"]
