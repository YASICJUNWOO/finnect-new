"""위키 지우기 — [ADR-0072](../docs/adr/0072-위키-지우기를-운영-화면에-연다.md).

**여기서 잠그는 것 여섯.**

1. **목록의 모수가 위키 쪽 표다.** 초안·판정만 남은 회사는 안 선다 — 이 버튼이 그
   둘을 안 지우므로, 세워 두면 눌러도 아무 일도 안 일어난다
2. **`x-ingest-trigger-token` 이 지킨다.** 수집·첨부와 **같은 문**이다(ADR-0071 결정 3)
3. **행과 원본 파일이 같이 없어진다.** 행만 지우면 디스크에 고아가 남고, 그 파일은
   가리키는 행이 없어 아무도 못 찾는다
4. **초안과 판정은 남는다.** 사람이 고친 글이 초안에 있다(ADR-0055)
5. **세우는 중이면 409 다.** 202 에 `started: false` 가 아니다 — 여기는 시작할 것이
   없고, 안 지웠으면 그것은 성공이 아니다
6. **`CASCADE` 가 근거를 데려간다.** 사실이 없어지면 그 사실을 인용한 `draft_evidence`
   도 없어져야 한다 — 안 그러면 초안이 없는 사실을 근거로 든다

**FK 를 켠다.** SQLite 는 기본이 꺼짐이라 6번이 로컬에서만 통과한다
(`tests/test_draft_service.py` 와 같은 자리).
"""

from __future__ import annotations

import base64
import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from finnect.api import admin_service
from finnect.api import app as api
from finnect.config import settings
from finnect.ingest import jobs
from finnect.models import (
    Base,
    Chunk,
    CompanyAccount,
    CompanyValue,
    Document,
    DocumentItem,
    DocumentKind,
    Draft,
    DraftEvidence,
    DraftItem,
    DraftItemStatus,
    NoticeFit,
    UserFile,
    UserFileStatus,
    ValueEvidence,
    WikiEvidence,
    WikiFact,
    WikiNode,
)
from finnect.wiki import storage

COMPANY = "c_purge"
#: 초안만 있고 위키가 없는 회사. **목록에 서면 안 된다**
DRAFT_ONLY = "c_draftonly"
USER = "운영자"
PASSWORD = "비밀!@#"
#: **ASCII 다.** HTTP 헤더 값이라 한글을 못 싣는다 — Basic 쪽은 base64 라 상관없다
TRIGGER = "trigger-token"
SHA = storage.digest("원본 바이트".encode())

#: 「세우는 중」을 만들려면 **안 끝나는 일**이 필요하다. 테스트가 끝낼 수 있게 문을 둔다
_GATE = threading.Event()


def _wait() -> None:
    _GATE.wait(5)

TABLES = [
    CompanyAccount, UserFile, Chunk, WikiNode, WikiFact, CompanyValue,
    WikiEvidence, ValueEvidence, Document, DocumentItem, Draft, DraftItem,
    DraftEvidence, NoticeFit,
]


def _basic() -> dict[str, str]:
    raw = base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
    return {"authorization": f"Basic {raw}"}


def _headers(token: str | None = TRIGGER) -> dict[str, str]:
    h = _basic()
    if token is not None:
        h["x-ingest-trigger-token"] = token
    return h


