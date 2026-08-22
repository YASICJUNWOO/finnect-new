"""사람이 고친 글 — plan/21 T-0123 · [ADR-0055](
../docs/adr/0055-사람이-고친-글을-집필-출력-위에-덮지-않는다.md).

여기서 잠그는 것 다섯.

1. **`body` 를 안 덮는다.** 집필기의 출력이 그대로 남아야 되돌릴 수 있다
2. **`None` 과 `""` 가 다르다.** 앞은 되돌리기, 뒤는 일부러 비운 것 — 섞으면
   지운 항목에 초안이 다시 나타난다
3. **고친 항목은 문단 근거를 안 낸다.** `draft_evidence` 행은 DB 에 그대로 남는다 —
   [ADR-0028](../docs/adr/0028-초안을-먼저-완성하고-못-채운-자리에서-묻는다.md) 4번의
   파급 계산이 그 행으로 돈다
4. **`status` 를 안 바꾼다.** 저 표는 집필이 어떻게 됐나를 말한다 — `blank` 였던
   자리가 사람 편집으로 `drafted` 가 되면 **물어볼 목록에서 조용히 빠진다**
5. **분량을 고친 글로 잰다.** 안 그러면 100자 제한을 넘겨 써도 `ok` 로 앉는다

`tests/test_draft_api.py` 와 같은 픽스처를 쓴다 — Postgres 없이 SQLite 로 돈다.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
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

COMPANY = "c_edit"
NOTICE = "PBLN-EDIT"
SHA = "d" * 64
#: 근거가 붙은 항목. 「고치면 근거가 떨어진다」를 보는 자리다
DRAFTED = 2
#: 아무도 안 쓴 자리. **`status` 가 안 바뀌는지 보는 자리다**
BLANK = 4

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
        for i, (no, title, limit) in enumerate([
            ("1", "신청기업 현황", None),
            ("1-1", "일반현황", "100자 이내"),
            ("2", "목적 및 필요성", None),
            ("3", "팀 구성", None),
        ]):
            s.add(DocumentItem(id=i + 1, document_id=1, parent_id=None, ordinal=i,
                               number=no, title=title, instruction=None,
                               limit_text=limit, input_kind="narrative"))
        s.add(ItemNeed(document_item_id=BLANK, place="team", place_kind="event",
                       required=True))

        f = UserFile(company_id=COMPANY, sha256="e" * 64, filename="소개서.pdf",
                     ext="pdf", byte_size=1, status="built")
        s.add(f)
        s.flush()
        c = Chunk(user_file_id=f.id, company_id=COMPANY, ordinal=0,
                  text="2025년 매출은 8,640만원이다", chars=17, char_start=0, char_end=17)
        s.add(c)
        s.flush()
        s.add(WikiFact(id=1, company_id=COMPANY, place_kind="value", place="revenue",
                       dedupe_key="k", topic="revenue", text="2025년 매출 8,640만원",
                       extractor="stub/v1"))
        s.flush()
        s.add(WikiEvidence(company_id=COMPANY, fact_id=1, chunk_id=c.id,
                           user_file_id=f.id, quote="매출은 8,640만원"))

        s.add(Draft(id=1, company_id=COMPANY, notice_id=NOTICE, source="bizinfo",
                    document_id=1, allotment={}, allotted_by="none"))
        s.flush()
        for iid, (item_id, status, body, missing) in enumerate([
            (1, DraftItemStatus.NO_NEEDS, "", []),
            (DRAFTED, DraftItemStatus.DRAFTED, "집필기가 쓴 글이다.", []),
            (3, DraftItemStatus.UNWRITTEN, "", []),
            (BLANK, DraftItemStatus.BLANK, "", ["team"]),
        ]):
            s.add(DraftItem(id=iid + 1, draft_id=1, document_item_id=item_id,
                            ordinal=iid, status=str(status), body=body,
                            missing=missing, missing_optional=[]))
        s.flush()
        s.add(DraftEvidence(draft_item_id=2, paragraph=0, fact_id=1,
                            chunk_id=c.id, source_type="document"))
        s.commit()
    yield factory


def _edit(factory, item_id: int, text: str | None):  # noqa: ANN001, ANN202
    with factory() as s:
        out = draft_service.edit_item(s, COMPANY, "bizinfo", NOTICE, item_id, text)
        s.commit()
        return out


def _row(factory, item_id: int) -> DraftItem:
    with factory() as s:
        return s.scalars(
            select(DraftItem).where(DraftItem.document_item_id == item_id)
        ).one()


def _read(factory, item_id: int):  # noqa: ANN001, ANN202
    out = draft_service.notice_draft
    with factory() as s:
        got = out(s, COMPANY, "bizinfo", NOTICE)
    flat = {i.document_item_id: i for d in got.documents for i in _walk(d.items)}
    return flat[item_id]


def _walk(items):  # noqa: ANN001, ANN202
    for i in items:
        yield i
        yield from _walk(i.children)


class Test집필_출력을_안_덮는다:
    def test_body_가_그대로_남는다(self, db) -> None:  # noqa: ANN001
        """**되돌릴 자리다.** 덮어쓰면 집필기의 글을 영영 못 찾는다."""
        _edit(db, DRAFTED, "사람이 고쳐 쓴 글이다.")

        row = _row(db, DRAFTED)
        assert row.body == "집필기가 쓴 글이다."
        assert row.edited_body == "사람이 고쳐 쓴 글이다."

    def test_화면이_고친_글을_본다(self, db) -> None:  # noqa: ANN001
        _edit(db, DRAFTED, "사람이 고쳐 쓴 글이다.")
        item = _read(db, DRAFTED)

        assert [p.text for p in item.paragraphs] == ["사람이 고쳐 쓴 글이다."]
        assert item.edited is True
        assert item.original == "집필기가 쓴 글이다."

    def test_되돌리면_집필기의_글이_돌아온다(self, db) -> None:  # noqa: ANN001
        """`text: null` 이 되돌리기다. **원본이 안 지워졌으니 된다.**"""
        _edit(db, DRAFTED, "사람이 고쳐 쓴 글이다.")
        _edit(db, DRAFTED, None)
        item = _read(db, DRAFTED)

        assert [p.text for p in item.paragraphs] == ["집필기가 쓴 글이다."]
        assert item.edited is False
        assert item.original is None
        assert _row(db, DRAFTED).edited_at is None


class Test빈_문자열과_None_이_다르다:
    def test_빈_문자열은_일부러_비운_것이다(self, db) -> None:  # noqa: ANN001
        """**섞으면 지운 항목에 초안이 다시 나타난다**(ADR-0055 결정 6)."""
        item = _edit(db, DRAFTED, "")

        assert item.edited is True
        assert item.paragraphs == []
        assert _row(db, DRAFTED).edited_body == ""

    def test_빈_문자열에도_고친_시각이_남는다(self, db) -> None:  # noqa: ANN001
        _edit(db, DRAFTED, "")

        assert _row(db, DRAFTED).edited_at is not None


class Test근거:
    def test_고치면_문단_근거를_안_낸다(self, db) -> None:  # noqa: ANN001
        """사람이 고친 문장 옆에 「이 사실에서 나왔어요」를 적으면 **거짓이 될 수 있다.**"""
        assert _read(db, DRAFTED).paragraphs[0].evidence  # 고치기 전에는 있다

        _edit(db, DRAFTED, "사람이 고쳐 쓴 글이다.")
        item = _read(db, DRAFTED)

        assert all(not p.evidence for p in item.paragraphs)
        assert item.evidence_detached is True

    def test_draft_evidence_행은_안_지운다(self, db) -> None:  # noqa: ANN001
        """**ADR-0028 4번의 파급 계산이 이 행으로 돈다.** 화면에만 안 낸다."""
        _edit(db, DRAFTED, "사람이 고쳐 쓴 글이다.")

        with db() as s:
            assert s.scalars(select(DraftEvidence)).all()

    def test_되돌리면_근거가_다시_붙는다(self, db) -> None:  # noqa: ANN001
        _edit(db, DRAFTED, "고침")
        _edit(db, DRAFTED, None)
        item = _read(db, DRAFTED)

        assert item.paragraphs[0].evidence
        assert item.evidence_detached is False

    def test_근거가_없던_항목은_떨어질_것도_없다(self, db) -> None:  # noqa: ANN001
        """`evidence_detached` 는 **떨어진 근거가 있을 때만** 참이다."""
        item = _edit(db, BLANK, "빈 자리에 사람이 직접 썼다.")

        assert item.edited is True
        assert item.evidence_detached is False


class Test상태를_안_바꾼다:
    def test_blank_가_blank_로_남는다(self, db) -> None:  # noqa: ANN001
        """**`drafted` 로 올리면 물어볼 목록에서 조용히 빠진다**(F6-6)."""
        item = _edit(db, BLANK, "사람이 직접 채웠다.")

        assert item.status == str(DraftItemStatus.BLANK)
        assert _row(db, BLANK).status == str(DraftItemStatus.BLANK)

    def test_못_채운_자리도_그대로_남는다(self, db) -> None:  # noqa: ANN001
        """`missing` 은 위키에 무엇이 없나이지 **이 칸이 비었나가 아니다.**"""
        item = _edit(db, BLANK, "사람이 직접 채웠다.")

        assert [m.place for m in item.missing] == ["team"]


class Test분량:
    def test_고친_글로_잰다(self, db) -> None:  # noqa: ANN001
        """`1-1` 이 100자 제한이다. **집필기 글로 재면 넘겨 써도 `ok` 로 앉는다.**"""
        item = _edit(db, 2, "가" * 200)

        assert item.length.verdict == "over"
        assert item.length.measured == 200


class Test없는_항목:
    def test_없으면_ItemNotFound_다(self, db) -> None:  # noqa: ANN001
        """**404 로 나간다.** 조회와 반대다 — 없는 항목에 쓰라는 요청이라
        원인이 요청 쪽에 있다."""
        with db() as s, pytest.raises(draft_service.ItemNotFound):
            draft_service.edit_item(s, COMPANY, "bizinfo", NOTICE, 999, "글")

    def test_다른_회사의_항목을_못_고친다(self, db) -> None:  # noqa: ANN001
        """**격리가 `company_id` 하나에 걸려 있다.**"""
        with db() as s, pytest.raises(draft_service.ItemNotFound):
            draft_service.edit_item(s, "c_남", "bizinfo", NOTICE, DRAFTED, "글")


class Test진행:
    def test_running_은_부르는_쪽이_준다(self, db) -> None:  # noqa: ANN001
        """**이 모듈은 `jobs` 를 모른다.** 그래야 세션만 있으면 테스트가 돈다."""
        with db() as s:
            assert draft_service.notice_draft(s, COMPANY, "bizinfo", NOTICE).running is False
            got = draft_service.notice_draft(s, COMPANY, "bizinfo", NOTICE, running=True)
        assert got.running is True
