"""트랙 B — 매칭 정보의 어휘(ADR-0056 결정 5). **트리와 무관하다.**

질문이 **열다섯 고정**이다. 그래서 못 채운 칸을 셀 수 있고, 셀 수 있어서 물어볼 수 있다
([ADR-0028](../../../docs/adr/0028-초안을-먼저-완성하고-못-채운-자리에서-묻는다.md)).
트랙 A 는 정답지가 없어서 이걸 못 한다.

**자격 판별(M1)이 `key` 이름으로 꺼낸다.** 그래서 그래프가 어떻게 자라도 자격이 안
흔들린다 — [ADR-0013](../../../docs/adr/0013-판정-두-층.md) 이 「자격은 결정론」이라고
한 자리가 여기다.

## 별칭 표가 이 파일의 요점이다

같은 값이 문서마다 다른 이름으로 온다.

    상시 근로자 7명 (2025-08) · 종업원 수 8명 (2025-11)
    구성원 10명 (2026-01) · 임직원 15명 (2026-08)

**문자열이 다르다고 자리가 갈리면 안 된다.** 넷이 `headcount` 하나로 모이고, 시점이
달라서 시계열이 된다.

**이 표는 사전이 아니라 LLM 이 고를 보기다.** 프롬프트가 이 목록을 통째로 싣고
「이 중 하나를 쓰라」고 한다 — 문서가 `인력 규모` 라고 써도 모델이 `임직원` 으로
옮겨 낸다. 목록 밖 이름이 오면 그 값은 안 선다.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProfileKey:
    """매칭 정보 한 칸의 성질."""

    #: 화면에 쓰는 이름. 해요체가 아니라 명사다 — 라벨이다
    label: str
    #: 시점을 갖는가. **이 한 칸이 시계열과 충돌을 가른다.**
    #:
    #: `True` 면 시점이 다른 값이 나란히 선다(직원 수 7 → 8 → 10 → 15).
    #: `False` 면 시점을 떼어 버린다 — 안 떼면 같은 사업자등록번호가 **문서 수만큼**
    #: 행이 된다. **이건 문서를 읽어서 아는 게 아니라 그 값의 정의라서** LLM 에 맡기면
    #: 회차마다 흔들린다(ADR-0056 결정 5).
    dated: bool
    #: 자격 판별(M1)의 입력인가. **못 채운 자리에서 묻는다**(ADR-0028).
    #:
    #: ADR-0056 은 이걸 `match/` 로 옮기라고 적었는데 **여기 뒀다** — 위키 화면도
    #: 「자격 판별에 써요」 배지에 읽어서, `match/` 에 두면 `wiki` 가 `match` 를
    #: 임포트하게 된다. 방향이 거꾸로다.
    eligibility: bool = False
    #: 화면에 어떻게 보일 값인가. **저장값은 안 건드린다.**
    #:
    #: `money` 는 `120000000` 을 `120,000,000원` 으로 편다 — 자릿수를 눈으로 세게 두면
    #: 1억 2천만원과 1천 2백만원이 구분되지 않는다. `count` 는 `명` 을 붙인다.
    unit: str = "text"


#: 매칭 정보 열다섯. **`ValueSpec.qualified` 는 읽는 코드가 하나도 없어서 지웠다**(ADR-0056).
#:
#: **업력과 만 나이는 여기 없다.** 개업일과 생년월일만 저장하고 판정 시점에 계산한다 —
#: 공고마다 기준일이 다르다. 코퍼스의 성남시 신청서에 `업력 1년 6개월` 이 박혀 있는데
#: 2025-08 기준 값이라 지금은 틀렸다.
#:
#: **중소기업 여부도 여기 없다**(2026-08-23). 공고가 `중소기업` 을 자주 요구하지만
#: 그건 `headcount` 와 `revenue` 로 계산되는 파생값이다 — 업력·만 나이를 안 넣은 것과
#: 같은 이유다. 저장하면 두 곳이 갈리고, 갈리면 어느 쪽이 맞는지 코드가 모른다.
PROFILE_KEYS: dict[str, ProfileKey] = {
    "company_name": ProfileKey("상호", dated=False),
    "business_no": ProfileKey("사업자등록번호", dated=False, eligibility=True),
    "corp_no": ProfileKey("법인등록번호", dated=False),
    "founded_on": ProfileKey("개업연월일", dated=False, eligibility=True),
    "ceo_name": ProfileKey("대표자", dated=False),
    "ceo_birth": ProfileKey("대표자 생년월일", dated=False, eligibility=True),
    "location": ProfileKey("소재지", dated=True, eligibility=True),
    #: **업태와 종목을 한 칸에 넣으면 안 된다.** 사업자등록증이 두 칸으로 주고
    #: 사업계획서도 두 줄로 쓴다. 하나로 접으면 `정보통신업` 과 `응용 소프트웨어 개발 및
    #: 공급업` 이 같은 자리에 값 둘로 앉아 **없는 충돌이 생긴다.**
    "industry": ProfileKey("업종(업태)", dated=True, eligibility=True),
    "industry_item": ProfileKey("업종(종목)", dated=True, eligibility=True),
    "headcount": ProfileKey("직원 수", dated=True, eligibility=True, unit="count"),
    "capital": ProfileKey("자본금", dated=True, unit="money"),
    "revenue": ProfileKey("매출액", dated=True, unit="money"),
    "funding": ProfileKey("조달액", dated=True, unit="money"),
    "gov_program": ProfileKey("정부지원 수혜 이력", dated=True, eligibility=True, unit="money"),
    #: **실측으로 더했다**(2026-08-23 · 공고 50건). 자격 판정을 못 한 스무 건 중
    #: **여섯이 이것 하나** 때문이었다 — `벤처기업 확인서 유효기간 시작일이 …이후인
    #: 기업` · `기업부설연구소 또는 연구개발전담부서` · `벤처확인을 준비하는 기업`.
    #:
    #: **`dated=True` 다.** 벤처기업확인은 유효기간이 있어서 "언제 기준으로 가졌나" 가
    #: 판정을 가른다 — 취득일 없는 인증은 조건을 넘는지 알 수 없다.
    #:
    #: 값은 인증 이름(`벤처기업확인` · `이노비즈` · `기업부설연구소`)이고 여럿이면
    #: 여러 행이다. **특허·상표는 여기 안 넣는다** — 그건 트랙 A 의 `Custom/특허` 이고
    #: 자리에 원문이 붙어 있다. 여기는 「가졌나 못 가졌나」를 묻는 칸이다.
    "certification": ProfileKey("보유 인증", dated=True, eligibility=True),
}


#: 원문 표현 → key. **왼쪽은 문서가 쓴 말이고 오른쪽은 우리 이름이다.**
#:
#: 코퍼스에 실제로 나온 표현만 담는다. 없는 표현을 미리 넣지 않는다 — 새 이름이 나오면
#: 그 값이 안 서고, 그때 여기 한 줄을 더한다.
ALIASES: dict[str, str] = {
    "상호": "company_name",
    "기업명": "company_name",
    "회사명": "company_name",
    "법인명": "company_name",
    "사업자등록번호": "business_no",
    "등록번호": "business_no",
    "법인등록번호": "corp_no",
    "개업연월일": "founded_on",
    "개업일": "founded_on",
    "설립일": "founded_on",
    "설립연월일": "founded_on",
    "대표자": "ceo_name",
    "대표이사": "ceo_name",
    "대표자명": "ceo_name",
    "대표": "ceo_name",
    "생년월일": "ceo_birth",
    "대표자 생년월일": "ceo_birth",
    "소재지": "location",
    "사업장소재지": "location",
    "본사": "location",
    "본점소재지": "location",
    "주소": "location",
    # 업종 — 등록증도 사업계획서도 '업태'와 '종목' 두 칸으로 준다
    "업종": "industry",
    "업태": "industry",
    "산업 분류": "industry",
    "종목": "industry_item",
    # 직원 수 — **넷이 다른 이름으로 온다.** 이 네 줄이 픽스처 함정 1이다
    "상시 근로자": "headcount",
    "종업원 수": "headcount",
    "구성원": "headcount",
    "임직원": "headcount",
    "직원 수": "headcount",
    "자본금": "capital",
    "매출액": "revenue",
    "직전연도 매출액": "revenue",
    "직전연도 매출": "revenue",
    "매출": "revenue",
    # 조달 — 한정어(시드 · 정책자금)는 문서가 말한다. 여기서 못 박지 않는다
    "시드 투자": "funding",
    "시드 라운드": "funding",
    "자본잉여금": "funding",
    "정책자금 대출": "funding",
    "장기차입금": "funding",
    "정부지원사업 참여 이력": "gov_program",
    "지원금": "gov_program",
    # 인증 — **코퍼스에 실제로 나온 표현만 담는다.** 없는 표현을 미리 안 넣는다
    "벤처기업확인": "certification",
    "벤처기업 확인서": "certification",
    "벤처기업 인증": "certification",
    "이노비즈": "certification",
    "메인비즈": "certification",
    "기업부설연구소": "certification",
    "연구개발전담부서": "certification",
    "보유 인증": "certification",
    "인증 현황": "certification",
}


#: 자격 판별(M1)이 읽는 것들. `match/` 가 이걸 본다
ELIGIBILITY_KEYS: frozenset[str] = frozenset(
    k for k, v in PROFILE_KEYS.items() if v.eligibility
)

#: 공백을 지운 별칭 색인. **정확 일치라 부분 문자열 오탐이 없다.**
#:
#: HWP 표와 OCR 이 `상시근로자` · `직원수` 처럼 띄어쓰기를 지워서 내보내는데 별칭 표에는
#: `상시 근로자` · `직원 수` 로 적혀 있어서 **표에 있는 말이 안 서고 있었다**(plan/19 T-0088).
_TIGHT: dict[str, str] = {"".join(k.split()): v for k, v in ALIASES.items()}


def key_of(name: str | None) -> str | None:
    """원문 표현 하나를 key 로. 모르면 `None` — **추측하지 않는다.**"""
    if not name:
        return None
    k = " ".join(name.split()).strip().strip(":·").strip()
    return ALIASES.get(k) or _TIGHT.get("".join(k.split()))


def display(key: str, value: str) -> str:
    """저장값을 화면에 쓸 글자로. **저장값은 그대로 둔다.**

    정규화된 값(`120000000`)이 병합의 재료라 손대면 충돌 판정이 깨진다. 사람이 읽는
    것은 여기서만 만든다 — 화면·마크다운·API 가 같은 함수를 쓴다.
    """
    spec = PROFILE_KEYS.get(key)
    if spec is None or spec.unit == "text":
        return value
    try:
        n = int(value)
    except ValueError:
        # 숫자가 아니면 손대지 않는다. **추출기가 못 고친 값을 여기서 꾸미지 않는다**
        return value
    return f"{n:,}원" if spec.unit == "money" else f"{n:,}명"


def as_of_for(key: str, as_of: dt.date | None) -> dt.date | None:
    """key 가 시점을 갖는가에 따라 시점을 남기거나 뗀다. **병합 규칙이다.**"""
    spec = PROFILE_KEYS.get(key)
    return as_of if (spec and spec.dated) else None


def dedupe_key(key: str, qualifier: str | None, as_of: dt.date | None, value: str) -> str:
    """매칭 정보 한 칸의 병합 키.

    **값이 키에 들어가는 것이 요점이다.** 시점이 같은데 값이 다르면 키가 달라 행이 둘이
    되고, 그게 곧 충돌이다. 값을 빼면 나중 것이 앞엣것을 덮어 **충돌을 영영 못 본다.**
    """
    d = as_of_for(key, as_of)
    return f"value|{key}|{qualifier or ''}|{d or ''}|{_norm(value)}"


def _norm(s: str | None) -> str:
    """비교용 정규화. **공백을 전부 지운다.**

    OCR 이 `응용 소프트웨어개발및공급업` 을 내고 사업계획서가 `응용 소프트웨어 개발 및
    공급업` 을 낸다. 띄어쓰기만 다른 같은 값이라 **공백을 지워야 하나로 모인다** —
    안 지우면 OCR 노이즈가 전부 충돌로 둔갑한다.
    """
    return "".join((s or "").split())
