"""양식 구간 판별 — **규칙이 네 번 실패한 자리다** (plan/11 T-0036 · ADR-0037).

구간 하나를 받아 셋 중 하나로 답한다.

    narrative   글로 써서 내는 양식. **집필의 축이다**(ADR-0019)
    fields      칸에 값을 적어 내는 서식. 규칙이 이미 가른다
    none        채울 것이 없다. 공고문·안내문·지침·평가표

## 왜 LLM 인가

번호 붙은 헤딩만으로는 못 가른다. `1. 사업개요 / 2. 신청자격`(공고문)과
`1. 추진배경 / 2. 주요내용`(양식)이 **형태가 같다.** 파일명도 뜻을 안 준다
(`붙임 1-5.hwp`). 규칙이 26.1% → 10.3% → 22.5% → 26.6% 로 네 번 실패했고
마지막 26.6% 는 표본 8건 중 진짜가 3건이었다
([실측 §3](../../../docs/adr/evidence/2026-08-17-양식-항목-추출-실측.md)).

**여기서 규칙을 다섯 번째로 만들지 않는다.**

## 판정자를 기록에 남긴다

`document.decided_by` 가 `rule/v1` 또는 `llm/<모델>` 이다. 다시 판정할 때
무엇이 바뀌었는지 이것으로 본다. **같은 구간을 두 번 묻지 않는다** — 키가
`sha256` 이라 같은 양식이 여러 공고에 붙어도 한 번만 돈다.

## 잘라서 보낸다

구간 하나가 공고문 전체일 수 있다. 앞뒤만 보내고 **잘랐다고 말한다** —
말하지 않으면 모델이 "항목이 여기서 끝난다" 고 읽는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from finnect.config import settings
from finnect.extract import fields as fx
from finnect.models import DocumentKind

#: 앞에서 이만큼. 표지와 첫 항목들이 여기 있다
HEAD_CHARS = 3_500
#: 뒤에서 이만큼. `신청합니다 / 귀하 / (인)` 과 분량 제한이 여기 붙는다
TAIL_CHARS = 700

#: 이보다 짧으면 **안 묻는다.** 실측으로 정했다 — 40건을 돌려 보니 표지 한 줄만
#: 남은 구간(17~53자)이 여섯이었고, 모델이 `reason` 에 "제목만 제시되어 있다" 고
#: 적으면서도 답을 냈다. 셋 중 하나를 강제하면 **모르는 것을 고를 수밖에 없다.**
#: 진짜 내용이 있는 가장 짧은 구간은 102자(표 머리글 + 값)였다.
MIN_BODY_CHARS = 80


@dataclass(frozen=True, slots=True)
class SegmentView:
    """판정기에 넘기는 구간 하나. **DB 도 ORM 도 모른다.**"""

    #: 구간 표지 원문. `[붙임2] 사업계획서`
    title: str
    #: 구간 원문
    text: str

    def prompt_body(self) -> str:
        """앞뒤를 잘라 잇는다. **자른 사실을 글로 적는다.**"""
        t = self.text
        if len(t) <= HEAD_CHARS + TAIL_CHARS:
            return t
        cut = len(t) - HEAD_CHARS - TAIL_CHARS
        return f"{t[:HEAD_CHARS]}\n\n…(가운데 {cut:,}자 생략)…\n\n{t[-TAIL_CHARS:]}"


@dataclass(frozen=True, slots=True)
class Verdict:
    """판정 하나.

    **`reason` 을 DB 에 저장하지 않는다.** 손 분류와 대조할 때 눈으로 읽는 것이라
    저장하면 컬럼 하나가 영영 안 읽히는 채로 남는다(plan/11 T-0036 완료 조건).
    """

    kind: DocumentKind
    reason: str


class SegmentClassifier(Protocol):
    """구간 하나 → 종류 하나. **이것이 전부다.**"""

    @property
    def name(self) -> str:
        """`document.decided_by` 에 그대로 들어간다."""
        ...

    def classify(self, view: SegmentView) -> Verdict: ...


@dataclass(slots=True)
class RuleClassifier:
    """규칙이 아는 것만 답한다. **서술형은 `unknown` 으로 남긴다.**

    쓸모가 둘이다. 배관을 키 없이 시험하는 것과, LLM 이 얼마나 더 잡는지
    비교할 바닥선이 되는 것이다. **이걸로 `--classify` 를 돌리면 아무것도 안
    바뀐다. 그게 맞다** — 규칙은 이미 분할 때 한 번 돌았다.
    """

    @property
    def name(self) -> str:
        return "rule/v1"

    def classify(self, view: SegmentView) -> Verdict:
        if fx.is_fields(view.text):
            return Verdict(DocumentKind.FIELDS, "칸 채우기 신호가 있다")
        return Verdict(DocumentKind.UNKNOWN, "규칙으로는 못 가른다")


SYSTEM = """\
너는 한국 정부지원사업 공고 첨부에서 잘라 낸 **구간 하나**를 보고 그것이 무엇인지
판정한다. 셋 중 하나만 고른다.