@pytest.fixture
def db(monkeypatch, tmp_path):  # noqa: ANN001, ANN201
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    # **FK 를 켠다.** 꺼져 있으면 `draft_evidence` 가 사실과 함께 안 지워지고,
    # 그 차이가 **배포 DB 에서만** 나타난다.
    @event.listens_for(engine, "connect")
    def _fk_on(conn, _rec) -> None:  # noqa: ANN001
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine, tables=[t.__table__ for t in TABLES])
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    with factory() as s:
        s.add(CompanyAccount(company_id=COMPANY, name="나린데이터", password="pw"))
        s.add(UserFile(id=1, company_id=COMPANY, sha256=SHA, filename="회사소개서.pdf",
                       byte_size=10, ext="pdf", status=str(UserFileStatus.DONE),
                       chunk_count=1))
        s.flush()
        s.add(Chunk(id=1, user_file_id=1, company_id=COMPANY, ordinal=0,
                    text="우리는 2024년 매출 1억을 냈다", chars=20,
                    char_start=0, char_end=20))
        s.add(WikiNode(id=1, company_id=COMPANY, path="Financial/매출.md",
                       category="Financial", name="매출.md", parent="Financial",
                       norm_path="Financial/매출.md"))
        s.flush()
        s.add(WikiFact(id=1, company_id=COMPANY, node_id=1, text="2024년 매출 1억",
                       dedupe_key="Financial/매출.md|2024|2024년 매출 1억",
                       extractor="stub/v1"))
        s.flush()
        s.add(WikiEvidence(id=1, company_id=COMPANY, fact_id=1, chunk_id=1,
                           user_file_id=1, quote="매출 1억"))

        # 초안 — **안 지워야 한다.** 근거만 사실과 함께 없어진다
        s.add(Document(id=1, sha256=SHA, seq=1, title="사업계획서",
                       kind=str(DocumentKind.NARRATIVE), char_start=0, char_end=10,
                       decided_by="llm/gpt-5.6-luna"))
        s.flush()
        s.add(DocumentItem(id=1, document_id=1, parent_id=None, ordinal=0,
                           number="1", title="목적", instruction=None,
                           limit_text=None, input_kind="narrative"))
        s.add(Draft(id=1, company_id=COMPANY, notice_id="PBLN-1", source="bizinfo",
                    document_id=1, allotment={}, allotted_by="none"))
        s.flush()
        s.add(DraftItem(id=1, draft_id=1, document_item_id=1, ordinal=0,
                        status=str(DraftItemStatus.DRAFTED), body="사람이 고친 글이다.",
                        missing=[], missing_optional=[]))
        s.flush()
        s.add(DraftEvidence(id=1, draft_item_id=1, paragraph=0, fact_id=1, chunk_id=1))
        s.add(NoticeFit(id=1, company_id=COMPANY, source="bizinfo",
                        external_id="PBLN-1", verdict="맞다", reason="맞아요"))

        # 위키가 없고 초안만 있는 회사. **목록에 서면 안 된다**
        s.add(Draft(id=2, company_id=DRAFT_ONLY, notice_id="PBLN-2", source="bizinfo",
                    document_id=1, allotment={}, allotted_by="none"))
        s.commit()

    # 원본 파일도 실제로 깐다. **행만 보고 지웠다고 하면 디스크에 고아가 남는다**
    monkeypatch.setattr(settings, "user_file_dir", tmp_path)
    storage.put(COMPANY, "원본 바이트".encode())

    monkeypatch.setattr(api, "SessionFactory", factory)
    monkeypatch.setattr(settings, "admin_user", USER)
    monkeypatch.setattr(settings, "admin_password", PASSWORD)
    monkeypatch.setattr(settings, "ingest_trigger_token", TRIGGER)
    monkeypatch.setattr(settings, "api_token", "")
    monkeypatch.setattr(jobs, "_locks", {})
    monkeypatch.setattr(jobs, "_progress", {})

    with TestClient(app=api.app) as c:
        yield c, factory



