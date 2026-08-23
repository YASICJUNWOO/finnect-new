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
    AttachmentFile,
    Base,
    CompanyValue,
    FitVerdict,
    NoticeFit,
    NoticeFitEvidence,
    ValueEvidence,
    WikiFact,
    WikiNode,
)
from finnect.views import Notice

TODAY = dt.date(2026, 8, 20)
COMPANY = "c_api"
TABLES = [Notice, NoticeFit, NoticeFitEvidence, Attachment, AttachmentFile, WikiFact, WikiNode,
    CompanyValue, ValueEvidence]


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


class Test상세의_왜_맞는지:
    """공고 상세의 「왜 맞는지」 칸 (plan/21 T-0120).

    **자격은 안 낸다.** [ADR-0003](../docs/adr/0003-판별-비노출.md) 이 「판정은
    뒤에서 하고 화면은 결과만 준다」로 정했고, 자격 결과는 **목록에서 빼는 것**으로
    이미 나갔다. 여기 대조표를 두면 그 결정을 되돌린다.
    """

    def test_company_를_안_주면_안_판다(self, s) -> None:  # noqa: ANN001
        """**기본이 `None` 이다.** 로그인 없이 아무나 여는 공고 링크가 남의
        판정을 열면 안 된다."""
        got = service.get_notice(s, "bizinfo", "A", today=TODAY)
        assert got is not None
        assert got.fit is None

    def test_company_를_주면_이유가_온다(self, s) -> None:  # noqa: ANN001
        got = service.get_notice(s, "bizinfo", "A", today=TODAY, company_id=COMPANY)
        assert got.fit is not None
        assert got.fit.reason == "이유예요"
        assert got.fit.evidence_count == 2  # A 만 근거가 둘이다

    def test_판정이_없으면_None_이다(self, s) -> None:  # noqa: ANN001
        """**빈 객체를 주지 않는다** — 화면이 「이유가 비었다」와 「아직 안 봤다」를
        못 가른다."""
        got = service.get_notice(s, "bizinfo", "A", today=TODAY, company_id="c_없는회사")
        assert got.fit is None

    def test_이유가_없으면_안_낸다(self, s) -> None:  # noqa: ANN001
        """**근거 없는 등급은 안 내보낸다**(ADR-0013). `recommendations()` 와
        같은 조건이어야 한다 — CLI 가 셋을 찍는데 상세만 다르게 말하면 안 된다."""
        by = {f.external_id: f for f in s.scalars(__import__("sqlalchemy").select(NoticeFit))}
        by["A"].reason = ""
        s.commit()
        got = service.get_notice(s, "bizinfo", "A", today=TODAY, company_id=COMPANY)
        assert got.fit is None

    def test_자격을_안_낸다(self, s) -> None:  # noqa: ANN001
        """**ADR-0003 이 금지한 것이다.** 필드가 생기면 화면이 그것을 그린다."""
        got = service.get_notice(s, "bizinfo", "A", today=TODAY, company_id=COMPANY)
        fields = set(type(got.fit).model_fields)
        assert fields == {"verdict", "reason", "evidence_count"}


