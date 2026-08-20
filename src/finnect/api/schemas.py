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


class DocumentItemOut(BaseModel):
    """작성 항목 하나. **양식이 쓴 말을 그대로 넘긴다** — 우리가 고쳐 쓰지 않는다."""

    number: str | None
    title: str
    instruction: str | None
    limit_text: str | None
    input_kind: str
    children: list[DocumentItemOut] = []


class DocumentOut(BaseModel):
    """낼 서류 한 벌. 첨부 하나 안의 한 구간이다(plan/11 T-0035)."""

    id: int
    title: str
    #: `fields` 칸 채우기 · `narrative` 글로 쓰는 것 · `none` · `unknown`
    kind: str
    #: 무엇이 판정했나. `rule/v1` · `llm/<모델>`
    decided_by: str
    filename: str
    url: str | None
    items: list[DocumentItemOut]


class NoticeDocumentsOut(BaseModel):
    """공고 하나가 요구하는 서류 전부.

    **`unknown` 구간은 안 내보낸다.** 서술형 판정이 아직 없어서(plan/11 T-0036)
    내보내면 공고문 절이 작성 항목으로 보인다. **모르는 것을 아는 척하지 않는다.**
    """

    source: str
    external_id: str
    documents: list[DocumentOut]
    #: 양식이 없을 때 공고문이 서류에 대해 말한 줄. 원문 그대로다.
    submit_hint: list[str]
    #: 아직 안 갈라 낸 구간 수. 0 이 아니면 화면이 그렇게 말해야 한다.
    undecided: int


# --- 초안 (plan/16 · F6) -----------------------------------------------------


class EvidenceOut(BaseModel):
    """문단 하나가 어디서 나왔나 (F6-13).

    **`fact_id` 를 내보낸다.** 화면이 그 사실을 눌러 위키로 건너가고, 그 사실이
    갱신되면 어느 항목이 낡았는지 되짚는다([ADR-0028](
    ../../../docs/adr/0028-초안을-먼저-완성하고-못-채운-자리에서-묻는다.md) 4번).
    """

    fact_id: int
    #: 위키에서 어느 자리인가. `problem` · `revenue`
    place: str
    #: 사람이 읽는 자리 이름. **화면이 한국어를 짓지 않는다**(`topics.display()` 규율)
    place_label: str
    #: 그 사실 문장
    text: str
    #: 근거 청크. **`user_stated` 면 없다** — 사용자가 말한 것은 원문이 없다
    chunk_id: int | None
    #: 청크에서 잘라 온 조각. 원문을 열기 전에 이걸 먼저 보여 준다
    quote: str | None
    #: `document` · `user_stated`. **색을 새로 주지 않고 글자로 가른다**(ADR-0028 결과 절)
    source_type: str


class ParagraphOut(BaseModel):
    """문단 하나와 그 근거."""

    ordinal: int
    text: str
    evidence: list[EvidenceOut]


class MissingOut(BaseModel):
    """필요한데 위키에 없는 자리. **F6-6 이 가리키는 것**."""

    place: str
    place_label: str
    #: 없으면 이 항목을 아예 못 쓰는가
    required: bool


class LengthOut(BaseModel):
    """분량. **저장하지 않고 읽을 때 계산한다**(`draft/limits.py`)."""

    #: `none` 제한 없음 · `ok` · `over` · `unmeasurable`
    verdict: str
    #: 양식이 쓴 말. `50페이지 내외`
    limit_text: str | None
    #: 잰 값. 쪽 수 제한이면 None — **환산하지 않는다**
    measured: int | None
    note: str


class DraftItemOut(BaseModel):
    """항목 하나의 초안.

    **`body` 가 비어 있어도 내보낸다.** `blank` 인 항목이 화면에서 사라지면 적립
    루프의 입구가 없어진다 — 못 쓴 자리를 보여 주는 것이 F6-6 이다.
    """

    document_item_id: int
    number: str | None
    title: str
    #: 양식이 쓴 "무엇을 쓰라". **우리가 고쳐 쓰지 않는다**
    instruction: str | None

    #: `drafted` 문서 근거로 썼다 · `answered` 사용자 답변이 들어갔다 ·
    #: `blank` **위키에 없어서 못 썼다 — 여기만 물어본다** ·
    #: `no_needs` 쓸 자리가 아니다(상위 묶음) ·
    #: `yielded` 위키에는 있는데 다른 항목이 맡았다 ·
    #: `unwritten` **재료는 받았는데 글이 안 나왔다 — 집필 실패다** ·
    #: `stale` 근거가 바뀌었다
    status: str
    paragraphs: list[ParagraphOut]
    missing: list[MissingOut]
    #: 있으면 좋은데 없는 자리. **물어볼 목록의 뒷줄이다**
    missing_optional: list[MissingOut]
    length: LengthOut
    #: `yielded` 일 때, 그 재료를 맡은 항목 번호들. **"그 얘기는 6번에 썼어요"**
    yielded_to: list[str]
    #: 이 항목만 실패했다. 나머지는 남는다(ADR-0015)
    error: str | None
    children: list[DraftItemOut] = []


class DraftDocumentOut(BaseModel):
    """양식 하나에 대한 초안 한 벌."""

    document_id: int
    title: str
    filename: str
    #: 무엇이 배분했나. `llm/<모델>` · `none`(다툰 것이 없어 안 불렀다)
    allotted_by: str | None
    items: list[DraftItemOut]


class DraftOut(BaseModel):
    """공고 하나 + 회사 하나의 초안.

    **없으면 빈 목록이다. 404 가 아니다.** 아직 안 쓴 것과 쓸 수 없는 것을 화면이
    같은 자리에서 말해야 하고, 404 는 원인을 안 남긴다(ADR-0034 와 같은 규율).
    """

    company_id: str
    source: str
    external_id: str
    documents: list[DraftDocumentOut]
    #: 이 공고에 서술형 양식이 있는데 초안이 아직 없다 — 돌리면 생긴다
    pending_documents: int
