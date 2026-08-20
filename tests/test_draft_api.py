"""초안 조회 API (plan/16 · F6 · `docs/api-contract.md`).

여기서 막는 것은 **계약과 배포**다.

1. **`status` 여섯을 갈라 준다.** 섞이면 화면이 사용자에게 이미 아는 것을 묻는다 —
   실측에서 `못 채움` 7 로 보인 것이 실은 상위 묶음 3 · 배분에서 못 받음 4 였다
2. **트리로 준다.** 평평하게 내보내면 화면이 트리를 다시 세운다
3. **`place_label` 을 API 가 붙인다.** 화면이 한국어를 지으면 `topics.py` 와 갈린다
4. **없으면 빈 목록이다. 404 가 아니다** — 404 는 원인을 안 남긴다
5. **`api/draft_service.py` 가 `finnect.draft.service` 를 안 끌고 온다.** 그쪽은
   `llm` 을 타고 `httpx` 를 부르고, `requirements.txt` 가 그것을 뺐다
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from finnect.api import draft_service
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
    ParseStatus,
    UserFile,
    WikiEvidence,
    WikiFact,
)

COMPANY = "c_api"
NOTICE = "PBLN-API"
SHA = "e" * 64
TABLES = [
    Attachment, AttachmentFile, Document, DocumentItem, ItemNeed,
    Draft, DraftItem, DraftEvidence, WikiFact, WikiEvidence, Chunk, UserFile,
]


@pytest.fixture
def db():  # noqa: ANN201
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[t.__table__ for t in TABLES])
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    with factory() as s:
        s.add(Attachment(id=1, source="bizinfo", external_id=NOTICE, url="u1",
                         position=0, kind="file", filename="신청서식.hwp", ext="hwp"))
        s.add(AttachmentFile(id=1, url="u1", source="bizinfo", sha256=SHA,
                             fetch_status="ok", parse_status=str(ParseStatus.OK)))
        s.add(Document(id=1, sha256=SHA, seq=1, title="[붙임2] 사업계획서",
                       kind=str(DocumentKind.NARRATIVE), char_start=0, char_end=900,
                       decided_by="llm/gpt-5.6-luna"))
        s.flush()
        # 1 묶음 → 1-1 · 1-2 ·   2 홀로
        for i, (pid, no, title, ins, limit) in enumerate([
            (None, "1", "신청기업 현황", None, None),
            (1, "1-1", "일반현황", "기업 개요를 기재", "100자 이내"),
            (1, "1-2", "매출 현황", "매출을 기재", "3페이지 이내"),
            (None, "2", "목적 및 필요성", "필요성을 기술", None),
        ]):
            s.add(DocumentItem(id=i + 1, document_id=1, parent_id=pid, ordinal=i,
                               number=no, title=title, instruction=ins,
                               limit_text=limit, input_kind="narrative"))
        s.add(ItemNeed(document_item_id=2, place="revenue", place_kind="slot", required=True))
        s.add(ItemNeed(document_item_id=3, place="revenue", place_kind="slot", required=True))
        s.add(ItemNeed(document_item_id=4, place="team", place_kind="node", required=True))

        f = UserFile(company_id=COMPANY, sha256="f" * 64, filename="소개서.pdf",
                     ext="pdf", byte_size=1, status="built")
        s.add(f)
        s.flush()
        c = Chunk(user_file_id=f.id, company_id=COMPANY, ordinal=0,
                  text="2025년 매출은 8,640만원이다", chars=17, char_start=0, char_end=17)
        s.add(c)
        s.flush()
        fact = WikiFact(id=1, company_id=COMPANY, place_kind="slot", place="revenue",
                        dedupe_key="k", topic="revenue", text="2025년 매출 8,640만원",
                        extractor="stub/v1")
        s.add(fact)
        s.flush()
        s.add(WikiEvidence(company_id=COMPANY, fact_id=1, chunk_id=c.id,
                           user_file_id=f.id, quote="매출은 8,640만원"))

        s.add(Draft(id=1, company_id=COMPANY, notice_id=NOTICE, source="bizinfo",
                    document_id=1, allotment={"2": [1], "3": [], "4": []},
                    allotted_by="llm/gpt-5.6-luna"))
        s.flush()
        for iid, (item_id, status, body, missing) in enumerate([
            (1, DraftItemStatus.NO_NEEDS, "", []),
            (2, DraftItemStatus.DRAFTED, "2025년 매출은 8,640만원이다.", []),
            (3, DraftItemStatus.YIELDED, "", []),
            (4, DraftItemStatus.BLANK, "", ["team"]),
        ]):
            s.add(DraftItem(draft_id=1, document_item_id=item_id, ordinal=iid,
                            status=str(status), body=body, missing=missing,
                            missing_optional=[]))
        s.flush()
        s.add(DraftEvidence(draft_item_id=2, paragraph=0, fact_id=1,
                            chunk_id=c.id, source_type="document"))
        s.commit()
    yield factory


def _get(factory):  # noqa: ANN001, ANN201
    with factory() as s:
        return draft_service.notice_draft(s, COMPANY, "bizinfo", NOTICE)


class Test트리:
    def test_부모_자식으로_접힌다(self, db) -> None:  # noqa: ANN001
        """**평평하게 내보내면 화면이 트리를 다시 세운다.**"""
        items = _get(db).documents[0].items

        assert [i.number for i in items] == ["1", "2"]
        assert [c.number for c in items[0].children] == ["1-1", "1-2"]

    def test_양식_정보를_같이_준다(self, db) -> None:  # noqa: ANN001
        doc = _get(db).documents[0]

        assert doc.title == "[붙임2] 사업계획서"
        assert doc.filename == "신청서식.hwp"
        assert doc.allotted_by == "llm/gpt-5.6-luna"


class Test상태:
    def test_여섯을_갈라_준다(self, db) -> None:  # noqa: ANN001
        """**섞이면 화면이 사용자에게 이미 아는 것을 묻는다.**"""
        items = _get(db).documents[0].items
        got = {i.number: i.status for i in items}
        got |= {c.number: c.status for i in items for c in i.children}

        assert got == {
            "1": "no_needs", "1-1": "drafted", "1-2": "yielded", "2": "blank",
        }

    def test_물어볼_자리만_missing_이_찬다(self, db) -> None:  # noqa: ANN001
        items = _get(db).documents[0].items
        blank = next(i for i in items if i.status == "blank")

        assert [m.place for m in blank.missing] == ["team"]
        assert blank.missing[0].required is True

    def test_상위_묶음은_missing_이_비어_있다(self, db) -> None:  # noqa: ANN001
        """**초안 자리로 그리지 않는다.**"""
        top = next(i for i in _get(db).documents[0].items if i.status == "no_needs")

        assert top.missing == [] and top.paragraphs == []

    def test_넘긴_항목이_어디로_갔는지_말한다(self, db) -> None:  # noqa: ANN001
        """**"못 채웠어요" 가 아니라 "그 얘기는 1-1 에 썼어요" 다.**"""
        items = _get(db).documents[0].items
        yielded = next(c for i in items for c in i.children if c.status == "yielded")

        assert yielded.yielded_to == ["1-1"]


class Test근거:
    def test_문단마다_붙는다(self, db) -> None:  # noqa: ANN001
        """**F6-13.** 나중에 붙일 수 없다(ADR-0014)."""
        items = _get(db).documents[0].items
        drafted = next(c for i in items for c in i.children if c.status == "drafted")

        assert len(drafted.paragraphs) == 1
        ev = drafted.paragraphs[0].evidence[0]
        assert ev.fact_id == 1
        assert ev.chunk_id is not None
        assert ev.quote == "매출은 8,640만원"

    def test_자리_이름을_API_가_붙인다(self, db) -> None:  # noqa: ANN001
        """**화면이 한국어를 지으면 `topics.py` 와 갈린다.**"""
        items = _get(db).documents[0].items
        drafted = next(c for i in items for c in i.children if c.status == "drafted")
        blank = next(i for i in items if i.status == "blank")

        assert drafted.paragraphs[0].evidence[0].place_label == "매출액"
        assert blank.missing[0].place_label == "팀 구성"


class Test분량:
    def test_글자_제한을_잰다(self, db) -> None:  # noqa: ANN001
        items = _get(db).documents[0].items
        drafted = next(c for i in items for c in i.children if c.number == "1-1")

        assert drafted.length.verdict == "ok"
        assert drafted.length.limit_text == "100자 이내"
        assert drafted.length.measured == 18   # 공백·쉼표를 뺀 글자 수

    def test_쪽_수는_못_잰다고_말한다(self, db) -> None:  # noqa: ANN001
        """**틀린 숫자를 내는 것보다 못 잰다고 말하는 것이 낫다.**"""
        items = _get(db).documents[0].items
        got = next(c for i in items for c in i.children if c.number == "1-2")

        assert got.length.verdict == "unmeasurable"
        assert got.length.measured is None

    def test_제한이_없으면_none(self, db) -> None:  # noqa: ANN001
        top = next(i for i in _get(db).documents[0].items if i.number == "1")

        assert top.length.verdict == "none"


class Test없을_때:
    def test_초안이_없으면_빈_목록이다(self, db) -> None:  # noqa: ANN001
        """**404 가 아니다.** 404 는 원인을 안 남긴다."""
        with db() as s:
            got = draft_service.notice_draft(s, "c_없는회사", "bizinfo", NOTICE)

        assert got.documents == []
        # 서술형 양식은 있는데 초안이 없다 — 돌리면 생긴다
        assert got.pending_documents == 1

    def test_모르는_공고면_비어_있다(self, db) -> None:  # noqa: ANN001
        with db() as s:
            got = draft_service.notice_draft(s, COMPANY, "bizinfo", "없는공고")

        assert got.documents == [] and got.pending_documents == 0


def test_쓰기_경로를_안_끌고_온다() -> None:
    """**로컬은 통과하고 배포본만 죽는** 그 함정이다(CLAUDE.md · `test_admin_api.py`).

    `finnect.draft.service` 는 `llm` 을 타고 `httpx` 를 부르는데
    `requirements.txt` 가 그것을 뺐다.
    """
    import ast
    import pathlib

    src = pathlib.Path(draft_service.__file__).read_text()
    top = [n for n in ast.parse(src).body if isinstance(n, (ast.Import, ast.ImportFrom))]
    mods = {a.name for n in top if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module or "" for n in top if isinstance(n, ast.ImportFrom)}

    assert "httpx" not in mods
    assert "finnect.draft.service" not in mods
    assert "finnect.llm" not in mods