## unclear — 판단할 내용이 없다
표지 한 줄만 있거나, 제목·쪽번호·머리말뿐이거나, 잘려서 판단할 것이 남지 않은 구간이다.
**억지로 셋 중 하나를 고르지 마라.** 모른다고 답하는 것이 답이다.

## narrative — 글로 써서 내는 양식
신청자가 **문장으로 채워 넣는** 틀이다. 항목마다 "무엇을 쓰라" 는 지시가 붙는다.

    2-1. 사업수행 배경 및 목적
         사업 수행 배경 및 필요성, 과제추진 목적 등에 대하여 자세하게 기술
    ※ 항목별 작성 요령을 참고하여 작성  ·  (1page 이내)  ·  (붉은 글씨는 삭제)

## fields — 칸에 값을 적어 내는 서식
표에 **값 하나씩** 적는다. 기업명·사업자등록번호·대표자·연락처 같은 칸이 늘어서고
끝에 `위와 같이 신청합니다 / OO장 귀하 / (인)` 이 온다. 문장을 쓰는 자리가 아니다.

## none — 채울 것이 없다
공고문·안내문·지침·규정·평가표·제출서류 목록·개인정보 동의서 본문.
**주최 기관이 신청자에게 알리는 글**이다.

# 가르는 기준은 형태가 아니라 **누가 쓰는 글인가** 다

번호 붙은 헤딩만으로는 못 가른다. 아래 둘은 생김새가 같지만 반대다.

    1. 사업개요   2. 신청자격   3. 신청방법     → none  (기관이 알린다)
    1. 추진배경   2. 주요내용   3. 기대효과     → narrative (신청자가 쓴다)

빈칸·밑줄·표 껍데기·"○○○" 같은 자리표시자, 분량 제한, 작성 요령, 붉은 글씨 안내가
있으면 신청자가 채우는 틀이다. 접수 기간·문의처·제출처·공고 번호가 있으면 공고문이다.

# 헷갈릴 때

- **양식 앞머리의 안내문은 양식이다.** "작성 시 유의사항" 이 앞에 붙어 있어도
  뒤에 채울 항목이 있으면 `narrative` 다
- **평가표는 `none` 이다.** 심사위원이 쓰는 것이지 신청자가 쓰는 것이 아니다
- **표 안에 긴 글을 쓰게 하면 `narrative` 다.** 칸 이름이 있어도 채울 것이 문장이면
  `fields` 가 아니다
- 가운데가 생략됐다고 적혀 있으면 **생략된 자리에 항목이 더 있다고 보라.** 앞뒤로
  판단하고, 끊긴 것을 끝난 것으로 읽지 마라

