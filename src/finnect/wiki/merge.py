"""중복 방지와 충돌 판정 — **전부 결정론이다**(plan/12 T-0046).

**트랙 A 에는 병합이 없다.** 2026-08-22 자리표를 고정하면서 `key` 를 없앴고
(`extract_nodes.py` 첫 문단), 그 `key` 가 **「이 둘은 같은 사실이다」를 정하던 유일한
근거**였다. 지우면서 그 판단을 대신할 것을 만들지 않기로 했다 — 만들 수 있는 것은
문장 유사도뿐이고, 그건 같은 문서를 두 번 올릴 때 다른 답을 내서 비결정론이다.

그래서 트랙 A 에 남은 것은 **똑같은 것을 두 번 세우지 않는 것** 하나다. 같은 자리 ·
같은 시점 · 같은 문장이면 근거만 더한다. 그 밖에는 전부 쌓인다.

**대가를 적어 둔다.** 같은 사실이 문서 넷에 다르게 쓰여 있으면(`올랐다`·`상승했다`·
`올랐습니다`·`34% → 51%`) **사실 넷이 선다.** 근거를 펼치면 넷이 같은 얘기인 것이
보이지만, 코드는 모른다.

**트랙 B 는 그대로다.** 거기는 key 가 고정 열다섯이라 자리가 흔들리지 않고, 자격
판별이 걸려 있어 충돌 판정이 실제로 필요하다.

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

**이 규칙은 트랙 B 에만 건다.** 트랙 A 의 값에도 걸었었는데, `key` 가 없어지면서 한
자리 안에서 무엇과 무엇을 견줄지가 정해지지 않는다 — `Market/시장규모` 의 TAM·SAM·SOM
은 같은 시점에 값이 셋이고 **그건 충돌이 아니라 원래 셋이다.** 자리만 보고 판정하면
그 셋이 전부 `conflict` 로 뜬다. 그래서 **트랙 A 값에는 상태를 안 매긴다**(`status`
가 NULL 이고, 화면은 시점 내림차순으로만 세운다).

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
    """트랙 A 의 중복 방지 키. **병합 키가 아니다.**

        값     value|<자리>|<이름>|<시점>|<값>
        서술   event|<자리>|<시점>|<문장>

    **값에는 이름이 들어가고 서술에는 안 들어간다**(ADR-0059). 이름이 없으면 같은
    자리·같은 시점의 다른 항목이 우연히 같은 숫자일 때 하나가 사라진다 — 실측에서
    `Company/팀` 의 「경영은 1명」과 「운영은 1명」이 정확히 그 짝이었다.

    **이름에서 시점을 떼고 온다**(`extract_nodes.bare_key`). `2024년 매출액` 과
    `2025년 매출액` 이 같은 이름이 되어야 `as_of` 가 둘을 가르고 이력이 선다.

    **값이 키에 들어가는 것이 요점이다.** 같은 자리·같은 이름·같은 시점인데 값이
    다르면 행이 둘로 서고, 그것이 곧 사용자가 봐야 할 어긋남이다(F1-1-7) — 시드
    3억과 2.8억이 둘 다 남는 이유다.

    서술은 문장이 열쇠다. 파서마다 줄바꿈이 달라서 `_norm` 이 공백을 지운다.
    """
    if fact.key and fact.value is not None:
        return f"value|{fact.path}|{_norm(fact.key)}|{fact.as_of or ''}|{_norm(fact.value)}"
    return f"event|{fact.path}|{fact.as_of or ''}|{_norm(fact.text)}"


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

    **트랙 B 만 쓴다.** `key` 는 매칭 정보 열다섯 중 하나(`headcount`)이고, 그 열다섯이
    고정이라 「무엇과 무엇을 견주나」가 정해진다. 트랙 A 에는 그 축이 없다 —
    이 모듈 첫 문단 참고.
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
