"""청크 → 사실 → 노드, 끝까지 — plan/12 T-0045 · T-0046.

코퍼스 다섯 건(OCR 없이 읽히는 것)을 실제로 넣고 위키가 서는지 본다. `merge` 의 단위
테스트가 규칙을 보고, **여기는 그 규칙이 실제 문서에서 실제로 갈리는지**를 본다.

Postgres 없이 돈다 — `user_file` · `chunk` · `wiki_fact` · `wiki_evidence` 만 SQLite 에
만든다. 나머지 표는 JSONB 를 써서 SQLite 가 못 만들고, 여기서 안 쓴다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from finnect.config import settings
from finnect.models import (
    Base,
    Chunk,
    UserFile,
    UserFileStatus,
    WikiEvidence,
    WikiFact,
    WikiPlace,
)
from finnect.wiki import build, merge, service, topics

FIXTURES = Path(__file__).parent / "fixtures" / "wiki"
COMPANY = "c_build"

#: OCR 없이 읽히는 다섯. 나머지 둘(스캔 PDF · JPG)은 `--group ocr` 이 있어야 한다.
READABLE = [
    "성남시_시범사업_신청서.hwpx",
    "사업계획서_2026_초기창업패키지.docx",
    "회사소개서_v3.pdf",
    "재무제표_2025.xlsx",
    "피치덱_2026H2.pptx",
]


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory):  # noqa: ANN201
    """다섯 건을 한 번만 넣고 위키를 세운다. 해독이 느려서 모듈 단위로 재사용한다."""
    if not (FIXTURES / "facts.json").exists():
        pytest.skip("사실 표가 없다")

    tmp = tmp_path_factory.mktemp("wiki")
    old_dir, old_ocr = settings.user_file_dir, settings.user_file_ocr
    settings.user_file_dir, settings.user_file_ocr = tmp / "files", False
    try:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(
            engine,
            tables=[
                UserFile.__table__,
                Chunk.__table__,
                WikiFact.__table__,
                WikiEvidence.__table__,
            ],
        )
        factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

        paths = [FIXTURES / n for n in READABLE if (FIXTURES / n).exists()]
        if len(paths) < len(READABLE):
            pytest.skip("픽스처가 모자란다")
        service.ingest_files(factory, COMPANY, paths)

        with factory() as s:
            report = build.build_company(s, COMPANY)
            s.commit()
        yield factory, report
    finally:
        settings.user_file_dir, settings.user_file_ocr = old_dir, old_ocr


def _facts(factory, **where):  # noqa: ANN001, ANN202
    with factory() as s:
        q = select(WikiFact).where(WikiFact.company_id == COMPANY)
        for k, v in where.items():
            q = q.where(getattr(WikiFact, k) == v)
        return s.scalars(q).all()


# ─────────────────────────────────────────────────────────────────
# 세워지는가
# ─────────────────────────────────────────────────────────────────


def test_다섯_건_전부에서_사실이_나온다(built):  # noqa: ANN001
    _, report = built
    assert report.files == 5
    assert report.built == 5
    assert report.skipped == 0
    assert report.facts > 0


def test_근거_없는_사실이_하나도_없다(built):  # noqa: ANN001
    """**ADR-0014 가 막으려던 것이 정확히 이것이다.** 값만 들고 문단을 쓰면 지어낸다."""
    factory, _ = built
    with factory() as s:
        orphans = s.scalars(
            select(WikiFact).where(
                WikiFact.company_id == COMPANY,
                ~WikiFact.id.in_(select(WikiEvidence.fact_id)),
            )
        ).all()
    assert not orphans, [f.text for f in orphans]


def test_서술_노드가_전부_찬다(built):  # noqa: ANN001
    """정체성 하나 + 사업 내용 아홉(SPEC F1-2).

    **구상도의 topic 22개로는 둘이 빈다** — 지역 연계와 로드맵. 그래서 둘을 더했다.
    정체성은 2026-08-18 하나 더 붙었다(ADR-0033)."""
    factory, _ = built
    filled = {f.place for f in _facts(factory, place_kind=WikiPlace.NODE)}
    assert filled == set(topics.NODES)


def test_자격_판별_입력이_전부_찬다(built):  # noqa: ANN001
    """**못 채운 자리에서 묻는다**(ADR-0028). 여기가 비면 무엇을 물을지가 정해진다.

    OCR 을 껐으므로 사업자등록증이 빠졌는데도 나머지 넷이 채워야 한다 —
    등록증에만 있는 값에 자격 판별이 매달리면 안 된다.
    """
    factory, _ = built
    with factory() as s:
        views = {v.name: v for v in build.read_slots(s, COMPANY)}
    need = [n for n, spec in topics.SLOTS.items() if spec.eligibility]
    empty = [n for n in need if not views[n].current]
    assert not empty, f"자격 판별 입력이 비었다: {empty}"


# ─────────────────────────────────────────────────────────────────
# 함정 — 픽스처가 일부러 심어 둔 것들
# ─────────────────────────────────────────────────────────────────


def test_직원_수는_시계열로_서고_충돌이_아니다(built):  # noqa: ANN001
    """7 → 8 → 10 → 15. **충돌로 세우면 오탐이다.**"""
    factory, _ = built
    rows = _facts(factory, place="headcount")
    assert sorted(r.value for r in rows) == ["10", "15", "7", "8"]
    assert not [r for r in rows if r.status == merge.Status.CONFLICT]

    current = [r for r in rows if r.status == merge.Status.CURRENT]
    assert [r.value for r in current] == ["15"]


def test_시드_금액은_충돌로_선다(built):  # noqa: ANN001
    """3억(사업계획서·재무제표) 대 2.8억(피치덱). **둘 다 보관한다** — 다수결로 안 푼다."""
    factory, _ = built
    seed = [r for r in _facts(factory, place="funding") if r.qualifier == "시드"]
    assert {r.value for r in seed} == {"300000000", "280000000"}
    assert all(r.status == merge.Status.CONFLICT for r in seed)


def test_같은_사실은_하나로_서고_근거만_쌓인다(built):  # noqa: ANN001
    """재구매율 34→51% 가 네 문서에 있다. **사실 넷이 되면 틀렸다**(픽스처 README 3번)."""
    factory, _ = built
    rows = [r for r in _facts(factory, place="problem") if "재구매율" in r.text]
    assert len(rows) == 1

    with factory() as s:
        n = len(s.scalars(select(WikiEvidence).where(WikiEvidence.fact_id == rows[0].id)).all())
    assert n == 4


def test_매출액은_표기가_달라도_한_값이다(built):  # noqa: ANN001
    """`24,100천원` · `2,410만원` · `24100000` 이 같은 값이다. 안 모으면 없는 충돌이 난다."""
    factory, _ = built
    rows = [r for r in _facts(factory, place="revenue") if r.as_of and r.as_of.year == 2024]
    assert len(rows) == 1
    assert rows[0].value == "24100000"
    assert rows[0].status == merge.Status.SUPERSEDED  # 2025년 값이 더 늦다


def test_수혜_이력_셋이_hwpx_에서만_나온다(built):  # noqa: ANN001
    """**HWP 파서를 빼면 중복수혜 판정이 통째로 틀린다**(픽스처 README 4번)."""
    factory, _ = built
    rows = _facts(factory, place="gov_program")
    assert len(rows) == 3
    with factory() as s:
        files = {
            uf.filename
            for r in rows
            for uf in s.scalars(
                select(UserFile)
                .join(WikiEvidence, WikiEvidence.user_file_id == UserFile.id)
                .where(WikiEvidence.fact_id == r.id)
            )
        }
    assert files == {"성남시_시범사업_신청서.hwpx"}


def test_문서에_박힌_업력은_슬롯에_안_들어간다(built):  # noqa: ANN001
    """`업력 1년 6개월` 은 2025-08 기준이라 지금은 틀렸다. **버리지도 않는다.**"""
    factory, _ = built
    assert "tenure" not in topics.SLOTS
    un = _facts(factory, place_kind=WikiPlace.UNCATEGORIZED)
    assert any("업력" in r.text for r in un)


def test_근거가_쪽까지_나온다(built):  # noqa: ANN001
    """`회사소개서_v3.pdf` 가 아니라 `회사소개서_v3.pdf 3쪽` 이어야 한다(ADR-0014)."""
    factory, _ = built
    with factory() as s:
        paged = s.execute(
            select(Chunk.page)
            .join(WikiEvidence, WikiEvidence.chunk_id == Chunk.id)
            .join(UserFile, UserFile.id == WikiEvidence.user_file_id)
            .where(UserFile.filename == "회사소개서_v3.pdf", Chunk.page.is_not(None))
        ).all()
    assert paged, "PDF 근거에 쪽 번호가 하나도 없다"


# ─────────────────────────────────────────────────────────────────
# 다시 돌려도 같은가
# ─────────────────────────────────────────────────────────────────


def test_두_번_돌려도_같은_배치가_나온다(built):  # noqa: ANN001
    """**T-0045 의 완료 조건이다.** 라우팅에 모델이 안 들어가야 성립한다."""
    factory, _ = built
    before = sorted((f.dedupe_key, f.status) for f in _facts(factory))

    with factory() as s:
        build.build_company(s, COMPANY)
        s.commit()

    assert sorted((f.dedupe_key, f.status) for f in _facts(factory)) == before


def test_지우고_다시_세우면_원래대로다(built):  # noqa: ANN001
    """추출기를 바꿔 다시 돌릴 때 쓴다. **원본과 청크는 안 건드린다.**"""
    factory, _ = built
    before = sorted(f.dedupe_key for f in _facts(factory))

    with factory() as s:
        build.clear(s, COMPANY)
        s.commit()
    assert not _facts(factory)
    with factory() as s:
        chunks = s.scalars(select(Chunk).where(Chunk.company_id == COMPANY)).all()
    assert chunks, "청크가 같이 지워졌다"

    with factory() as s:
        build.build_company(s, COMPANY)
        s.commit()
    assert sorted(f.dedupe_key for f in _facts(factory)) == before


def test_모르는_파일은_그_파일만_건너뛴다(built):  # noqa: ANN001
    """**파일별로 독립이다**(F1-1-8). 스텁이 모르는 파일 하나가 나머지를 죽이면 안 된다."""
    factory, _ = built
    with factory() as s:
        s.add(
            UserFile(
                company_id=COMPANY,
                sha256="f" * 64,
                filename="남의_사업계획서.hwp",
                byte_size=1,
                ext="hwp",
                status=UserFileStatus.CHUNKED,
                chunk_count=1,
            )
        )
        s.flush()
        uf = s.scalars(select(UserFile).where(UserFile.sha256 == "f" * 64)).one()
        s.add(
            Chunk(
                user_file_id=uf.id,
                company_id=COMPANY,
                ordinal=0,
                text="아무 내용",
                chars=5,
                char_start=0,
                char_end=5,
            )
        )
        s.commit()

    with factory() as s:
        report = build.build_company(s, COMPANY)
        s.commit()

    assert report.skipped == 1
    assert report.built == 5
    assert any(name == "남의_사업계획서.hwp" for name, _ in report.problems)


def test_탈퇴하면_사실도_같이_지워진다(built):  # noqa: ANN001
    """**2026-08-18 여기가 새어 있었다.**

    `wiki_fact` 에 `user_file` FK 가 없어서 — 사실 하나가 파일 여럿을 근거로 드니 그게
    맞다 — 파일을 지워도 사실이 남았다. 탈퇴 뒤 다시 올렸더니 118건이 전부 '이미 있음'
    으로 나왔고, **지웠어야 할 값이 DB 에 그대로 있었다.**
    """
    factory, _ = built
    with factory() as s:
        build.build_company(s, COMPANY)
        s.commit()
    assert _facts(factory), "먼저 위키가 서 있어야 한다"

    with factory() as s:
        files, facts = service.purge(s, COMPANY)
        s.commit()
    assert files and facts

    assert not _facts(factory)
    with factory() as s:
        assert not s.scalars(select(WikiEvidence).where(WikiEvidence.company_id == COMPANY)).all()
        assert not s.scalars(select(UserFile).where(UserFile.company_id == COMPANY)).all()
        assert not s.scalars(select(Chunk).where(Chunk.company_id == COMPANY)).all()
