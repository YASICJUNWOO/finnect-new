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
from sqlalchemy import create_engine, delete, event, select
from sqlalchemy.orm import sessionmaker

import wikifix
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
    CompanyValue,
    Document,
    DocumentItem,
    DocumentKind,
    Draft,
    DraftEvidence,
    DraftItem,
    DraftItemStatus,
    DraftValueEvidence,
    ItemNeed,
    ItemOverlap,
    ParseStatus,
    UserFile,
    ValueEvidence,
    WikiEvidence,
    WikiFact,
    WikiNode,
)
from finnect.views import Notice

#: 옛 orbit 이름 → 노드 경로. **테스트가 쓰는 자리만 적는다**
#: 옛 orbit 이름 → 노드 경로. **`item_need.place` 는 카테고리를 가리키고**
#: 사실은 그 아래 경로에 앉는다 — `_index` 가 조상으로 이어 준다(ADR-0056)
_PATH = {
    "problem": "Customer/고객문제",
    "solution": "Product/기능",
    "team": "Company/팀",
    "roadmap": "Plan/일정",
    "finance": "Financial/자금계획",
    "identity": "Company/비전",
    "Customer": "Customer/고객문제",
    "Company": "Company/팀",
    "Product": "Product/기능",
    "Plan": "Plan/일정",
    "Financial": "Financial/자금계획",
}

