"""노드 트리를 마크다운으로 — **위키의 유일한 뷰다**(ADR-0056).

**고정 표가 없어졌다.** 2026-08-22 아침까지 이 파일은 자리 47개를 손으로 적은
`TREE` 를 들고 있었고, 「어느 값이 어느 자리에 뜨나」도 우리가 골라 적었다. 지금은
**DB 의 `wiki_node` 에서 만든다** — 카테고리 열만 고정이고 나머지는 문서가 정한다
([ADR-0056](../../../docs/adr/0056-위키를-동적-노드-트리로-바꾸고-매칭-정보를-따로-뽑는다.md)).

**저장 모델을 이 모양으로 바꾸지 않는다.** 마크다운을 저장하지 않기로 한 것과 같은
이유다 — 사실이 `wiki_fact` 에 있는데 파일 트리로도 들고 있으면 둘 중 하나가 먼저
낡는다. 여기는 **읽을 때마다 만든다.**

## `.md` 는 사실이 붙은 노드다. 자식이 있든 없든

「잎만 `.md`」로 하면 **지금 잎인 노드에 자식이 생기는 날 그 내용이 갈 곳을 잃는다** —
사용자가 보고 있던 자리가 사라지는 일이라 안 한다(ADR-0056 결정 4). 옵시디언의 폴더
노트와 같은 모양이다.

**빈 카테고리는 파일을 안 낸다.** 그래프에는 점으로 서지만(무엇이 없는지 보여야 한다)
내용이 없는 `.md` 를 만들면 볼트에 빈 파일 열 개가 생긴다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from finnect.models import SourceType
from finnect.wiki import markdown, storage, tree
from finnect.wiki.build import NodeView

#: 기획 문서 §5 의 자료 등급 다섯. **우리가 내는 것은 앞 둘과 마지막뿐이다.**
#:
#: `2차`(외부 인용)와 `가정`(추정)을 안 내는 이유는 **추출기가 그것을 판정하지 않기**
#: 때문이다. 「이 시장 규모가 KOSIS 인용인가 대표가 어림한 값인가」는 문서 안에 답이
#: 있을 때도 없을 때도 있는데 지금 프롬프트가 묻지 않는다. 없는 판정을 그럴듯한 등급으로
#: 채우면 `Market/` 값이 전부 `2차` 로 보이고, **기획이 이 필드를 만든 목적(심사에서
#: 산출 근거를 대는 것)이 정확히 거기서 깨진다.**
GRADES: tuple[str, ...] = ("실측", "1차", "2차", "가정", "미정")

#: 사용자가 직접 답한 값(ADR-0028). 문서보다 세다
GRADE_MEASURED = "실측"
#: 사용자가 올린 문서에서 나왔다. **자기 자료가 1차 자료다**
GRADE_PRIMARY = "1차"
#: 자리가 비었다
GRADE_UNKNOWN = "미정"


@dataclass(slots=True)
class Page:
    """노드 한 장. **저장된 것이 아니라 매번 만든 것이다.**"""

    node: NodeView
    body: str

    #: --- 기획 문서 §5 의 파일 머리 ---
    grade: str = GRADE_UNKNOWN
    sources: tuple[str, ...] = ()
    source_paths: tuple[str, ...] = ()
    updated_at: str | None = None
    #: 자식 노드 경로. **폴더 노트가 자기 아래를 가리킨다**
    children: tuple[str, ...] = field(default_factory=tuple)

    @property
    def path(self) -> str:
        return self.node.path

    @property
    def filled(self) -> bool:
        return self.node.filled


def grade_of(node: NodeView) -> str:
    """노드 하나의 자료 등급. **판정할 수 없는 등급을 지어내지 않는다.**

    비었으면 `미정`, 사실이 전부 사용자 답변이면 `실측`, 그 밖에는 `1차` 다.
    `2차` 와 `가정` 은 추출기가 출처를 판정하는 날 생긴다 — **그날까지 안 낸다.**
    """
    kinds = [f.source_type for f in node.facts]
    if not kinds:
        return GRADE_UNKNOWN
    if all(k == SourceType.USER_STATED for k in kinds):
        return GRADE_MEASURED
    return GRADE_PRIMARY


def render(nodes: list[NodeView], company: str = "") -> list[Page]:
    """사실이 붙은 노드마다 한 장. **빈 뼈대는 파일을 안 낸다.**"""
    kids: dict[str, list[str]] = {}
    for n in nodes:
        if n.parent:
            kids.setdefault(n.parent, []).append(n.path)

    out = []
    for node in nodes:
        if not node.filled:
            continue
        page = Page(
            node=node,
            body="",
            grade=grade_of(node),
            updated_at=_latest(f.updated_at.isoformat() for f in node.facts if f.updated_at),
            children=tuple(sorted(kids.get(node.path, ()))),
        )
        page.sources, page.source_paths = _sources_of(company, node)
        page.body = _page(page, company)
        out.append(page)
    return out


def _latest(items) -> str | None:  # noqa: ANN001
    """ISO 날짜 중 가장 늦은 것. **문자열로 비교한다** — ISO 라 사전순이 곧 시간순이다."""
    seen = sorted(x for x in items if x)
    return seen[-1] if seen else None


def _sources_of(company: str, node: NodeView) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """근거 파일 이름과 저장 위치. **둘의 순서가 같다** — 짝이 어긋나면 위치가 거짓말이 된다."""
    by_name: dict[str, str] = {}
    for f in node.facts:
        for e in f.evidence:
            by_name.setdefault(e.filename, e.sha256)
    names = tuple(sorted(by_name))
    paths = tuple(
        storage.source_path(company, by_name[n]) if by_name[n] and company else "" for n in names
    )
    return names, paths


def _page(page: Page, company: str) -> str:
    """노드 한 장의 마크다운. 머리는 **기획 문서 §5 모양**이다.

    **만든 시각을 안 넣는다.** `updated_at` 은 `wiki_fact` 의 값이라 같은 DB 면 같다 —
    그래서 두 번 내보낸 결과를 바이트로 비교할 수 있다.
    """
    node = page.node
    lines = [
        "---",
        f"path: {node.path}",
        f"title: {node.name}",
        f"category: {node.category}",
        f"company: {company}",
        f"grade: {page.grade}",
    ]
    if page.sources:
        lines.append(f"source: {' · '.join(page.sources)}")
    if any(page.source_paths):
        lines.append(f"source_path: {' · '.join(p for p in page.source_paths if p)}")
    if page.updated_at:
        lines.append(f"updated_at: {page.updated_at}")
    if page.children:
        lines.append(f"children: {' · '.join(page.children)}")
    lines.append(f"facts: {len(node.facts)}")
    lines.append("---")

    out = ["\n".join(lines), "", f"# {node.name}", ""]
    out += markdown.render_facts(node.facts)
    out += markdown.render_sources([e for f in node.facts for e in f.evidence])
    return "\n".join(out).rstrip() + "\n"


def file_of(path: str) -> str:
    """내보낼 파일 경로. **폴더 노트라 경로 그대로에 `.md` 를 붙인다.**

    `Custom/특허` 는 `Custom/특허.md` 이고 그 아래 `Custom/특허/등록-….md` 가 같이 산다.
    """
    return f"{path}.md"


def bundle(pages: list[Page], company: str) -> str:
    """전부를 한 덩어리로. 화면에서 통째로 보거나 복사할 때 쓴다.

    **F1-6(밖으로 꺼내기)이 아니다.** 저기는 노드마다 `.md` 하나로 떨어져 옵시디언
    볼트가 되는 것이고, 여기는 한 덩어리다.

    카테고리가 바뀔 때 이름을 한 줄 세운다. **제목 층이 노드 제목과 겹치는데** 그대로
    둔다 — 낱장으로 열려야 하는 문서를 이어 붙인 것이라 낱장 쪽이 정본이다.
    """
    out: list[str] = [f"# 사업 위키 — {company}", ""]
    last = ""
    for page in pages:
        if page.node.category != last:
            last = page.node.category
            out += [f"# {tree.CATEGORIES.get(last, last)}", ""]
        out += [page.body, ""]
    return "\n".join(out).rstrip() + "\n"
