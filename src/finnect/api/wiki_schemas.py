"""사업 위키 응답 모양(S7).

**필드 이름을 새로 짓지 않는다.** `wiki/tree.py`·`wiki/profile.py`·`wiki/markdown.py` 가
쓰는 이름을 그대로 쓴다. 공고 쪽이 `views.py` 의 이름을 그대로 쓰는 것과 같은 이유다 —
이름이 한 번 더 바뀌면 화면에서 본 값이 DB 의 어느 칸인지 추적이 끊긴다.

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


class StatementOut(BaseModel):
    """자리에 앉은 사실 하나(트랙 A).

    **`key` 가 없어졌다**(2026-08-22 · ADR-0058). 자리가 곧 이름이라 사실마다 이름을
    한 번 더 짓는 것이 모호했다 — 같은 것을 두 어휘로 부르게 되고, 그 모호함이 자리를
    다시 갈랐다. **화면은 절 제목 없이 시점 내림차순으로 세운다.**
    """

    text: str
    #: `value` 또는 `event`
    kind: str
    #: 정규화된 저장값. `event` 면 null 이다. **화면이 이걸 고쳐 쓰지 않는다**
    #:
    #: **`display` 짝이 없다.** 단위표(`profile.PROFILE_KEYS`)는 매칭 정보 열넷의 것이고
    #: 트랙 A 의 값은 자유롭게 오니 거기 없다 — 없는 단위를 붙이면 값이 거짓이 된다
    value: str | None
    #: 같은 자리 안에서 무엇을 가리키나. `TAM` · `시드`. **자유 문자열이다**
    qualifier: str | None
    as_of: str | None
    #: 기획 §5 의 자료 등급. `1차` · `2차` · `가정`. 안 매겨졌으면 빈 문자열
    grade: str
    #: `2차` 일 때 문서가 밝힌 기관·자료 이름
    source: str
    evidence: list[EvidenceOut]


class WikiNodeOut(BaseModel):
    """자리 하나(트랙 A). **빈 폴더도 온다** — 무엇이 없는지 보여야 한다.

    **`path` 가 이 자리의 이름이다**(기획 §4-3 "경로가 곧 노드 제목이다"). 화면과 기획
    문서와 집필 에이전트가 같은 문자열을 쓴다.
    """

    #: `Company/팀` · `Custom/특허/등록-10-2025-0114882`
    path: str
    #: 경로의 마지막 마디. 화면에 쓰는 이름
    name: str
    #: 최상위 폴더. **각도 구획이다.** 라벨은 `WikiOut.categories` 가 준다
    category: str
    #: 부모 경로. 최상위면 빈 문자열
    parent: str
    #: 몇 번째 층인가. 0 이 폴더다
    depth: int

    #: **시점 내림차순으로 이미 정렬돼 있다**(ADR-0057 결정 3). 시점 없는 것이 뒤로
    #: 간다. **정렬 규칙을 프론트에 안 적으려고** 서버가 순서를 정해 준다.
    #: 그래프는 이 길이를 점 개수로 쓴다
    statements: list[StatementOut]
    #: 근거로 쓰인 **파일 수**. 근거 개수가 아니다
    source_count: int
    filled: bool

    #: 기획 §5 의 자료 등급 다섯 중 하나. **한 장에 사실이 여럿이면 가장 약한 것이다**
    grade: str
    source: list[str]
    #: `source` 와 같은 순서다
    source_path: list[str]
    #: 사실이 바뀐 시각. **만든 시각이 아니다**
    updated_at: str | None
    #: 이 노드 한 장의 마크다운. 빈 뼈대면 빈 문자열이다
    markdown: str


class ValueOut(BaseModel):
    """회사 정보 한 칸의 주장 하나(트랙 B). **충돌하면 같은 자리에 여럿이 온다.**"""

    #: 정규화된 저장값. 병합의 재료라 화면이 이걸 고쳐 쓰지 않는다
    value: str
    #: 사람이 읽는 값. 단위가 붙어 있다
    display: str
    #: `시드` · `정책자금`. **자유 문자열이다**
    qualifier: str | None
    as_of: str | None
    #: `current` 지금 값 · `superseded` 더 늦은 값이 있다 · `conflict` 값이 갈렸다
    status: str
    evidence: list[EvidenceOut]


class ProfileKeyOut(BaseModel):
    """회사 정보 한 칸. **열넷 고정이라 빈 칸을 셀 수 있다**(ADR-0028)."""

    key: str
    label: str
    #: 자격 판별(M1)의 입력인가. **비면 물어야 한다**
    eligibility: bool
    #: 지금 값들. 충돌이면 둘 이상이다
    current: list[ValueOut]
    #: 더 늦은 값이 있어 밀린 것들
    history: list[ValueOut]
    conflicted: bool


class ProfileOut(BaseModel):
    """회사 정보 한 장(`/company`). **그래프에 안 뜬다**(ADR-0056 결정 1)."""

    company_id: str
    #: 열넷 고정. 순서가 `PROFILE_KEYS` 표 순서다
    keys: list[ProfileKeyOut]
    #: 채운 칸 수. **막대를 만들지 않는다** — 「14칸 중 12칸」으로만 말한다
    filled: int
    total: int
    conflicts: int


class WikiFileOut(BaseModel):
    """올린 파일 하나와 **그 파일이 채운 자리**(F1-4-7)."""

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
    #: 이 파일이 근거가 된 트리 자리들. **경로다** — 이름은 `spots[].title` 이 준다
    spots: list[str]


class WikiOut(BaseModel):
    """S7 한 장(트랙 A). **폴더 열은 비어도 온다.**"""

    company_id: str
    #: 자리 전부. **순서는 `spots.FOLDERS` 표가 정하고 그 안에서는 경로순이다**
    nodes: list[WikiNodeOut]
    files: list[WikiFileOut]
    #: 폴더 키 → 한국어 이름. 열 개 고정. **화면이 이름을 짓지 않는다**
    categories: dict[str, str]

    # --- 채움 상태 (F1-4-2). **막대를 만들지 않는다** — 숫자로만 말한다 ---
    #: 사실이 앉은 **자리표 자리** 수. `{…}` 자리는 인스턴스 여럿이 하나로 접힌다
    filled: int
    #: **자리표 마흔여섯 고정이다**(`spots.SPOTS`). 노드 수가 아니다 — 조상 뼈대와
    #: 폴더 열이 섞여 들어가서 2026-08-22 화면이 「자리 71개」라고 말했고, 그중
    #: 스물다섯은 **사용자가 채울 수 있는 것이 아니었다**
    total: int
    #: **이번 회차에 새로 만든 노드가 아니라 검토 대기에 선 사실 수다**
    review: int
    #: 아직 스텁이 뽑고 있나. 화면이 그렇게 말해야 한다(ADR-0031)
    extractor: str | None


# --- 올리기와 진행 표시 (S1 · plan/15) --------------------------------------
#
# **여기 값은 전부 `wiki/progress.py` 가 정한다.** 화면이 단계 이름을 지으면 서버와
# 갈리고, 갈린 순간 어느 쪽이 진짜 상태인지 알 수 없게 된다. `topics.display()` 로
# 단위를 한 자리에 모은 것과 같은 이유다.


class StepOut(BaseModel):
    """단계 하나. **다섯 개가 고정이고 순서가 곧 진행 순서다.**"""

    key: str
    label: str


class FileProgressOut(BaseModel):
    """올린 파일 하나가 지금 어디까지 왔나(SPEC F1-1-9).

    **파일별로 독립이다**(F1-1-8). 하나가 실패해도 나머지는 계속 간다 — 그래서 전체
    진행률 하나가 아니라 파일마다 한 줄이다.
    """

    filename: str
    ext: str | None
    byte_size: int
    #: DB 의 원래 상태. `uploaded` · `parsing` · `chunked` · … 여덟 가지
    status: str
    #: 끝낸 칸 수. 0 ~ 5. **백분율이 아니다**
    reached: int
    #: 사람이 읽는 한 마디. 도는 중과 멈춘 것이 다른 말을 한다
    label: str
    #: 아직 움직이나
    moving: bool
    #: 끝났고 성공인가. 움직이는 중이면 항상 False 다 — **아직 모른다**
    ok: bool
    #: 왜 못 했나. 성공이면 null. **조용히 버리지 않는다**
    detail: str | None
    chunk_count: int | None
    page_count: int | None
    #: 해독 글자 수. **0 이면 스캔본이다** — OCR 이 붙어야 찬다(ADR-0030)
    text_chars: int | None
    #: 무엇으로 읽었나. `<종류>/<구현>` 이고 **`ocr/` 로 시작하면 사진에서 읽은 것이다**
    #: (`attach/extract.py` `OCR_PARSER`). 화면은 그 하나만 보고 구현 이름은 안 보여 준다 —
    #: `pdf/plumber` 는 우리 사정이고 사용자가 조작하는 대상이 아니다(DESIGN.md §8.3-1)
    parser: str | None
    #: 이 파일이 근거가 된 사실 수. **파일 사이에 겹친다** — 병합된 사실은 근거가 여럿이라
    #: 두 파일에서 각각 한 번 세어진다. **다 더해도 위키의 사실 수가 아니다**
    fact_count: int
    #: 이 파일이 채운 트리 자리들. **경로다.** 비어 있으면 아직 아무것도 못 채웠다
    spots: list[str]


class ProgressOut(BaseModel):
    """구축 진행 한 장(S1).

    **위키가 없어도 200 이고 단계 다섯이 온다.** 처음 온 사람도 무엇이 일어날지
    먼저 볼 수 있어야 한다(DESIGN.md §7-5).
    """

    company_id: str
    #: 단계 정의 다섯. 순서가 곧 진행 순서다
    steps: list[StepOut]
    files: list[FileProgressOut]
    #: 트리 자리 경로 → 제목. **`files[].spots` 가 경로라서 이게 없으면 화면이 이름을 짓는다**
    #: (`WikiOut.folders` 와 같은 이유). 마흔일곱 개 고정이라 매번 보내도 값이 싸다
    #:
    #: **S7 과 같은 이름이어야 한다**(ADR-0052). 두 화면이 같은 자리를 다르게 부르면
    #: 사용자가 그것을 다른 자리로 읽는다
    spot_titles: dict[str, str]

    # --- 셈 (F1-1-9). **막대를 만들지 않는다** — 숫자로만 말한다 ---
    total: int
    #: 다 된 것
    done: int
    #: 아직 움직이는 것
    moving: int
    #: 글자가 안 나온 것. **실패와 다르다** — OCR 이 붙으면 읽힌다
    needs_review: int
    #: 못 읽은 것과 사실을 못 뽑은 것
    stuck: int

    #: 이 회사의 구축이 지금 도는 중인가. **화면이 계속 물어볼지를 이 값으로 정한다**
    running: bool

    # --- 결과 한 줄. S7 로 넘어갈 때가 됐는지 여기서 안다 ---
    filled: int
    slots: int
    conflicts: int
    #: 무엇이 사실을 뽑았나. `stub/v1` 이면 픽스처 밖에서는 안 돈 것이다(ADR-0031)
    extractor: str | None


class UploadOut(BaseModel):
    """올리기의 답. **받았다는 말이지 다 됐다는 말이 아니다.**

    받는 것과 읽는 것을 나눈 이유가 여기 있다(plan/15). 해독까지 기다렸다 답하면
    OCR 이 걸린 파일 하나에 요청이 몇 분씩 묶이고, 그동안 화면은 아무 말도 못 한다.
    """

    #: 이번에 새로 받은 파일 수
    received: int
    #: 이미 있어서 안 받은 것. **회사 안에서만 본다**(ADR-0029)
    duplicate: int
    #: 저장조차 못 한 것. (파일명, 사유)
    rejected: list[tuple[str, str]]
    #: 뒤에서 구축을 시작했나. 이미 돌고 있었으면 False 다 — **두 번 눌러도 두 번 안 돈다**
    started: bool
    #: 시작 못 했으면 왜인지. 시작했으면 빈 문자열
    reason: str
    progress: ProgressOut
