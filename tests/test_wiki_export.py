"""기획 트리로 내보내기 — ADR-0048 결정 4.

**뷰가 둘이라는 것이 여기서 검증된다.** 같은 `NodeView` 목록에서 궤도 뷰 열다섯 장과
트리 뷰 마흔일곱 장이 나오고, 둘 다 저장된 것이 아니라 만들어진 것이다.

DB 를 안 쓴다 — `NodeView` 를 손으로 만들어 넣는다.
"""

from __future__ import annotations

from finnect.wiki import export, topics
from finnect.wiki.markdown import Evidence, NodeView, Statement, Value

E = Evidence("사업계획서.hwp", 3, "임직원 15명")


def _nodes() -> list[NodeView]:
    """자리 둘만 채운 위키. 나머지는 비어 있다."""
    return [
        NodeView(
            key="team",
            label="팀 구성",
            kind="content",
            sector="팀과 계획",
            company_id="c_t",
            values=(Value("headcount", "직원 수", "15", None, "2026-08-31", "current", (E,)),),
            statements=(Statement("개발 3명과 영업 2명이다.", "team", (E,)),),
        ),
        NodeView(
            key="solution",
            label="솔루션과 기술",
            kind="content",
            sector="문제와 해결",
            company_id="c_t",
            values=(),
            statements=(
                Statement("실시간 매출 대시보드를 제공한다.", "service_feature", (E,)),
                Statement("출원번호 10-2025-0012345.", "patent", (E,)),
            ),
        ),
    ]


def test_기획_자리_마흔여섯에_우리가_하나_더했다():
    """**우리가 더한 자리를 기획 것으로 섞지 않는다.** `ours` 로 표가 난다."""
    plan = [s for s in export.TREE if not s.ours]
    ours = [s for s in export.TREE if s.ours]
    assert len(plan) == 46
    assert [s.path for s in ours] == ["Company/지역관계.md"]


def test_topic_전부가_자리를_갖는다():
    """**자리 없는 topic 이 있으면 내보내기가 사실을 조용히 버린다.**"""
    placed_values = {v for s in export.TREE for v in s.values}
    placed_events = {e for s in export.TREE for e in s.events}
    assert topics.VALUE_TOPICS - placed_values == set()
    assert topics.EVENT_TOPICS - placed_events == set()


def test_한_topic_이_두_자리에_안_간다():
    """같은 사실이 파일 둘에 실리면 어느 쪽이 정본인지 알 수 없다."""
    for topic in topics.EVENT_TOPICS:
        spots = [s.path for s in export.TREE if topic in s.events]
        assert len(spots) == 1, (topic, spots)


def test_빈_자리는_왜_비는지_적는다():
    """**«데이터 없음»으로 끝내지 않는다**(DESIGN.md §7-5)."""
    for spot in export.TREE:
        if not spot.filled:
            assert spot.gap, spot.path


def test_내보내는_경로에_중괄호가_안_남는다():
    for spot in export.TREE:
        assert "{" not in spot.file, spot.path
        assert spot.file.endswith(".md")


def test_파일_동적이_열둘이고_폴더만_동적이_다섯이다():
    """기획 문서 1장 3번이 센 «늘어나는 것»이 열둘이다. 폴더만 동적인 Product 다섯은 다르다."""
    plan = [s for s in export.TREE if not s.ours]
    assert sum(1 for s in plan if s.instanced) == 12
    assert sum(1 for s in plan if s.folded and not s.instanced) == 5


def test_접힌_자리는_접혔다고_적는다():
    """**조용히 접으면 트리를 지원한다는 말이 거짓이 된다.**"""
    pages = {p.spot.path: p for p in export.render(_nodes())}
    patent = pages["Custom/특허/{상태}-{번호}.md"]
    assert "collapsed: Custom/특허/{상태}-{번호}.md" in patent.body
    assert patent.spot.file == "Custom/특허/특허.md"
    #: 고정 자리에는 안 붙는다
    assert "collapsed:" not in pages["Company/비전.md"].body


def test_우리가_더한_자리는_표를_남긴다():
    pages = {p.spot.path: p for p in export.render(_nodes())}
    assert "added_by: finnect" in pages["Company/지역관계.md"].body


def test_한_궤도의_사실이_자리_여럿으로_갈린다():
    """`solution` 한 장에 섞여 있던 기능과 특허가 파일 둘이 된다. **이게 이 뷰의 이유다.**"""
    pages = {p.spot.path: p for p in export.render(_nodes())}
    feature = pages["Product/{서비스명}/기능.md"].body
    patent = pages["Custom/특허/{상태}-{번호}.md"].body
    assert "실시간 매출 대시보드를 제공한다." in feature
    assert "출원번호" not in feature
    assert "출원번호 10-2025-0012345." in patent
    assert "대시보드" not in patent


def test_값과_문장이_한_장에_같이_선다():
    """`Company/팀.md` 는 기획 문서가 프론트매터 + 본문으로 그린 그 자리다."""
    body = {p.spot.path: p.body for p in export.render(_nodes())}["Company/팀.md"]
    assert "# 팀" in body
    assert "## 직원 수" in body
    assert "**15명**" in body
    assert "개발 3명과 영업 2명이다." in body
    assert "- 사업계획서.hwp" in body.split("## 근거 파일")[1]


def test_안_채운_자리는_이유를_적고_근거_절을_안_만든다():
    body = {p.spot.path: p.body for p in export.render(_nodes())}["Plan/KPI.md"]
    assert "이 자리는 아직 안 채워요" in body
    assert "## 근거 파일" not in body


def test_채울_수_있는데_아직_빈_자리는_다르게_말한다():
    """«우리가 안 다룬다»와 «아직 안 올렸다»는 다른 말이다."""
    body = {p.spot.path: p.body for p in export.render(_nodes())}["Company/비전.md"]
    assert "아직 비어 있어요" in body


def test_시각이_안_들어간다():
    """궤도 뷰와 같은 규칙이다. 넣으면 바이트로 비교할 수 없다."""
    a = [p.body for p in export.render(_nodes())]
    b = [p.body for p in export.render(_nodes())]
    assert a == b
    assert not any("generated" in x for x in a)
