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


class RecommendationOut(NoticeOut):
    """추천 한 장 (plan/17 T-0075).

    **적합도 숫자가 없다.** 목록이 이미 적합도순이라 순서가 정보를 담는다
    (`DESIGN.md` §6). 92 와 74 의 차이를 설명할 눈금이 없다.
    """

    #: 왜 맞는지 한 줄. **비어 있으면 추천에 오르지 않는다** — 이유 없는 점수는
    #: 근거가 없다(ADR-0013)
    reason: str
    #: 이 이유가 위키의 몇 개 사실에서 나왔나. 화면이 "근거 2" 로 쓴다
    evidence_count: int


class RecommendationsOut(BaseModel):
    """`DESIGN.md` §6.1 의 두 섹션 중 위쪽. 아래쪽은 `/api/notices` 다."""

    items: list[RecommendationOut]
    #: 위키가 아직 없거나 판정이 안 돌았다. **빈 목록과 다르다** —
    #: 저쪽은 맞는 것이 없다는 뜻이고 이쪽은 아직 못 봤다는 뜻이다
    computed: bool


class FitOut(BaseModel):
    """이 공고가 이 회사에게 왜 맞는가 (plan/21 T-0120).

    **자격을 안 낸다.** [ADR-0003](../../../docs/adr/0003-판별-비노출.md) 이
    「판정은 뒤에서 하고 화면은 결과만 준다」로 정했고, 자격 결과는 **목록에서
    빼는 것**으로 이미 나갔다. 여기 등급별 대조표를 두면 그 결정을 되돌리는 것이다.

    **`맞다`·`애매` 만 저장된다**(`notice_fit`). 없으면 이 필드가 통째로 `None` 이고,
    화면은 자리를 안 그린다 — **「안 맞아요」가 아니라 「아직 안 봤어요」다.**
    """

    #: `맞다` · `애매`. **점수가 없다**(`DESIGN.md` §7 · §12.2)
    verdict: str
    #: 왜 맞는지 한 줄. 템플릿이 만들고 LLM 이 안 만든다(`match/rank.py`)
    reason: str
    #: 그 이유가 위키의 몇 개 사실에서 나왔나
    evidence_count: int


class NoticeDetailOut(NoticeOut):
    """상세. 목록에 요약과 첨부가 붙는다."""

    #: HTML 을 푼 평문. 내용이 없으면 None 이다(`api/text.py`)
    summary: str | None
    attachments: list[AttachmentOut]
    #: 첨부 중 텍스트가 나온 것의 수. `len(attachments)` 와 다르다
    decoded_count: int
    #: `?company=` 를 줬고 판정이 있을 때만 찬다. **없으면 `None` 이다** —
    #: 빈 객체를 주면 화면이 「이유가 비었다」와 「아직 안 봤다」를 못 가른다
    fit: FitOut | None = None


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
    #: 원본 파일의 콘텐츠 주소. `/api/attachments/{sha256}/file` 이 이걸 받는다.
    #: **미리보기가 원본을 열려면 있어야 한다** — 파일명은 같은 이름이 여럿이라 키가 안 된다.
    sha256: str
    #: 내용으로 판정한 확장자. **파일명의 확장자가 아니다** — 3,354건 중 7건이 서로 다르다.
    #: 화면이 이걸로 「미리보기가 열 수 있는 포맷인가」를 정한다.
    ext: str | None
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
    #: **사람이 고쳤다.** `status` 에 안 넣는다 — 저 표는 집필이 어떻게 됐나를
    #: 말하고 이것은 다른 축이다([ADR-0055](
    #: ../../../docs/adr/0055-사람이-고친-글을-집필-출력-위에-덮지-않는다.md) 결정 2)
    edited: bool = False
    #: 고친 뒤라 **문단과 근거의 대응이 깨졌다.** `draft_evidence` 는 DB 에 그대로
    #: 남아 파급 계산이 돌지만(ADR-0028 4번), 화면에는 안 낸다 — 사람이 고친 문장
    #: 옆에 「이 사실에서 나왔어요」를 적으면 그것이 거짓이 될 수 있다
    evidence_detached: bool = False
    #: 집필기가 쓴 글. **고쳤을 때만 찬다** — 되돌릴 자리를 화면이 알아야 한다
    original: str | None = None
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
    #: 지금 쓰고 있다. **이 값 없이는 「빈 목록」이 「아직 안 눌렀다」인지
    #: 「누르고 기다리는 중」인지 안 갈린다**([ADR-0054](
    #: ../../../docs/adr/0054-초안을-만드는-길을-api-에-열고-공고-회사-단위로-잠근다.md) 결정 7)
    running: bool = False


class DraftStartOut(BaseModel):
    """초안 만들기를 눌렀을 때 (plan/21 T-0121 · ADR-0054).

    **202 다.** 시작만 하고 답한다 — 항목 수십 개를 다 쓰고 답하면 요청이 몇 분씩
    묶인다. 올리기(`UploadOut`)와 같은 모양이다.
    """

    #: 시작했나. **거절이 오류가 아니다** — 이미 돌고 있으면 `false` 다
    started: bool
    #: 왜 못 시작했나. 시작했으면 빈 문자열
    reason: str = ""
    #: 지금 상태. 시작 직후를 화면이 그대로 그린다
    draft: DraftOut


class DraftItemEditIn(BaseModel):
    """사람이 고친 글 (plan/21 T-0123 · ADR-0055).

    **`None` 과 `""` 가 다르다.** `None` 은 되돌리기(집필기 글이 다시 보인다)이고
    빈 문자열은 **일부러 비운 것**이다. 둘을 섞으면 지운 항목에 초안이 다시 나타난다.
    """

    #: 고친 본문. 문단은 `\n\n` 으로 가른다. `null` 이면 되돌린다
    text: str | None
