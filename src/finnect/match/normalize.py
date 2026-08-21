"""공고 정규화 — **공고가 누구를 찾나** (plan/17 T-0070).

## 회사와 무관하다

`document` 가 콘텐츠 주소라 양식 읽기가 회사를 안 보는 것과 같다(plan/16 T-0063).
공고를 한 번 읽으면 **모든 회사가 쓴다.** 그래서 LLM 호출이 회사 수와 무관하다 —
회사가 1,000개여도 709회다. 회사 사실을 여기서 보면 그 성질이 사라진다.

## 첨부를 열지 않는다

지원대상이 **본문 필드에 있다.** 실측 —

    기업마당 bsnsSumryCn 1절
      "채용을 희망하는 충북 소재 구인기업, … 충청남도, 대전광역시, 세종특별자치시 내
       바이오헬스, 미래모빌리티 기업"
                                        ↑ 지역 넷 · 업종 둘이 여기 다 있다

    K-Startup aply_trgt_ctnt
      "· 하드웨어 관련 제조 분야(국내외 중소벤처기업)
       · 프로토타입 수준의 시연 가능한 제품 필요"

첨부에 있는 것은 **양식**이고 그건 plan/16 이 쓴다.

## 제목의 지역 태그를 안 쓴다

실측으로 틀렸다. `[경기]` 46건 중 성남시가 **2건**이고 나머지는 김포·화성·안양·
시흥·안산·용인이다. 반대로 태그 없는 205건 안에 수성알파시티(대구)·대구콘텐츠
코리아랩·제주형 그린바이오·울산창조경제혁신센터가 섞여 있다.

**광역 태그는 시·군 사업을 가리고, 태그 없음은 전국을 뜻하지 않는다.**

## 앵커가 본문에 없으면 버린다

`wiki/extract.py` 와 같은 규율이다. 조용히 비면 **"아무것도 안 나온 것" 과 구분이
안 된다**(ADR-0031 이 `UnknownFile` 로 막은 상황).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

#: 프롬프트에 넣을 본문 상한(자). K-Startup `pbanc_ctnt` 는 수천 자가 온다.
#: **1절·2절을 먼저 넣고 남는 자리에 본문을 넣는다** — 지원대상이 잘리면 안 된다.
_MAX_TARGET = 1200
_MAX_BODY = 1800


@dataclass(frozen=True, slots=True)
class NoticeBody:
    """정규화가 읽는 것. **DB 도 ORM 도 모른다.**

    두 출처가 필드 이름을 하나도 공유하지 않으므로(22 · 30 · 교집합 0) 여기로
    모은다. 매핑은 `service.py` 가 한다 — `views.py` 와 같은 자리다.
    """

    source: str
    external_id: str
    title: str
    #: 지원대상 절. 기업마당 `bsnsSumryCn` 1절 · K-Startup `aply_trgt_ctnt`
    target: str
    #: 지원내용·본문. 기업마당 `bsnsSumryCn` 2절 · K-Startup `pbanc_ctnt`
    body: str

    @property
    def text(self) -> str:
        """모델에 보내는 것. **앵커를 대조하는 것도 이것이다.**

        `user_prompt()` 가 이 값을 그대로 쓴다. 둘을 따로 만들었더니 앵커가
        **구분선을 넘어가면 대조가 실패했다** — 실측(2026-08-20 손 라벨 15건):

            앵커  "국내에 사업자를 둔 소상공인\\n\\n--- 지원내용 ---\\n제품 및 매장 …"

        모델이 구역 둘을 걸쳐 인용한 것인데, 대조 대상에는 `--- 지원내용 ---` 이
        없어서 **정상 응답이 버려졌다.** 보낸 것과 대조하는 것이 같으면 안 생긴다.
        """
        return (
            f"제목: {self.title}\n\n"
            f"--- 지원대상 ---\n{self.target[:_MAX_TARGET]}\n\n"
            f"--- 지원내용 ---\n{self.body[:_MAX_BODY]}"
        )

    @property
    def body_hash(self) -> str:
        """판정에 **실제로 쓰는 것만** 해싱한다.

        `content_hash` 를 쓰면 안 된다 — 조회수(`inqireCo`)가 그 재료라 기업마당은
        재수집마다 1,538건 전부가 '변경' 이다. 거기 캐시를 걸면 조회수 하나에
        709회를 다시 쓴다.
        """
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Profile:
    """정규화 결과 하나."""

    regions: tuple[str, ...]
    industries: tuple[str, ...]
    conditions: tuple[str, ...]
    keywords: tuple[str, ...]
    purpose: str


SYSTEM = """\
너는 한국 정부·지자체 지원사업 공고에서 **누구를 찾는 공고인가**를 뽑는 추출기다.
요약하지 말고 공고에 적힌 것만 낸다.

## regions — 신청할 수 있는 지역
**시·군·구까지 적힌 대로 낸다.** `경기` 가 아니라 `성남시` 다 — 광역만 내면 김포시
사업과 성남시 사업이 같아진다. 여러 곳이면 전부 낸다.

**제한이 없으면 빈 배열이다.** '전국' 같은 말을 넣지 마라. 그리고 **지역이 안 적혀
있어도 주최가 지역 기관이면 그 지역을 낸다** — `대구콘텐츠코리아랩`,
`수성알파시티`, `울산창조경제혁신센터` 는 제목에 지역 표시가 없어도 지역 사업이다.

