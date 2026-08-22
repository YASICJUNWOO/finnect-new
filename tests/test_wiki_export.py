"""자리 트리를 마크다운으로 — ADR-0058.

자리는 `spots.py` 의 마흔여섯이고 장은 **DB 의 노드에서** 만든다. 그래서 이 파일이
보는 것은 「표가 맞나」(그건 `test_wiki_markdown.py`)가 아니라 **「같은 DB 에서 항상
같은 글이 나오나」** 와 **기획 §5 파일 머리**다.

DB 를 안 쓴다 — `NodeView` 를 손으로 만들어 넣는다.
"""

from __future__ import annotations

import datetime as dt

from finnect.models import SourceType
from finnect.wiki import export, tree
from finnect.wiki.build import NodeView
from finnect.wiki.markdown import Evidence, Statement

E = Evidence("사업계획서.hwp", 3, "임직원 15명", "abc123def456")


def _node(path: str, *facts: Statement) -> NodeView:
    return NodeView(
        path=path,
        category=tree.category_of(path),
        name=tree.name_of(path),
        parent=tree.parent_of(path),
        facts=facts,
    )


def _nodes() -> list[NodeView]:
    """카테고리 둘에 잎 셋. **뼈대(빈 카테고리)도 같이 온다.**"""
    return [
        _node("Company"),
        _node(
            "Company/팀",
            Statement("개발 3명과 영업 2명이다.", (E,), updated_at=dt.date(2026, 8, 22),
                      as_of=dt.date(2026, 8, 31), grade="1차"),
        ),
        _node("Custom"),
        _node("Custom/특허"),
        _node(
            "Custom/특허/등록-10-2025-0114882",
            Statement("오프라인 재고 동기화 방법 및 장치.", (E,), grade="1차"),
        ),
    ]


def _pages() -> dict[str, export.Page]:
    return {p.path: p for p in export.render(_nodes(), "c_t")}


# ─────────────────────────────────────────────────────────────────
# 장을 내는 규칙
# ─────────────────────────────────────────────────────────────────


def test_사실이_붙은_노드만_장이_된다():
    """**빈 뼈대는 파일을 안 낸다**(ADR-0056 결정 4).

    그래프에는 점으로 서지만 내용이 없는 `.md` 를 만들면 볼트에 빈 파일이 쌓인다.
    """
    assert set(_pages()) == {"Company/팀", "Custom/특허/등록-10-2025-0114882"}


def test_폴더_노트라_경로_그대로에_md_를_붙인다():
    """**자식이 있어도 `.md` 다.** 잎만 파일로 하면 자식이 생기는 날 내용이 갈 곳을 잃는다."""
    assert export.file_of("Custom/특허") == "Custom/특허.md"
    assert export.file_of("Custom/특허/등록-1") == "Custom/특허/등록-1.md"


def test_자식이_있으면_프론트매터가_가리킨다():
    """폴더 노트가 자기 아래를 가리킨다. **경로가 곧 이름이라** 링크가 따로 필요 없다."""
    page = [p for p in export.render(_nodes(), "c_t")]
    kids = {p.path: p.children for p in page}
    assert kids["Custom/특허/등록-10-2025-0114882"] == ()


def test_장_하나가_사실과_근거를_같이_낸다():
    body = _pages()["Company/팀"].body
    assert "# 팀" in body
    assert "개발 3명과 영업 2명이다." in body
    assert "- 사업계획서.hwp" in body.split("## 근거 파일")[1]


def test_시각이_안_들어간다():
    """두 번 만들면 바이트가 같아야 한다. **`updated_at` 은 DB 값이라 이걸 안 깬다.**"""
    a = [p.body for p in export.render(_nodes(), "c_t")]
    b = [p.body for p in export.render(_nodes(), "c_t")]
    assert a == b
    assert not any("generated" in x for x in a)


# ─────────────────────────────────────────────────────────────────
# 기획 문서 §5 파일 머리
# ─────────────────────────────────────────────────────────────────


def test_파일_머리가_기획_5_모양이다():
    head = _pages()["Company/팀"].body.split("---")[1]
    for line in [
        "path: Company/팀",
        "title: 팀",
        "category: Company",
        "company: c_t",
        "grade: 1차",
        "source: 사업계획서.hwp",
        "source_path: c_t/ab/abc123def456",
        "base_date: 2026-08-31",
        "updated_at: 2026-08-22",
    ]:
        assert line in head, line


def test_사용자가_답한_사실은_실측이다():
    """ADR-0028 — 사용자 답변은 문서보다 세다. 등급도 그것을 말한다."""
    said = _node("Company/팀", Statement("직원 15명이에요.", (E,), SourceType.USER_STATED))
    assert export.grade_of(said) == export.GRADE_MEASURED
    assert export.grade_of(_node("Company")) == export.GRADE_UNKNOWN


def test_섞이면_가장_약한_등급이_이긴다():
    """**머리가 본문보다 세게 말하면 안 된다**(기획 §3-3 「근거가 약한 항이 보인다」).

    실측 하나와 추정 하나가 같이 있는 장을 `실측` 이라고 적으면 심사에서 그 장을
    통째로 믿게 된다.
    """
    mixed = _node(
        "Company/팀",
        Statement("직원 15명이에요.", (E,), SourceType.USER_STATED),
        Statement("2027년엔 30명 예상.", (E,), grade="가정"),
    )
    assert export.grade_of(mixed) == "가정"

    cited = _node(
        "Market/시장규모",
        Statement("우리 추정 3조.", (E,), grade="1차"),
        Statement("통계청 기준 2.8조.", (E,), grade="2차", source="통계청"),
    )
    assert export.grade_of(cited) == "2차"


def test_등급이_안_매겨진_사실은_1차로_본다():
    """옛 행과 스텁이 그렇다. **`미정` 으로 안 내린다** — 비었다는 뜻이라 거짓이 된다."""
    assert export.grade_of(_node("Company/팀", Statement("사실", (E,)))) == export.GRADE_PRIMARY
    assert export.GRADES == ("실측", "1차", "2차", "가정", "미정")


def test_외부_출처가_파일보다_앞에_오고_위치는_비어_있다():
    """**짝이 어긋나면 위치가 거짓말이 된다.** 기관에는 우리 저장소 경로가 없다."""
    page = _pages()["Company/팀"]
    assert page.sources == ("사업계획서.hwp",)
    assert page.source_paths == ("c_t/ab/abc123def456",)

    cited = export.render(
        [_node("Market/시장규모", Statement("2.8조.", (E,), grade="2차", source="통계청"))],
        "c_t",
    )[0]
    assert cited.sources == ("통계청", "사업계획서.hwp")
    assert cited.source_paths == ("", "c_t/ab/abc123def456")


# ─────────────────────────────────────────────────────────────────
# 묶음
# ─────────────────────────────────────────────────────────────────


def test_묶음이_폴더로_나뉜다():
    out = export.bundle(export.render(_nodes(), "c_t"), "c_t")
    assert out.startswith("# 사업 위키 — c_t")
    assert out.index("# 회사") < out.index("# 지식 재산")
    assert out.index("# 팀") < out.index("# 등록-10-2025-0114882")
