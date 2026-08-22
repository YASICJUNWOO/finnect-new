"""자리 한 장을 마크다운으로 — **뷰다. 저장하지 않는다**(plan/12 `구상도와의 차이`).

구상도는 ⑥에서 마크다운을 만들고 ⑦에서 SQL 로도 저장한다. **우리는 저장하지 않는다.**
`SPEC.md` §2-1 이 "소스가 갈라지면 불일치가 생긴다"고 적었고, 사실이 `wiki_fact` 에
있는데 같은 내용을 마크다운으로도 들고 있으면 둘 중 하나가 먼저 낡는다.

그래서 이 파일은 **읽을 때마다 다시 만든다.** 대가는 매번 조인 몇 번이고, 얻는 것은
"화면에 보이는 글자가 DB 와 다를 수 없다"는 성질이다.

## 시각이 안 들어간다

프론트매터에 `generated: 2026-08-18` 같은 것을 넣지 않는다. 넣으면 같은 DB 에서 만든
마크다운이 매일 달라져 **바이트로 비교할 수 없다.** 테스트가 그걸 본다.

## `SPEC.md` F1-3 의 한 장이 이 모양이다

머리말 · 본문 · **자기 근거가 되는 원문 조각** 셋이다. 근거는 `파일명 N쪽` 까지 적는다 —
"출처는 문자열이 아니라 연결이다"(F1-3)라고 한 그 연결의 마크다운 표현이다.

F1-6(밖으로 꺼내기)이 이걸 그대로 쓴다. 옵시디언에서 열리는 것이 목표라 프론트매터는
YAML 이고 자리 사이 링크는 `[[제목]]` 이다.
"""

from __future__ import annotations

from dataclasses import dataclass

from finnect.wiki import merge, topics

#: 충돌한 값 앞에 붙는 말. **이모지를 쓰지 않는다** — 옵시디언과 터미널에서 폭이 갈린다.
CONFLICT_NOTE = "> 값이 갈려요. 어느 쪽이 맞는지 정해야 해요 — 둘 다 두었어요."

#: 절은 섰는데 그 topic 에 사실이 없을 때. **자리를 지우지 않는다**(ADR-0028).
EMPTY_TOPIC = "아직 없어요."


@dataclass(frozen=True, slots=True)
class Evidence:
    """근거 하나. `파일명 3쪽`."""

    filename: str
    page: int | None
    quote: str

    def __str__(self) -> str:
        return f"{self.filename}{f' {self.page}쪽' if self.page else ''}"


@dataclass(frozen=True, slots=True)
class Value:
    """value topic 의 주장 하나."""

    slot: str
    label: str
    value: str
    qualifier: str | None
    as_of: str | None
    status: str
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class Statement:
    """event topic 의 사실 하나."""

    text: str
    topic: str
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class NodeView:
    """마크다운을 만들기에 충분한 만큼. **DB 를 모른다** — 서비스가 채워서 넘긴다."""

    key: str
    label: str
    kind: str
    sector: str
    company_id: str
    values: tuple[Value, ...]
    statements: tuple[Statement, ...]

    @property
    def filled(self) -> bool:
        return bool(self.values or self.statements)

    @property
    def conflicted(self) -> bool:
        return any(v.status == merge.Status.CONFLICT for v in self.values)

    @property
    def source_count(self) -> int:
        """근거로 쓰인 파일 수. **근거 개수가 아니라 파일 수다.**"""
        return len({e.filename for e in self._all_evidence})

    @property
    def _all_evidence(self) -> list[Evidence]:
        return [e for v in self.values for e in v.evidence] + [
            e for s in self.statements for e in s.evidence
        ]


def render(node: NodeView) -> str:
    """자리 한 장. **빈 자리도 만든다** — 비어 있다는 것도 사실이고, 물어야 할 자리다."""
    out = [_front_matter(node), "", f"# {node.label}", ""]

    if not node.filled:
        out += [
            "아직 비어 있어요. 이 자리를 채우려면 관련된 파일을 더 올리면 돼요.",
            "",
        ]
        return "\n".join(out)

    if node.values:
        out += _values(node.values)
    out += _statements(node)

    out += _sources(node._all_evidence)
    return "\n".join(out).rstrip() + "\n"


def _front_matter(node: NodeView) -> str:
    """YAML. **옵시디언이 읽는 모양이다**(F1-6).

    `kind` 를 넣는 이유는 옵시디언 그래프에서도 종류가 색으로 갈리게 하려는 것이다 —
    `DESIGN.md` §4.1 의 "색은 종류만 말한다"가 밖에서도 유지된다.
    """
    lines = [
        "---",
        f"node: {node.key}",
        f"title: {node.label}",
        f"kind: {node.kind}",
        f"sector: {node.sector}",
        f"company: {node.company_id}",
    ]
    if node.values:
        lines.append(f"values: {len(node.values)}")
    if node.statements:
        lines.append(f"statements: {len(node.statements)}")
    if node.filled:
        lines.append(f"sources: {node.source_count}")
    if node.conflicted:
        lines.append("conflict: true")
    lines.append("---")
    return "\n".join(lines)


