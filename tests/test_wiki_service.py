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

from finnect.attach import ocr
from finnect.config import settings
from finnect.models import Base, Chunk, UserFile, UserFileStatus
from finnect.wiki import service, storage

FIXTURES = Path(__file__).parent / "fixtures" / "wiki"
COMPANY = "c_test"


def _factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, use_ocr: bool):  # noqa: ANN202
    monkeypatch.setattr(settings, "user_file_dir", tmp_path / "files")
    monkeypatch.setattr(settings, "user_file_ocr", use_ocr)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[UserFile.__table__, Chunk.__table__])
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@pytest.fixture
def factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
    """**OCR 을 끈 상태가 기본이다.** 켜면 스위트가 5초에서 46초로 가고, 첫 실행에
    모델을 내려받아야 해서 네트워크에 묶인다. OCR 은 아래 전용 테스트가 본다."""
    return _factory(tmp_path, monkeypatch, use_ocr=False)


@pytest.fixture
def ocr_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
    return _factory(tmp_path, monkeypatch, use_ocr=True)


def _fixture(name: str) -> Path:
    path = FIXTURES / name
    if not path.exists():
        pytest.skip(f"픽스처가 없다: {name}")
    return path


#: 읽히는 픽스처 전부와 기대 쪽 유무. **포맷 하나만 검사하면 못 잡는 버그가 있다** —
#: `from_pptx` 가 슬라이드를 "\n\n" 로, 청커가 "\n" 로 이어서 pptx 청크 12개 중 11개의
#: 좌표가 거짓이었는데 PDF 만 보던 테스트가 통과했다.
READABLE = [
    ("회사소개서_v3.pdf", True),
    ("사업계획서_2026_초기창업패키지.docx", False),
    ("성남시_시범사업_신청서.hwpx", False),
    ("재무제표_2025.xlsx", False),  # 시트는 쪽이 아니다
    ("피치덱_2026H2.pptx", True),  # 슬라이드는 쪽처럼 세어진다
]


@pytest.mark.parametrize(("name", "has_pages"), READABLE)
def test_청크_좌표가_저장된_텍스트와_정확히_일치한다(factory, name, has_pages) -> None:  # noqa: ANN001
    """**저장하는 텍스트와 청크 좌표가 같은 기준을 써야 한다.**

    파서의 `text` 와 청커가 이은 것이 갈라지면 이으는 문자 하나 차이로 모든 좌표가
    어긋난다. 그래서 `chunk.join` 이 좌표계의 유일한 주인이다.
    """
    report = service.ingest_files(factory, COMPANY, [_fixture(name)])

    assert report.done == 1, f"{name} 이 안 읽혔다"
    assert report.chunks > 0

    with factory() as s:
        uf = s.scalar(select(UserFile))
        assert uf.status == UserFileStatus.CHUNKED
        assert uf.text_chars == len(storage.read_text(COMPANY, uf.sha256) or "")

        text = storage.read_text(COMPANY, uf.sha256)
        chunks = s.scalars(select(Chunk).order_by(Chunk.ordinal)).all()
        assert chunks
        for c in chunks:
            assert text[c.char_start : c.char_end] == c.text, f"{name} #{c.ordinal} 좌표 어긋남"

        pages = {c.page for c in chunks}
        if has_pages:
            assert None not in pages, f"{name} 은 쪽을 안다"
            assert uf.page_count and uf.page_count > 1
        else:
            assert pages == {None}, f"{name} 에는 쪽이 없다"
            assert uf.page_count is None


def test_표_구조가_살아_있다(factory) -> None:  # noqa: ANN001
    """**뭉개면 연도-항목-값 대응이 깨진다.** 헤더 행과 데이터 행이 같은 조각에 있어야
    `매출액 24100000 86400000` 의 두 값이 각각 2024·2025 임을 알 수 있다."""
    service.ingest_files(factory, COMPANY, [_fixture("재무제표_2025.xlsx")])

    with factory() as s:
        c = s.scalar(select(Chunk).where(Chunk.text.like("%매출총이익%")))
        assert c is not None
        assert c.heading == "## 손익계산서", "시트 이름이 제목으로 와야 한다"

        rows = [ln.split("\t") for ln in c.text.split("\n") if "\t" in ln]
        lines = {r[0]: r for r in rows}
        assert "과목" in lines, "헤더 행이 같은 조각에 있어야 한다"
        assert lines["과목"][1:3] == ["제1기 (2024)", "제2기 (2025)"]
        assert lines["매출액"][1:3] == ["24100000", "86400000"]
        assert lines["매출액"][3] == "258.5%", "백분율은 서식을 반영해야 한다"


