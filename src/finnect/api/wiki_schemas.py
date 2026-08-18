"""사업 위키 응답 모양(S7).

**필드 이름을 새로 짓지 않는다.** `wiki/topics.py` 와 `wiki/markdown.py` 가 쓰는 이름을
그대로 쓴다. 공고 쪽이 `views.py` 의 이름을 그대로 쓰는 것과 같은 이유다 — 이름이 한 번
더 바뀌면 화면에서 본 값이 DB 의 어느 칸인지 추적이 끊긴다.

**저장값과 표시값을 둘 다 낸다.** `value` 는 `120000000`, `display` 는 `120,000,000원` 이다.
프론트가 단위를 붙이면 슬롯마다 규칙을 한 벌 더 들게 되고, 그 규칙이 서버와 갈린다.
"""

from __future__ import annotations

from pydantic import BaseModel


class EvidenceOut(BaseModel):
    """근거 하나. **출처는 문자열이 아니라 연결이다**(SPEC F1-3).

    `filename` 과 `page` 를 따로 주는 이유는 화면이 "3쪽"을 다르게 쓸 수 있어서다.
    미리 이어 붙인 문자열을 주면 그 자유가 없어진다.
    """

    filename: str
    #: PDF · PPTX 만 찬다. 나머지 포맷에는 쪽이라는 것이 없다
    page: int | None
    #: 청크 안에서 근거가 된 조각. 청크 전문을 열기 전에 이걸 먼저 보여 준다
    quote: str


class ValueOut(BaseModel):
    """정형 슬롯의 주장 하나. **충돌하면 같은 자리에 여럿이 온다.**"""

    slot: str
    label: str
    #: 정규화된 저장값. 병합의 재료라 화면이 이걸 고쳐 쓰지 않는다
    value: str
    #: 사람이 읽는 값. 단위가 붙어 있다
    display: str
    #: `시드` · `정책자금` · `예비창업패키지`
    qualifier: str | None
    #: 언제 기준의 값인가. 시점 없는 슬롯은 항상 null
    as_of: str | None
    #: `current` 지금 값 · `superseded` 더 늦은 값이 있다 · `conflict` 값이 갈렸다
    status: str
    evidence: list[EvidenceOut]


class StatementOut(BaseModel):
    """서술 노드의 사실 하나."""

    text: str
    #: LLM 이 붙인 라벨. **목적지가 아니다** — 목적지는 `wiki/topics.py` 가 정했다
    topic: str
    evidence: list[EvidenceOut]


class WikiNodeOut(BaseModel):
    """궤도 위의 자리 하나. **빈 자리도 온다** — 비어 있다는 것도 보여야 한다."""

    key: str
    label: str
    #: `identity` · `company` · `content`. **색은 이것만 말한다**(DESIGN.md §4.1)
    kind: str
    sector: str
    #: 자격 판별(M1)의 입력을 담은 자리인가. 비면 물어야 한다(ADR-0028)
    eligibility: bool
    values: list[ValueOut]
    statements: list[StatementOut]
    #: 근거로 쓰인 **파일 수**. 근거 개수가 아니다
    source_count: int
    filled: bool
    conflicted: bool
    #: 이 자리 한 장의 마크다운. **저장된 것이 아니라 매번 만든 것이다**
    markdown: str


class WikiFileOut(BaseModel):
    """올린 파일 하나와 **그 파일이 만든 자리**(F1-4-7)."""

    filename: str
    ext: str | None
    byte_size: int
    #: `done` · `chunked` · `needs_review` · `failed` …
    status: str
    parse_status: str | None
    parser: str | None
    parse_error: str | None
    chunk_count: int | None
    page_count: int | None
    #: 이 파일이 근거가 된 궤도 자리들
    nodes: list[str]


class WikiOut(BaseModel):
    """S7 한 장. **궤도 열다섯이 항상 온다.**"""

    company_id: str
    #: 궤도 자리 열다섯. 순서가 곧 배치 순서다(ADR-0017)
    nodes: list[WikiNodeOut]
    files: list[WikiFileOut]
    #: 구획 이름. 궤도 위에 얹는 라벨(ADR-0017 결정 2)
    sectors: dict[str, str]

    # --- 채움 상태 (F1-4-2). **막대를 만들지 않는다** — 숫자로만 말한다 ---
    filled: int
    total: int
    conflicts: int
    #: 갈 자리를 못 찾아 검토 대기에 선 사실 수. **버린 것이 아니다**
    uncategorized: int
    #: 아직 스텁이 뽑고 있나. 화면이 그렇게 말해야 한다(ADR-0031)
    extractor: str | None
