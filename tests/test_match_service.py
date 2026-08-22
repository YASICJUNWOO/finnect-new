"""배관이 끝까지 이어진다 (plan/17).

Postgres 없이 돈다 — 필요한 표만 SQLite 에 만든다. **LLM 은 가짜를 넣는다.**
여기서 보는 것은 뽑은 값이 좋은지가 아니라 **배관이 끝까지 이어지는가**다.

1. ① 정규화가 `notice_profile` 에 앉고 **`company_id` 가 없다**
2. 본문이 그대로면 안 부른다 (캐시)
3. ③ 자격이 지역으로 뺀다
4. ④ 분야가 해외진출을 민다
5. ⑤ 이유가 서고 `notice_fit_evidence` 에 `fact_id` 가 앉는다
6. **정규화가 없으면 판정하지 않고 추천만 빈다** — 키 없이도 화면이 산다
7. 회사가 둘이어도 ① 호출이 안 늘어난다
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from finnect.match import normalize as nz
from finnect.match import service
from finnect.models import (
    Base,
    BizinfoNotice,
    FitVerdict,
    KstartupNotice,
    NoticeFit,
    NoticeFitEvidence,
    NoticeProfile,
    WikiFact,
)
from finnect.views import Notice

TODAY = dt.date(2026, 8, 20)
COMPANY = "c_match"
TABLES = [
    Notice, BizinfoNotice, KstartupNotice, NoticeProfile, NoticeFit,
    NoticeFitEvidence, WikiFact,
]

#: 공고 셋. **지역·분야·취지가 서로 다르게 걸리도록 골랐다**
공고 = [
    # ① 성남 · 사업화 · 취지 겹침  → 추천 1위
    ("P1", "성남시 소상공인 디지털 전환 지원사업", "사업화지원",
     "☞ 지원대상 : 성남시 소재 창업 7년 이내 기업\n☞ 지원내용 : 사업화 자금 최대 5천만원",
     dt.date(2026, 9, 1)),
    # ② 성남 · 해외진출 · 취지 안 겹침  → ④가 민다
    ("P2", "성남시 수출기업 해외 전시회 참가 지원", "해외진출",
     "☞ 지원대상 : 성남시 소재 수출기업\n☞ 지원내용 : 해외 전시회 부스 지원",
     dt.date(2026, 8, 25)),
    # ③ 대구  → ③이 뺀다
    ("P3", "수성알파시티 기업 전용 5G 통신망 지원", "사업화지원",
     "☞ 지원대상 : 대구광역시 수성구 소재 기업\n☞ 지원내용 : 통신망 서비스",
     dt.date(2026, 8, 30)),
]


class 가짜정규화기:
    """제목을 보고 정해진 답을 준다. **앵커는 본문에서 떠 온다.**"""

    name = "llm/가짜"

    def __init__(self) -> None:
        self.dropped: list[tuple[str, str]] = []
        self.calls: list[str] = []

    def read(self, b: nz.NoticeBody):  # noqa: ANN201
        self.calls.append(b.external_id)
        표 = {
            "P1": (("성남시",), (), (), ("소상공인", "디지털전환"),
                   "지역 소상공인의 디지털 전환을 돕는다"),
            "P2": (("성남시",), (), (), ("수출", "전시회"), "수출기업의 해외 판로를 돕는다"),
            "P3": (("대구광역시",), (), (), ("통신망",), "입주기업 통신망을 지원한다"),
        }
        r, i, c, k, p = 표[b.external_id]
        return nz.Profile(regions=r, industries=i, conditions=c, keywords=k, purpose=p)


def _fact(**kw) -> WikiFact:  # noqa: ANN003
    kw.setdefault("company_id", COMPANY)
    kw.setdefault("topic", "solution")
    kw.setdefault("extractor", "stub/v1")
    kw.setdefault("dedupe_key", f"{kw['place']}|{kw.get('text', '')[:20]}")
    return WikiFact(**kw)


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[t.__table__ for t in TABLES])
    monkeypatch.setattr(service, "engine", engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    with factory() as s:
        for ext, title, cat, summary, end in 공고:
            s.add(Notice(source="bizinfo", external_id=ext, title=title, apply_end=end))
            s.add(BizinfoNotice(
                pblancId=ext, pblancNm=title, bsnsSumryCn=summary,
                pldirSportRealmMlsfcCodeNm=cat, pldirSportRealmLclasCodeNm="창업",
                # **조회수가 `content_hash` 재료다.** 캐시를 거기 걸면 안 되는 이유다
                inqireCo="100", content_hash=f"h{ext}",
            ))
        # 마감이 지난 공고 — **후보에 안 든다**
        s.add(Notice(source="bizinfo", external_id="OLD", title="지난 것",
                     apply_end=dt.date(2026, 1, 1)))
        s.add(BizinfoNotice(pblancId="OLD", pblancNm="지난 것", bsnsSumryCn="☞ 가",
                            content_hash="hOLD"))

        s.add_all([
            _fact(place_kind="value", place="location", status="current",
                  value="경기도 성남시 분당구 판교로 255", text="소재지",
                  as_of=dt.date(2026, 1, 31)),
            _fact(place_kind="value", place="founded_on", status="current",
                  value="2024-03-11", text="개업"),
            _fact(place_kind="event", place="identity",
                  text="소상공인용 재고관리 소프트웨어"),
            _fact(place_kind="event", place="roadmap",
                  text="2단계 경기 남부 지역 영업망 구축, 유료 전환 매장 300곳"),
            _fact(place_kind="event", place="finance",
                  text="정부지원금 집행 계획 합계 7,000만원 — 인건비 3,600만원"),
        ])
        s.commit()
    return factory


# ─────────────────────────── ① 정규화 ───────────────────────────


def test_정규화가_앉고_회사와_무관하다(db) -> None:  # noqa: ANN001
    n = 가짜정규화기()
    rep = service.normalize(today=TODAY, normalizer=n)
    assert rep.seen == 3  # 마감 지난 `OLD` 는 후보에 안 든다
    assert rep.written == 3
    with db() as s:
        rows = list(s.scalars(select(NoticeProfile)))
    assert len(rows) == 3
    assert not hasattr(rows[0], "company_id")
    assert rows[0].decided_by == "llm/가짜"


def test_본문이_그대로면_안_부른다(db) -> None:  # noqa: ANN001
    n = 가짜정규화기()
    service.normalize(today=TODAY, normalizer=n)
    n2 = 가짜정규화기()
    rep = service.normalize(today=TODAY, normalizer=n2)
    assert rep.cached == 3
    assert n2.calls == []


def test_redo_면_다시_부른다(db) -> None:  # noqa: ANN001
    service.normalize(today=TODAY, normalizer=가짜정규화기())
    n = 가짜정규화기()
    rep = service.normalize(today=TODAY, normalizer=n, redo=True)
    assert rep.written == 3 and len(n.calls) == 3


def test_dry_는_저장하지_않는다(db, capsys) -> None:  # noqa: ANN001
    service.normalize(today=TODAY, normalizer=가짜정규화기(), dry=True)
    with db() as s:
        assert s.scalar(select(func.count()).select_from(NoticeProfile)) == 0
    assert "성남시" in capsys.readouterr().out


def test_공고_하나가_실패해도_나머지가_남는다(db) -> None:  # noqa: ANN001
    class 하나만터짐(가짜정규화기):
        def read(self, b):  # noqa: ANN001, ANN201
            if b.external_id == "P2":
                raise RuntimeError("타임아웃")
            return super().read(b)

    rep = service.normalize(today=TODAY, normalizer=하나만터짐())
    assert rep.written == 2
    assert rep.failed and rep.failed[0][0] == "bizinfo:P2"


# ─────────────────────────── ③④⑤ 대조 ───────────────────────────


def test_대조가_끝까지_이어진다(db) -> None:  # noqa: ANN001
    service.normalize(today=TODAY, normalizer=가짜정규화기())
    rep = service.run(COMPANY, today=TODAY)

    assert rep.candidates == 3
    assert rep.failed_eligibility == 1  # P3 대구
    assert rep.match == 1  # P1
    assert rep.miss == 1  # P2 — 취지도 분야도 안 맞는다
    assert rep.sector_hit == 1  # P1 사업화. P2 해외진출은 밀린다

    assert len(rep.top) == 1
    assert "디지털 전환" in rep.top[0][1]
    # **겹친 키워드만 문장에 온다.** `디지털전환` 은 노드에 없어서 빠진다 —
    # 공고 취지를 되풀이하지 않고 우리 위키에 실제로 있는 것만 말한다
    assert rep.top[0][2] == "소상공인이 주제예요. 소상공인용 재고관리 소프트웨어"


def test_근거에_fact_id_가_앉는다(db) -> None:  # noqa: ANN001
    """**나중에 붙일 수 없다**(ADR-0014)."""
    service.normalize(today=TODAY, normalizer=가짜정규화기())
    service.run(COMPANY, today=TODAY)
    with db() as s:
        fit = s.scalars(
            select(NoticeFit).where(NoticeFit.verdict == str(FitVerdict.MATCH))
        ).first()
        assert fit is not None
        ev = list(s.scalars(select(NoticeFitEvidence).where(NoticeFitEvidence.fit_id == fit.id)))
        assert ev
        facts = set(s.scalars(select(WikiFact.id)))
        assert {e.fact_id for e in ev} <= facts


def test_이유_없는_적합도가_저장되지_않는다(db) -> None:  # noqa: ANN001
    service.normalize(today=TODAY, normalizer=가짜정규화기())
    service.run(COMPANY, today=TODAY)
    with db() as s:
        for f in s.scalars(select(NoticeFit)):
            if f.verdict == str(FitVerdict.MATCH):
                assert f.reason
            # `아니다` 와 `확인 필요` 는 아예 안 앉는다
            assert f.verdict in (str(FitVerdict.MATCH), str(FitVerdict.MAYBE))


def test_다시_돌리면_행이_안_쌓인다(db) -> None:  # noqa: ANN001
    service.normalize(today=TODAY, normalizer=가짜정규화기())
    service.run(COMPANY, today=TODAY)
    service.run(COMPANY, today=TODAY)
    with db() as s:
        assert s.scalar(select(func.count()).select_from(NoticeFit)) == 1


# ─────────────────────────── 키가 없을 때 ───────────────────────────


def test_정규화가_없으면_판정하지_않고_추천만_빈다(db) -> None:  # noqa: ANN001
    """**키 없이도 화면이 산다**(`DESIGN.md` §6.1 이 목록을 둘로 나눈 이유)."""
    rep = service.run(COMPANY, today=TODAY)
    assert rep.candidates == 3
    assert rep.no_profile == 3
    assert rep.failed_eligibility == 0  # 아무것도 안 뺀다
    assert rep.top == []


def test_확인_필요를_아니다로_안_읽는다(db) -> None:  # noqa: ANN001
    rep = service.run(COMPANY, today=TODAY)
    assert rep.miss == 0  # 봤는데 안 맞는 것이 아니다
    assert rep.no_profile == 3  # 아직 안 본 것이다


# ─────────────────────────── 회사가 늘 때 ───────────────────────────


def test_회사가_늘어도_정규화_호출이_안_늘어난다(db) -> None:  # noqa: ANN001
    """**이 계획의 원칙 하나가 이 테스트다.**"""
    n = 가짜정규화기()
    service.normalize(today=TODAY, normalizer=n)
    첫호출 = len(n.calls)

    with db() as s:
        s.add(WikiFact(
            company_id="c_other", place_kind="event", place="identity",
            topic="identity", text="소상공인용 배달 대행 서비스",
            extractor="stub/v1", dedupe_key="event|identity|other",
        ))
        s.commit()
    service.run(COMPANY, today=TODAY)
    service.run("c_other", today=TODAY)

    n2 = 가짜정규화기()
    service.normalize(today=TODAY, normalizer=n2)
    assert 첫호출 == 3
    assert n2.calls == []  # 회사가 둘이어도 0회다


def test_회사마다_다른_추천이_나온다(db) -> None:  # noqa: ANN001
    service.normalize(today=TODAY, normalizer=가짜정규화기())
    with db() as s:
        s.add_all([
            WikiFact(company_id="c_daegu", place_kind="value", place="location",
                     status="current", value="대구광역시 수성구 알파시티1로",
                     topic="company_profile", text="소재지", extractor="stub/v1",
                     dedupe_key="location|대구", as_of=dt.date(2026, 1, 31)),
            WikiFact(company_id="c_daegu", place_kind="event", place="identity",
                     topic="identity", text="기업 전용 통신망 구축 서비스",
                     extractor="stub/v1", dedupe_key="event|identity|daegu"),
        ])
        s.commit()

    성남 = service.run(COMPANY, today=TODAY)
    대구 = service.run("c_daegu", today=TODAY)
    assert 성남.failed_eligibility == 1  # 대구 공고를 뺀다
    assert 대구.failed_eligibility == 2  # 성남 공고 둘을 뺀다
    assert 대구.top and "통신망" in 대구.top[0][1]


# ─────────────────────────── 목록으로 좁히기 ───────────────────────────


def test_only_가_후보를_좁힌다(db) -> None:  # noqa: ANN001
    """`attach --only` 와 같은 방식이다 — 이쪽은 목록을 누가 만들었는지 모른다."""
    service.normalize(today=TODAY, normalizer=가짜정규화기())
    rep = service.run(COMPANY, only={"P1"}, today=TODAY)
    assert rep.candidates == 1


def test_only_가_정규화도_좁힌다(db) -> None:  # noqa: ANN001
    n = 가짜정규화기()
    rep = service.normalize(today=TODAY, normalizer=n, only={"P1", "P2"})
    assert rep.seen == 2 and sorted(n.calls) == ["P1", "P2"]


# ─────────────────────── 병렬 (T-0070) ───────────────────────


def test_병렬과_순차의_결과가_같다(db) -> None:  # noqa: ANN001
    """저장 순서가 답을 바꾸지 않는다."""
    service.normalize(today=TODAY, normalizer=가짜정규화기(), workers=1)
    with db() as s:
        순차 = {
            (p.external_id, tuple(p.regions), tuple(p.keywords))
            for p in s.scalars(select(NoticeProfile))
        }
    service.normalize(today=TODAY, normalizer=가짜정규화기(), workers=8, redo=True)
    with db() as s:
        병렬 = {
            (p.external_id, tuple(p.regions), tuple(p.keywords))
            for p in s.scalars(select(NoticeProfile))
        }
    assert 순차 == 병렬


def test_병렬에서도_하나만_실패한다(db) -> None:  # noqa: ANN001
    class 하나만터짐(가짜정규화기):
        def read(self, b):  # noqa: ANN001, ANN201
            if b.external_id == "P2":
                raise RuntimeError("타임아웃")
            return super().read(b)

    rep = service.normalize(today=TODAY, normalizer=하나만터짐(), workers=8)
    assert rep.written == 2
    assert [f[0] for f in rep.failed] == ["bizinfo:P2"]


def test_워커가_하나면_순차다(db) -> None:  # noqa: ANN001
    n = 가짜정규화기()
    service.normalize(today=TODAY, normalizer=n, workers=1)
    assert n.calls == ["P1", "P2", "P3"]
