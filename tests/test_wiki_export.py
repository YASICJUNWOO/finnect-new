"""기획 폴더 트리 — ADR-0052 · plan/20.

**이제 위키의 유일한 뷰다.** 2026-08-22 까지는 궤도 15장이 화면이었고 이 트리는
`--export` 뒤에만 있었다([ADR-0052](../docs/adr/0052-위키-화면을-기획-폴더-트리로-바꾼다.md)가
[ADR-0048](../docs/adr/0048-노드-층을-없애고-topic-을-orbit-에-직접-매단다.md) 결정 4 를 대체).

DB 를 안 쓴다 — `NodeView` 를 손으로 만들어 넣는다.
"""

from __future__ import annotations

import datetime as dt

from finnect.models import SourceType
from finnect.wiki import export, topics
from finnect.wiki.markdown import Evidence, NodeView, Statement, Value

E = Evidence("사업계획서.hwp", 3, "임직원 15명", "abc123def456")


def _nodes() -> list[NodeView]:
    """자리 둘만 채운 위키. 나머지는 비어 있다."""
    return [
        NodeView(
            key="team",
            label="팀 구성",
            kind="content",
            company_id="c_t",
            values=(
                Value(
                    "headcount",
                    "직원 수",
                    "15",
                    None,
                    "2026-08-31",
                    "current",
                    (E,),
                    updated_at=dt.date(2026, 8, 22),
                ),
            ),
            statements=(Statement("개발 3명과 영업 2명이다.", "team", (E,)),),
        ),
        NodeView(
            key="solution",
            label="솔루션과 기술",
            kind="content",
            company_id="c_t",
            values=(),
            statements=(
                Statement("실시간 매출 대시보드를 제공한다.", "service_feature", (E,)),
                Statement("출원번호 10-2025-0012345.", "patent", (E,)),
            ),
        ),
    ]


def _pages() -> dict[str, export.Page]:
    return {p.spot.path: p for p in export.render(_nodes())}


# ─────────────────────────────────────────────────────────────────
# 자리 표
# ─────────────────────────────────────────────────────────────────


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


# ─────────────────────────────────────────────────────────────────
# 폴더 열 — ADR-0052 결정 3
# ─────────────────────────────────────────────────────────────────


def test_폴더가_열이고_자리마다_제_폴더가_있다():
    """`sector` 여섯을 대신하는 묶음이다.

    **자리가 모르는 폴더에 앉으면 화면이 그 자리를 잃는다.**
    """
    assert len(export.FOLDERS) == 10
    assert {s.folder for s in export.TREE} == set(export.FOLDERS)


def test_폴더_순서가_기획_문서_2장_순서다():
    """**표가 순서를 정하고 데이터가 정하지 않는다.** 자리가 폴더별로 뭉쳐 있어야 한다."""
    seen: list[str] = []
    for spot in export.TREE:
        if not seen or seen[-1] != spot.folder:
            seen.append(spot.folder)
    assert seen == list(export.FOLDERS)


def test_폴더_이름이_자리_제목과_안_겹친다():
    """겹치면 `# 경쟁 상대` 밑에 `## 경쟁사` 가 서서 DESIGN.md §10 을 어긴다.

    `TOPIC_LABELS` 를 orbit 라벨과 안 겹치게 고른 것과 같은 규율이다.
    """
    assert set(export.FOLDERS.values()) & {s.title for s in export.TREE} == set()


def test_자리_마흔일곱에_스물여섯이_닿는다():
    """**궤도 열다섯은 15/15 였다.** 감춰져 있던 것이 드러나는 것이지 나빠진 것이 아니다."""
    assert len(export.TREE) == 47
    assert sum(1 for s in export.TREE if s.filled) == 26


# ─────────────────────────────────────────────────────────────────
# 장 한 장
# ─────────────────────────────────────────────────────────────────


def test_접힌_자리는_접혔다고_적는다():
    """**조용히 접으면 트리를 지원한다는 말이 거짓이 된다.**"""
    pages = _pages()
    patent = pages["Custom/특허/{상태}-{번호}.md"]
    assert "collapsed: Custom/특허/{상태}-{번호}.md" in patent.body
    assert patent.spot.file == "Custom/특허/특허.md"
    #: 고정 자리에는 안 붙는다
    assert "collapsed:" not in pages["Company/비전.md"].body


def test_우리가_더한_자리는_표를_남긴다():
    assert "added_by: finnect" in _pages()["Company/지역관계.md"].body


def test_한_저장_묶음의_사실이_자리_여럿으로_갈린다():
    """`solution` 한 장에 섞여 있던 기능과 특허가 파일 둘이 된다. **이게 이 뷰의 이유다.**"""
    pages = _pages()
    feature = pages["Product/{서비스명}/기능.md"].body
    patent = pages["Custom/특허/{상태}-{번호}.md"].body
    assert "실시간 매출 대시보드를 제공한다." in feature
    assert "출원번호" not in feature
    assert "출원번호 10-2025-0012345." in patent
    assert "대시보드" not in patent


