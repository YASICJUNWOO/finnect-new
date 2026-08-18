"""고정 topic 온톨로지와 목적지 표(plan/12 T-0044 · T-0045).

**이 파일이 '사람이 만든 표'다.** LLM 은 `topic` 라벨과 근거 위치만 붙이고 **목적지는
정하지 않는다**(plan/12 T-0045). LLM 이 목적지를 정하면 같은 사실이 어제는 A, 오늘은
B 로 가서 위키가 돌릴 때마다 달라진다. 라우팅이 결정론인 이유가 이것이고, 그래서 이
표를 코드로 둔다.

두 층으로 가른다. **병합 키가 다르기 때문이다**(plan/12 T-0044).

  정형 슬롯   키가 (이름, 한정어, 시점). 같은 키에 값이 둘이면 **충돌**이다
  서술 노드   키가 없다. 근거 청크를 쌓기만 한다

## 구상도와 다른 곳 셋

1. **`topic` 22개로는 서술 노드 아홉 중 둘에 못 닿는다.** `region_link`(지역 연계)와
   `roadmap`(로드맵)이 도면의 목록에 없다. 둘 다 `SPEC.md` F1-2 의 아홉에 있고
   코퍼스에도 풍부하다 — 성남산업진흥원 입주·상인회 3개소, 1·2·3단계 사업화 일정.
   지역 연계는 **지자체 공고 매칭에 직결된다.** 그래서 둘을 더했다.
2. **이벤트 계열 넷 중 `application_history` 하나만 쓴다.** `meeting`·`decision`·
   `action_item` 은 사업계획서·IR·재무제표에서 나오지 않는다. 도면이 스스로 적은
   `선형 증가` 가 F1-4 의 "노드가 열다섯이라 검색이 필요 없다"를 첫날부터 깬다.
3. **`company_profile` 하나를 슬롯 여럿으로 가른다.** 도면은 이걸 topic 하나로 뒀는데,
   자격 판별(M1)은 사업자등록번호·개업일·소재지·업종을 **각각** 본다. 어느 슬롯인지는
   LLM 이 아니라 아래 `SLOT_ALIASES` 가 정한다.

## 별칭 표가 이 파일의 요점이다

같은 값이 문서마다 다른 이름으로 온다. 코퍼스에 직원 수가 이렇게 있다.

    상시 근로자 7명 (2025-08) · 종업원 수 8명 (2025-11)
    구성원 10명 (2026-01) · 임직원 15명 (2026-08)

**문자열이 다르다고 슬롯이 갈리면 안 된다.** 넷이 `headcount` 하나로 모이고, 시점이
달라서 시계열이 된다. 별칭 표에 없는 이름은 **버리지 않고** `uncategorized` 로 세운다.
"""

from __future__ import annotations

from dataclasses import dataclass

# ─────────────────────────────────────────────────────────────────
# 정형 슬롯
# ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SlotSpec:
    """슬롯 하나의 성질."""

    #: 화면에 쓰는 이름. 해요체가 아니라 명사다 — 라벨이다
    label: str
    #: 시점을 갖는가. **이 한 칸이 시계열과 충돌을 가른다**
    #:
    #: `True` 면 시점이 다른 값이 나란히 선다(직원 수 7 → 8 → 10 → 15).
    #: `False` 면 시점과 무관하게 값이 하나여야 한다(사업자등록번호).
    dated: bool
    #: 한정어를 갖는가. 같은 슬롯에 종류가 여럿인 것
    #: (조달 — 시드 · 정책자금 / 수혜 이력 — 예비창업패키지 · 소상공인 정책자금)
    qualified: bool = False
    #: 자격 판별(M1)의 입력인가. **못 채운 자리에서 묻는다**(ADR-0028)
    eligibility: bool = False
    #: 화면에 어떻게 보일 값인가. **저장값은 안 건드린다** — 정규화된 값 그대로 둔다.
    #:
    #: `money` 는 `120000000` 을 `120,000,000원` 으로 편다. 자릿수를 눈으로 세게 두면
    #: 1억 2천만원과 1천 2백만원이 구분되지 않는다. `count` 는 `명` 을 붙인다 —
    #: 직원 수 15 에 천 단위 쉼표가 붙으면 금액으로 읽힌다.
    unit: str = "text"


