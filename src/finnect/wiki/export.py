"""자리 트리를 마크다운으로 — **위키의 유일한 뷰다.**

**자리표는 여기 없다.** 마흔여섯은 `spots.py` 가 들고 있고(기획 문서 §2), 이 파일은
**DB 의 `wiki_node` 에서 장을 만든다.** 사실이 앉은 자리만 `.md` 가 되므로 표를 여기서
다시 읽을 필요가 없다.

**저장 모델을 이 모양으로 바꾸지 않는다.** 마크다운을 저장하지 않기로 한 것과 같은
이유다 — 사실이 `wiki_fact` 에 있는데 파일 트리로도 들고 있으면 둘 중 하나가 먼저
낡는다. 여기는 **읽을 때마다 만든다.**

## `.md` 는 사실이 붙은 노드다. 자식이 있든 없든

「잎만 `.md`」로 하면 **지금 잎인 노드에 자식이 생기는 날 그 내용이 갈 곳을 잃는다** —
사용자가 보고 있던 자리가 사라지는 일이라 안 한다(ADR-0056 결정 4). 옵시디언의 폴더
노트와 같은 모양이다.

**빈 폴더는 파일을 안 낸다.** 그래프에는 점으로 서지만(무엇이 없는지 보여야 한다)
내용이 없는 `.md` 를 만들면 볼트에 빈 파일 열 개가 생긴다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from finnect.models import SourceType
from finnect.wiki import markdown, spots, storage
from finnect.wiki.build import NodeView

#: 기획 문서 §5 의 자료 등급 다섯. **순서가 센 것부터다** — `grade_of` 가 이 순서를 쓴다.
#:
#: 2026-08-22 까지 우리가 내는 것이 앞 둘과 마지막뿐이었다. 추출기가 출처를 판정하지
#: 않아서였고, **지금은 묻는다**(`extract_nodes` 프롬프트 `## grade`). `2차` 는 문서가
#: 외부 출처를 **밝히고** 인용했을 때만 붙고 그때 기관 이름이 같이 온다 — 밝히지 않은
#: 인용은 `1차` 로 남는다. 없는 판정을 그럴듯한 등급으로 채우면 `Market/` 값이 전부
#: `2차` 로 보이고 **이 필드를 만든 목적(심사에서 산출 근거를 대는 것)이 거기서 깨진다.**
GRADES: tuple[str, ...] = ("실측", "1차", "2차", "가정", "미정")

#: 사용자가 직접 답한 값(ADR-0028). 문서보다 세다. **추출기가 이걸 못 낸다**
GRADE_MEASURED = "실측"
#: 사용자가 올린 문서에서 나왔다. **자기 자료가 1차 자료다**
GRADE_PRIMARY = "1차"
#: 자리가 비었다. **추출기가 이걸 못 낸다**
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
    #: 기준 연도나 시점. 이 장 사실들의 `as_of` 중 가장 늦은 것
    base_date: str | None = None
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
    """자리 하나의 자료 등급. **한 장에 사실이 여럿이면 가장 약한 것이 이긴다.**

    비었으면 `미정`, 전부 사용자 답변이면 `실측`, 그 밖에는 추출기가 매긴 등급 중
    **가장 약한 것**이다(`실측` → `1차` → `2차` → `가정` 순으로 약해진다).

    가장 센 것이 아니라 약한 것을 고르는 이유는 이 값이 「이 장을 심사에서 얼마나 믿을
    수 있나」이기 때문이다. 실측 하나와 추정 하나가 같이 있는 장을 `실측` 이라고 적으면
    **머리가 본문보다 세게 말한다** — 기획이 §3-3 에서 「근거가 약한 항이 어디인지 그
    파일 안에서 보인다」고 한 것이 여기서도 걸린다.

    등급이 안 매겨진 사실(옛 행 · 스텁)은 `1차` 로 본다. **`미정` 으로 안 내린다** —
    비었다는 뜻이라 사실이 있는 장에 붙으면 거짓이다.
    """
    if not node.facts:
        return GRADE_UNKNOWN
    rank = {g: i for i, g in enumerate(GRADES)}
    got = [
        GRADE_MEASURED
        if f.source_type == SourceType.USER_STATED
        else (f.grade if f.grade in rank else GRADE_PRIMARY)
        for f in node.facts
    ]
    return max(got, key=lambda g: rank[g])


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
            base_date=_latest(f.as_of.isoformat() for f in node.facts if f.as_of),
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
    """출처와 저장 위치. 기획 §5 가 「출처 기관명 **또는** 원본 파일명」이라고 적었다.

    **외부 출처를 앞에 둔다.** `2차` 사실이 밝힌 기관 이름(KOSIS·중소벤처기업부)이
    먼저 오고 그 뒤에 근거 파일이 온다 — `Market/` 아래 값에서 심사가 묻는 것은 우리
    파일 이름이 아니라 그 기관이다.

    **`source_paths` 는 파일 쪽만 찬다.** 외부 기관에는 우리 저장소 경로가 없어서
    앞쪽이 빈 문자열이고, 그래서 **둘의 순서가 같아야 짝이 안 어긋난다.**
    """
    cited = sorted({f.source for f in node.facts if f.source})

    by_name: dict[str, str] = {}
    for f in node.facts:
        for e in f.evidence:
            by_name.setdefault(e.filename, e.sha256)
    files = sorted(by_name)

    def where(name: str) -> str:
        sha = by_name[name]
        return storage.source_path(company, sha) if sha and company else ""

    return (*cited, *files), (*("" for _ in cited), *(where(n) for n in files))


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
    if page.base_date:
        lines.append(f"base_date: {page.base_date}")
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

    폴더가 바뀔 때 이름을 한 줄 세운다. **제목 층이 자리 제목과 겹치는데** 그대로
    둔다 — 낱장으로 열려야 하는 문서를 이어 붙인 것이라 낱장 쪽이 정본이다.
    """
    out: list[str] = [f"# 사업 위키 — {company}", ""]
    last = ""
    for page in pages:
        if page.node.category != last:
            last = page.node.category
            out += [f"# {spots.FOLDERS.get(last, last)}", ""]
        out += [page.body, ""]
    return "\n".join(out).rstrip() + "\n"