def test_파일_하나가_실패해도_나머지가_완주한다(factory) -> None:  # noqa: ANN001
    """**부분 성공이 예외가 아니라 정상 상태다**(F1-1-8). OCR 이 꺼진 상태로 본다."""
    paths = [
        _fixture("현장사진_파일럿매장.jpg"),  # 그림. OCR 이 꺼져 있어 실패
        _fixture("회사소개서_v3.pdf"),  # 읽힌다
        _fixture("사업자등록증_스캔.pdf"),  # 스캔본. 텍스트 레이어가 0자
        _fixture("성남시_시범사업_신청서.hwpx"),  # 읽힌다
    ]

    report = service.ingest_files(factory, COMPANY, paths)

    assert report.done == 2, "읽히는 둘이 통과해야 한다"
    assert report.failed == 1
    assert report.needs_review == 1
    assert report.chunks > 0
    assert len(report.problems) == 2, "못 읽은 것이 이유와 함께 남아야 한다"


def test_OCR_이_꺼져_있으면_스캔본은_검토_대기다(factory) -> None:  # noqa: ANN001
    """포맷이 없는 것과 글자가 안 나온 것은 다르다. **스캔본은 OCR 이 붙으면 읽힌다.**"""
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


# ─────────────────────────────────────────────────────────────
# OCR (ADR-0030). **모델을 내려받아야 하고 쪽당 십수 초 걸린다.**
# 스위트를 여기 묶지 않으려고 나눠 뒀다.
# ─────────────────────────────────────────────────────────────

ocr_needed = pytest.mark.skipif(
    not ocr.available(), reason="rapidocr 가 없다 (uv sync --group ocr)"
)


@ocr_needed
def test_OCR_을_켜면_스캔본에서_글자가_나온다(ocr_factory) -> None:  # noqa: ANN001
    """**위키의 정형 슬롯 다섯 중 넷이 사업자등록증에서 나온다.** OCR 없이는 0자다."""
    report = service.ingest_files(ocr_factory, COMPANY, [_fixture("사업자등록증_스캔.pdf")])

    assert report.done == 1, "OCR 을 켰는데도 안 읽혔다"
    assert report.needs_review == 0
    assert report.chunks > 0

    with ocr_factory() as s:
        uf = s.scalar(select(UserFile))
        assert uf.status == UserFileStatus.CHUNKED
        assert uf.parser and uf.parser.startswith("ocr/"), "OCR 로 읽은 것이 기록돼야 한다"

        text = "".join(c.text for c in s.scalars(select(Chunk)))
        flat = text.replace(" ", "")
        # 자격 판별의 입력. **라벨이 아니라 값을 본다** — 라벨은 자간 때문에 깨진다
        assert "501-86-33271" in flat, "사업자등록번호"
        assert "110111-8842301" in flat, "법인등록번호"
        assert "주식회사다시로" in flat, "법인명"
        assert "판교로255" in flat, "소재지"
        assert "2024년03월11일" in flat, "개업일"


@ocr_needed
def test_OCR_을_켜면_그림_파일도_읽는다(ocr_factory) -> None:  # noqa: ANN001
    report = service.ingest_files(ocr_factory, COMPANY, [_fixture("현장사진_파일럿매장.jpg")])

    assert report.failed == 0, "OCR 을 켰는데 그림이 실패했다"
    with ocr_factory() as s:
        uf = s.scalar(select(UserFile))
        assert uf.parser and uf.parser.startswith("ocr/")


@ocr_needed
def test_OCR_은_텍스트가_있는_PDF_를_건드리지_않는다(ocr_factory) -> None:  # noqa: ANN001
    """**순서를 뒤집으면 읽히는 PDF 에도 쪽당 십수 초를 쓴다.**"""
    service.ingest_files(ocr_factory, COMPANY, [_fixture("회사소개서_v3.pdf")])

    with ocr_factory() as s:
        uf = s.scalar(select(UserFile))
        assert uf.parser == "pdf/plumber", f"OCR 로 갔다: {uf.parser}"