#: **업력과 만 나이는 여기 없다.** 개업일과 생년월일만 저장하고 판정 시점에 계산한다 —
#: 공고마다 기준일이 다르다(`SPEC.md` F1-2). 코퍼스의 성남시 신청서에 `업력 1년 6개월`
#: 이 박혀 있는데 2025-08 기준 값이라 지금은 틀렸다. 그걸 슬롯에 넣으면 안 된다.
SLOTS: dict[str, SlotSpec] = {
    "company_name": SlotSpec("상호", dated=False),
    "business_no": SlotSpec("사업자등록번호", dated=False, eligibility=True),
    "corp_no": SlotSpec("법인등록번호", dated=False),
    "founded_on": SlotSpec("개업연월일", dated=False, eligibility=True),
    "ceo_name": SlotSpec("대표자", dated=False),
    "ceo_birth": SlotSpec("대표자 생년월일", dated=False, eligibility=True),
    "location": SlotSpec("소재지", dated=True, eligibility=True),
    #: **업태와 종목을 한 슬롯에 넣으면 안 된다.** 사업자등록증은 두 칸으로 주고
    #: 사업계획서도 두 줄로 쓴다. 하나로 접으면 `정보통신업` 과 `응용 소프트웨어 개발 및
    #: 공급업` 이 같은 자리에 값 둘로 앉아 **없는 충돌이 생긴다.**
    "industry": SlotSpec("업종(업태)", dated=True, eligibility=True),
    "industry_item": SlotSpec("업종(종목)", dated=True, eligibility=True),
    "headcount": SlotSpec("직원 수", dated=True, eligibility=True, unit="count"),
    "capital": SlotSpec("자본금", dated=True, unit="money"),
    "revenue": SlotSpec("매출액", dated=True, unit="money"),
    "funding": SlotSpec("조달액", dated=True, qualified=True, unit="money"),
    #: 중복수혜 제한 판정의 입력. 도면의 `application_history` 가 여기로 온다
    "gov_program": SlotSpec(
        "정부지원 수혜 이력", dated=True, qualified=True, eligibility=True, unit="money"
    ),
}


#: 원문 표현 → 슬롯. **왼쪽은 문서가 쓴 말이고 오른쪽은 우리 이름이다.**
#:
#: 코퍼스 7건에 실제로 나온 표현만 담았다. 없는 표현을 미리 넣지 않는다 —
#: 새 문서에서 새 이름이 나오면 `uncategorized` 로 서고, 그때 여기 한 줄을 더한다.
SLOT_ALIASES: dict[str, str] = {
    # 상호
    "상호": "company_name",
    "기업명": "company_name",
    "회사명": "company_name",
    "법인명": "company_name",
    # 등록번호
    "사업자등록번호": "business_no",
    "등록번호": "business_no",
    "법인등록번호": "corp_no",
    # 개업
    "개업연월일": "founded_on",
    "개업일": "founded_on",
    "설립일": "founded_on",
    "설립연월일": "founded_on",
    # 대표자
    "대표자": "ceo_name",
    "대표이사": "ceo_name",
    "대표자명": "ceo_name",
    "대표": "ceo_name",
    "생년월일": "ceo_birth",
    "대표자 생년월일": "ceo_birth",
    # 소재지
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
    # 자본
    "자본금": "capital",
    # 매출
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
    # 수혜 이력
    "정부지원사업 참여 이력": "gov_program",
    "지원금": "gov_program",
}


# ─────────────────────────────────────────────────────────────────
# 서술 노드
# ─────────────────────────────────────────────────────────────────