def test_값과_문장이_한_장에_같이_선다():
    """`Company/팀.md` 는 기획 문서가 프론트매터 + 본문으로 그린 그 자리다."""
    body = _pages()["Company/팀.md"].body
    assert "# 팀" in body
    assert "## 직원 수" in body
    assert "**15명**" in body
    assert "개발 3명과 영업 2명이다." in body
    assert "- 사업계획서.hwp" in body.split("## 근거 파일")[1]


def test_event_topic_이_둘_이상인_자리만_절을_세운다():
    """`# 매출` 밑의 `## 매출 실적` 은 DESIGN.md §10 을 어긴다(ADR-0048 결정 5)."""
    revenue = [s for s in export.TREE if s.path == "Financial/매출.md"][0]
    assert len(revenue.events) == 1
    #: 값 절(`## 직원 수`)은 서지만 topic 절은 안 선다 — event topic 이 `team` 하나다
    team = _pages()["Company/팀.md"].body.split("## 근거 파일")[0]
    assert "## 구성원" not in team
    assert "## 직원 수" in team


def test_안_채운_자리는_이유를_적고_근거_절을_안_만든다():
    body = _pages()["Plan/KPI.md"].body
    assert "이 자리는 아직 안 채워요" in body
    assert "## 근거 파일" not in body


def test_채울_수_있는데_아직_빈_자리는_다르게_말한다():
    """«우리가 안 다룬다»와 «아직 안 올렸다»는 다른 말이다."""
    assert "아직 비어 있어요" in _pages()["Company/비전.md"].body


def test_시각이_안_들어간다():
    """두 번 만들면 바이트가 같아야 한다. **`updated_at` 은 DB 값이라 이걸 안 깬다.**"""
    a = [p.body for p in export.render(_nodes())]
    b = [p.body for p in export.render(_nodes())]
    assert a == b
    assert not any("generated" in x for x in a)


# ─────────────────────────────────────────────────────────────────
# 기획 문서 §5 파일 머리 — ADR-0052 결정 4
# ─────────────────────────────────────────────────────────────────


def test_파일_머리가_기획_5_모양이다():
    head = _pages()["Company/팀.md"].body.split("---")[1]
    for line in [
        "path: Company/팀.md",
        "title: 팀",
        "company: c_t",
        "grade: 1차",
        "source: 사업계획서.hwp",
        "source_path: c_t/ab/abc123def456",
        "base_date: 2026-08-31",
        "updated_at: 2026-08-22",
    ]:
        assert line in head, line


def test_빈_자리는_등급이_미정이고_출처_줄이_없다():
    """**없는 출처를 지어내지 않는다.** 줄 자체가 안 나온다."""
    body = _pages()["Company/비전.md"].body
    assert "grade: 미정" in body
    assert "source:" not in body
    assert "base_date:" not in body


def test_사용자가_답한_값은_실측이다():
    """ADR-0028 — 사용자 답변은 문서보다 세다. 등급도 그것을 말한다."""
    v = Value("headcount", "직원 수", "15", None, None, "current", (E,), SourceType.USER_STATED)
    assert export.grade_of([v], []) == export.GRADE_MEASURED
    #: 하나라도 문서에서 왔으면 1차다 — **더 센 등급을 섞어서 올리지 않는다**
    doc = Value("headcount", "직원 수", "9", None, None, "current", (E,))
    assert export.grade_of([v, doc], []) == export.GRADE_PRIMARY


def test_판정_못_하는_등급을_안_낸다():
    """**`2차`·`가정` 은 추출기가 출처를 판정하는 날 생긴다**(ADR-0052 결정 4).

    지금 내면 `Market/` 값이 전부 `2차` 로 보이고 기획이 이 필드를 만든 목적이 깨진다.
    """
    made = {p.grade for p in export.render(_nodes())}
    assert made <= {export.GRADE_MEASURED, export.GRADE_PRIMARY, export.GRADE_UNKNOWN}
    assert "2차" not in made and "가정" not in made
    #: 표에는 다섯이 그대로 있다 — 나중에 채울 자리를 지우지 않는다
    assert export.GRADES == ("실측", "1차", "2차", "가정", "미정")


def test_출처와_위치의_순서가_같다():
    """**짝이 어긋나면 위치가 거짓말이 된다.**"""
    page = _pages()["Company/팀.md"]
    assert len(page.sources) == len(page.source_paths)
    assert page.sources == ("사업계획서.hwp",)
    assert page.source_paths == ("c_t/ab/abc123def456",)


# ─────────────────────────────────────────────────────────────────
# 묶음
# ─────────────────────────────────────────────────────────────────


def test_묶음이_폴더로_나뉘고_자리_순서를_지킨다():
    out = export.bundle(export.render(_nodes()), "c_t")
    assert out.startswith("# 사업 위키 — c_t")
    assert out.index("# 회사") < out.index("# 제품") < out.index("# 기록")
    #: 빈 자리도 들어간다 — **무엇이 없는지가 이 문서의 절반이다**(ADR-0028)
    assert "# 창업 계기" in out
    assert out.index("# 팀") < out.index("# 기능")
