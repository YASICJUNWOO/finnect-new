"""초안이 끝까지 선다 (plan/16 T-0063 ~ T-0068).

Postgres 없이 돈다 — 필요한 표만 SQLite 에 만든다. **LLM 은 가짜를 넣는다.**
문장이 좋은지는 사람이 읽어야 하고, 여기서 보는 것은 **배관이 끝까지 이어지는가**다.

1. 양식을 읽어 `item_need` 와 `item_overlap` 이 선다 (T-0063)
2. 겹침 쌍에서 배분이 갈리고 그 결과가 `draft.allotment` 에 남는다 (T-0064)
3. 문단마다 `chunk_id` 와 `fact_id` 가 저장된다 (T-0065 · F6-13)
4. 못 채운 자리가 `draft_item.missing` 에 남는다 (F6-6)
5. **항목 하나가 실패해도 나머지가 남는다** (ADR-0015)
"""

from __future__ import annotations

import re

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

from finnect.draft import allot as al
from finnect.draft import dedupe as dd
from finnect.draft import needs as nd
from finnect.draft import service
from finnect.draft import write as wr
from finnect.models import (
    Attachment,
    AttachmentFile,
    Base,
    Chunk,
    Document,
    DocumentItem,
    DocumentKind,
    Draft,
    DraftEvidence,
    DraftItem,
    DraftItemStatus,
    ItemNeed,
    ItemOverlap,
    ParseStatus,
    UserFile,
    WikiEvidence,
    WikiFact,
)
from finnect.views import Notice

COMPANY = "c_draft"
SHA = "d" * 64
NOTICE = "PBLN-000"
TABLES = [
    Attachment, AttachmentFile, Document, DocumentItem, ItemNeed, ItemOverlap,
    Draft, DraftItem, DraftEvidence, WikiFact, WikiEvidence, Chunk, UserFile,
    # Postgres 에서는 뷰지만 매핑된 클래스라 SQLite 에서는 표로 만든다.
    # **구멍 1 이 이 표를 읽는다** — 없으면 공고 데이터가 재료에 안 들어간다
    Notice,
]


class 가짜클라이언트:
    model = "gpt-5.6-luna"

    def __init__(self, out: dict) -> None:
        self._out = out
        self.calls: list[dict] = []

    def json(self, **kw) -> dict:  # noqa: ANN003
        self.calls.append(kw)
        return self._out