#: `SPEC.md` F1-2 의 **정체성 하나 + 사업 내용 아홉**. 늘리지 않는다 —
#: `DESIGN.md` §4.1 의 노드 분류색 셋과 ADR-0017 의 궤도 배치가 이 위에 선다.
#:
#: **`identity` 가 2026-08-18 하나 더 붙었다**(ADR-0033). ADR-0032 는 아홉으로 뒀는데
#: `SPEC.md` F1-2 가 "정체성 노드 하나가 따로 있다. 사업 한 줄 정의이고 그래프의
#: 중심이다"라고 적었고 SPEC 이 정본이다. ADR-0032 자신이 `vision → solution` 매핑을
#: "가장 약하다"고 적어 둔 그 자리다.
NODES: dict[str, str] = {
    "identity": "우리가 하는 일",
    "problem": "문제 인식",
    "solution": "솔루션과 기술",
    "customer": "목표 고객",
    "market": "시장과 경쟁",
    "region": "지역 연계",
    "traction": "매출과 성과",
    "team": "팀 구성",
    "roadmap": "로드맵",
    "finance": "자금 현황",
}


#: topic → 서술 노드. **여기 없는 topic 은 서술로 안 간다.**
#:
#: `company_profile` 과 `application_history` 가 일부러 빠져 있다. 둘은 정형 슬롯의
#: 재료라 서술로 오면 `uncategorized` 다. 라벨이 세밀할수록 좋고 노드는 집필 단위와
#: 맞아야 해서 25 → 9 로 모은다.
TOPIC_NODE: dict[str, str] = {
    "customer_problem": "problem",
    "customer_evidence": "problem",
    #: **사업 한 줄 정의는 정체성으로 간다.** 솔루션과 기술은 "무엇을 어떻게 만들었나"이고
    #: 이건 "우리가 무슨 일을 하는가"라 층이 다르다 — 그래프의 중심이 그 자리다
    "vision": "identity",
    "service_overview": "solution",
    "service_feature": "solution",
    "service_differentiator": "solution",
    "development_status": "solution",
    "technology": "solution",
    "patent": "solution",
    "certification": "solution",
    "target_customer": "customer",
    "market_size": "market",
    "market_trend": "market",
    "competitor": "market",
    "region_link": "region",
    "revenue": "traction",
    "revenue_model": "traction",
    "pricing": "traction",
    "go_to_market": "traction",
    "team": "team",
    "roadmap": "roadmap",
    "cost": "finance",
    "funding": "finance",
}


#: 추출기에 줄 라벨 목록. **자유 생성 금지**(구상도 ④). 밖의 것은 `uncategorized` 다.
#:
#: 도면 22 + 우리가 더한 둘(`region_link` · `roadmap`) + `company_profile` ·
#: `application_history`. `meeting` · `decision` · `action_item` 은 뺐다 — 위 문서 2번.
TOPICS: frozenset[str] = frozenset(TOPIC_NODE) | {"company_profile", "application_history"}

#: 목적지를 못 찾은 것이 가는 자리. **버리지 않는다**(구상도 ④ 예외).
UNCATEGORIZED = "uncategorized"


def slot_of(key: str | None) -> str | None:
    """원문 표현 하나를 슬롯 이름으로. 모르면 `None` — **추측하지 않는다.**"""
    if not key:
        return None
    k = " ".join(key.split()).strip().strip(":·").strip()
    return SLOT_ALIASES.get(k)


def display(slot: str, value: str) -> str:
    """저장값을 화면에 쓸 글자로. **저장값은 그대로 둔다.**

    정규화된 값(`120000000`)이 병합의 재료라 손대면 충돌 판정이 깨진다. 사람이 읽는
    것은 여기서만 만든다 — 화면·마크다운·API 가 같은 함수를 쓴다.
    """
    spec = SLOTS.get(slot)
    if spec is None or spec.unit == "text":
        return value
    try:
        n = int(value)
    except ValueError:
        # 숫자가 아니면 손대지 않는다. **추출기가 못 고친 값을 여기서 꾸미지 않는다**
        return value
    return f"{n:,}원" if spec.unit == "money" else f"{n:,}명"


