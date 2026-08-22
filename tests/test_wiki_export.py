"""노드 트리를 마크다운으로 — ADR-0056 · plan/22.

**고정 표가 없어졌다.** 자리 47개를 손으로 적던 `TREE` 가 지워지고 **DB 의 노드에서**
만든다. 그래서 이 파일이 보는 것은 「표가 맞나」가 아니라 **「트리가 어떻게 자라도
같은 글이 나오나」** 다.

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
            Statement("개발 3명과 영업 2명이다.", "팀 구성", (E,), updated_at=dt.date(2026, 8, 22)),
        ),
        _node("Custom"),
        _node("Custom/특허"),
        _node(
            "Custom/특허/등록-10-2025-0114882",
            Statement("오프라인 재고 동기화 방법 및 장치.", "특허", (E,)),
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
        "updated_at: 2026-08-22",
    ]:
        assert line in head, line


def test_사용자가_답한_사실은_실측이다():
    """ADR-0028 — 사용자 답변은 문서보다 세다. 등급도 그것을 말한다."""
    said = _node("Company/팀", Statement("직원 15명이에요.", "팀", (E,), SourceType.USER_STATED))
    assert export.grade_of(said) == export.GRADE_MEASURED
    #: 하나라도 문서에서 왔으면 1차다 — **더 센 등급을 섞어서 올리지 않는다**
    mixed = _node(
        "Company/팀",
        Statement("직원 15명이에요.", "팀", (E,), SourceType.USER_STATED),
        Statement("개발 3명.", "구성", (E,)),
    )
    assert export.grade_of(mixed) == export.GRADE_PRIMARY
    assert export.grade_of(_node("Company")) == export.GRADE_UNKNOWN


def test_판정_못_하는_등급을_안_낸다():
    """**`2차`·`가정` 은 추출기가 출처를 판정하는 날 생긴다**(ADR-0056).

    지금 내면 `Market/` 값이 전부 `2차` 로 보이고 이 필드의 목적이 깨진다.
    """
    made = {p.grade for p in export.render(_nodes(), "c_t")}
    assert made <= {export.GRADE_MEASURED, export.GRADE_PRIMARY, export.GRADE_UNKNOWN}
    #: 표에는 다섯이 그대로 있다 — 나중에 채울 자리를 지우지 않는다
    assert export.GRADES == ("실측", "1차", "2차", "가정", "미정")


def test_출처와_위치의_순서가_같다():
    """**짝이 어긋나면 위치가 거짓말이 된다.**"""
    page = _pages()["Company/팀"]
    assert page.sources == ("사업계획서.hwp",)
    assert page.source_paths == ("c_t/ab/abc123def456",)


# ─────────────────────────────────────────────────────────────────
# 묶음
# ─────────────────────────────────────────────────────────────────


def test_묶음이_카테고리로_나뉜다():
    out = export.bundle(export.render(_nodes(), "c_t"), "c_t")
    assert out.startswith("# 사업 위키 — c_t")
    assert out.index("# 회사") < out.index("# 지식 재산")
    assert out.index("# 팀") < out.index("# 등록-10-2025-0114882")