class Test데모_고정:
    """**데모용 고정 추천** — `DEMO_RECOMMENDATIONS=true` 일 때만 도는 길 (2026-08-23).

    판정을 안 거치고 두 건을 그대로 세우는 임시 경로다. 데모가 끝나면 플래그·상수와
    함께 이 클래스도 지운다.

    **위의 테스트 전부가 플래그 없이 돈다** — 기본이 꺼짐이라 원래 규칙 넷(숫자 없음 ·
    세 건 · `computed` · 마감)이 그대로 잠겨 있다. 데모를 상수 하나로 항상 켜 두면
    저것들이 한꺼번에 깨지고, 그때 테스트를 고치면 되돌릴 때 무엇이 맞았는지 모른다.

    여기서 잠그는 것 넷.

    1. **플래그가 꺼져 있으면 아무 일도 안 난다** — 상수가 있어도 원래 경로다
    2. **`notice_fit` 을 안 본다** — 회사 위키가 0행이어도 두 건이 선다
    3. **제목·마감일을 지어내지 않는다** — `notice` 뷰에서 읽는다
    4. **없는 공고는 빠진다** — 코퍼스를 다시 세우면 공고가 사라질 수 있다
    """

    #: `(출처, 공고번호, 이유, 근거 수)`. 픽스처의 A·B 를 쓴다
    PICKS = (("bizinfo", "B", "데모 이유예요", 4), ("bizinfo", "A", "또 다른 이유예요", 1))

    @staticmethod
    def _켠다(monkeypatch, picks) -> None:  # noqa: ANN001
        monkeypatch.setattr(service.settings, "demo_recommendations", True)
        monkeypatch.setattr(service, "DEMO_PICKS", picks)

    def test_플래그가_꺼져_있으면_원래_경로다(self, s, monkeypatch) -> None:  # noqa: ANN001
        """**레포 기본값이 이것이다.** 상수가 있어도 판정 결과가 나온다."""
        monkeypatch.setattr(service, "DEMO_PICKS", self.PICKS)
        out = service.recommendations(s, COMPANY, today=TODAY)
        assert [i.external_id for i in out.items] == ["A", "B", "D"]
        assert all(i.reason == "이유예요" for i in out.items)

    def test_플래그가_꺼져_있으면_위키가_없는_회사는_그대로_빈다(
        self, s, monkeypatch
    ) -> None:  # noqa: ANN001
        """데모가 새면 「아직 안 봤어요」가 사라진다 — 그 문장이 화면의 상태 셋 중 하나다."""
        monkeypatch.setattr(service, "DEMO_PICKS", self.PICKS)
        out = service.recommendations(s, "c_없는회사", today=TODAY)
        assert out.items == [] and out.computed is False

    def test_판정이_없어도_선다(self, s, monkeypatch) -> None:  # noqa: ANN001
        """**`notice_fit` 을 안 읽는다.** 회사 쪽이 통째로 비어 있어도 뜨는 것이 목적이다."""
        self._켠다(monkeypatch, self.PICKS)
        out = service.recommendations(s, "c_위키가_없는회사", today=TODAY)
        assert [i.external_id for i in out.items] == ["B", "A"]
        assert out.computed is True

    def test_적힌_순서_그대로다(self, s, monkeypatch) -> None:  # noqa: ANN001
        """정렬을 안 한다 — 상수에 적은 순서가 화면 순서다."""
        self._켠다(monkeypatch, self.PICKS[::-1])
        out = service.recommendations(s, COMPANY, today=TODAY)
        assert [i.external_id for i in out.items] == ["A", "B"]

    def test_이유와_근거_수는_상수의_것이다(self, s, monkeypatch) -> None:  # noqa: ANN001
        self._켠다(monkeypatch, self.PICKS)
        out = service.recommendations(s, COMPANY, today=TODAY)
        got = {i.external_id: (i.reason, i.evidence_count) for i in out.items}
        assert got["B"] == ("데모 이유예요", 4)
        # 픽스처의 A 는 `notice_fit` 에 근거가 둘인데 **그것을 안 본다**
        assert got["A"] == ("또 다른 이유예요", 1)

    def test_제목과_마감일은_notice_에서_읽는다(self, s, monkeypatch) -> None:  # noqa: ANN001
        """넷까지 지어내면 화면이 말하는 마감일이 상세와 어긋난다."""
        self._켠다(monkeypatch, self.PICKS)
        out = service.recommendations(s, COMPANY, today=TODAY)
        got = {i.external_id: i for i in out.items}
        assert got["A"].title == "분야 맞고 겹침 둘"
        assert got["A"].apply_end == dt.date(2026, 9, 30)

    def test_마감이_지나도_뺀다(self, s, monkeypatch) -> None:  # noqa: ANN001
        """**진짜 경로와 반대다.** 데모는 날짜가 지나도 그 자리가 서야 한다 —
        `178697` 이 오늘 마감이라 하루만 지나도 화면이 도로 빈다."""
        self._켠다(monkeypatch, (("bizinfo", "E", "마감 지난 것", 1),))
        out = service.recommendations(s, COMPANY, today=TODAY)
        assert [i.external_id for i in out.items] == ["E"]

    def test_없는_공고는_빠진다(self, s, monkeypatch) -> None:  # noqa: ANN001
        """**지어내지 않는다.** 기업마당 공고는 마감되면 API 에서 사라진다."""
        self._켠다(monkeypatch, (("bizinfo", "없는번호", "이유", 1), self.PICKS[1]))
        out = service.recommendations(s, COMPANY, today=TODAY)
        assert [i.external_id for i in out.items] == ["A"]

    def test_상세도_같은_문장을_낸다(self, s, monkeypatch) -> None:  # noqa: ANN001
        """**카드를 눌러 들어간 자리다.** 두 화면이 다르게 말하면 다른 판정으로 읽힌다.

        픽스처의 `B` 는 `notice_fit` 에 「이유예요」가 앉아 있는데 **그것을 덮는다** —
        데모 경로는 `notice_fit` 을 아예 안 본다.
        """
        self._켠다(monkeypatch, self.PICKS)
        추천 = service.recommendations(s, COMPANY, today=TODAY)
        목록 = {i.external_id: i.reason for i in 추천.items}
        got = service.get_notice(s, "bizinfo", "B", today=TODAY, company_id=COMPANY)
        assert got.fit is not None
        assert got.fit.reason == 목록["B"] == "데모 이유예요"
        assert got.fit.evidence_count == 4

    def test_상세는_표_밖_공고를_안_건드린다(self, s, monkeypatch) -> None:  # noqa: ANN001
        """**데모가 판정을 가리지 않는다.** `C` 는 표에 없으니 진짜 `notice_fit` 이 온다."""
        self._켠다(monkeypatch, self.PICKS)
        got = service.get_notice(s, "bizinfo", "C", today=TODAY, company_id=COMPANY)
        assert got.fit is not None
        assert got.fit.reason == "이유예요"

    def test_상세도_플래그가_꺼져_있으면_원래_경로다(self, s, monkeypatch) -> None:  # noqa: ANN001
        monkeypatch.setattr(service, "DEMO_PICKS", self.PICKS)
        got = service.get_notice(s, "bizinfo", "B", today=TODAY, company_id=COMPANY)
        assert got.fit.reason == "이유예요"
        assert got.fit.evidence_count == 1