COMPANY = "c_draft"
SHA = "d" * 64
NOTICE = "PBLN-000"
TABLES = [
    Attachment, AttachmentFile, Document, DocumentItem, ItemNeed, ItemOverlap,
    Draft, DraftItem, DraftEvidence, DraftValueEvidence, WikiFact, WikiNode,
    CompanyValue, ValueEvidence, WikiEvidence, Chunk, UserFile,
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
    r"""**받은 사실을 그대로 인용한다.** 고정 응답을 쓰면 항목마다 배분이 다른데
    답이 같아서, `근거 없는 문단` 으로 전부 버려진다 — 배관을 못 본다.

    자리 이름에 `[^\]]+` 를 쓰는 이유는 **노드 경로에 `/` 가 들어가서다**(ADR-0056).
    `\w+` 로 두면 `#1 [Customer/고객문제]` 가 안 잡히고 전부 안 쓴 것이 된다.

    id 에 `-?` 를 쓰는 이유는 **매칭 정보가 음수 id 로 온다**는 것이다(`draft/refs.py` ·
    T-0134). `\d+` 로 두면 트랙 B 재료만 통째로 안 잡혀서 **값을 요구한 항목이 전부
    `unwritten` 이 된다** — 위키에 값이 있는데 못 채운 것처럼 보이는, 고치려던 바로 그
    증상이다.
    """

    def json(self, **kw) -> dict:  # noqa: ANN003
        self.calls.append(kw)
        got = re.findall(r"^#(-?\d+) \[[^\]]+\](?: \([^)]*\))? (.+)$", kw["user"], re.M)
        return {"paragraphs": [{"text": f"{t}.", "facts": [int(i)]} for i, t in got]}


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
    engine = create_engine("sqlite://")

    # **FK 를 켠다.** SQLite 는 기본이 꺼짐이고 그러면 `ON DELETE CASCADE` 가 안 돈다 —
    # `_draft_row` 의 `delete(DraftItem)` 이 근거를 남기는데 배포 DB(Postgres)에서는
    # 지워진다. 켜지 않으면 **재작성이 로컬에서만 깨지거나 로컬에서만 통과한다.**
    @event.listens_for(engine, "connect")
    def _fk_on(conn, _rec) -> None:  # noqa: ANN001
        conn.execute("PRAGMA foreign_keys=ON")

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
        for text, place in [("철강 경기로 수주가 끊겼다", "Customer"),
                            ("설비 노후로 불량률이 올랐다", "Customer")]:
            fact = wikifix.fact(
                s, COMPANY, _PATH.get(place, f"Custom/{place}"), text, key=text[:30]
            )
            s.add(WikiEvidence(company_id=COMPANY, fact_id=fact.id, chunk_id=c.id,
                               user_file_id=f.id, quote=text))
        s.commit()
        yield factory, doc.id


def _read(db, out: dict, redo: bool = False):  # noqa: ANN001, ANN201, FBT001, FBT002
    return service.read_forms(reader=nd.LlmReader(client=가짜클라이언트(out)), redo=redo)


READING = {
    "items": [
        {"index": 0, "summary_of_others": False,
         "needs": [{"place": "Customer", "required": True}]},
        {"index": 1, "summary_of_others": False,
         "needs": [{"place": "Customer", "required": True}]},
        {"index": 2, "summary_of_others": False,
         "needs": [{"place": "Company", "required": True}]},
    ],
    "overlaps": [{"a": 0, "b": 1, "note": "둘 다 필요성을 묻는다"}],
}


class Test양식_읽기:
    def test_필요한_자리가_선다(self, db) -> None:  # noqa: ANN001
        factory, _ = db
        _read(db, READING)

        with factory() as s:
            assert s.scalars(select(ItemNeed.place)).all() == ["Customer", "Customer", "Company"]

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

    def test_칸_채우기_서식도_읽는다(self, db) -> None:  # noqa: ANN001
        """**서술형만 고르면 신청서 한 벌이 통째로 빠진다.**

        실측 공고 `kstartup:178881` 은 붙은 서류가 `fields` 둘뿐이라 「초안 쓰기」를
        눌러도 고를 것이 없어 즉시 끝났다. 사용자에게는 버튼이 안 먹는 것으로 보인다.

        **`place_kind` 가 여기서 갈린다.** 칸 이름이 매칭 정보 key 면 `value` 라
        집필이 글을 쓰지 않고 값을 옮긴다.
        """
        factory, _ = db
        _read(db, READING)  # 서술형을 먼저 읽어 둔다 — 다음 호출은 그것을 건너뛴다
        _칸_서식(factory, titles=["대표자 정보"])

        _read(db, {
            "items": [
                {
                    "index": 0,
                    "needs": [{"place": "ceo_name", "required": True}],
                    "summary_of_others": False,
                }
            ],
            "overlaps": [],
        })

        with factory() as s:
            need = s.scalars(
                select(ItemNeed).where(ItemNeed.document_item_id == _FIELD_ITEM)
            ).all()
            assert [n.place for n in need] == ["ceo_name"]
            assert need[0].place_kind == "value"


#: 칸 채우기 서식의 첫 항목 id. 서술형 픽스처(1~3)와 안 겹치게 띄워 둔다
_FIELD_ITEM = 10


def _칸_서식(factory, *, titles: list[str]) -> int:  # noqa: ANN001
    """칸 채우기 서식 하나를 **같은 공고에** 붙인다.

    한 공고에 서술형과 칸 서식이 같이 오는 것이 실제 모양이다 — `kstartup:178881`
    은 `fields` 만 둘이고, 붙임이 넷인 공고에서 종류가 섞여 온다.
    """
    sha = "e" * 64
    with factory() as s:
        s.add(Attachment(id=2, source="bizinfo", external_id=NOTICE, url="u2",
                         position=1, kind="file", filename="신청서.hwp", ext="hwp"))
        s.add(AttachmentFile(id=2, url="u2", source="bizinfo", sha256=sha,
                             fetch_status="ok", parse_status=str(ParseStatus.OK)))
        doc = Document(id=2, sha256=sha, seq=1, title="신청서",
                       kind=str(DocumentKind.FIELDS), char_start=0, char_end=200,
                       decided_by="rule/v1")
        s.add(doc)
        s.flush()
        for i, t in enumerate(titles):
            s.add(DocumentItem(id=_FIELD_ITEM + i, document_id=doc.id, ordinal=i,
                               number=None, title=t, instruction=None, input_kind="field"))
        s.commit()
        return doc.id


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

        assert report.missing == {"Company": 1}
        with factory() as s:
            team = s.scalars(
                select(DraftItem).join(DocumentItem).where(DocumentItem.number == "4")
            ).one()
            assert team.missing == ["Company"]
            assert team.status == str(DraftItemStatus.BLANK)

    def test_재료가_없으면_안_쓴다(self, db) -> None:  # noqa: ANN001
        """**지어낸 것을 지우면 `[확인 필요]` 만 남는다. 안 쓰는 것이 낫다.**"""
        report = _build(db)

        assert report.blank == 1
        assert report.drafted == 2

    def test_주인을_못_정하면_아무도_안_쓴다(self, db) -> None:  # noqa: ANN001
        """겹침 쌍에서 배분이 안 되면 **양쪽 다 비운다**(T-0064).

        **`blank` 가 아니라 `yielded` 다.** 위키에는 `Customer` 가 있으니 물어볼
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


class Test다시_쓰기:
    """T-0161 · [ADR-0062](
    ../docs/adr/0062-다시-쓰기가-고친-글을-지우되-먼저-알린다.md).

    **이 클래스가 지키는 것은 「안 덮어쓴다」가 아니라 「부르기 전에 안다」다.**
    안 덮어쓰는 것은 예전에도 그랬는데 **저장 직전에 걸러서** 배분과 집필을 다
    부른 뒤에 버렸다 — 화면은 아무 일도 안 일어난 것처럼 보이고 토큰만 나갔다.
    """

    def _writer(self, db):  # noqa: ANN001, ANN202
        """집필기를 밖에서 들고 있어야 **몇 번 불렀는지** 센다."""
        _read(db, READING)
        client = 받은대로쓰는집필기({})
        service.build_draft(
            COMPANY, "bizinfo", NOTICE, workers=1,
            allotter=al.Allotter(client=가짜클라이언트({"assign": ASSIGN})),
            writers=lambda: wr.LlmWriter(client=client),
            checker=dd.LlmChecker(client=가짜클라이언트({"clashes": []})),
        )
        return client

    def test_이미_있으면_llm_을_안_부른다(self, db) -> None:  # noqa: ANN001
        """**여기가 요점이다.** 둘째 호출에서 집필기 호출이 하나도 안 늘어야 한다."""
        first = self._writer(db)
        assert first.calls, "첫 호출은 실제로 써야 이 테스트가 뜻이 있다"

        second = self._writer(db)

        assert second.calls == []

    def test_건너뛴_양식을_보고한다(self, db) -> None:  # noqa: ANN001
        """**조용히 건너뛰지 않는다.** 숫자가 없으면 「왜 안 늘었지」를 못 되짚는다."""
        _build(db)
        report = _build(db)

        assert report.skipped == 1
        assert report.forms == 0
        assert "건너뜀 1" in report.line()

    def test_안_덮어쓴다(self, db) -> None:  # noqa: ANN001
        factory, _ = db
        _build(db)
        with factory() as s:
            before = [(i.ordinal, i.body) for i in s.scalars(select(DraftItem)).all()]

        _build(db)

        with factory() as s:
            assert [(i.ordinal, i.body) for i in s.scalars(select(DraftItem)).all()] == before

    def test_redo_면_다시_쓴다(self, db) -> None:  # noqa: ANN001
        """**id 로 갈렸는지 보지 않는다.** SQLite 는 지운 기본키를 재사용해서 새 행이
        같은 번호를 받는다 — 배포 DB(Postgres)는 시퀀스라 안 그렇고, 그 차이에
        기대는 단언은 방언을 시험하는 것이지 우리 코드를 시험하는 것이 아니다."""
        factory, _ = db
        _build(db)
        with factory() as s:
            first = s.scalars(select(DraftItem).order_by(DraftItem.ordinal)).first()
            written = first.body
            first.body = "누가 밖에서 덮어쓴 글"
            s.commit()

        report = _build(db, redo=True)

        assert report.skipped == 0
        assert report.forms == 1
        assert report.items == 3
        with factory() as s:
            items = s.scalars(select(DraftItem).order_by(DraftItem.ordinal)).all()
            # **다시 깔았다.** 항목이 늘지도 않고 옛 본문이 남지도 않는다
            assert len(items) == 3
            assert items[0].body == written
            # 초안 행은 남는다 — `_draft_row` 가 항목만 간다
            assert len(s.scalars(select(Draft)).all()) == 1

    def test_redo_가_고친_글도_지운다(self, db) -> None:  # noqa: ANN001
        """**ADR-0062 가 감수한 대가다.** 화면이 이 사실을 먼저 말하고 누르게 한다 —
        여기서 고친 항목만 남기면 새 글과 옛 글이 한 문서에 섞이고, 둘의 근거가
        서로 다른 사실을 가리켜 문서 단위 대조가 안 맞는다."""
        factory, _ = db
        _build(db)
        with factory() as s:
            item = s.scalars(select(DraftItem).order_by(DraftItem.ordinal)).first()
            item.edited_body = "내가 손으로 고친 문장이다"
            s.commit()

        _build(db, redo=True)

        with factory() as s:
            bodies = [i.edited_body for i in s.scalars(select(DraftItem)).all()]
            assert bodies == [None] * len(bodies)


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


class Test매칭_정보:
    """**트랙 B 를 집필이 읽는다** (plan/22 T-0134).

    이 결함은 테스트 150개가 전부 통과하는 채로 살아 있었다 — 위 픽스처가 노드 경로만
    쓰고 `item_need.place` 가 매칭 정보 열넷을 가리키는 길을 **한 번도 안 밟아서**다.
    그래서 여기는 `wikifix.value()` 로 트랙 B 에만 값을 넣고 시작한다.
    """

    #: 3번 항목이 `Company` 대신 `headcount` 를 요구한다. 나머지는 위와 같다
    READING_VALUE = {
        "items": [
            {"index": 0, "summary_of_others": False,
             "needs": [{"place": "Customer", "required": True}]},
            {"index": 1, "summary_of_others": False,
             "needs": [{"place": "Customer", "required": True}]},
            {"index": 2, "summary_of_others": False,
             "needs": [{"place": "headcount", "required": True}]},
        ],
        "overlaps": [],
    }

    def _seed(self, factory) -> None:  # noqa: ANN001
        with factory() as s:
            f = s.scalars(select(UserFile)).first()
            c = s.scalars(select(Chunk)).first()
            v = wikifix.value(s, COMPANY, "headcount", "15")
            s.add(ValueEvidence(company_id=COMPANY, value_id=v.id, chunk_id=c.id,
                                user_file_id=f.id, quote="상시 근로자 15명"))
            s.commit()

    def _run(self, db):  # noqa: ANN001, ANN202
        _read(db, self.READING_VALUE)
        return service.build_draft(
            COMPANY, "bizinfo", NOTICE, workers=1,
            allotter=al.Allotter(client=가짜클라이언트({"assign": []})),
            writers=lambda: wr.LlmWriter(client=받은대로쓰는집필기({})),
            checker=dd.LlmChecker(client=가짜클라이언트({"clashes": []})),
        )

    def test_값이_재료에_들어간다(self, db) -> None:  # noqa: ANN001
        """**`headcount` 는 `wiki_fact` 에 없다.** `company_value` 에만 있다."""
        factory, _ = db
        self._seed(factory)

        with factory() as s:
            mats = service._company_facts(s, COMPANY)
        got = [m for m in mats.values() if m.place == "headcount"]

        assert len(got) == 1
        #: **저장값이 아니라 라벨 붙은 문장이다.** `15` 만 주면 집필이 단위를 지어낸다
        assert got[0].text == "직원 수 15명"
        assert got[0].quotes == ("상시 근로자 15명",)

    def test_못_채움이_아니다(self, db) -> None:  # noqa: ANN001
        """**이 한 줄이 T-0134 다.** 위키에 값이 있는데 「없어요」가 뜨던 자리."""
        factory, _ = db
        self._seed(factory)
        report = self._run(db)

        assert "headcount" not in report.missing
        with factory() as s:
            item = s.scalars(
                select(DraftItem).join(DocumentItem).where(DocumentItem.number == "4")
            ).one()
            assert item.missing == []
            assert item.status == str(DraftItemStatus.DRAFTED)

    def test_값을_인용한_문단에_근거가_붙는다(self, db) -> None:  # noqa: ANN001
        """**표가 갈려 있다**(ADR-0056 과 같은 이유). `draft_evidence` 에 안 앉는다."""
        factory, _ = db
        self._seed(factory)
        self._run(db)

        with factory() as s:
            ev = s.scalars(select(DraftValueEvidence)).all()
            assert ev
            assert all(e.value_id and e.chunk_id for e in ev)

    def test_값이_없으면_그때는_못_채움이다(self, db) -> None:  # noqa: ANN001
        """**반대쪽도 잠근다.** 안 그러면 「항상 채워짐」으로 고쳐도 통과한다."""
        factory, _ = db
        report = self._run(db)

        assert report.missing == {"headcount": 1}
        with factory() as s:
            item = s.scalars(
                select(DraftItem).join(DocumentItem).where(DocumentItem.number == "4")
            ).one()
            assert item.status == str(DraftItemStatus.BLANK)

    def test_값_칸에는_값만_앉는다(self, db) -> None:  # noqa: ANN001
        """**값 칸에 문장을 쓰면 안 된다.**

        `상시 근로자 수` 같은 칸은 답이 문단이 아니라 값 하나다. 집필기에 맡기면
        문장이 나오고 그 문장이 신청서 칸에 앉는다 — 라벨까지 들어가서 `직원 수` 칸에
        「직원 수 15명」이 적힌다.

        **가르는 것은 문서 종류가 아니라 자리다.** 서술형 양식에도 값 칸이 있고 칸
        서식에도 `협업계획 요약` 같은 서술 칸이 있다.
        """
        factory, _ = db
        self._seed(factory)
        self._run(db)

        with factory() as s:
            item = s.scalars(
                select(DraftItem).join(DocumentItem).where(DocumentItem.number == "4")
            ).one()
            #: 라벨(`직원 수`)이 아니라 값만. 칸 이름이 이미 라벨 노릇을 한다
            assert item.body == "15명"
            assert item.status == str(DraftItemStatus.DRAFTED)

    def test_한_칸이_값_둘을_요구하면_둘_다_넣는다(self, db) -> None:  # noqa: ANN001
        """**하나만 고르면 엉뚱한 쪽이 남는다.**

        실측(`kstartup:178881`)에서 `대표자 정보` 칸에 이름 대신 `1992-07-04` 이
        앉았다. 한 칸이 값 둘을 요구하는 일이 흔하다 — 그 양식은 `사업자등록번호
        (법인등록번호)` 도 괄호로 둘을 같이 묻는다.

        **순서는 `item_need` 의 것이다.** LLM 이 칸 이름을 읽은 순서라 괄호로 뒤에
        온 것이 뒤에 온다.
        """
        factory, _ = db
        with factory() as s:
            f = s.scalars(select(UserFile)).first()
            c = s.scalars(select(Chunk)).first()
            for key, val in [("ceo_name", "윤세라"), ("ceo_birth", "1992-07-04")]:
                v = wikifix.value(s, COMPANY, key, val)
                s.add(ValueEvidence(company_id=COMPANY, value_id=v.id, chunk_id=c.id,
                                    user_file_id=f.id, quote=val))
            s.commit()

        _read(db, {
            "items": [
                {"index": 0, "summary_of_others": False, "needs": []},
                {"index": 1, "summary_of_others": False, "needs": []},
                {"index": 2, "summary_of_others": False, "needs": [
                    {"place": "ceo_name", "required": True},
                    {"place": "ceo_birth", "required": True},
                ]},
            ],
            "overlaps": [],
        })
        service.build_draft(
            COMPANY, "bizinfo", NOTICE, workers=1,
            allotter=al.Allotter(client=가짜클라이언트({"assign": []})),
            writers=lambda: wr.LlmWriter(client=받은대로쓰는집필기({})),
            checker=dd.LlmChecker(client=가짜클라이언트({"clashes": []})),
        )

        with factory() as s:
            item = s.scalars(
                select(DraftItem).join(DocumentItem).where(DocumentItem.number == "4")
            ).one()
            assert item.body == "윤세라 / 1992-07-04"

    def test_값_칸은_집필기를_안_부른다(self, db) -> None:  # noqa: ANN001
        """**LLM 을 아낀다.** 옮기면 되는 값에 호출을 쓰면 느리고 비싸고, 무엇보다
        모델이 값을 고쳐 쓸 자리가 생긴다."""
        factory, _ = db
        self._seed(factory)
        writer = 받은대로쓰는집필기({})
        _read(db, self.READING_VALUE)
        service.build_draft(
            COMPANY, "bizinfo", NOTICE, workers=1,
            allotter=al.Allotter(client=가짜클라이언트({"assign": []})),
            writers=lambda: wr.LlmWriter(client=writer),
            checker=dd.LlmChecker(client=가짜클라이언트({"clashes": []})),
        )

        #: 서술 항목 둘은 부르고 값 항목 하나는 안 부른다
        assert len(writer.calls) == 2
        assert all("상시 근로자" not in c["user"] for c in writer.calls)
