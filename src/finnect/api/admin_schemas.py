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


class AttachProgressOut(BaseModel):
    """첨부 받기 진행. `attach/service.py` `AttachProgress` 사본이고 **`running` 일 때만
    의미가 있다.**

    **`total` 에 이미 받아 둔 것은 없다.** 3,354건 중 2,827건이 끝난 상태에서 분모가
    3,354 면 막대가 처음부터 84% 에서 시작한다 — 그것은 이번 실행의 진행이 아니다.
    """

    #: 이번에 받을 것
    total: int
    #: 그중 처리한 것
    done: int
    #: 이미 받아 둬서 대상에서 뺀 것. **`total` 밖의 숫자다**
    skipped: int
    bytes_in: int
    #: 이번에 받기로 한 건수(맛보기). None 이면 전량
    target: int | None
    #: 막대의 분모. **`total` 이 아니다** — 맛보기 2건이면 2다. **화면이 다시 안 나눈다**
    goal: int | None
    #: 분모가 0 이면 None 이다. **0% 로 그리지 않는다** — 받을 것이 없는 것과 다르다
    percent: int | None


class JobOutcomeOut(BaseModel):
    """마지막 실행이 어떻게 끝났나. `ingest/jobs.py` `Outcome` 사본.

    **메모리에만 산다** — API 를 재시작하면 사라진다. 수집은 `ingest_run` 표가 이
    자리를 대신하지만 첨부 받기는 그 표가 없다([ADR-0071](
    ../../../docs/adr/0071-첨부-받기를-운영-화면에-연다.md)).
    """

    ok: bool
    detail: str


class AdminAttachOut(BaseModel):
    """첨부 받기 카드.

    **`AdminAttachmentsOut`(해독 현황)과 따로다.** 저건 집계 다섯을 훑는 무거운
    질의라 실행 중에 1.5초마다 두드릴 것이 아니다. 여기는 URL 표만 센다.
    """

    running: bool
    #: 첫 보고 전에는 None 이다. **`running` 이 참인데 여기가 비어 있으면 "세는 중" 이다**
    progress: AttachProgressOut | None
    #: 아직 안 받은 첨부 URL 수. **버튼이 이 숫자만큼만 받는다**
    pending: int
    #: 첨부 URL 전체. `pending` 이 그중 몇인지 화면이 말할 수 있어야 한다
    urls: int
    last: JobOutcomeOut | None


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
    """지금까지 받은 양. `running` 이 참일 때만 의미가 있다 — `ingest/jobs.py` `Progress` 사본.

    **단계가 둘이다**(2026-08-24). K-Startup 을 모집중만 받으면 목록 뒤에 상세 페이지
    긁기가 이어 붙는데, `phase` 없이는 화면이 그 몇 분을 "멈췄다"로 그린다.
    `goal`·`percent` 는 단계에 맞는 분모로 이미 계산돼서 온다 — **화면이 다시 안 나눈다.**
    """

    pages: int
    items: int
    expected: int | None
    target: int | None
    goal: int | None
    percent: int | None
    #: "목록" 또는 "첨부". 화면이 이 값으로 문장을 고른다
    phase: str
    #: 첨부 단계에서만 찬다. 목록 단계에서는 0 이다
    scraped: int
    scrape_total: int


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