# reason
왜 그렇게 골랐는지 **한 문장**으로 적는다. 원문의 근거가 되는 표현을 넣어라.
**`reason` 에 "내용이 없다" 고 쓰게 될 것 같으면 `kind` 를 `unclear` 로 해라** —
이유와 답이 어긋나면 그 판정은 쓸 수 없다. 지어내지 마라.
"""

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["kind", "reason"],
    "properties": {
        "kind": {"type": "string", "enum": ["narrative", "fields", "none", "unclear"]},
        "reason": {"type": "string"},
    },
}


@dataclass(slots=True)
class LlmClassifier:
    """구간을 LLM 에 넘겨 종류를 받는다 (ADR-0037).

    **호출 하나에 구간 하나다.** 여럿을 묶어 보내면 싸지지만, 하나가 실패했을 때
    묶음 전체가 죽고 어느 것이 왜 틀렸는지 못 되짚는다. 구간당 2천 토큰으로 잡아
    7,717개가 $3 남짓이라 묶을 이유가 없다(ADR-0037).
    """

    client: object | None = None
    #: 스키마 밖 값이 와서 되돌린 것. **조용히 넘기지 않는다**
    dropped: list[tuple[str, str]] = field(default_factory=list)
    #: 모델이 스스로 "판단할 내용이 없다" 고 답한 것. **버린 것과 따로 센다** —
    #: 이건 실패가 아니라 정상 응답이다
    declined: list[tuple[str, str]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"llm/{self._c().model}"

    def _c(self):  # noqa: ANN202
        """**함수 안에서 임포트한다.** 최상단에 두면 이 모듈을 읽는 것만으로
        httpx 가 딸려 와 **로컬은 통과하고 배포본만 죽는다**(CLAUDE.md 함정).
        """
        from finnect import llm

        if self.client is None:
            self.client = llm.client()
        return self.client

    def classify(self, view: SegmentView) -> Verdict:
        out = self._c().json(
            system=SYSTEM,
            user=_user_prompt(view),
            schema=_SCHEMA,
            schema_name="segment_kind",
        )
        raw = (out.get("kind") or "").strip()
        reason = (out.get("reason") or "").strip()
        if raw == "unclear":
            # **정상 응답이다.** `unknown` 으로 남겨 다시 볼 대상에 둔다
            self.declined.append((view.title[:60], reason[:60]))
            return Verdict(DocumentKind.UNKNOWN, reason or "판단할 내용이 없다")
        try:
            kind = DocumentKind(raw)
        except ValueError:
            # `strict` 스키마라 안 와야 정상이다. **와도 아는 척하지 않는다.**
            self.dropped.append((view.title[:60], raw[:40]))
            return Verdict(DocumentKind.UNKNOWN, f"모르는 답 {raw!r}")
        if kind is DocumentKind.UNKNOWN:
            self.dropped.append((view.title[:60], raw[:40]))
            return Verdict(DocumentKind.UNKNOWN, "unknown 은 답이 아니다")
        return Verdict(kind, reason)


def _user_prompt(view: SegmentView) -> str:
    return f"구간 표지: {view.title}\n\n--- 구간 원문 ---\n{view.prompt_body()}"


def get_classifier() -> SegmentClassifier:
    """설정이 고른 판정기.

    **`llm` 은 키가 있어야 돈다.** 없으면 `llm.MissingKey` 로 멈춘다 — 조용히
    규칙으로 물러나지 않는다(ADR-0037 결정 4). 물러나면 규칙이 이미 실패한 것을
    다시 실패시키고, **그 실패가 "LLM 도 못 가른다" 처럼 보인다.**
    """
    choice = settings.document_classifier
    if choice == "rule":
        return RuleClassifier()
    if choice == "llm":
        return LlmClassifier()
    raise NotImplementedError(
        f"판정기 '{choice}' 를 몰라요. `rule` 또는 `llm` 이에요 — ADR-0037"
    )