def _values(values: tuple[Value, ...]) -> list[str]:
    """value topic. **현재값을 먼저 쓰고 이전값을 밑에 접는다.** 지우지 않는다(F1-1-7)."""
    out: list[str] = []
    # (value topic, 한정어) 로 묶는다. 한정어가 다르면 다른 것이다 — 시드와 정책자금
    groups: dict[tuple[str, str | None], list[Value]] = {}
    for v in values:
        groups.setdefault((v.slot, v.qualifier), []).append(v)

    for (slot, qualifier), items in groups.items():
        label = topics.VALUE_SPECS[slot].label if slot in topics.VALUE_SPECS else slot
        head = f"{label} [{qualifier}]" if qualifier else label
        out += [f"## {head}", ""]

        current = [v for v in items if v.status != merge.Status.SUPERSEDED]
        history = [v for v in items if v.status == merge.Status.SUPERSEDED]

        if any(v.status == merge.Status.CONFLICT for v in current):
            out += [CONFLICT_NOTE, ""]

        for v in current:
            shown = topics.display(v.slot, v.value)
            out.append(f"**{shown}**{f'  · {v.as_of} 기준' if v.as_of else ''}")
            out.append("")
            out += [f"- 근거 — {e}" for e in v.evidence]
            out.append("")

        if history:
            out += ["이전 값", ""]
            for v in sorted(history, key=lambda x: x.as_of or "", reverse=True):
                where = " · ".join(str(e) for e in v.evidence)
                shown = topics.display(v.slot, v.value)
                out.append(f"- {shown}{f' · {v.as_of}' if v.as_of else ''} — {where}")
            out.append("")
    return out


def _statements(node: NodeView) -> list[str]:
    """event topic. **한 사실에 근거가 여럿이다** — 문서 넷이 같은 말을 하면 줄 하나에 근거 넷.

    **event topic 이 둘 이상인 자리는 topic 마다 `##` 절을 세운다**(ADR-0048 결정 5).
    하나뿐이면 안 세운다 — `# 목표 고객` 밑의 `## 목표 고객` 은 `DESIGN.md` §10
    ("제목이 말한 것을 부제에서 반복하지 않는다")을 정면으로 어긴다.

    절이 서는 자리에서는 **빈 topic 도 절을 낸다.** 비어 있다는 것도 사실이고 물어야 할
    자리다(ADR-0028) — 지금 «솔루션과 기술» 한 장에 기능·특허·인증이 구분 없이 섞여
    있어서 무엇이 없는지 볼 수가 없었다.

    절이 안 서는 자리(단일 topic 다섯)는 빈 것을 따로 알리지 않는다. 제목이 없어서
    「아직 없어요」한 줄만 뜨면 무엇이 없다는 말인지 알 수 없다.
    """
    order = topics.ORBIT_TOPICS.get(node.key, ())
    if len(order) < 2:
        return _facts(node.statements)

    out: list[str] = []
    for topic in order:
        out += [f"## {topics.TOPIC_LABELS.get(topic, topic)}", ""]
        items = [s for s in node.statements if s.topic == topic]
        out += _facts(items) if items else [EMPTY_TOPIC, ""]

    #: 표에 없는 topic 으로 온 것. **버리지 않는다** — 라우팅 표를 고치면 생긴다
    rest = [s for s in node.statements if s.topic not in order]
    return out + _facts(rest)


def _facts(items: tuple[Statement, ...] | list[Statement]) -> list[str]:
    out: list[str] = []
    for s in items:
        out += [s.text, ""]
        where = " · ".join(str(e) for e in s.evidence)
        out.append(f"> 근거 {len(s.evidence)} — {where}")
        out.append("")
    return out


def _sources(evidence: list[Evidence]) -> list[str]:
    """이 장을 만든 파일들. **어느 파일을 지우면 무엇이 사라지는지** 보이는 자리다."""
    files = sorted({e.filename for e in evidence})
    return ["## 근거 파일", "", *[f"- {f}" for f in files], ""]


def bundle(nodes: list[NodeView]) -> str:
    """전부를 한 파일로. 화면에서 통째로 보거나 복사할 때 쓴다.

    **F1-6(밖으로 꺼내기)이 아니다.** 저기는 자리마다 `.md` 파일 하나로 떨어져 옵시디언
    볼트가 되는 것이고, 여기는 한 덩어리다. 파일로 떨어뜨리는 것은 그 태스크에서 한다.
    """
    company = nodes[0].company_id if nodes else ""
    out = [f"# 사업 위키 — {company}", ""]
    for node in nodes:
        out.append(render(node))
        out.append("")
    return "\n".join(out).rstrip() + "\n"