class Test목록:
    def test_이름이_붙는다(self, db) -> None:  # noqa: ANN001
        """입장 게이트로 들어온 회사는 `company_id` 가 아니라 이름으로 보여야 한다 —
        운영자가 시연에서 찾는 것이 「나린데이터」이지 `c_purge` 가 아니다."""
        c, _ = db
        rows = c.get("/api/admin/wiki", headers=_basic()).json()["companies"]

        assert [r["name"] for r in rows] == ["나린데이터"]

    def test_초안만_있는_회사는_안_선다(self, db) -> None:  # noqa: ANN001
        """**이 버튼이 초안을 안 지운다.** 세워 두면 눌러도 아무 일이 안 일어난다."""
        c, _ = db
        rows = c.get("/api/admin/wiki", headers=_basic()).json()["companies"]

        assert DRAFT_ONLY not in {r["company_id"] for r in rows}

    def test_안_지우는_것을_같이_센다(self, db) -> None:  # noqa: ANN001
        """화면이 「초안 1 · 판정 1 은 남아요」를 적으려면 이 숫자가 있어야 한다."""
        c, _ = db
        row = c.get("/api/admin/wiki", headers=_basic()).json()["companies"][0]

        assert (row["drafts"], row["fits"]) == (1, 1)

    def test_읽기는_실행_토큰을_안_묻는다(self, db) -> None:  # noqa: ANN001
        """보는 것과 지우는 것은 다른 문이다. 목록까지 토큰을 물으면 **무엇을 지울지
        모르는 채로 토큰을 치게 된다.**"""
        c, _ = db

        assert c.get("/api/admin/wiki", headers=_basic()).status_code == 200


class Test문:
    def test_토큰이_없으면_401_이다(self, db) -> None:  # noqa: ANN001
        c, _ = db
        r = c.post(f"/api/admin/wiki/purge/{COMPANY}", headers=_headers(token=None))

        assert r.status_code == 401

    def test_토큰이_틀리면_401_이다(self, db) -> None:  # noqa: ANN001
        c, _ = db
        r = c.post(f"/api/admin/wiki/purge/{COMPANY}", headers=_headers("wrong-token"))

        assert r.status_code == 401

    def test_운영_자격이_없으면_401_이다(self, db) -> None:  # noqa: ANN001
        """**문이 둘이다.** 실행 토큰만 들고 있어도 운영 경로를 못 지난다(ADR-0067)."""
        c, _ = db
        r = c.post(
            f"/api/admin/wiki/purge/{COMPANY}",
            headers={"x-ingest-trigger-token": TRIGGER},
        )

        assert r.status_code == 401

    def test_401_일_때_아무것도_안_지운다(self, db) -> None:  # noqa: ANN001
        """**문이 열리기 전에 지우면 문이 없는 것이다.**"""
        c, factory = db
        c.post(f"/api/admin/wiki/purge/{COMPANY}", headers=_headers("wrong-token"))

        with factory() as s:
            assert s.scalar(select(UserFile).where(UserFile.company_id == COMPANY)) is not None

    def test_실행_토큰이_비어_있으면_503_이다(self, db, monkeypatch) -> None:  # noqa: ANN001
        """`api_token` 과 반대다 — 잊고 비워 뒀을 때 **닫히는 쪽**이어야 한다."""
        c, _ = db
        monkeypatch.setattr(settings, "ingest_trigger_token", "")
        r = c.post(f"/api/admin/wiki/purge/{COMPANY}", headers=_headers())

        assert r.status_code == 503


