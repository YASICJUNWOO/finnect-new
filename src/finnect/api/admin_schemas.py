"""운영 화면 응답 모양.

**제품 응답(`schemas.py`)과 섞지 않는다.** 저기는 사용자가 볼 값을 고른 것이고
여기는 **출처가 준 것을 하나도 안 고르고 다 낸다.** 목적이 반대다 —
`admin/app.py` 독스트링이 그 목적을 적어 뒀다. L1 스키마 설계를 위한 코퍼스 관찰이다.

이름은 DB 컬럼 이름 그대로다. 여기서 한 번 더 바꾸면
**화면에서 본 값이 DB 의 어느 칸인지 추적이 끊긴다**(`schemas.py` 와 같은 이유).
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class AdminNoticeOut(BaseModel):
    """운영 목록 한 줄. 제품 목록(`NoticeOut`)과 열이 다르다."""

    source: str
    external_id: str
    title: str | None
    organization: str | None
    apply_end: dt.date | None
    apply_period_raw: str | None
    #: 저장된 첨부 수. `attachment_status` 가 `unknown` 이면 0 과 뜻이 다르다
    attachment_count: int
    #: 출처가 첨부를 알려줬는가. K-Startup 은 전량이 `unknown` 이다
    attachment_status: str | None
    last_seen_at: dt.datetime | None


class AdminNoticeListOut(BaseModel):
    items: list[AdminNoticeOut]
    total: int
    page: int
    pages: int
    page_size: int
    sort: str
    #: 고를 수 있는 정렬 {키: 이름}. 프론트가 목록을 짓지 않는다
    sorts: dict[str, str]
    #: 출처별 전체 건수. 필터와 무관하다
    by_source: dict[str, int]


class FieldOut(BaseModel):
    """컬럼 한 칸. **값과 설명과 출처를 함께 낸다.**"""

    name: str
    #: 문자열로 낸다. 원문 컬럼이 전부 TEXT 라 타입을 지어낼 자리가 없다
    value: str | None
    #: 공식 문서에 있는 항목명. None 이면 **문서에 없다.** 이름으로 추측해 채우지 않는다
    description: str | None


class AdminAttachmentOut(BaseModel):
    """첨부 하나 — 메타(`attachment`)와 해 본 결과(`attachment_file`)를 한 줄로."""

    position: int
    kind: str
    filename: str
    ext: str | None
    url: str | None

    fetch_status: str | None
    parse_status: str | None
    parser: str | None
    text_chars: int | None
    #: 내용으로 판정한 확장자. `ext`(파일명 기준)와 다를 수 있다
    detected_ext: str | None
    fetch_error: str | None
    parse_error: str | None
    #: ZIP 안 파일 이름들. **풀지는 않았다**
    contents: list[str]


class RawFetchOut(BaseModel):
    """원문 응답 한 건. **봉투를 남기는 이유는 두 API 가 실패를 200 으로 주기 때문이다.**"""

    id: int
    #: 인증키는 `ingest/base.py` `mask()` 가 지운 뒤 저장된다
    request_url: str
    fetched_at: dt.datetime | None
    page: int | None
    item_count: int
    byte_size: int
    ratelimit_remaining: int | None
    #: 공고 배열을 뺀 나머지. 이미 JSON 문자열이다
    envelope: str
    #: 이 공고의 item. 응답 안에서 못 찾으면 None
    item: str | None
    #: 같은 응답에 함께 온 공고 수
    siblings: int


class AdminNoticeDetailOut(BaseModel):
    """운영 상세. **뷰를 거치지 않고 출처별 표에서 직접 읽는다.**"""

    source: str
    external_id: str
    table: str

    #: 출처가 준 컬럼. 기업마당 22 · K-Startup 30
    api_fields: list[FieldOut]
    #: 우리가 붙인 컬럼. `extra` 는 빠져 있다 — 아래 `extra` 가 그것이다
    ours: list[FieldOut]
    #: 처음 보는 필드. 비어 있지 않으면 **API 가 늘어났다는 뜻이다**
    extra: dict[str, str]

    #: 설명이 문서에 있는 컬럼 수 / API 컬럼 수
    described: int
    described_total: int
    doc_label: str
    doc_url: str | None

    attachments: list[AdminAttachmentOut]
    decoded_count: int

    raw: RawFetchOut | None


class StatusCountOut(BaseModel):
    """상태별 건수. `status` 가 None 이면 **아직 안 해 봤다**는 뜻이다."""

    status: str | None
    count: int


class ByExtOut(BaseModel):
    ext: str | None
    status: str
    count: int
    avg_chars: int


class CoverageOut(BaseModel):
    """해독 현황.

    **`unaccounted` 가 첫 줄이다.** 첨부 URL 중 상태 행이 없는 것, 곧 조용히 사라진 건수다.
    0이 아니면 아래 숫자는 모집단이 아니다(plan/07 검증).
    """

    listed: int
    urls: int
    files: int
    unaccounted: int
    fetch: list[StatusCountOut]
    parse: list[StatusCountOut]
    by_ext: list[ByExtOut]


class OcrOut(BaseModel):
    """OCR 없이는 0바이트인 것들. **T-0007 의 입력이고 여기서 결정하지 않는다.**"""

    pdf_empty: int
    images: int
    image_notices: int


class AdminAttachmentsOut(BaseModel):
    coverage: CoverageOut
    ocr: OcrOut
    #: `ATTACHMENT_FORMATS` 설정값. 여기 없는 포맷은 `unsupported` 로 **기록된다**
    formats: list[str]


class RunOut(BaseModel):
    """수집 실행 한 건. **실패한 실행도 행으로 남는다.**"""

    id: int
    source: str
    only_open: bool
    #: 어느 솎기 정책으로 받았나. `only_open` 과 같은 자리다 — 한쪽만 기록하면
    #: 나중에 "이 코퍼스가 왜 이 크기지" 를 못 푼다(ADR-0064).
    filter_name: str | None
    #: 정책으로 뺀 건수. `skipped`(외부 ID 가 없어 못 넣은 사고)와 다른 숫자다
    filtered: int
    trigger: str
    status: str
    started_at: dt.datetime | None
    #: 사람이 읽는 문자열. 날짜 계산을 프론트가 하지 않는다
    elapsed: str
    item_limit: int | None
    expected: int | None
    truncated: bool
    pages: int
    items: int
    inserted: int
    changed: int
    unchanged: int
    report: str | None
    error: str | None
    #: 처음 보는 필드 {이름: 건수}. **조용히 사라지지 않게 화면까지 들고 간다**
    unknown_fields: dict[str, int]


class IngestProgressOut(BaseModel):
    """지금까지 받은 양. `running` 이 참일 때만 의미가 있다 — `ingest/jobs.py` `Progress` 사본."""

    pages: int
    items: int
    expected: int | None
    target: int | None
    goal: int | None
    percent: int | None


class SourceCardOut(BaseModel):
    """출처 카드 한 장.

    **`running`·`progress` 가 2026-08-24 부터 있다**(ADR-0065). API 가 더 이상
    서버리스가 아니라 이 값을 만드는 프로세스와 같은 프로세스에서 읽는다 — ADR-0027 이
    "배포본이 알 수 없다"고 적은 전제가 ADR-0035 로 바뀌었다.
    """

    name: str
    label: str
    expected: int
    requests: str
    note: str
    stored: int
    last: RunOut | None
    running: bool
    progress: IngestProgressOut | None


class AdminIngestOut(BaseModel):
    cards: list[SourceCardOut]
    runs: list[RunOut]


class IngestTriggerOut(BaseModel):
    """실행 요청의 결과. `ingest/jobs.py` `Launch` 사본."""

    started: bool
    reason: str = ""
