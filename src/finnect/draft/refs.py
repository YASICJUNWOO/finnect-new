"""재료 id 한 공간 — 트랙 둘을 정수 하나로 부른다 (plan/22 T-0134).

## 왜 한 공간이어야 하나

집필 배관이 사실을 **정수 하나로** 부른다. 배분 스키마와 집필 스키마가 둘 다
`{"type": "integer", "enum": [...]}` 이고(`allot.py` · `write.py`), 모델이 고른 것이
`draft.allotment` 에 그대로 앉는다. 트랙이 둘이 되면서 재료가 표 둘에서 오는데
(`wiki_fact` · `company_value`) **둘 다 1부터 시작하는 자동증가라 그냥 섞으면
`#3` 이 어느 표의 3인지 알 수 없다.**

## 음수로 가른다

트랙 B 는 **부호를 뒤집어** 싣는다. `company_value.id == 3` 이면 재료 공간에서 `-3` 이다.

**상수를 더하지 않는다.** `id + 10**9` 같은 방식은 언젠가 그 경계를 넘고, 넘는 날
조용히 틀린다 — 두 표 다 `BigInteger` 라 상한이 우리 손에 없다. 부호는 **넘을 수 있는
경계가 아니다.**

`0` 은 어느 쪽도 아니다. 자동증가가 1부터라 실제로 안 나온다.
"""

from __future__ import annotations


def value_ref(value_id: int) -> int:
    """`company_value.id` → 재료 공간 id."""
    return -value_id


def is_value(ref: int) -> bool:
    """재료 공간 id 가 트랙 B 의 것인가."""
    return ref < 0


def value_id(ref: int) -> int:
    """재료 공간 id → `company_value.id`. **트랙 B 인 것을 확인하고 부른다.**"""
    return -ref


def split(refs: object) -> tuple[list[int], list[int]]:
    """재료 공간 id 들을 `(wiki_fact.id 들, company_value.id 들)` 로 가른다.

    **부르는 쪽이 두 번 세지 않게 여기서 한 번에 가른다** — 근거를 저장할 때도
    화면에 낼 때도 같은 질문을 하기 때문이다.
    """
    facts: list[int] = []
    values: list[int] = []
    for r in refs:  # type: ignore[union-attr]
        (values if is_value(r) else facts).append(value_id(r) if is_value(r) else r)
    return facts, values
