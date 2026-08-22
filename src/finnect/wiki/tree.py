"""트랙 A — 노드 트리의 어휘(ADR-0056 결정 2). **고정은 맨 윗줄 하나뿐이다.**

    category   Company · Custom/특허            최상위 열 고정 · 하위는 동적
      node     팀 · 등록-10-2025-0114882        .md 한 장 · 그래프 점 하나
        key    직원 수 · 팀 구성                  VALUE 또는 EVENT

`Custom` 이 탈출구다. 아홉에 안 맞는 것은 전부 거기로 오고, **그래서 갈 곳 없는 사실이
없다** — 옛 `uncategorized` 가 이 결정으로 없어졌다.

## 경로가 정체성이다

노드를 `id` 가 아니라 **경로**로 찾는다. 기획 문서 §4-3 「경로가 곧 노드 제목이다」이고,
화면·마크다운·집필 에이전트가 같은 문자열을 부른다.

## 정규화는 정확 일치까지만 한다

`norm()` 이 공백과 구두점을 지운다. `기 능` 과 `기능` 은 같은 자리이고, `기능` 과
`주요기능` 은 **다른 자리다.** 유사도를 쓰면 같은 문서를 두 번 올릴 때 다른 자리로 가서
비결정론이 된다(ADR-0056 결정 6). 그 그물이 실제로 걸리는 자리는 `port.Roster` 다.

## 목적지 표가 여기 없다

2026-08-22 까지 `EVENT_PATH`(topic 스물셋 → 경로)가 여기 있었고 `merge.place` 가 그걸
봐서 자리를 정했다. **T-0126 이 그 표를 지웠다** — 이제 추출기가 경로를 직접 내고,
표는 픽스처의 옛 어휘를 옮기는 데만 쓴다(`extract_nodes.FIXTURE_PATH`).
"""

from __future__ import annotations

import re

#: 최상위 카테고리 열. **기획 문서 §2 의 것이고 이것만 고정이다.**
#:
#: 키(영문)는 기획 문서 것 그대로다 — 경로가 곧 이름이라 여기서 번역하면 집필
#: 에이전트가 부르는 이름과 갈린다. `Custom` 이 내용을 안 가리킨다는 것은 기획도
#: 알고 있고(§7-4) **그 이름을 우리가 먼저 고치지 않는다.**
#:
#: 한국어 이름은 **자리 제목과 겹치면 안 된다** — 겹치면 `# 경쟁 상대` 밑에 `## 경쟁사`
#: 가 서서 `DESIGN.md` §10("제목이 말한 것을 부제에서 반복하지 않는다")을 어긴다.
CATEGORIES: dict[str, str] = {
    "Company": "회사",
    "Product": "제품",
    "Market": "시장",
    "Competitor": "경쟁 상대",
    "Customer": "고객",
    "BusinessModel": "사업 모델",
    "Financial": "재무",
    "Custom": "지식 재산",
    "Plan": "계획",
    "Events": "기록",
}

#: 아홉에 안 맞는 것이 가는 곳. **버리지 않는다**
FALLBACK = "Custom"


#: 갈 자리를 못 찾은 사실이 가는 노드. **검토 대기가 자리로 산다** —
#: 옛 `uncategorized` 는 트리에 자리가 없어서 화면 어디에도 안 나왔다.
REVIEW_PATH = "Custom/검토 대기"


#: 지우는 것 — 공백 · 가운뎃점 · 괄호 · 구두점. 마디 구분자(`/`)는 따로 다룬다
_PUNCT = re.compile(r"[\s·:()\[\]{},.\-_]+")


def norm(s: str) -> str:
    """공백과 구두점을 지운다. **병합 그물이 이걸로 찾는다.**

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


def clean(path: str) -> str:
    """LLM 이 낸 경로를 쓸 수 있는 모양으로.

    빈 마디를 지우고 앞뒤 공백을 턴다. **카테고리가 표에 없으면 `Custom` 밑으로 민다** —
    LLM 이 enum 을 어겨도 사실이 안 사라진다.
    """
    parts = [p.strip() for p in (path or "").split("/") if p.strip()]
    if not parts:
        return REVIEW_PATH
    if parts[0] not in CATEGORIES:
        parts = [FALLBACK, *parts]
    return "/".join(parts)