## industries — 요구하는 업종
`바이오헬스` · `의료기기` · `식품` · `콘텐츠` 처럼 공고가 요구하는 분야를 낸다.
**업종을 안 가리면 빈 배열이다.** 지원 분야(사업화·판로·컨설팅)를 여기 넣지 마라 —
그건 신청자의 업종이 아니라 공고가 주는 것이다.

## conditions — 그 밖의 요구
`만 39세 이하` · `프로토타입 필요` · `사업장 보유` · `기수혜 기업 제외` 처럼
**신청자가 갖춰야 하는 것**을 짧게 낸다. 지역·업종은 위에 이미 냈으니 빼라.

## keywords — 이 사업의 주제
`소상공인` · `디지털전환` · `지역상생` · `수출` 처럼 **공고가 이루려는 것**의 낱말을
낸다. 3~8개. 사업 절차 용어(모집·신청·접수·공고)를 넣지 마라.

## purpose — 하려는 일 한 문장
`지역 소상공인의 디지털 전환을 지원한다` 처럼 한 문장으로. 30자 안팎.

## anchor — 가장 중요하다
위 판단의 근거가 된 **원문 조각을 그대로** 낸다. 20자 이상. **고쳐 쓰면 버려진다** —
공백만 다른 것은 괜찮지만 낱말을 바꾸거나 요약하면 그 공고가 통째로 버려진다.
"""

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["regions", "industries", "conditions", "keywords", "purpose", "anchor"],
    "properties": {
        "regions": {"type": "array", "items": {"type": "string"}},
        "industries": {"type": "array", "items": {"type": "string"}},
        "conditions": {"type": "array", "items": {"type": "string"}},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "purpose": {"type": "string"},
        "anchor": {"type": "string"},
    },
}

_WS = re.compile(r"\s+")

#: 프롬프트가 넣은 구역 표시. **앵커 대조에서 양쪽 다 지운다.**
#:
#: 지우지 않으면 **모델이 두 구역을 걸쳐 인용할 때 정상 응답이 버려진다.** 실측
#: (2026-08-20 · 150건 중 8건 = 5.3%) —
#:
#:     앵커  "관내 사회적경제기업\n제품 디자인설계, 3D 모델링, 목업 및 간이금형 제작"
#:     원문  "관내 사회적경제기업\n\n--- 지원내용 ---\n제품 디자인설계, 3D 모델링 …"
#:
#: 모델이 구분선을 **요약해 버려서** 가운데가 안 맞았다. 우리가 넣은 표시라 우리가
#: 지우는 것이 맞다 — 공고 본문에는 원래 없던 글자다.
_MARKERS = ("제목:", "--- 지원대상 ---", "--- 지원내용 ---")


def squash(s: str) -> str:
    """대조용 형태로 접는다 — **공백을 지우고 구역 표시를 뺀다.**

    공백을 지우는 것은 `wiki/extract.py` 와 같은 규칙이다(모델이 줄바꿈과 띄어쓰기를
    바꿔 쓴다). 구역 표시를 빼는 것은 위 `_MARKERS` 주석 참고.
    """
    out = s or ""
    for m in _MARKERS:
        out = out.replace(m, "")
    return _WS.sub("", out)


def user_prompt(b: NoticeBody) -> str:
    """**`b.text` 를 그대로 보낸다.** 여기서 다르게 만들면 앵커 대조가 깨진다."""
    return b.text


@dataclass(slots=True)
class LlmNormalizer:
    """공고 하나를 LLM 에 넘겨 프로필을 받는다 (ADR-0037).

    **자기 출력을 원문에 대조한다.** 앵커가 본문에 없으면 그 공고를 버리고 센다.
    """

    client: object | None = None
    #: 앵커가 원문에 없어 버린 것. **조용히 사라지면 성공과 구분이 안 된다**
    dropped: list[tuple[str, str]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"llm/{self._c().model}"

    def _c(self):  # noqa: ANN202
        """**함수 안에서 임포트한다.** 최상단에 두면 `import finnect.api.app` 이
        httpx 를 끌고 와 로컬은 통과하고 배포본만 죽는다(CLAUDE.md 함정)."""
        from finnect import llm

        if self.client is None:
            self.client = llm.client()
        return self.client

    def read(self, b: NoticeBody) -> Profile | None:
        out = self._c().json(
            system=SYSTEM,
            user=user_prompt(b),
            schema=_SCHEMA,
            schema_name="notice_profile",
        )
        anchor = (out.get("anchor") or "").strip()
        if not anchor or squash(anchor) not in squash(b.text):
            self.dropped.append((f"{b.source}:{b.external_id}", anchor[:60]))
            return None
        return _profile(out)


def _profile(out: dict) -> Profile:
    """스키마가 `strict` 라 키는 다 온다. **값의 뜻을 여기서 다시 검사한다.**"""
    return Profile(
        regions=_clean(out.get("regions")),
        industries=_clean(out.get("industries")),
        conditions=_clean(out.get("conditions")),
        keywords=_clean(out.get("keywords")),
        purpose=(out.get("purpose") or "").strip()[:200],
    )


#: 지역 배열에 오면 버리는 말. **모델이 '전국' 을 넣으면 제한이 있는 것이 된다.**
_NOT_A_REGION = frozenset({"전국", "전지역", "전 지역", "해당없음", "제한없음", "무관"})


def _clean(v: object) -> tuple[str, ...]:
    if not isinstance(v, list):
        return ()
    out: list[str] = []
    for x in v:
        s = (x or "").strip() if isinstance(x, str) else ""
        if not s or s in _NOT_A_REGION or s in out:
            continue
        out.append(s[:60])
    return tuple(out)
