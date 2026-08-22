"""회사 프로필 — **위키에서 읽기만 한다** (plan/17 T-0071).

LLM 호출이 0회다. `wiki_fact` 가 이미 자격 슬롯 넷과 서술 노드 열을 들고 있어서
새로 뽑을 것이 없다.

## 파생값을 저장하지 않는다

업력과 만 나이는 **판정 시점에 계산한다.** `wiki/profile.py` 가 적어 둔 이유가
그대로다 — 공고마다 기준일이 다르고, 기준일이 `신청일` 인지 `모집마감일` 인지도
공고마다 다르다(plan/03 실측: 초기창업패키지 양식이 "(모집마감일 기준)").

그래서 `as_of(기준일)` 로 두 번 물어볼 수 있게 만든다.

## `current` 를 그냥 읽으면 틀린다

`c_dasiro` 의 `headcount` `current` 가 **`as_of 2026-08-31`** 이다. 미래 시점 값이라
2026-08-20 판정에 쓰면 **아직 오지 않은 상태로 판정한다.** 그래서 기준일 이전의
최신값을 고른다 — `current` 플래그가 아니라 날짜로 고른다.

## `conflict` 는 판정 불가다

`c_dasiro` 의 `funding` 에 이미 충돌 2행이 서 있다(3억 · 2.8억, 둘 다 2025-09).
자격 슬롯에 충돌이 나면 **그 축을 판정하지 않는다** — 둘 중 하나를 골라 판정하면
어느 쪽으로 골랐는지가 화면에 안 남는다(`SPEC.md` F3-1-5).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from finnect.models import CompanyValue, WikiFact, WikiNode
from finnect.wiki import profile as wiki_profile

#: 자격 판별의 입력. `wiki/profile.py` 의 `eligibility=True` 여덟 개다.
#: **여기 목록을 손으로 적지 않는다** — 슬롯 표가 정본이다
ELIGIBILITY_SLOTS: tuple[str, ...] = tuple(
    k for k, v in wiki_profile.PROFILE_KEYS.items() if v.eligibility
)

#: ④ 분야 대조가 읽는 노드. **"지금 무엇이 필요한가" 를 말하는 자리들이다**
#: ④ 가 읽는 갈래. **노드 경로의 앞자리로 본다**(ADR-0056).
#:
#: 옛 orbit 이름(`roadmap`·`finance`·`solution`)이 카테고리로 옮겨 갔다 — 로드맵은
#: `Plan`, 자금은 `Financial`, 솔루션은 `Product` 다. **`Company` 를 안 넣는다** —
#: 정체성 문장이 들어오면 무슨 분야든 걸린다.
NEED_NODES: tuple[str, ...] = ("Plan", "Financial", "Product")


@dataclass(frozen=True, slots=True)
class SlotValue:
    """슬롯 하나의 판정용 값."""

    value: str
    as_of: dt.date | None
    #: 충돌이라 못 쓴다. **`None` 과 다르다** — 저쪽은 아예 없는 것이다
    conflicted: bool = False

    @property
    def usable(self) -> bool:
        return bool(self.value) and not self.conflicted


@dataclass(frozen=True, slots=True)
class NodeFact:
    """서술 사실 하나. **`fact_id` 를 든다** — 이유의 근거가 된다."""

    fact_id: int
    place: str
    text: str


@dataclass(frozen=True, slots=True)
class CompanyProfile:
    """판정에 쓰는 회사 한 벌. **DB 를 모른다.**"""

    company_id: str
    #: 슬롯 이름 → 값. **없는 슬롯은 키가 없다**
    slots: dict[str, SlotValue]
    #: 서술 사실 전부. ④는 `NEED_NODES` 만, ⑤는 전부 본다
    nodes: tuple[NodeFact, ...]

    # --- 파생값. 저장하지 않고 여기서 계산한다 ---

    def business_years(self, on: dt.date) -> float | None:
        """기준일 시점의 업력(년). 개업일이 없으면 `None`."""
        v = self.slots.get("founded_on")
        if v is None or not v.usable:
            return None
        d = _date(v.value)
        return None if d is None else (on - d).days / 365.25

    def age(self, on: dt.date) -> int | None:
        """기준일 시점의 만 나이. 생년월일이 없으면 `None`."""
        v = self.slots.get("ceo_birth")
        if v is None or not v.usable:
            return None
        d = _date(v.value)
        if d is None:
            return None
        return on.year - d.year - ((on.month, on.day) < (d.month, d.day))

    def value(self, slot: str) -> str | None:
        v = self.slots.get(slot)
        return v.value if v is not None and v.usable else None

    def need_text(self) -> str:
        """④ 가 읽는 것 — 로드맵·자금·기술을 이어 붙인 글."""
        return " ".join(n.text for n in self.nodes if n.place.split("/", 1)[0] in NEED_NODES)


def load(s: Session, company_id: str, *, on: dt.date | None = None) -> CompanyProfile:
    """위키에서 프로필을 만든다.

    `on` 은 슬롯 값을 고르는 기준일이다. **기본이 오늘이 아니라 `None` 이면 오늘**
    인데, 공고별 기준일(신청일·마감일)로 다시 부를 수 있도록 인자로 받는다.
    """
    on = on or dt.date.today()
    rows = list(
        s.scalars(select(CompanyValue).where(CompanyValue.company_id == company_id))
    )

    slots: dict[str, list[CompanyValue]] = {}
    for r in rows:
        if r.key in ELIGIBILITY_SLOTS:
            slots.setdefault(r.key, []).append(r)

    #: 서술은 노드에서 온다. **경로의 첫 마디(카테고리)가 옛 orbit 자리를 대신한다**
    nodes = [
        NodeFact(fact_id=fid, place=path, text=text)
        for fid, path, text in s.execute(
            select(WikiFact.id, WikiNode.path, WikiFact.text)
            .join(WikiNode, WikiNode.id == WikiFact.node_id)
            .where(WikiFact.company_id == company_id)
        ).all()
    ]

    return CompanyProfile(
        company_id=company_id,
        slots={k: _pick(v, on) for k, v in slots.items()},
        nodes=tuple(nodes),
    )


def _pick(claims: list[CompanyValue], on: dt.date) -> SlotValue:
    """기준일 이전의 최신값을 고른다.

    **`status == 'current'` 를 믿지 않는다.** 그 값은 "가장 늦은 시점" 이라 미래
    날짜도 `current` 가 된다(`c_dasiro` 의 직원 수 15 · `as_of 2026-08-31`).
    판정은 **오늘 아는 것**으로 해야 한다.

    충돌이 섞여 있으면 그 슬롯을 못 쓴다 — 어느 값이 맞는지 코드가 모른다.
    """
    if any(c.status == "conflict" for c in claims):
        return SlotValue(value="", as_of=None, conflicted=True)

    dated = [c for c in claims if c.as_of is not None and c.as_of <= on]
    if dated:
        best = max(dated, key=lambda c: c.as_of)  # type: ignore[arg-type,return-value]
        return SlotValue(value=(best.value or "").strip(), as_of=best.as_of)

    # 시점 없는 슬롯(사업자등록번호·개업일)은 날짜로 못 고른다. 하나뿐이어야 정상이다
    undated = [c for c in claims if c.as_of is None]
    if undated:
        return SlotValue(value=(undated[0].value or "").strip(), as_of=None)

    # 남은 것은 전부 미래 시점이다. **쓰지 않는다** — 아직 오지 않은 상태다
    return SlotValue(value="", as_of=None)


def _date(s: str) -> dt.date | None:
    """`2024-03-11` · `2024.03.11` · `20240311` 을 받는다. 아니면 `None`."""
    t = (s or "").strip().replace(".", "-").replace("/", "-")
    if len(t) == 8 and t.isdigit():
        t = f"{t[:4]}-{t[4:6]}-{t[6:]}"
    try:
        return dt.date.fromisoformat(t)
    except ValueError:
        return None
