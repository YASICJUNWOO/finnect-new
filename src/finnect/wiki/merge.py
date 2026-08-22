"""병합 — **전부 결정론이다**(plan/12 T-0046).

**라우팅이 여기서 나갔다.** 2026-08-22 까지 `place()` 가 `topic` 을 표에서 찾아 자리를
정했는데, T-0126 이 추출을 트랙 둘로 가르면서 **추출기가 자리를 이미 알고 나온다** —
트랙 A 는 노드 경로를, 트랙 B 는 고정 key 열넷 중 하나를. 표를 우리가 안 들고 있는
것이 [ADR-0056](../../../docs/adr/0056-위키를-동적-노드-트리로-바꾸고-매칭-정보를-따로-뽑는다.md)
의 요점이라 그 단계가 통째로 없어졌다.

남은 것은 **같은 것을 두 번 세우지 않는 규칙**과 **무엇이 충돌인가**다. 둘 다 LLM 이
없다 — 같은 파일을 두 번 넣으면 같은 배치가 나온다.

## 충돌이냐 시계열이냐 — 규칙 하나로 가른다

    자리 = (key, 한정어, 시점)

    한 자리에 서로 다른 값이 둘 이상   →  전부 conflict
    한 자리에 값이 하나                →  같은 (key, 한정어) 중 시점이 가장 늦으면
                                          current, 아니면 superseded

**코퍼스의 함정 둘이 이 한 줄로 갈린다.**

| | 자리 | 결과 |
|---|---|---|
| 직원 수 7 · 8 · 10 · 15 | 시점이 넷 다 다르다 | **시계열.** 15 가 current, 나머지 superseded |
| 시드 3억 · 3억 · 2.8억 | 셋 다 2025-09 | **충돌.** 셋 다 conflict |

앞의 것을 충돌로 세우면 오탐이고, 뒤의 것을 시계열로 세우면 거짓이다. 시점이 다르면
성장이고 같으면 모순이다 — **근거 수로 값을 정하지 않는다.** 2 대 1 이라고 3억을
고르지 않고 둘 다 보관한다(F1-1-7).

**트랙 A 의 값도 같은 규칙으로 판정한다.** 다만 자리에 노드가 하나 더 붙는다 —
`Company/팀` 의 `직원 수` 와 `Financial/매출` 의 `직원 수` 는 다른 자리다.

## 시점 없는 값

`dated=False` key(사업자등록번호 등)는 시점을 **떼어 버린다**(`profile.as_of_for`).
문서마다 발급일이 달라도 사업자등록번호는 하나여야 하고, 시점을 남기면 같은 번호가
자리 둘로 갈려 충돌이 안 잡힌다.

`dated=True` 인데 시점이 없는 값은 **가장 오래된 것으로 놓는다.** 시점 있는 값이
하나라도 있으면 current 가 되지 못한다 — 언제 것인지 모르는 값이 아는 값을 밀어내면
안 된다.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from finnect.wiki import profile
from finnect.wiki.extract_nodes import NodeFact
from finnect.wiki.extract_profile import ProfileFact


class Status:
    """값 주장 하나의 상태. **`event` 사실에는 안 붙는다.**"""

    #: 이 자리의 지금 값
    CURRENT = "current"
    #: 더 늦은 시점의 값이 있다. **지우지 않는다** — 이력이다
    SUPERSEDED = "superseded"
    #: 같은 시점에 값이 둘 이상이다. **둘 다 보관하고 묻는다**
    CONFLICT = "conflict"


def node_key(fact: NodeFact) -> str:
    """트랙 A 의 병합 키.

    **서술은 `(노드, key, 시점)` 으로 묶는다**
    ([ADR-0057](../../../docs/adr/0057-서술을-쌓고-시점을-남긴다.md)).
    시점이 더해진 것이 2026-08-22 의 변경이고, **문장은 여전히 키가 아니다.**

    **문장을 키에 넣으면 안 된다.** 같은 사실이 문서마다 다르게 쓰여 있다 — 픽스처의
    재구매율 하나가 네 문서에 `올랐다`·`상승했다`·`올랐습니다`·`34% → 51%` 로 있고,
    문장으로 가르면 그 넷이 사실 넷이 된다. **같은지 아닌지를 정하는 것은 `key` 이고
    그것은 추출기가 준다** — 프롬프트가 「같은 내용이 문서 여럿에 다른 문장으로 있으면
    같은 key 를 줘라 · 확신이 없으면 새 key 를 만든다」고 시킨 그 판단이다.

    **안 쓰이는 것은 문장이지 정보가 아니다.** 같은 key·같은 시점이면 먼저 온 `text` 가
    남는데, 각 문서의 **원래 표현은 `wiki_evidence.quote` 에 그대로 쌓인다.** 근거를
    펼치면 문서별 원문이 나온다 — `text` 는 대표 문장이고 `quote` 가 출처다.

    **시점이 빠져 있던 것이 진짜 결함이었다.** `팀 구성` 의 2026-08 과 2025-11 이 같은
    키로 접혀서, 추출기가 그걸 피하려고 시점을 이름에 박았다(`team_roles_2026_08`).
    시점이 키에 들어가면 key 는 `팀 구성` 하나면 되고 **한 절 안에서 이력으로 쌓인다.**

    **값은 자리와 값이 같으면 같은 주장이다.** 값이 키에 들어가는 것이 요점 — 시점이
    같은데 값이 다르면 키가 달라 행이 둘이 되고 그게 곧 충돌이다.
    """
    if fact.kind != "value":
        return f"event|{fact.path}|{fact.key}|{fact.as_of or ''}"
    q, d = fact.qualifier or "", fact.as_of or ""
    return f"value|{fact.path}|{fact.key}|{q}|{d}|{_norm(fact.value)}"


def value_key(fact: ProfileFact) -> str:
    """트랙 B 의 병합 키. **시점을 뗄지는 `profile` 이 정한다** — 값의 정의라서다."""
    return profile.dedupe_key(fact.key, fact.qualifier, fact.as_of, fact.value)


def _norm(s: str | None) -> str:
    """비교용 정규화. **공백을 전부 지운다** — `profile._norm` 과 같은 규칙이다.

    OCR 이 `응용 소프트웨어개발및공급업` 을 내고 사업계획서가 `응용 소프트웨어 개발 및
    공급업` 을 낸다. 안 지우면 OCR 노이즈가 전부 충돌로 둔갑한다.
    """
    return "".join((s or "").split())


@dataclass(frozen=True, slots=True)
class Claim:
    """상태를 매길 때 보는 최소 단위. DB 행에서 이만큼만 꺼낸다.

    `key` 에 무엇이 들어가는지는 부르는 쪽이 정한다 — 트랙 B 는 `headcount`, 트랙 A 는
    `<노드 id>|<key>` 다. **자리가 다르면 문자열이 달라야 한다**는 것만 지키면 된다.
    """

    key: str
    qualifier: str | None
    as_of: dt.date | None
    value: str


def decide(claims: list[Claim]) -> dict[Claim, str]:
    """주장들에 상태를 매긴다. **한 회사의 값 전부를 한 번에 넣는다.**

    부분만 넣으면 틀린다 — 어느 시점이 가장 늦은지는 전체를 봐야 안다.
    """
    out: dict[Claim, str] = {}

    #: (자리, 한정어) → {시점: {값}}
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
