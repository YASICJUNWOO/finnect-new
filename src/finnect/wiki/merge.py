"""라우팅과 병합 — **전부 결정론이다**(plan/12 T-0045 · T-0046).

여기 LLM 이 없다. 목적지는 `topics.py` 의 표가 정하고, 무엇이 충돌인지는 아래 규칙
하나가 정한다. **같은 파일을 두 번 넣으면 같은 배치가 나온다**(T-0045 완료 조건).

## 충돌이냐 시계열이냐 — 규칙 하나로 가른다

    자리 = (슬롯, 한정어, 시점)

    한 자리에 서로 다른 값이 둘 이상   →  전부 conflict
    한 자리에 값이 하나                →  같은 (슬롯, 한정어) 중 시점이 가장 늦으면
                                          current, 아니면 superseded

**코퍼스의 함정 둘이 이 한 줄로 갈린다.**

| | 자리 | 결과 |
|---|---|---|
| 직원 수 7 · 8 · 10 · 15 | 시점이 넷 다 다르다 | **시계열.** 15 가 current, 나머지 superseded |
| 시드 3억 · 3억 · 2.8억 | 셋 다 2025-09 | **충돌.** 셋 다 conflict |

앞의 것을 충돌로 세우면 오탐이고, 뒤의 것을 시계열로 세우면 거짓이다. 시점이 다르면
성장이고 같으면 모순이다 — **근거 수로 값을 정하지 않는다.** 2 대 1 이라고 3억을
고르지 않고 둘 다 보관한다(F1-1-7).

## 시점 없는 값

`dated=False` 슬롯(사업자등록번호 등)은 시점을 **떼어 버린다.** 문서마다 발급일이
달라도 사업자등록번호는 하나여야 하고, 시점을 남기면 같은 번호가 자리 둘로 갈려
충돌이 안 잡힌다.

`dated=True` 슬롯인데 시점이 없는 값은 **가장 오래된 것으로 놓는다.** 시점 있는 값이
하나라도 있으면 current 가 되지 못한다 — 언제 것인지 모르는 값이 아는 값을 밀어내면
안 된다.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from finnect.wiki import topics
from finnect.wiki.extract import Fact


class Status:
    """정형 슬롯 주장 하나의 상태. **서술 노드에는 붙지 않는다.**"""

    #: 이 슬롯의 지금 값
    CURRENT = "current"
    #: 더 늦은 시점의 값이 있다. **지우지 않는다** — 이력이다
    SUPERSEDED = "superseded"
    #: 같은 시점에 값이 둘 이상이다. **둘 다 보관하고 묻는다**
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class Placement:
    """사실 하나가 갈 자리."""

    #: `slot` · `node` · `uncategorized`
    kind: str
    #: 슬롯 이름 또는 노드 이름. `uncategorized` 면 빈 문자열
    name: str
    #: 왜 uncategorized 인가. 검토 큐에서 사람이 읽는다
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.kind != topics.UNCATEGORIZED


def place(fact: Fact) -> Placement:
    """사실 하나의 목적지. **모르면 버리지 않고 `uncategorized` 로 세운다**(구상도 ④ 예외)."""
    if fact.topic == topics.UNCATEGORIZED:
        return Placement(topics.UNCATEGORIZED, "", "온톨로지 밖 topic")

    if fact.kind == "slot":
        slot = topics.slot_of(fact.key)
        if slot is None:
            return Placement(topics.UNCATEGORIZED, "", f"모르는 항목 이름 — {fact.key!r}")
        if not (fact.value or "").strip():
            return Placement(topics.UNCATEGORIZED, "", f"값이 비어 있음 — {fact.key!r}")
        return Placement("slot", slot)

    node = topics.node_of(fact.topic)
    if node is None:
        # `company_profile` · `application_history` 가 서술로 오면 여기다.
        # 둘은 정형 슬롯의 재료라 서술 노드가 없다.
        return Placement(topics.UNCATEGORIZED, "", f"서술 노드가 없는 topic — {fact.topic}")
    return Placement("node", node)


def as_of_for(slot: str, as_of: dt.date | None) -> dt.date | None:
    """슬롯이 시점을 갖는가에 따라 시점을 남기거나 뗀다."""
    spec = topics.SLOTS.get(slot)
    return as_of if (spec and spec.dated) else None


def dedupe_key(fact: Fact, spot: Placement) -> str:
    """같은 사실을 두 번 세우지 않게 하는 키.

    **정형은 자리와 값이 같으면 같은 주장이다.** 사업자등록번호가 문서 넷에 있으면
    행 하나에 근거 넷이다.

    **서술은 추출기가 준 `fact_key` 로 묶는다.** 같은 사실이 문서마다 다른 문장으로
    쓰여 있어서(`재구매율이 51%로 올랐습니다` / `34% → 51%`) 문자열로는 못 묶는다.
    `fact_key` 가 없으면 문장 자체가 키다 — 안 묶인다.
    """
    if spot.kind == "slot":
        d = as_of_for(spot.name, fact.as_of)
        return f"slot|{spot.name}|{fact.qualifier or ''}|{d or ''}|{_norm(fact.value)}"
    if spot.kind == "node":
        return f"node|{spot.name}|{fact.fact_key or _norm(fact.text)}"
    return f"uncategorized|{fact.topic}|{_norm(fact.text)}"


def _norm(s: str | None) -> str:
    """비교용 정규화. **공백을 전부 지운다.**

    OCR 이 `응용 소프트웨어개발및공급업` 을 내고 사업계획서가 `응용 소프트웨어 개발 및
    공급업` 을 낸다. 띄어쓰기만 다른 같은 값이라 **공백을 지워야 하나로 모인다.**
    지우지 않으면 OCR 노이즈가 전부 충돌로 둔갑한다.

    단위와 표기(`24,100천원` → `24100000`)는 여기서 못 고친다. **그건 추출기의 일이다** —
    `Fact.value` 가 정규화된 값이고 문서가 쓴 표현은 `Fact.text` 에 남는다.
    """
    return "".join((s or "").split())


@dataclass(frozen=True, slots=True)
class Claim:
    """상태를 매길 때 보는 최소 단위. DB 행에서 이만큼만 꺼낸다."""

    slot: str
    qualifier: str | None
    as_of: dt.date | None
    value: str


def decide(claims: list[Claim]) -> dict[Claim, str]:
    """주장들에 상태를 매긴다. **한 회사의 정형 슬롯 전부를 한 번에 넣는다.**

    부분만 넣으면 틀린다 — 어느 시점이 가장 늦은지는 전체를 봐야 안다.
    """
    out: dict[Claim, str] = {}

    #: (슬롯, 한정어) → {시점: {값}}
    groups: dict[tuple[str, str | None], dict[dt.date | None, set[str]]] = {}
    for c in claims:
        groups.setdefault((c.slot, c.qualifier), {}).setdefault(c.as_of, set()).add(c.value)

    latest: dict[tuple[str, str | None], dt.date | None] = {}
    for key, by_date in groups.items():
        dated = [d for d in by_date if d is not None]
        # 시점 있는 값이 하나라도 있으면 그중 가장 늦은 것이 current 후보다.
        # 없으면 시점 없는 자리(None)가 current 다.
        latest[key] = max(dated) if dated else None

    for c in claims:
        key = (c.slot, c.qualifier)
        if len(groups[key][c.as_of]) > 1:
            out[c] = Status.CONFLICT
        elif c.as_of == latest[key]:
            out[c] = Status.CURRENT
        else:
            out[c] = Status.SUPERSEDED
    return out
