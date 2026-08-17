"""응답 모양.

**필드 이름을 새로 짓지 않는다.** `views.py` 의 `Notice` 가 쓰는 이름을 그대로 쓴다.
저장 모델이 "API 가 준 이름 그대로"를 지키는 것과 같은 이유다 — 이름이 한 번 더 바뀌면
화면에서 본 값이 DB 의 어느 칸인지 추적이 끊긴다.

파생값은 `apply_end` 옆에 `days_left` 처럼 나란히 두고 **원문을 지우지 않는다**(ADR-0024).
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class AttachmentOut(BaseModel):
    """첨부 하나. **API 가 준 메타와 우리가 해 본 결과를 한 덩어리로 준다.**

    앞의 다섯은 `attachment`(출처가 준 것), 뒤의 넷은 `attachment_file`(우리가 한 것)에서 온다.
    화면이 둘을 갈라 보여줄 필요는 없지만 **못 읽은 것을 안 읽은 척하면 안 된다**(plan/09 T-0027).
    """

    position: int
    kind: str
    filename: str
    ext: str | None
    url: str | None

    #: None 이면 **아직 안 받아 봤다**. 실패와 구분한다.
    fetch_status: str | None
    #: None 이면 아직 안 읽어 봤다. `unsupported`·`failed`·`empty`·`container` 는 각각 뜻이 다르다.
    parse_status: str | None
    text_chars: int | None
    #: 내용으로 판정한 확장자. `ext`(파일명 기준)와 다를 수 있다 — 3,354건 중 7건.
    detected_ext: str | None


class NoticeOut(BaseModel):
    """목록 한 줄."""

    source: str
    external_id: str
    title: str | None
    organization: str | None
    supervisor: str | None
    category: str | None

    # --- 접수 기간. 셋을 함께 낸다(ADR-0024) ---
    apply_start: dt.date | None
    apply_end: dt.date | None
    #: 날짜가 아닌 원문. 876건이 "예산 소진시까지" 같은 값이다. **뭉개지 않는다**
    apply_period_raw: str | None
    #: `apply_end` 가 있을 때만. 음수면 이미 지난 것이다. 프론트가 날짜 계산을 하지 않는다
    days_left: int | None

    detail_url: str | None
    attachment_count: int


class NoticeListOut(BaseModel):
    items: list[NoticeOut]
    total: int
    page: int
    pages: int
    #: 마감된 공고를 뺀 응답인가. 화면이 "무엇을 안 보여주고 있는지" 말할 수 있어야 한다
    open_only: bool


class NoticeDetailOut(NoticeOut):
    """상세. 목록에 요약과 첨부가 붙는다."""

    #: HTML 을 푼 평문. 내용이 없으면 None 이다(`api/text.py`)
    summary: str | None
    attachments: list[AttachmentOut]
    #: 첨부 중 텍스트가 나온 것의 수. `len(attachments)` 와 다르다
    decoded_count: int