def node_of(topic: str | None) -> str | None:
    """topic 하나를 서술 노드 이름으로. 모르면 `None`."""
    return TOPIC_NODE.get(topic or "")


# ─────────────────────────────────────────────────────────────────
# 궤도 배치 (ADR-0017 · SPEC §5.3)
# ─────────────────────────────────────────────────────────────────

#: `SPEC.md` F1-2 가 센 열다섯은 **슬롯 열넷과 다른 셈이다.** 저기는 화면의 단위이고
#: 여기는 병합의 단위다. 사업체 정보 다섯은 슬롯 여럿을 묶은 것이다.
#:
#:     정체성 1  +  사업체 정보 5  +  사업 내용 9  =  15
#:
#: **남는 슬롯 넷(직원 수·자본금·매출액·조달액)은 사업체 정보가 아니라 사업 내용으로 간다.**
#: `SPEC.md` F1-2 의 다섯에 그것들이 없고, 실제로 팀 구성·매출과 성과·자금 현황을 읽을 때
#: 같이 봐야 하는 값이다.


@dataclass(frozen=True, slots=True)
class Orbital:
    """궤도 위의 자리 하나. **자리가 고정돼 두 번째 볼 때 찾는다**(ADR-0017)."""

    #: 화면에 쓰는 이름
    label: str
    #: `identity` · `company` · `content`. **색은 이것만 말한다**(DESIGN.md §4.1)
    kind: str
    #: 구획. 각도가 의미를 갖는다
    sector: str
    #: 이 자리에 딸린 정형 슬롯
    slots: tuple[str, ...] = ()
    #: 이 자리에 딸린 서술 노드
    node: str | None = None


#: 구획 여섯. **사업 내용 넷 · 사업체 정보 둘**(ADR-0017 결정 2).
SECTORS: dict[str, str] = {
    "registration": "등록 정보",
    "principal": "대표와 이력",
    "problem_solution": "문제와 해결",
    "market_customer": "시장과 고객",
    "result_money": "성과와 자금",
    "team_plan": "팀과 계획",
}


#: 궤도 열다섯. **순서가 곧 배치 순서다** — 프론트가 이 순서로 각도를 나눈다.
ORBIT: dict[str, Orbital] = {
    # 중심 — 사업 한 줄 정의. 그래프의 중심이다
    "identity": Orbital(
        "우리가 하는 일", "identity", "registration", ("company_name",), node="identity"
    ),
    # 안쪽 궤도 — 사업체 정보 다섯. M1 자격 판별의 입력
    "biz": Orbital(
        "사업자 정보", "company", "registration",
        ("business_no", "corp_no", "founded_on"),
    ),  # fmt: skip
    "where": Orbital("소재지", "company", "registration", ("location",)),
    "what": Orbital("업종", "company", "registration", ("industry", "industry_item")),
    "who": Orbital("대표자", "company", "principal", ("ceo_name", "ceo_birth")),
    "grants": Orbital("수령 이력", "company", "principal", ("gov_program",)),
    # 바깥 궤도 — 사업 내용 아홉. M2 적합도와 G 집필의 입력
    "problem": Orbital("문제 인식", "content", "problem_solution", node="problem"),
    "solution": Orbital("솔루션과 기술", "content", "problem_solution", node="solution"),
    "customer": Orbital("목표 고객", "content", "market_customer", node="customer"),
    "market": Orbital("시장과 경쟁", "content", "market_customer", node="market"),
    "region": Orbital("지역 연계", "content", "market_customer", node="region"),
    "traction": Orbital(
        "매출과 성과", "content", "result_money", ("revenue",), node="traction"
    ),
    "finance": Orbital(
        "자금 현황", "content", "result_money", ("capital", "funding"), node="finance"
    ),
    "team": Orbital("팀 구성", "content", "team_plan", ("headcount",), node="team"),
    "roadmap": Orbital("로드맵", "content", "team_plan", node="roadmap"),
}
