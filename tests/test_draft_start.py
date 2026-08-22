"""초안 만들기·고치기 경로 — plan/21 T-0121 · T-0123 · [ADR-0054](
../docs/adr/0054-초안을-만드는-길을-api-에-열고-공고-회사-단위로-잠근다.md).

**쓰기 경로가 하나에서 셋이 됐다.** 올리기(plan/15) · 초안 만들기 · 초안 고치기다.
여기서 잠그는 것 여섯.

1. **202 다.** 다 쓰고 답하면 요청이 몇 분씩 묶인다
2. **두 번 누르면 둘째가 거절된다. 오류가 아니다** — 두 번 누른 사람에게 보여 줄
   것은 오류가 아니라 지금 돌고 있다는 사실이다
3. **락이 `(회사, 공고)` 다.** 같은 회사가 공고 둘을 같이 쓰는 것은 안 막는다
4. **락 키에 `hash()` 를 안 쓴다** — `PYTHONHASHSEED` 가 프로세스마다 달라
   둘 다 통과한다(plan/12 T-0094 가 밟은 함정)
5. **`finnect.draft` 를 함수 안에서 임포트한다.** 최상단에 두면 `llm` 과 `httpx` 가
   딸려 와 읽기만 담은 배포본에서 죽는다
6. **`PUT` 이 CORS 에 열려 있다.** 안 열면 브라우저 preflight 에서 막힌다

집필기를 실제로 안 부른다 — `_write_draft` 를 갈아 끼운다. **키를 태우지 않는다.**
"""

from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from finnect.api import app as api
from finnect.ingest import jobs
from finnect.models import (
    Attachment,
    AttachmentFile,
    Base,
    CompanyValue,
    Document,
    DocumentItem,
    DocumentKind,
    Draft,
    DraftEvidence,
    DraftItem,
    DraftItemStatus,
    ItemNeed,
    ParseStatus,
    ValueEvidence,
    WikiEvidence,
    WikiFact,
    WikiNode,
)
from finnect.views import Notice

COMPANY = "c_start"
NOTICE = "PBLN-START"
OTHER = "PBLN-다른공고"
SHA = "a" * 64
ITEM = 1

TABLES = [
    Notice, Attachment, AttachmentFile, Document, DocumentItem, ItemNeed,
    Draft, DraftItem, DraftEvidence, WikiFact, WikiNode, CompanyValue, ValueEvidence, WikiEvidence,
]


@pytest.fixture
def client(monkeypatch):  # noqa: ANN001, ANN201
    # **`StaticPool` 이 필요하다.** 메모리 SQLite 는 연결마다 다른 DB 라, 없으면
    # 라우트가 새 세션을 열 때 빈 DB 를 본다("no such table"). 스레드도 같이 쓴다.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine, tables=[t.__table__ for t in TABLES])
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    with factory() as s:
        for ext in (NOTICE, OTHER):
            s.add(Notice(source="bizinfo", external_id=ext, title=f"공고 {ext}"))
        s.add(Attachment(id=1, source="bizinfo", external_id=NOTICE, url="u1",
                         position=0, kind="file", filename="서식.hwp", ext="hwp"))
        s.add(AttachmentFile(id=1, url="u1", source="bizinfo", sha256=SHA,
                             fetch_status="ok", parse_status=str(ParseStatus.OK)))
        s.add(Document(id=1, sha256=SHA, seq=1, title="사업계획서",
                       kind=str(DocumentKind.NARRATIVE), char_start=0, char_end=10,
                       decided_by="llm/gpt-5.6-luna"))
        s.flush()
        s.add(DocumentItem(id=ITEM, document_id=1, parent_id=None, ordinal=0,
                           number="1", title="목적", instruction=None,
                           limit_text=None, input_kind="narrative"))
        s.add(Draft(id=1, company_id=COMPANY, notice_id=NOTICE, source="bizinfo",
                    document_id=1, allotment={}, allotted_by="none"))
        s.flush()
        s.add(DraftItem(id=1, draft_id=1, document_item_id=ITEM, ordinal=0,
                        status=str(DraftItemStatus.DRAFTED), body="집필기의 글이다.",
                        missing=[], missing_optional=[]))
        s.commit()

    monkeypatch.setattr(api, "SessionFactory", factory)
    # 락은 프로세스 전역이다. 테스트끼리 새게 두면 둘째 테스트가 먼저 것의 락을 본다.
    monkeypatch.setattr(jobs, "_locks", {})
    monkeypatch.setattr(jobs, "_progress", {})

    with TestClient(app=api.app) as c:
        yield c, factory


def _hold(monkeypatch):  # noqa: ANN001, ANN202
    """집필기 자리에 **안 끝나는 일**을 끼운다. 「돌고 있다」를 만들려면 필요하다."""
    gate = threading.Event()
    monkeypatch.setattr(api, "_write_draft", lambda *a: gate.wait(5))
    return gate


def _post(c, ext: str = NOTICE):  # noqa: ANN001, ANN202
    return c.post(f"/api/notices/bizinfo/{ext}/draft", params={"company": COMPANY})


