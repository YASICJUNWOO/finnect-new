"""추천 API — plan/17 T-0075.

**`DESIGN.md` §6.1 의 두 섹션 중 위쪽이다.** 아래쪽(전체 공고 · 마감 임박순)은
`/api/notices` 가 그대로 낸다.

여기서 잠그는 것 넷.

1. **적합도 숫자가 없다.** 응답 어디에도 점수가 없다(`DESIGN.md` §6)
2. **세 건까지다**(`SPEC.md` F4-1)
3. **판정을 안 돌린 것과 맞는 것이 없는 것을 가른다** — `computed`
4. **마감이 지난 것은 낸 뒤에 뺀다.** 판정은 어제 돌았어도 오늘 마감일 수 있다

Postgres 없이 돈다 — 필요한 표만 SQLite 에 만든다.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from finnect.api import service
from finnect.models import (
    Attachment,
    Base,
    FitVerdict,
    NoticeFit,
    NoticeFitEvidence,
    WikiFact,
)
from finnect.views import Notice

TODAY = dt.date(2026, 8, 20)
COMPANY = "c_api"
TABLES = [Notice, NoticeFit, NoticeFitEvidence, Attachment, WikiFact]


def _fit(i: int, ext: str, *, hit: bool, matched: int, reason: str = "이유예요") -> NoticeFit:
    return NoticeFit(
        id=i, company_id=COMPANY, source="bizinfo", external_id=ext,
        verdict=str(FitVerdict.MATCH), reason=reason, sector_hit=hit,
        matched=["k"] * matched,
    )


@pytest.fixture
def s():  # noqa: ANN201
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[t.__table__ for t in TABLES])
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with factory() as sess:
        for ext, title, end in [
            ("A", "분야 맞고 겹침 둘", dt.date(2026, 9, 30)),
            ("B", "분야 맞고 겹침 하나", dt.date(2026, 8, 25)),
            ("C", "분야 밀림", dt.date(2026, 8, 22)),
            ("D", "네 번째", None),
            ("E", "마감 지남", dt.date(2026, 8, 1)),
        ]:
            sess.add(Notice(source="bizinfo", external_id=ext, title=title, apply_end=end))
        sess.add_all([
            _fit(1, "A", hit=True, matched=2),
            _fit(2, "B", hit=True, matched=1),
            _fit(3, "C", hit=False, matched=3),
            _fit(4, "D", hit=True, matched=1),
            _fit(5, "E", hit=True, matched=9),
        ])
        # 근거. A 만 둘이다
        sess.add_all([
            NoticeFitEvidence(fit_id=1, fact_id=11),
            NoticeFitEvidence(fit_id=1, fact_id=12),
            NoticeFitEvidence(fit_id=2, fact_id=11),
        ])
        sess.commit()
        yield sess


def test_적합도_숫자가_없다(s) -> None:  # noqa: ANN001
    """`DESIGN.md` §6 — 92 와 74 의 차이를 설명할 눈금이 없다."""
    out = service.recommendations(s, COMPANY, today=TODAY)
    dumped = out.model_dump_json()
    for 금지 in ("score", "fit_score", "percent", "verdict", "matched", "sector_hit"):
        assert 금지 not in dumped


def test_세_건까지다(s) -> None:  # noqa: ANN001
    out = service.recommendations(s, COMPANY, today=TODAY)
    assert len(out.items) == service.TOP_N == 3


def test_분야_일치가_먼저_겹침이_다음_마감이_마지막(s) -> None:  # noqa: ANN001
    """`match/rank.py` 의 정렬과 같은 규칙이다."""
    out = service.recommendations(s, COMPANY, today=TODAY)
    assert [i.external_id for i in out.items] == ["A", "B", "D"]
    # 겹침이 셋인 C 가 밀린다 — 분야가 안 맞으면 앞에 못 온다
    assert "C" not in [i.external_id for i in out.items]


def test_마감_지난_것은_낸_뒤에_뺀다(s) -> None:  # noqa: ANN001
    """판정은 어제 돌았어도 오늘 마감일 수 있다."""
    out = service.recommendations(s, COMPANY, today=TODAY)
    assert "E" not in [i.external_id for i in out.items]


def test_근거_수를_함께_낸다(s) -> None:  # noqa: ANN001
    out = service.recommendations(s, COMPANY, today=TODAY)
    got = {i.external_id: i.evidence_count for i in out.items}
    assert got["A"] == 2
    assert got["B"] == 1
    assert got["D"] == 0


def test_이유가_비면_추천에_안_오른다(s) -> None:  # noqa: ANN001
    """이유 없는 점수는 근거가 없다(ADR-0013)."""
    for f in s.scalars(__import__("sqlalchemy").select(NoticeFit)):
        f.reason = ""
    s.commit()
    out = service.recommendations(s, COMPANY, today=TODAY)
    assert out.items == []
    assert out.computed is True  # 돌긴 돌았다


def test_판정을_안_돌리면_computed_가_거짓이다(s) -> None:  # noqa: ANN001
    """빈 목록과 다르다 — 화면이 "아직 없어요" 와 "맞는 것이 없어요" 를 다르게 말한다."""
    out = service.recommendations(s, "c_없는회사", today=TODAY)
    assert out.items == [] and out.computed is False


def test_이유가_있으면_애매도_오른다(s) -> None:  # noqa: ANN001
    """**등급이 아니라 이유로 거른다** (T-0076).

    ④ 분야가 살린 `애매` 도 근거가 `wiki_fact` 에 실제로 있다. `match/service.py` 의
    `rep.top` 과 같은 규칙이어야 한다 — **CLI 가 셋을 찍는데 화면이 비면 안 된다.**
    """
    for f in s.scalars(__import__("sqlalchemy").select(NoticeFit)):
        f.verdict = str(FitVerdict.MAYBE)
    s.commit()
    out = service.recommendations(s, COMPANY, today=TODAY)
    assert len(out.items) == 3
    assert out.computed is True


def test_이유가_없으면_등급과_무관하게_안_오른다(s) -> None:  # noqa: ANN001
    for f in s.scalars(__import__("sqlalchemy").select(NoticeFit)):
        f.reason = ""
    s.commit()
    out = service.recommendations(s, COMPANY, today=TODAY)
    assert out.items == []
    assert out.computed is True  # 돌긴 돌았다


def test_맞다가_애매보다_앞이다(s) -> None:  # noqa: ANN001
    """등급이 정렬의 맨 앞이다. **분야 일치보다 앞이다.**"""
    by = {f.external_id: f for f in s.scalars(__import__("sqlalchemy").select(NoticeFit))}
    for ext, f in by.items():
        # `D` 는 살아 있는 넷 중 원래 셋째다 (분야는 맞지만 겹침 하나 · 마감일 없음)
        f.verdict = str(FitVerdict.MATCH if ext == "D" else FitVerdict.MAYBE)
    s.commit()
    out = service.recommendations(s, COMPANY, today=TODAY)
    assert out.items[0].external_id == "D"
    assert [i.external_id for i in out.items] == ["D", "A", "B"]


def test_회사가_섞이지_않는다(s) -> None:  # noqa: ANN001
    """같은 공고에 회사마다 다른 이유가 앉는다 — 유니크 키가 `(회사, 출처, 공고)` 다."""
    s.add(NoticeFit(
        id=9, company_id="c_다른회사", source="bizinfo", external_id="A",
        verdict=str(FitVerdict.MATCH), reason="남의 이유", sector_hit=True,
        matched=["x"] * 9,
    ))
    s.commit()
    내것 = service.recommendations(s, COMPANY, today=TODAY)
    assert all(i.reason != "남의 이유" for i in 내것.items)
    남것 = service.recommendations(s, "c_다른회사", today=TODAY)
    assert [i.reason for i in 남것.items] == ["남의 이유"]
