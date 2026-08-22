"""회사 프로필 — 위키에서 읽기만 한다 (plan/17 T-0071).

**함정 셋을 픽스처로 박아 둔다.** 셋 다 `c_dasiro` 실값에서 나왔다.

1. `current` 가 **미래 시점**이다 (직원 수 15 · `as_of 2026-08-31`)
2. `funding` 에 **충돌**이 있다 (3억 · 2.8억, 둘 다 2025-09)
3. 업력·만 나이를 **저장하지 않고 기준일마다 계산한다**
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from finnect.match import profile as pf
from finnect.models import Base, WikiFact

COMPANY = "c_prof"
TABLES = [WikiFact]


def _fact(**kw) -> WikiFact:  # noqa: ANN003
    kw.setdefault("company_id", COMPANY)
    kw.setdefault("place_kind", "value")
    kw.setdefault("topic", "company_profile")
    kw.setdefault("text", "")
    kw.setdefault("extractor", "stub/v1")
    kw.setdefault("dedupe_key", f"{kw['place']}|{kw.get('value')}|{kw.get('as_of')}")
    return WikiFact(**kw)


@pytest.fixture
def s():  # noqa: ANN201
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[t.__table__ for t in TABLES])
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with factory() as sess:
        sess.add_all(
            [
                # 시점 없는 슬롯
                _fact(place="founded_on", value="2024-03-11", status="current"),
                _fact(place="ceo_birth", value="1992-07-04", status="current"),
                # 시계열. **current 가 미래다**
                _fact(place="headcount", value="7", as_of=dt.date(2025, 8, 22),
                      status="superseded"),
                _fact(place="headcount", value="10", as_of=dt.date(2026, 1, 31),
                      status="superseded"),
                _fact(place="headcount", value="15", as_of=dt.date(2026, 8, 31),
                      status="current"),
                # 소재지·업종
                _fact(place="location", value="경기도 성남시 분당구 판교로 255, 3층",
                      as_of=dt.date(2026, 1, 31), status="current"),
                _fact(place="industry", value="정보통신업",
                      as_of=dt.date(2026, 1, 31), status="current"),
                _fact(place="industry_item", value="응용 소프트웨어 개발 및 공급업",
                      as_of=dt.date(2026, 1, 31), status="current"),
                # 충돌
                _fact(place="gov_program", value="300000000", qualifier="시드",
                      as_of=dt.date(2025, 9, 30), status="conflict"),
                _fact(place="gov_program", value="280000000", qualifier="시드",
                      as_of=dt.date(2025, 9, 30), status="conflict"),
                # 서술 노드
                _fact(place_kind="event", place="roadmap", topic="roadmap",
                      text="2단계 2026. 07. ~ 12. — 경기 남부 지역 영업망 구축",
                      dedupe_key="event|roadmap|a"),
                _fact(place_kind="event", place="identity", topic="identity",
                      text="소상공인용 재고관리 소프트웨어", dedupe_key="event|identity|b"),
                # **자격 슬롯이 아닌 슬롯은 안 담는다**
                _fact(place="revenue", value="86400000",
                      as_of=dt.date(2025, 12, 31), status="current"),
            ]
        )
        sess.commit()
        yield sess


def test_미래_시점_값을_안_쓴다(s) -> None:  # noqa: ANN001
    """`current` 가 `2026-08-31` 인데 판정일이 `2026-08-20` 이다."""
    p = pf.load(s, COMPANY, on=dt.date(2026, 8, 20))
    assert p.value("headcount") == "10"  # 2026-01-31 것


def test_기준일이_지나면_그_값을_쓴다(s) -> None:  # noqa: ANN001
    p = pf.load(s, COMPANY, on=dt.date(2026, 9, 1))
    assert p.value("headcount") == "15"


def test_충돌_슬롯은_못_쓴다(s) -> None:  # noqa: ANN001
    """어느 값이 맞는지 코드가 모른다. 골라서 판정하면 그 선택이 안 남는다."""
    p = pf.load(s, COMPANY, on=dt.date(2026, 8, 20))
    assert p.value("gov_program") is None
    assert p.slots["gov_program"].conflicted is True


def test_자격_슬롯만_담는다(s) -> None:  # noqa: ANN001
    p = pf.load(s, COMPANY, on=dt.date(2026, 8, 20))
    assert "revenue" not in p.slots
    assert set(p.slots) <= set(pf.ELIGIBILITY_SLOTS)


def test_업력과_만_나이를_기준일마다_계산한다(s) -> None:  # noqa: ANN001
    """**저장하지 않는다** — 공고마다 기준일이 다르다(`wiki/topics.py`)."""
    p = pf.load(s, COMPANY)
    y1 = p.business_years(dt.date(2026, 8, 20))
    y2 = p.business_years(dt.date(2027, 3, 11))
    assert y1 is not None and 2.4 < y1 < 2.5
    assert y2 is not None and y2 > y1

    assert p.age(dt.date(2026, 7, 3)) == 33  # 생일 전날
    assert p.age(dt.date(2026, 7, 4)) == 34  # 생일


def test_need_text_는_로드맵_계열만_모은다(s) -> None:  # noqa: ANN001
    """사업 내용 전부를 넣으면 무슨 분야든 걸린다."""
    p = pf.load(s, COMPANY)
    t = p.need_text()
    assert "영업망" in t
    assert "재고관리" not in t  # identity 는 ④가 안 본다


def test_슬롯이_없으면_키가_없다(s) -> None:  # noqa: ANN001
    p = pf.load(s, COMPANY)
    assert "business_no" not in p.slots
    assert p.value("business_no") is None


def test_날짜_모양_셋을_다_읽는다() -> None:
    assert pf._date("2024-03-11") == dt.date(2024, 3, 11)
    assert pf._date("2024.03.11") == dt.date(2024, 3, 11)
    assert pf._date("20240311") == dt.date(2024, 3, 11)
    assert pf._date("2024년 3월") is None
