"""출처 설명 — 화면 카드가 읽는 값.

**`ingest/service.py` 에서 떼어 낸 것이고 값은 그대로다.** 뗀 이유는 하나다.
저기는 `httpx` 와 수집 어댑터를 끌고 오는데, `requirements.txt` 가 **읽기만 하는 API 에서
그 둘을 뺐다.** 서버리스 함수가 `SOURCES` 하나를 읽으려고 다운로더를 싣게 되면
콜드 스타트만 길어지고, 그 전에 `ModuleNotFoundError` 로 죽는다.

그래서 이 모듈은 **서드파티를 하나도 임포트하지 않는다.** 늘릴 때도 그 선을 지킨다.

건수와 요청 수는 2026-08-16 실측이다 —
`docs/adr/evidence/2026-08-16-목록-API-실측.md`.
"""

from __future__ import annotations

from dataclasses import dataclass

from finnect.models import Source


@dataclass(frozen=True)
class SourceInfo:
    """화면 카드가 읽는 출처 설명."""

    name: str
    label: str
    key_env: str
    expected: int
    requests: str
    note: str


SOURCES: tuple[SourceInfo, ...] = (
    SourceInfo(
        name=str(Source.BIZINFO),
        label="기업마당",
        key_env="BIZINFO_API_KEY",
        expected=1538,
        requests="요청 1회",
        note="목록 API 가 첨부를 알려준다. 첨부 0개가 431건(28%)이고 그건 확인된 0개다.",
    ),
    SourceInfo(
        name=str(Source.KSTARTUP),
        label="K-Startup",
        key_env="DATA_GO_KR_API_KEY",
        expected=29789,
        requests="요청 149회 · 일 한도 10,000",
        note="첨부 필드가 없어 전량이 미확인이다. 수정일시도 없어 변경 감지는 해시뿐이다.",
    ),
)

BY_NAME: dict[str, SourceInfo] = {s.name: s for s in SOURCES}
