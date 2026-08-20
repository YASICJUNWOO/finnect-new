"""공고가 요구하는 서류 API — plan/11 T-0035~T-0037.

**트리를 잠근다.** T-0036 이 서술형 양식을 갈라 놓으면서 `document_item` 에 부모-자식이
생겼다(2026-08-20 현재 30개). 최상위만 내보내면 그 자식들이 화면에서 사라지고, 더 나쁘게는
`2 추진배경 및 목표` 가 잎이 되어 **가지에 쓰는 칸이 붙는다** — `FormFill` 의 `leafKeys` 가
자식 없는 항목을 쓰는 자리로 세기 때문이다. 그 칸에 쓴 글은 어느 항목의 것도 아니다.

같이 잠그는 것 둘.

1. **`unknown` 구간은 안 내보내고 세기만 한다.** 내보내면 공고문의 절이 작성 항목으로 보인다
2. **칸 채우기는 평평하다.** `fields` 에 트리를 만들면 199개짜리 양식이 접힌다

Postgres 없이 돈다 — 필요한 표만 SQLite 에 만든다.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from finnect.api import service
from finnect.models import (
    Attachment,
    AttachmentFile,
    Base,
    Document,
    DocumentItem,
    DocumentKind,
    ParseStatus,
)

NOTICE = "PBLN_000000000122724"
SHA_PLAN = "a" * 64
SHA_FORM = "b" * 64
SHA_ONLY = "c" * 64

TABLES = [Attachment, AttachmentFile, Document, DocumentItem]


def _att(i: int, sha: str, filename: str) -> list[object]:
    """첨부 하나와 그 파일. **공고와 문서는 표가 아니라 sha256 조인으로 붙는다**(ADR-0022)."""
    url = f"u{i}"
    return [
        Attachment(
            id=i, source="bizinfo", external_id=NOTICE, url=url,
            position=i, kind="file", filename=filename, ext="hwp",
        ),
        AttachmentFile(
            id=i, url=url, source="bizinfo", sha256=sha,
            fetch_status="ok", parse_status=str(ParseStatus.OK),
        ),
    ]


@pytest.fixture
def db():  # noqa: ANN201
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[t.__table__ for t in TABLES])
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    with factory() as s:
        # **id 를 손으로 준다.** `BigInteger` 기본키라 SQLite 가 자동증가를 안 시킨다.
        for row in (
            *_att(1, SHA_PLAN, "서식3 사업계획서.hwp"),
            *_att(2, SHA_FORM, "서식1 신청서.hwp"),
            *_att(3, SHA_ONLY, "공고문.hwp"),
        ):
            s.add(row)

        s.add(Document(
            id=1, sha256=SHA_PLAN, seq=1, title="서식 3 사업계획서",
            kind=str(DocumentKind.NARRATIVE), char_start=0, char_end=900,
            decided_by="llm/gpt-5.6-luna",
        ))
        s.add(Document(
            id=2, sha256=SHA_FORM, seq=1, title="서식 1 신청서",
            kind=str(DocumentKind.FIELDS), char_start=0, char_end=400,
            decided_by="rule/v1",
        ))
        # 아직 안 갈라 낸 구간. 예산 때문에 T-0036 이 일부만 돌았다
        s.add(Document(
            id=3, sha256=SHA_ONLY, seq=1, title="공고문",
            kind=str(DocumentKind.UNKNOWN), char_start=0, char_end=3208,
            decided_by="rule/v1",
        ))

        # 서술형. `ordinal` 은 문서 안에서 한 번만 매겨진다 — 형제 순서도 이것이다.
        # **`4` 를 `2` 보다 먼저 넣어 둔다** — 삽입 순서로 정렬되면 안 되기 때문이다
        s.add(DocumentItem(
            id=10, document_id=1, parent_id=None, ordinal=3, number="4",
            title="팀 구성", instruction="팀원 이력을 기재", input_kind="narrative",
        ))
        s.add(DocumentItem(
            id=11, document_id=1, parent_id=None, ordinal=0, number="2",
            title="추진배경 및 목표", instruction=None, input_kind="narrative",
        ))
        s.add(DocumentItem(
            id=12, document_id=1, parent_id=11, ordinal=2, number="2-2",
            title="지원필요성", instruction="애로사항 중심으로 기술",
            limit_text="5페이지 이내", input_kind="narrative",
        ))
        s.add(DocumentItem(
            id=13, document_id=1, parent_id=11, ordinal=1, number="2-1",
            title="사업수행 배경 및 목적", instruction="배경 및 필요성을 자세하게 기술",
            input_kind="narrative",
        ))

        for i, label in enumerate(["기 업 명", "대표자명", "사업자등록번호"]):
            s.add(DocumentItem(
                id=20 + i, document_id=2, parent_id=None, ordinal=i,
                number=None, title=label, instruction=None, input_kind="field",
            ))
        s.commit()
        yield factory


def _docs(db):  # noqa: ANN001, ANN202
    with db() as s:
        out = service.notice_documents(s, "bizinfo", NOTICE)
    assert out is not None
    return out


def test_서술형_항목이_트리로_온다(db):  # noqa: ANN001
    """자식을 안 내보내면 `2 추진배경 및 목표` 가 잎이 되고 가지에 쓰는 칸이 붙는다."""
    plan = next(d for d in _docs(db).documents if d.kind == str(DocumentKind.NARRATIVE))

    assert [i.number for i in plan.items] == ["2", "4"], "최상위는 둘이다"
    top = plan.items[0]
    assert [c.number for c in top.children] == ["2-1", "2-2"], "자식이 트리로 붙는다"
    assert top.children[0].instruction == "배경 및 필요성을 자세하게 기술"
    assert top.children[1].limit_text == "5페이지 이내"
    # 잎은 자식이 없어야 쓰는 자리가 된다
    assert all(c.children == [] for c in top.children)
    assert plan.items[1].children == [], "`4 팀 구성` 은 그 자체가 잎이다"


def test_형제_순서가_ordinal_이다(db):  # noqa: ANN001
    """삽입 순서도 `id` 순도 아니다. `4`(id 10)를 `2`(id 11)보다 먼저 넣어 뒀다."""
    plan = next(d for d in _docs(db).documents if d.kind == str(DocumentKind.NARRATIVE))
    assert [i.title for i in plan.items] == ["추진배경 및 목표", "팀 구성"]
    assert [c.title for c in plan.items[0].children] == [
        "사업수행 배경 및 목적",
        "지원필요성",
    ]


def test_칸_채우기는_평평하다(db):  # noqa: ANN001
    """트리를 만들면 199개짜리 양식이 접힌다. 라벨은 서로 부모가 아니다."""
    form = next(d for d in _docs(db).documents if d.kind == str(DocumentKind.FIELDS))
    assert [i.title for i in form.items] == ["기 업 명", "대표자명", "사업자등록번호"]
    assert all(i.children == [] for i in form.items)


def test_unknown_구간은_안_나오고_세기만_한다(db):  # noqa: ANN001
    """**모르는 것을 아는 척하지 않는다.** 내보내면 공고문 절이 작성 항목으로 보인다."""
    out = _docs(db)
    assert [d.id for d in out.documents] == [1, 2]
    assert out.undecided == 1
    assert out.submit_hint == [], "서류가 있으면 공고문에서 힌트를 안 긁는다"
