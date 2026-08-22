"""표본 고르기 — 공고번호를 나눈 나머지로 고른다. **멱등하다.**

무작위 시드를 안 쓴다. 언제 몇 번을 돌려도 같은 집합이 나와야 하고, 그래야
초기화를 두 번 해도 같은 DB 가 선다. `notice-filter/kstartup.py` 의 `demo_pick`
(`DEMO_MODULUS = 36`)이 같은 원리로 이미 돌고 있다 — 거기 주석이 근거다.

**`hash()` 를 쓰지 않는다.** `PYTHONHASHSEED` 가 프로세스마다 달라서 실행마다 다른
집합이 나온다. plan/12 T-0094 의 락 키와 똑같은 함정이고, **둘 다 테스트를 통과한다** —
한 프로세스 안에서는 일관되기 때문이다.
"""

from __future__ import annotations

import hashlib

__all__ = ["bucket", "keeps"]


def bucket(external_id: str, modulus: int) -> int:
    """공고번호를 `modulus` 로 나눈 나머지.

    숫자면 그 값을 그대로 쓴다 — K-Startup `pbanc_sn` 과 기업마당 `pblancId` 가
    둘 다 숫자다. **숫자를 먼저 보는 이유는 사람이 눈으로 검산할 수 있어서다**
    (`174036 % 3 == 0` 이면 남는다). 해시로만 하면 왜 그 공고가 남았는지
    설명할 길이 없어진다.

    숫자가 아니면 sha256 앞 16자리를 쓴다. 출처가 늘어 ID 규칙이 바뀌어도
    조용히 틀리지 않게 하려는 것이지, 지금 이 경로를 타는 값은 없다.
    """
    if modulus < 1:
        raise ValueError(f"modulus 는 1 이상이어야 한다 — 받은 값 {modulus}")
    s = external_id.strip()
    if not s:
        raise ValueError("빈 공고번호로는 표본을 못 고른다")
    if s.isdigit():
        return int(s) % modulus
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:16], 16) % modulus


def keeps(external_id: str, modulus: int) -> bool:
    """남길 것인가.

    `modulus == 1` 이면 나머지가 늘 0 이라 전부 남는다. 표본을 끄는 값이
    `None` 이 아니라 1 인 것이 이 함수의 계약이다.
    """
    return bucket(external_id, modulus) == 0
