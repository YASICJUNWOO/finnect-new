"""경로 산술 — 자리 이름을 마디로 자르고 붙이고 정규화한다.

**표는 여기 없다.** 자리 마흔여섯은 `spots.py` 가 들고 있고(기획 문서 §2), 여기는
그 경로를 다루는 함수만 있다. 나눈 이유는 표가 기획 문서의 것이고 산술은 우리
것이기 때문이다 — 기획이 자리를 하나 더하면 `spots.py` 만 바뀐다.

## 경로가 정체성이다

자리를 `id` 가 아니라 **경로**로 찾는다. 기획 §4-3 「경로가 곧 노드 제목이다」이고,
화면·마크다운·집필 에이전트가 같은 문자열을 부른다.

## 정규화는 정확 일치까지만 한다

`norm()` 이 공백과 구두점을 지운다. `기 능` 과 `기능` 은 같은 자리이고, `기능` 과
`주요기능` 은 **다른 자리다.** 유사도를 쓰면 같은 문서를 두 번 올릴 때 다른 자리로
가서 비결정론이 된다. 그 그물이 실제로 걸리는 자리는 `port.Roster` 이고,
**자리표가 고정된 뒤로는 인스턴스 이름에만 걸린다** — 나머지는 번호로 온다.
"""

from __future__ import annotations

import re

#: 지우는 것 — 공백 · 가운뎃점 · 괄호 · 구두점. 마디 구분자(`/`)는 따로 다룬다
_PUNCT = re.compile(r"[\s·:()\[\]{},.\-_]+")


def norm(s: str) -> str:
    """공백과 구두점을 지운다. **인스턴스 이름을 접을 때 이걸로 찾는다.**

    **유사도가 아니다.** `기 능` == `기능` 이고 `기능` != `주요기능` 이다.
    """
    return _PUNCT.sub("", s or "")


def norm_path(path: str) -> str:
    """경로는 마디를 유지한 채 마디마다 정규화한다.

    통째로 지우면 `A/BC` 와 `AB/C` 가 같아진다 — 다른 자리인데 하나로 묶인다.
    """
    return "/".join(norm(p) for p in path.split("/"))


def category_of(path: str) -> str:
    """경로의 첫 마디. **묶는 축이자 그래프의 각도 구획이다.**"""
    return path.split("/", 1)[0]


def name_of(path: str) -> str:
    """경로의 마지막 마디. 화면에 쓰는 이름."""
    return path.rsplit("/", 1)[-1]


def parent_of(path: str) -> str:
    """부모 경로. 최상위면 빈 문자열이다 — **`None` 을 안 쓴다.**"""
    return path.rsplit("/", 1)[0] if "/" in path else ""


def ancestors(path: str) -> list[str]:
    """자기를 포함한 조상 전부. 얕은 것부터.

    `Custom/특허/등록-10-…` → `[Custom, Custom/특허, Custom/특허/등록-10-…]`.
    **뼈대가 없으면 트리가 안 선다** — 노드를 만들 때 이 목록을 다 만든다.
    """
    parts = path.split("/")
    return ["/".join(parts[: i + 1]) for i in range(len(parts))]