class Test시작:
    def test_202_로_답한다(self, client, monkeypatch) -> None:  # noqa: ANN001
        """**시작만 하고 답한다.** 항목 수십 개를 다 쓰고 답하면 요청이 묶인다."""
        c, _ = client
        gate = _hold(monkeypatch)
        try:
            r = _post(c)
            assert r.status_code == 202
            assert r.json()["started"] is True
        finally:
            gate.set()

    def test_시작하면_진행이_같이_온다(self, client, monkeypatch) -> None:  # noqa: ANN001
        """화면이 누른 직후를 그대로 그린다 — **한 번 더 물어보지 않는다.**"""
        c, _ = client
        gate = _hold(monkeypatch)
        try:
            body = _post(c).json()
            assert body["draft"]["running"] is True
            assert body["draft"]["documents"][0]["items"][0]["number"] == "1"
        finally:
            gate.set()

    def test_company_없이는_못_부른다(self, client) -> None:  # noqa: ANN001
        """**두 코드가 다른 뜻이다.** 인자를 아예 안 주면 FastAPI 가 422 로 막고,
        빈 문자열은 우리가 400 으로 막는다 — 뒤쪽은 화면이 값을 못 채운 것이라
        원인이 다르다. **누구의 초안인지 모른 채로 돌리지 않는다.**"""
        c, _ = client
        assert c.post(f"/api/notices/bizinfo/{NOTICE}/draft").status_code == 422
        r = c.post(f"/api/notices/bizinfo/{NOTICE}/draft", params={"company": ""})
        assert r.status_code == 400

    def test_모르는_출처는_404_다(self, client) -> None:  # noqa: ANN001
        c, _ = client
        r = c.post("/api/notices/없는곳/X/draft", params={"company": COMPANY})
        assert r.status_code == 404


class Test락:
    def test_두_번_누르면_둘째가_거절된다(self, client, monkeypatch) -> None:  # noqa: ANN001
        """**오류가 아니다.** 409 로 올리면 화면이 오류 상태를 그리는데, 보여 줄
        것은 오류가 아니라 지금 돌고 있다는 사실이다."""
        c, _ = client
        gate = _hold(monkeypatch)
        try:
            _post(c)
            second = _post(c)

            assert second.status_code == 202
            assert second.json()["started"] is False
            assert second.json()["reason"]
            assert second.json()["draft"]["running"] is True
        finally:
            gate.set()

    def test_같은_회사의_다른_공고는_안_막힌다(self, client, monkeypatch) -> None:  # noqa: ANN001
        """**위키 빌드와 다르다**(ADR-0054 결정 3). `draft` 유니크 키가
        `(회사, 공고, 문서)` 라 경합할 자리가 없다."""
        c, _ = client
        gate = _hold(monkeypatch)
        try:
            _post(c, NOTICE)
            assert _post(c, OTHER).json()["started"] is True
        finally:
            gate.set()


class Test락_키:
    def test_공고까지_들어간다(self) -> None:
        a = api._draft_key(COMPANY, "bizinfo", NOTICE)
        b = api._draft_key(COMPANY, "bizinfo", OTHER)

        assert a != b
        assert COMPANY in a and NOTICE in a

    def test_출처가_다르면_다르다(self) -> None:
        """같은 번호가 두 출처에 있을 수 있다."""
        assert api._draft_key(COMPANY, "bizinfo", "X") != api._draft_key(
            COMPANY, "kstartup", "X"
        )

    def test_hash_를_안_쓴다(self) -> None:
        """**`PYTHONHASHSEED` 가 프로세스마다 달라 둘 다 통과한다**(T-0094).

        문자열이 그대로 들어 있으면 시드와 무관하다."""
        key = api._draft_key(COMPANY, "bizinfo", NOTICE)

        assert key == f"draft:{COMPANY}:bizinfo:{NOTICE}"


class Test고치기:
    def test_저장되고_다시_읽힌다(self, client) -> None:  # noqa: ANN001
        c, factory = client
        r = c.put(
            f"/api/notices/bizinfo/{NOTICE}/draft/items/{ITEM}",
            params={"company": COMPANY},
            json={"text": "사람이 고쳤다."},
        )

        assert r.status_code == 200
        assert r.json()["edited"] is True
        with factory() as s:
            row = s.scalars(select(DraftItem)).one()
        assert row.body == "집필기의 글이다."  # **안 덮는다**
        assert row.edited_body == "사람이 고쳤다."

    def test_되돌리기가_null_이다(self, client) -> None:  # noqa: ANN001
        c, _ = client
        path = f"/api/notices/bizinfo/{NOTICE}/draft/items/{ITEM}"
        c.put(path, params={"company": COMPANY}, json={"text": "고침"})
        r = c.put(path, params={"company": COMPANY}, json={"text": None})

        assert r.json()["edited"] is False
        assert r.json()["paragraphs"][0]["text"] == "집필기의 글이다."

    def test_없는_항목은_404_다(self, client) -> None:  # noqa: ANN001
        """**조회와 반대다** — 없는 항목에 쓰라는 요청이라 원인이 요청 쪽에 있다."""
        c, _ = client
        r = c.put(
            f"/api/notices/bizinfo/{NOTICE}/draft/items/9999",
            params={"company": COMPANY},
            json={"text": "글"},
        )

        assert r.status_code == 404


class Test배포_경계:
    def test_put_이_cors_에_열려_있다(self) -> None:
        """안 열면 브라우저 preflight 에서 막힌다. **로컬 서버 대 서버로는 안 걸려서
        늦게 잡힌다.**"""
        cors = [m for m in api.app.user_middleware if "CORS" in str(m)]
        assert cors, "CORS 미들웨어가 없다"
        assert "PUT" in cors[0].kwargs["allow_methods"]

    def test_쓰기_경로가_셋이다(self) -> None:
        """**늘어나면 여기가 먼저 깨진다.** 쓰기가 늘 때마다 계약 문서를 같이 고친다."""
        writes = {
            (r.path, m)
            for r in api.app.routes
            for m in getattr(r, "methods", set())
            if m in {"POST", "PUT", "PATCH", "DELETE"}
        }

        assert writes == {
            ("/api/wiki/{company_id}/files", "POST"),
            ("/api/notices/{source}/{external_id}/draft", "POST"),
            ("/api/notices/{source}/{external_id}/draft/items/{document_item_id}", "PUT"),
        }
