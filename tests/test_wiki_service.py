"""파일 하나를 받아 청크까지 — plan/12 T-0043 · T-0047.

**핵심은 파일별 독립이다**(SPEC F1-1-8). 다섯 중 하나가 읽히지 않아도 넷으로 위키가 서야
한다. 전체를 한 트랜잭션으로 묶으면 여기서 다 죽는다.

Postgres 없이 돈다. `user_file` 과 `chunk` 만 SQLite 에 만든다 — 다른 표는 JSONB 를 써서
SQLite 가 못 만들고, 이 두 표는 안 쓴다.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from finnect.config import settings
from finnect.models import Base, Chunk, UserFile, UserFileStatus
from finnect.wiki import service, storage

FIXTURES = Path(__file__).parent / "fixtures" / "wiki"
COMPANY = "c_test"


@pytest.fixture
def factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
    monkeypatch.setattr(settings, "user_file_dir", tmp_path / "files")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[UserFile.__table__, Chunk.__table__])
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def _fixture(name: str) -> Path:
    path = FIXTURES / name
    if not path.exists():
        pytest.skip(f"픽스처가 없다: {name}")
    return path


def test_읽을_수_있는_파일은_청크가_나오고_좌표를_들고_있다(factory) -> None:  # noqa: ANN001
    report = service.ingest_files(factory, COMPANY, [_fixture("회사소개서_v3.pdf")])

    assert report.done == 1
    assert report.chunks > 0

    with factory() as s:
        uf = s.scalar(select(UserFile))
        assert uf.status == UserFileStatus.CHUNKED
        assert uf.page_count == 4, "PDF 는 쪽을 안다"

        text = storage.read_text(COMPANY, uf.sha256)
        for c in s.scalars(select(Chunk).order_by(Chunk.ordinal)):
            assert text[c.char_start : c.char_end] == c.text, "좌표가 원문과 어긋난다"
            assert c.page is not None, "PDF 청크는 쪽 번호를 들고 있어야 한다"


def test_파일_하나가_실패해도_나머지가_완주한다(factory) -> None:  # noqa: ANN001
    """**부분 성공이 예외가 아니라 정상 상태다**(F1-1-8)."""
    paths = [
        _fixture("현장사진_파일럿매장.jpg"),  # 파서가 없다
        _fixture("회사소개서_v3.pdf"),  # 읽힌다
        _fixture("사업자등록증_스캔.pdf"),  # 글자가 0자다
        _fixture("성남시_시범사업_신청서.hwpx"),  # 읽힌다
    ]

    report = service.ingest_files(factory, COMPANY, paths)

    assert report.done == 2, "읽히는 둘이 통과해야 한다"
    assert report.failed == 1
    assert report.needs_review == 1
    assert report.chunks > 0
    assert len(report.problems) == 2, "못 읽은 것이 이유와 함께 남아야 한다"


def test_스캔본은_실패가_아니라_검토_대기다(factory) -> None:  # noqa: ANN001
    """포맷이 없는 것과 글자가 안 나온 것은 다르다. **스캔본은 OCR 이 붙으면 읽힌다**(T-0042)."""
    report = service.ingest_files(factory, COMPANY, [_fixture("사업자등록증_스캔.pdf")])

    assert report.needs_review == 1
    assert report.failed == 0
    with factory() as s:
        uf = s.scalar(select(UserFile))
        assert uf.status == UserFileStatus.NEEDS_REVIEW
        assert uf.text_chars == 0
        assert uf.chunk_count == 0


def test_같은_파일을_다시_올리면_청크가_두_벌_안_된다(factory) -> None:  # noqa: ANN001
    path = _fixture("회사소개서_v3.pdf")

    first = service.ingest_files(factory, COMPANY, [path])
    second = service.ingest_files(factory, COMPANY, [path])

    assert second.duplicate == 1
    assert second.done == 0
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(UserFile)) == 1
        assert s.scalar(select(func.count()).select_from(Chunk)) == first.chunks


def test_다른_회사_것은_안_보인다(factory, tmp_path: Path) -> None:  # noqa: ANN001
    """ADR-0029 의 검증 조건. A 사 파일을 B 사로 조회하면 못 찾아야 한다."""
    src = _fixture("회사소개서_v3.pdf")
    copy = tmp_path / src.name
    shutil.copy(src, copy)

    service.ingest_files(factory, "c_a", [src])
    service.ingest_files(factory, "c_b", [copy])

    with factory() as s:
        a = s.scalar(select(UserFile).where(UserFile.company_id == "c_a"))
        b = s.scalar(select(UserFile).where(UserFile.company_id == "c_b"))
        assert a.sha256 == b.sha256, "같은 내용이니 해시는 같다"
        assert a.id != b.id, "행은 따로여야 한다"

        # 원본도 두 벌이다 — 회사 사이 중복 제거를 안 한다(ADR-0029 4번)
        assert storage.abs_path("c_a", a.sha256) != storage.abs_path("c_b", b.sha256)
        assert storage.exists("c_a", a.sha256) and storage.exists("c_b", b.sha256)

        # 한쪽을 지워도 다른 쪽이 남는다
        storage.purge("c_a")
        assert storage.exists("c_a", a.sha256) is False
        assert storage.exists("c_b", b.sha256) is True


def test_쪽이_없는_포맷은_page_가_비어_있다(factory) -> None:  # noqa: ANN001
    service.ingest_files(factory, COMPANY, [_fixture("성남시_시범사업_신청서.hwpx")])

    with factory() as s:
        uf = s.scalar(select(UserFile))
        assert uf.page_count is None, "HWPX 에는 쪽이 없다"
        assert all(c.page is None for c in s.scalars(select(Chunk)))


def test_다시_쪼개도_원본을_안_읽는다(factory) -> None:  # noqa: ANN001
    """청킹 규칙을 고쳤을 때. `attach --redo` 와 같은 성격이다."""
    path = _fixture("성남시_시범사업_신청서.hwpx")
    service.ingest_files(factory, COMPANY, [path])

    with factory() as s:
        before = s.scalar(select(func.count()).select_from(Chunk))
        # 원본을 치워도 저장된 .txt 로 다시 쪼갤 수 있어야 한다
        uf = s.scalar(select(UserFile))
        storage.abs_path(COMPANY, uf.sha256).unlink()

        n = service.rechunk(s, COMPANY)
        s.commit()

        assert n > 0
        assert s.scalar(select(func.count()).select_from(Chunk)) == n
        assert before > 0


def test_읽을_파일이_없으면_조용히_끝난다(factory) -> None:  # noqa: ANN001
    report = service.ingest_files(factory, COMPANY, [])

    assert report.files == 0
    assert report.problems == []