class Test지우기:
    def test_위키가_통째로_없어진다(self, db) -> None:  # noqa: ANN001
        c, factory = db
        r = c.post(f"/api/admin/wiki/purge/{COMPANY}", headers=_headers())

        assert r.status_code == 200
        with factory() as s:
            for model in (UserFile, Chunk, WikiFact, WikiNode, CompanyValue, WikiEvidence):
                left = s.scalars(select(model).where(model.company_id == COMPANY)).all()
                assert left == [], model.__tablename__

    def test_원본_파일도_없어진다(self, db) -> None:  # noqa: ANN001
        """**행만 지우면 디스크에 고아가 남는다.** 그 파일은 가리키는 행이 없어 아무도
        못 찾고, 개인정보라 남아 있으면 안 된다(ADR-0029)."""
        c, _ = db
        assert storage.abs_path(COMPANY, SHA).exists(), "깔아 둔 원본이 없으면 이 시험이 헛돈다"
        r = c.post(f"/api/admin/wiki/purge/{COMPANY}", headers=_headers())

        assert r.json()["storage"] is True
        assert not (settings.user_file_dir / COMPANY).exists()

    def test_몇_건을_지웠는지_답한다(self, db) -> None:  # noqa: ANN001
        """**「지웠어요」만으로는 뭘 지웠는지 모른다.** 화면이 이 숫자를 그대로 읽는다."""
        c, _ = db
        body = c.post(f"/api/admin/wiki/purge/{COMPANY}", headers=_headers()).json()

        assert (body["company_id"], body["files"], body["facts"]) == (COMPANY, 1, 1)

    def test_초안과_판정은_남는다(self, db) -> None:  # noqa: ANN001
        """**사람이 고친 글이 초안에 있다**(ADR-0055). 지우는 자리는 화면의
        「초기화」다(ADR-0062)."""
        c, factory = db
        c.post(f"/api/admin/wiki/purge/{COMPANY}", headers=_headers())

        with factory() as s:
            assert s.get(Draft, 1) is not None
            assert s.get(DraftItem, 1) is not None
            assert s.get(NoticeFit, 1) is not None

    def test_사실을_인용한_근거는_같이_없어진다(self, db) -> None:  # noqa: ANN001
        """**FK 가 `CASCADE` 다.** 안 지워지면 초안이 **없는 사실**을 근거로 든다."""
        c, factory = db
        c.post(f"/api/admin/wiki/purge/{COMPANY}", headers=_headers())

        with factory() as s:
            assert s.get(DraftEvidence, 1) is None

    def test_두_번_눌러도_안_터진다(self, db) -> None:  # noqa: ANN001
        """지울 것이 없는 것은 오류가 아니다. **0 건으로 답한다.**"""
        c, _ = db
        c.post(f"/api/admin/wiki/purge/{COMPANY}", headers=_headers())
        again = c.post(f"/api/admin/wiki/purge/{COMPANY}", headers=_headers())

        assert again.status_code == 200
        assert again.json() == {
            "company_id": COMPANY, "files": 0, "facts": 0, "storage": False
        }

    def test_쓸_수_없는_id_는_400_이다(self, db) -> None:  # noqa: ANN001
        """경로에 들어가는 값이라 모양을 제한한다(ADR-0029 · `_COMPANY_ID`)."""
        c, _ = db
        r = c.post("/api/admin/wiki/purge/c_bad.id", headers=_headers())

        assert r.status_code == 400


class Test세우는_중:
    def test_이_프로세스에서_세우고_있으면_409_다(self, db) -> None:  # noqa: ANN001
        """**해독 단계에는 어드바이저리 락이 아직 안 잡혀 있다.** 이것 없이는 읽는
        중인 파일이 지워진다.

        **409 다.** 수집·첨부의 「이미 돌고 있어요」는 202 에 `started: false` 인데
        저건 시작하는 일이라 "안 시작했다" 가 답이 된다 — 여기는 시작할 것이 없다.
        """
        c, factory = db
        launched = jobs.launch(f"wiki:{COMPANY}", lambda: _wait())

        assert launched.started
        r = c.post(f"/api/admin/wiki/purge/{COMPANY}", headers=_headers())
        _GATE.set()

        assert r.status_code == 409
        with factory() as s:
            assert s.get(UserFile, 1) is not None



class Test읽기_계약:
    def test_admin_service_가_파서를_안_끌고_온다(self) -> None:
        """`wikis()` 를 저기 둔 이유다 — 모델만 읽는다. 지우는 쪽은 `app.py` 가 들고
        **함수 안에서** 임포트한다(`tests/test_admin_api.py` 와 같은 규율)."""
        import ast
        from pathlib import Path

        src = Path(admin_service.__file__).read_text(encoding="utf-8")
        names: set[str] = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                names |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)

        assert not (names & {"finnect.attach.service", "finnect.ingest.service",
                             "finnect.wiki.service", "httpx"})
