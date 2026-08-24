"""시연 스냅샷이 회사 여럿에 앉는다 (`wiki/demo.py` · 2026-08-24).

**임시 코드에 테스트를 붙인 자리다.** 붙인 이유는 이 결함이 **시연 당일에만 나오는
모양**이라서다 — 입장 게이트(ADR-0066)가 사람마다 `company_id` 를 발급하기 시작한 뒤로,
ID 를 그대로 앉히던 스냅샷은 **둘째 사람의 올리기에서 `duplicate key … user_file_pkey`**
였다. 스텁으로도 `--score` 로도 안 걸리고, 회사 하나로 재 보면 통과한다.

1. 회사 둘에 같은 스냅샷이 앉는다 — ID 가 서로도 원본과도 안 겹친다
2. 근거가 **제 회사** 청크·사실·파일을 가리킨다 (FK 를 다시 이었다)
3. 앉혀도 **뜬 회사 것은 그대로다** — `clear()` 가 앉을 회사만 지운다
4. 같은 회사에 두 번 앉히면 안 늘어난다
5. 참조가 끊긴 스냅샷은 **말하고 멈춘다** (FK 없는 SQLite 에서 조용히 서면 안 된다)
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

import wikifix
from finnect.models import (
    Base,
    Chunk,
    CompanyValue,
    UserFile,
    UserFileStatus,
    ValueEvidence,
    WikiEvidence,
    WikiFact,
    WikiNode,
)
from finnect.wiki import demo

#: 스냅샷을 뜬 회사. 시연 DB 에는 `c_narin` 이고, **그 행이 남아 있는 것이 요점이다**
SRC = "c_src"


def _seed(s: Session, company_id: str) -> None:
    """파일 하나 · 청크 둘 · 사실 하나 · 값 하나 · 근거 둘. 표 일곱이 다 찬다."""
    uf = UserFile(
        company_id=company_id,
        sha256="a" * 64,
        filename="회사소개.pdf",
        byte_size=1024,
        ext="pdf",
        status=str(UserFileStatus.DONE),
    )
    s.add(uf)
    s.flush()

    chunks = []
    for i, text in enumerate(["나린데이터는 2026년 6월에 문을 열었어요.", "직원은 셋이에요."]):
        c = Chunk(
            user_file_id=uf.id,
            company_id=company_id,
            ordinal=i,
            text=text,
            chars=len(text),
            char_start=0,
            char_end=len(text),
        )
        s.add(c)
        chunks.append(c)
    s.flush()

    fact = wikifix.fact(s, company_id, "Company/팀.md", "직원은 셋이다")
    value = wikifix.value(s, company_id, "headcount", "3")
    s.add(
        WikiEvidence(
            company_id=company_id,
            fact_id=fact.id,
            chunk_id=chunks[1].id,
            user_file_id=uf.id,
            quote="직원은 셋이에요.",
        )
    )
    s.add(
        ValueEvidence(
            company_id=company_id,
            value_id=value.id,
            chunk_id=chunks[1].id,
            user_file_id=uf.id,
            quote="직원은 셋이에요.",
        )
    )
    s.flush()


@pytest.fixture
def db():  # noqa: ANN201
    engine = create_engine("sqlite://")

    # **FK 를 켠다.** 기본이 꺼짐이라 끊긴 참조가 그냥 들어간다 — 그러면 이 테스트가
    # 재려는 것(근거가 제 회사를 가리키나)이 SQLite 에서만 통과한다.
    @event.listens_for(engine, "connect")
    def _fk_on(conn, _rec) -> None:  # noqa: ANN001
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine, tables=[m.__table__ for m in demo.TABLES])
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with factory() as s:
        _seed(s, SRC)
        s.commit()
        yield s


def _rows(s: Session, model: Any, company_id: str) -> list[Any]:
    return list(s.scalars(select(model).where(model.company_id == company_id)).all())


def test_회사_둘에_앉는다(db: Session) -> None:
    snap = demo.take(db, SRC)

    demo.put(db, "c_a", snap)
    demo.put(db, "c_b", snap)
    db.commit()

    for company in ("c_a", "c_b"):
        assert len(_rows(db, UserFile, company)) == 1
        assert len(_rows(db, Chunk, company)) == 2
        assert len(_rows(db, WikiFact, company)) == 1
        assert len(_rows(db, CompanyValue, company)) == 1
        assert len(_rows(db, WikiEvidence, company)) == 1
        assert len(_rows(db, ValueEvidence, company)) == 1

    ids = {c: {r.id for r in _rows(db, UserFile, c)} for c in (SRC, "c_a", "c_b")}
    assert ids["c_a"] & ids["c_b"] == set()
    assert ids["c_a"] & ids[SRC] == set()


def test_근거가_제_회사를_가리킨다(db: Session) -> None:
    snap = demo.take(db, SRC)
    demo.put(db, "c_a", snap)
    demo.put(db, "c_b", snap)
    db.commit()

    for company in (SRC, "c_a", "c_b"):
        for chunk in _rows(db, Chunk, company):
            assert db.get(UserFile, chunk.user_file_id).company_id == company
        for fact in _rows(db, WikiFact, company):
            assert db.get(WikiNode, fact.node_id).company_id == company
        for ev in _rows(db, WikiEvidence, company):
            assert db.get(WikiFact, ev.fact_id).company_id == company
            assert db.get(Chunk, ev.chunk_id).company_id == company
            assert db.get(UserFile, ev.user_file_id).company_id == company
        for ev in _rows(db, ValueEvidence, company):
            assert db.get(CompanyValue, ev.value_id).company_id == company
            assert db.get(Chunk, ev.chunk_id).company_id == company
            assert db.get(UserFile, ev.user_file_id).company_id == company


def test_뜬_회사_것은_그대로다(db: Session) -> None:
    before = demo.take(db, SRC)

    demo.put(db, "c_a", before)
    db.commit()

    assert demo.take(db, SRC) == before


def test_두_번_앉혀도_안_늘어난다(db: Session) -> None:
    snap = demo.take(db, SRC)

    demo.put(db, "c_a", snap)
    db.commit()

    counts = demo.put(db, "c_a", snap)
    db.commit()

    # **ID 가 같은지는 안 잰다.** 지우고 다시 넣으므로 SQLite 는 비운 자리를 되쓰고
    # Postgres 는 시퀀스를 이어 간다 — 화면이 보는 것은 회사뿐이라 어느 쪽이든 된다
    assert counts["user_file"] == 1
    assert len(_rows(db, UserFile, "c_a")) == 1
    assert len(_rows(db, WikiEvidence, "c_a")) == 1


def test_참조가_끊기면_말한다(db: Session) -> None:
    snap = demo.take(db, SRC)
    snap["chunk"][0]["user_file_id"] = 9999

    with pytest.raises(demo.SnapshotError) as got:
        demo.put(db, "c_a", snap)
    db.rollback()

    assert "chunk.user_file_id" in str(got.value)
