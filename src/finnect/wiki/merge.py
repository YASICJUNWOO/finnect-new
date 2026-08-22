"""라우팅과 병합 — **전부 결정론이다**(plan/12 T-0045 · T-0046).

여기 LLM 이 없다. 목적지는 `topics.py` 의 표가 정하고, 무엇이 충돌인지는 아래 규칙
하나가 정한다. **같은 파일을 두 번 넣으면 같은 배치가 나온다**(T-0045 완료 조건).

## 충돌이냐 시계열이냐 — 규칙 하나로 가른다

    자리 = (value topic, 한정어, 시점)

    한 자리에 서로 다른 값이 둘 이상   →  전부 conflict
    한 자리에 값이 하나                →  같은 (value topic, 한정어) 중 시점이 가장 늦으면
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

`dated=False` value topic(사업자등록번호 등)은 시점을 **떼어 버린다.** 문서마다 발급일이
달라도 사업자등록번호는 하나여야 하고, 시점을 남기면 같은 번호가 자리 둘로 갈려
충돌이 안 잡힌다.

`dated=True` value topic인데 시점이 없는 값은 **가장 오래된 것으로 놓는다.** 시점 있는 값이
하나라도 있으면 current 가 되지 못한다 — 언제 것인지 모르는 값이 아는 값을 밀어내면
안 된다.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from finnect.wiki import profile, tree
from finnect.wiki.extract import Fact


class Status:
    """value topic 주장 하나의 상태. **event topic에는 붙지 않는다.**"""

    #: 이 value topic 의 지금 값
    CURRENT = "current"
    #: 더 늦은 시점의 값이 있다. **지우지 않는다** — 이력이다
    SUPERSEDED = "superseded"
    #: 같은 시점에 값이 둘 이상이다. **둘 다 보관하고 묻는다**
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class Placement:
    """사실 하나가 갈 곳(ADR-0056). **트랙이 둘이라 목적지도 둘이다.**

        kind="value"   트랙 B — `company_value` 로. `key` 가 고정 열넷 중 하나
        kind="event"   트랙 A — `wiki_node` 로. `path` 가 노드 경로다

    **`uncategorized` 가 없다.** 카테고리가 enum 열이라 갈 곳 없는 사실이 없고, 모르는
    것은 `Custom/검토 대기` 라는 **진짜 자리**로 간다 — 옛 미분류는 트리에 자리가 없어서
    화면 어디에도 안 나왔다.
    """

    kind: str
    #: `event` 일 때 노드 경로. `value` 면 빈 문자열
    path: str = ""
    #: `value` 면 고정 key, `event` 면 라벨이자 병합 열쇠
    key: str = ""
    #: 왜 검토 대기로 갔나. 제자리를 찾았으면 빈 문자열
    why: str = ""


def place(fact: Fact) -> Placement:
    """사실 하나의 목적지. **값이면 트랙 B 로 샌다** — 트리에 안 앉는다."""
    if fact.kind == "value":
        key = profile.key_of(fact.key)
        if key is None:
            return _review(fact, f"모르는 항목 이름 — {fact.key!r}")
        if not (fact.value or "").strip():
            return _review(fact, f"값이 비어 있음 — {fact.key!r}")
        return Placement("value", key=key)

    path = tree.EVENT_PATH.get(fact.topic or "")
    if path is None:
        #: `company_profile` · `application_history` 가 서술로 오면 여기다.
        #: 둘은 매칭 정보의 재료라 노드 자리가 없다.
        return _review(fact, f"자리가 없는 topic — {fact.topic}")
    return Placement("event", path=path, key=_event_key(fact))


def _review(fact: Fact, why: str) -> Placement:
    """제자리를 못 찾았다. **버리지 않고 검토 대기 노드로 보낸다.**"""
    return Placement("event", path=tree.REVIEW_PATH, key=_event_key(fact), why=why)


def _event_key(fact: Fact) -> str:
    """노드 안에서 이 사실을 부르는 이름. **라벨이자 병합 열쇠다**(ADR-0056 결정 3).

    추출기가 아직 `fact_key`(`patent_offline_sync`)를 내므로 그것을 쓴다. 사람이 읽는
    말로 바꾸는 것은 plan/22 T-0126 이다. 없으면 문장 자체가 키라 **안 묶인다** —
    잘못 묶는 것보다 낫다.
    """
    return fact.fact_key or tree.norm(fact.text) or "사실"


def dedupe_key(fact: Fact, spot: Placement) -> str:
    """같은 사실을 두 번 세우지 않게 하는 키.

    **값은 자리와 값이 같으면 같은 주장이다.** 사업자등록번호가 문서 넷에 있으면 행
    하나에 근거 넷이다. 값이 키에 들어가는 것이 요점 — 시점이 같은데 값이 다르면 키가
    달라 행이 둘이 되고 그게 곧 충돌이다.

    **서술은 `(노드, key)` 로 묶는다.** 같은 사실이 문서마다 다른 문장으로 쓰여 있어서
    (`재구매율이 51%로 올랐습니다` / `34% → 51%`) 문장으로는 못 묶는다.
    """
    if spot.kind == "value":
        return profile.dedupe_key(spot.key, fact.qualifier, fact.as_of, fact.value or "")
    return f"event|{spot.path}|{spot.key}"


@dataclass(frozen=True, slots=True)
class Claim:
    """상태를 매길 때 보는 최소 단위. DB 행에서 이만큼만 꺼낸다."""

    key: str
    qualifier: str | None
    as_of: dt.date | None
    value: str


def decide(claims: list[Claim]) -> dict[Claim, str]:
    """주장들에 상태를 매긴다. **한 회사의 value topic 전부를 한 번에 넣는다.**

    부분만 넣으면 틀린다 — 어느 시점이 가장 늦은지는 전체를 봐야 안다.
    """
    out: dict[Claim, str] = {}

    #: (value topic, 한정어) → {시점: {값}}
    groups: dict[tuple[str, str | None], dict[dt.date | None, set[str]]] = {}
    for c in claims:
        groups.setdefault((c.key, c.qualifier), {}).setdefault(c.as_of, set()).add(c.value)

    latest: dict[tuple[str, str | None], dt.date | None] = {}
    for key, by_date in groups.items():
        dated = [d for d in by_date if d is not None]
        # 시점 있는 값이 하나라도 있으면 그중 가장 늦은 것이 current 후보다.
        # 없으면 시점 없는 자리(None)가 current 다.
        latest[key] = max(dated) if dated else None

    for c in claims:
        key = (c.key, c.qualifier)
        if len(groups[key][c.as_of]) > 1:
            out[c] = Status.CONFLICT
        elif c.as_of == latest[key]:
            out[c] = Status.CURRENT
        else:
            out[c] = Status.SUPERSEDED
    return out