class 받은대로쓰는집필기(가짜클라이언트):
    """**받은 사실을 그대로 인용한다.** 고정 응답을 쓰면 항목마다 배분이 다른데
    답이 같아서, `근거 없는 문단` 으로 전부 버려진다 — 배관을 못 본다."""

    def json(self, **kw) -> dict:  # noqa: ANN003
        self.calls.append(kw)
        got = re.findall(r"^#(\d+) \[\w+\](?: \([^)]*\))? (.+)$", kw["user"], re.M)
        return {"paragraphs": [{"text": f"{t}.", "facts": [int(i)]} for i, t in got]}


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[t.__table__ for t in TABLES])
    monkeypatch.setattr(service, "engine", engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    with factory() as s:
        # **id 를 손으로 준다.** 이 넷은 `BigInteger` 기본키라 SQLite 가 자동증가를
        # 안 시킨다(`_PK` 변형을 쓰는 표만 된다). 배포 DB 는 Postgres 라 상관없다
        s.add(Notice(
            source="bizinfo", external_id=NOTICE, title="2026년 철강 위기극복 지원사업",
            organization="포항시", supervisor="경상북도", category="기술",
            apply_period_raw="2026-08-01 ~ 2026-09-30",
            summary="지원금액은 기업당 최대 5,000만원이다. 접수는 온라인으로만 받는다.",
        ))
        s.add(Attachment(id=1, source="bizinfo", external_id=NOTICE, url="u1",
                         position=0, kind="file", filename="신청서식.hwp", ext="hwp"))
        s.add(AttachmentFile(id=1, url="u1", source="bizinfo", sha256=SHA,
                             fetch_status="ok", parse_status=str(ParseStatus.OK)))
        doc = Document(
            id=1, sha256=SHA, seq=1, title="[붙임2] 사업계획서",
            kind=str(DocumentKind.NARRATIVE), char_start=0, char_end=500,
            decided_by="llm/gpt-5.6-luna",
        )
        s.add(doc)
        s.flush()
        for i, (no, title, ins) in enumerate([
            ("2-1", "사업수행 배경 및 목적", "배경 및 필요성을 자세하게 기술"),
            ("2-2", "지원필요성", "애로사항 중심으로 필요성을 기술"),
            ("4", "팀 구성", "팀원 이력을 기재"),
        ]):
            s.add(DocumentItem(
                id=i + 1, document_id=doc.id, ordinal=i, number=no, title=title,
                instruction=ins, input_kind="narrative",
            ))

        f = UserFile(company_id=COMPANY, sha256="f" * 64, filename="회사소개서.pdf",
                     ext="pdf", byte_size=1, status="built")
        s.add(f)
        s.flush()
        c = Chunk(user_file_id=f.id, company_id=COMPANY, ordinal=0,
                  text="철강 경기로 수주가 끊겼다", chars=13, char_start=0, char_end=13)
        s.add(c)
        s.flush()
        for text, place in [("철강 경기로 수주가 끊겼다", "problem"),
                            ("설비 노후로 불량률이 올랐다", "problem")]:
            fact = WikiFact(company_id=COMPANY, place_kind="event", place=place,
                            dedupe_key=text, topic="customer_problem", text=text,
                            extractor="stub/v1")
            s.add(fact)
            s.flush()
            s.add(WikiEvidence(company_id=COMPANY, fact_id=fact.id, chunk_id=c.id,
                               user_file_id=f.id, quote=text))
        s.commit()
        yield factory, doc.id


def _read(db, out: dict, redo: bool = False):  # noqa: ANN001, ANN201, FBT001, FBT002
    return service.read_forms(reader=nd.LlmReader(client=가짜클라이언트(out)), redo=redo)


READING = {
    "items": [
        {"index": 0, "summary_of_others": False,
         "needs": [{"place": "problem", "required": True}]},
        {"index": 1, "summary_of_others": False,
         "needs": [{"place": "problem", "required": True}]},
        {"index": 2, "summary_of_others": False,
         "needs": [{"place": "team", "required": True}]},
    ],
    "overlaps": [{"a": 0, "b": 1, "note": "둘 다 필요성을 묻는다"}],
}


class Test양식_읽기:
    def test_필요한_자리가_선다(self, db) -> None:  # noqa: ANN001
        factory, _ = db
        _read(db, READING)

        with factory() as s:
            assert s.scalars(select(ItemNeed.place)).all() == ["problem", "problem", "team"]

    def test_겹침_쌍이_선다(self, db) -> None:  # noqa: ANN001
        factory, _ = db
        _read(db, READING)

        with factory() as s:
            ov = s.scalars(select(ItemOverlap)).all()
            assert len(ov) == 1
            assert ov[0].a_item_id < ov[0].b_item_id
            assert ov[0].note == "둘 다 필요성을 묻는다"

    def test_판독자를_남긴다(self, db) -> None:  # noqa: ANN001
        factory, _ = db
        _read(db, READING)

        with factory() as s:
            assert s.scalars(select(DocumentItem.needs_decided_by)).all() == (
                ["llm/gpt-5.6-luna"] * 3
            )


#: 겹침 쌍(0·1)에서 사실 둘을 갈라 준다. **안 주면 아무도 안 쓰고 전부 blank 다** —
#: 그것도 설계대로지만, 여기서 보려는 것은 그 뒤의 배관이다
ASSIGN = [{"fact": 1, "item": 0, "why": "배경이다"}, {"fact": 2, "item": 1, "why": "애로다"}]


def _build(db, *, paragraphs=None, assign=None, redo=False):  # noqa: ANN001, ANN201
    _read(db, READING)
    a = ASSIGN if assign is None else assign
    client = (
        가짜클라이언트({"paragraphs": paragraphs}) if paragraphs is not None
        else 받은대로쓰는집필기({})
    )
    return service.build_draft(
        COMPANY, "bizinfo", NOTICE, redo=redo,
        allotter=al.Allotter(client=가짜클라이언트({"assign": a})),
        writers=lambda: wr.LlmWriter(client=client),
        workers=1,
        checker=dd.LlmChecker(client=가짜클라이언트({"clashes": []})),
    )


class Test초안:
    def test_항목마다_행이_선다(self, db) -> None:  # noqa: ANN001
        factory, _ = db
        report = _build(db)

        assert report.items == 3
        with factory() as s:
            assert len(s.scalars(select(DraftItem)).all()) == 3

    def test_문단마다_근거를_남긴다(self, db) -> None:  # noqa: ANN001
        """**F6-13 이 이것이다.** 나중에 붙일 수 없다(ADR-0014)."""
        factory, _ = db
        _build(db)

        with factory() as s:
            ev = s.scalars(select(DraftEvidence)).all()
            assert ev
            assert all(e.fact_id and e.chunk_id for e in ev)

    def test_못_채운_자리가_남는다(self, db) -> None:  # noqa: ANN001
        """**F6-6 이 읽는다.** `team` 은 위키에 사실이 0건이다."""
        factory, _ = db
        report = _build(db)

        assert report.missing == {"team": 1}
        with factory() as s:
            team = s.scalars(
                select(DraftItem).join(DocumentItem).where(DocumentItem.number == "4")
            ).one()
            assert team.missing == ["team"]
            assert team.status == str(DraftItemStatus.BLANK)

    def test_재료가_없으면_안_쓴다(self, db) -> None:  # noqa: ANN001
        """**지어낸 것을 지우면 `[확인 필요]` 만 남는다. 안 쓰는 것이 낫다.**"""
        report = _build(db)

        assert report.blank == 1
        assert report.drafted == 2

    def test_주인을_못_정하면_아무도_안_쓴다(self, db) -> None:  # noqa: ANN001
        """겹침 쌍에서 배분이 안 되면 **양쪽 다 비운다**(T-0064).

        **`blank` 가 아니라 `yielded` 다.** 위키에는 `problem` 이 있으니 물어볼
        자리가 아니다 — 물어보면 사용자가 이미 준 것을 또 준다.
        """
        report = _build(db, assign=[])

        assert report.drafted == 0
        assert report.yielded == 2   # 다투다 아무도 못 받은 둘
        assert report.blank == 1     # team 이 위키에 없는 항목 — 여기만 물어본다

    def test_셋을_상태로_가른다(self, db) -> None:  # noqa: ANN001
        """**같은 이름으로 부르면 화면이 물어볼 자리를 잘못 가리킨다.**"""
        factory, _ = db
        _build(db, assign=[])

        with factory() as s:
            got = {i.status for i in s.scalars(select(DraftItem)).all()}

        assert got == {str(DraftItemStatus.YIELDED), str(DraftItemStatus.BLANK)}

    def test_배분_결과를_저장한다(self, db) -> None:  # noqa: ANN001
        """**안 들면 항목 하나를 재작성할 때 배분을 잊고 다시 겹친다.**"""
        factory, _ = db
        _build(db)

        with factory() as s:
            draft = s.scalars(select(Draft)).one()
            owned = {k: v for k, v in draft.allotment.items() if v}
            assert owned
            assert draft.allotted_by == "llm/gpt-5.6-luna"

    def test_겹침_쌍에서_배분이_갈린다(self, db) -> None:  # noqa: ANN001
        factory, _ = db
        _build(db)

        with factory() as s:
            draft = s.scalars(select(Draft)).one()
            rows = s.scalars(select(DocumentItem).order_by(DocumentItem.ordinal)).all()
            assert draft.allotment[str(rows[0].id)] == [1]
            assert draft.allotment[str(rows[1].id)] == [2]

    def test_두_번_돌려도_초안이_두_벌_안_된다(self, db) -> None:  # noqa: ANN001
        factory, _ = db
        _build(db)
        _build(db)

        with factory() as s:
            assert len(s.scalars(select(DraftItem)).all()) == 3


class Test실패:
    def test_항목_하나가_나머지를_안_죽인다(self, db) -> None:  # noqa: ANN001
        """**ADR-0015 결과 절** — 항목 단위로 실패를 처리하고 만든 항목은 유지한다."""
        factory, _ = db
        _read(db, READING)

        class 터지는클라이언트(가짜클라이언트):
            def json(self, **kw):  # noqa: ANN003, ANN201
                raise RuntimeError("모델이 죽었다")

        report = service.build_draft(
            COMPANY, "bizinfo", NOTICE,
            allotter=al.Allotter(client=가짜클라이언트({"assign": ASSIGN})),
            writers=lambda: wr.LlmWriter(client=터지는클라이언트({})),
            workers=1,
            checker=dd.LlmChecker(client=가짜클라이언트({"clashes": []})),
        )

        assert report.failed == 2  # 재료가 있는 둘. `team` 은 안 부르고 blank 다
        assert report.blank == 1
        with factory() as s:
            errs = [i.error for i in s.scalars(select(DraftItem)).all() if i.error]
            assert len(errs) == 2
            assert "모델이 죽었다" in errs[0]


class Test공고_연결:
    def test_다른_공고의_양식은_안_읽는다(self, db) -> None:  # noqa: ANN001
        report = service.build_draft(COMPANY, "bizinfo", "다른공고")

        assert report.forms == 0


class Test공고_데이터:
    """구멍 1 — F6-12 가 허용한 것을 verify() 가 지우고 있었다."""

    def test_공고_값이_재료에_들어간다(self, db) -> None:  # noqa: ANN001
        _read(db, READING)
        client = 받은대로쓰는집필기({})
        service.build_draft(
            COMPANY, "bizinfo", NOTICE, workers=1,
            allotter=al.Allotter(client=가짜클라이언트({"assign": ASSIGN})),
            writers=lambda: wr.LlmWriter(client=client),
            checker=dd.LlmChecker(client=가짜클라이언트({"clashes": []})),
        )
        user = client.calls[0]["user"]

        assert "사업명: 2026년 철강 위기극복 지원사업" in user
        assert "접수기간: 2026-08-01 ~ 2026-09-30" in user
        assert "최대 5,000만원" in user

    def test_공고가_준_금액을_verify_가_안_지운다(self, db) -> None:  # noqa: ANN001
        """**지키려다 허용한 것을 막고 있었다.**"""
        _read(db, READING)
        report = service.build_draft(
            COMPANY, "bizinfo", NOTICE, workers=1,
            allotter=al.Allotter(client=가짜클라이언트({"assign": ASSIGN})),
            writers=lambda: wr.LlmWriter(client=가짜클라이언트({"paragraphs": [
                {"text": "최대 5,000만원을 신청한다.", "facts": [1]},
            ]})),
            checker=dd.LlmChecker(client=가짜클라이언트({"clashes": []})),
        )

        assert report.unverified == 0
        with 팩토리(db)() as s:
            bodies = [i.body for i in s.scalars(select(DraftItem)).all() if i.body]
            assert all(wr.UNVERIFIED not in b for b in bodies)

    def test_공고가_없어도_돈다(self, db) -> None:  # noqa: ANN001
        """수집이 안 된 공고를 손으로 지목할 수 있다. 재료가 얇을 뿐이다."""
        _read(db, READING)
        report = service.build_draft(
            COMPANY, "bizinfo", "없는공고",
            allotter=al.Allotter(client=가짜클라이언트({"assign": []})),
        )

        assert report.forms == 0


def 팩토리(db):  # noqa: ANN001, ANN201
    return db[0]


class Test병렬:
    """T-0069 — 세션을 스레드가 만나지 않는다."""

    def test_병렬과_순차의_결과가_같다(self, db) -> None:  # noqa: ANN001
        factory, _ = db

        def run(workers: int) -> list[tuple[int, str]]:
            with factory() as s:
                s.execute(delete(DraftEvidence))
                s.execute(delete(DraftItem))
                s.execute(delete(Draft))
                s.commit()
            _read(db, READING, redo=True)
            service.build_draft(
                COMPANY, "bizinfo", NOTICE, workers=workers,
                allotter=al.Allotter(client=가짜클라이언트({"assign": ASSIGN})),
                writers=lambda: wr.LlmWriter(client=받은대로쓰는집필기({})),
                checker=dd.LlmChecker(client=가짜클라이언트({"clashes": []})),
            )
            with factory() as s:
                return [
                    (i.ordinal, i.body)
                    for i in s.scalars(select(DraftItem).order_by(DraftItem.ordinal)).all()
                ]

        assert run(1) == run(8)

    def test_저장이_ordinal_순이다(self, db) -> None:  # noqa: ANN001
        """**같은 입력에서 같은 초안이 나와야 --redo 로 무엇이 바뀌었는지 본다.**"""
        factory, _ = db
        _read(db, READING)
        service.build_draft(
            COMPANY, "bizinfo", NOTICE, workers=8,
            allotter=al.Allotter(client=가짜클라이언트({"assign": ASSIGN})),
            writers=lambda: wr.LlmWriter(client=받은대로쓰는집필기({})),
            checker=dd.LlmChecker(client=가짜클라이언트({"clashes": []})),
        )

        with factory() as s:
            rows = s.scalars(select(DraftItem).order_by(DraftItem.id)).all()
            assert [r.ordinal for r in rows] == sorted(r.ordinal for r in rows)

    def test_집필기를_워커마다_새로_만든다(self, db) -> None:  # noqa: ANN001
        """**Usage.calls += 1 이 원자적이 아니라 하나를 공유하면 토큰 수가 어긋난다.**"""
        _read(db, READING)
        made: list[wr.LlmWriter] = []

        def make() -> wr.LlmWriter:
            w = wr.LlmWriter(client=받은대로쓰는집필기({}))
            made.append(w)
            return w

        service.build_draft(
            COMPANY, "bizinfo", NOTICE, workers=8,
            allotter=al.Allotter(client=가짜클라이언트({"assign": ASSIGN})),
            writers=make,
            checker=dd.LlmChecker(client=가짜클라이언트({"clashes": []})),
        )

        assert len(made) == 3          # 항목마다 하나
        assert len({id(w) for w in made}) == 3


class Test분량:
    """구멍 2 — 제한을 주기만 하고 안 재고 있었다."""

    def test_상한을_넘으면_센다(self, db) -> None:  # noqa: ANN001
        factory, _ = db
        with factory() as s:
            row = s.scalars(select(DocumentItem).where(DocumentItem.ordinal == 0)).one()
            row.limit_text = "10자 이내"
            s.commit()
        _read(db, READING)
        report = service.build_draft(
            COMPANY, "bizinfo", NOTICE, workers=1,
            allotter=al.Allotter(client=가짜클라이언트({"assign": ASSIGN})),
            writers=lambda: wr.LlmWriter(client=받은대로쓰는집필기({})),
            checker=dd.LlmChecker(client=가짜클라이언트({"clashes": []})),
        )

        assert report.over_limit == 1

    def test_쪽_수는_못_잰_것으로_센다(self, db) -> None:  # noqa: ANN001
        factory, _ = db
        with factory() as s:
            row = s.scalars(select(DocumentItem).where(DocumentItem.ordinal == 0)).one()
            row.limit_text = "1페이지 이내"
            s.commit()
        _read(db, READING)
        report = service.build_draft(
            COMPANY, "bizinfo", NOTICE, workers=1,
            allotter=al.Allotter(client=가짜클라이언트({"assign": ASSIGN})),
            writers=lambda: wr.LlmWriter(client=받은대로쓰는집필기({})),
            checker=dd.LlmChecker(client=가짜클라이언트({"clashes": []})),
        )

        assert report.over_limit == 0
        assert report.unmeasured == 1
