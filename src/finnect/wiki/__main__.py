"""사업 위키 CLI — 파일을 던지면 청크까지 만든다(plan/12).

    uv run python -m finnect.wiki --company c_001 tests/fixtures/wiki/*
    uv run python -m finnect.wiki --company c_001 --report
    uv run python -m finnect.wiki --company c_001 --rechunk     # 청킹 규칙을 고쳤을 때
    uv run python -m finnect.wiki --company c_001 --purge       # 탈퇴. 원본까지 지운다

**아직 사실을 뽑지 않는다.** 청크까지가 T-0043 이고 추출은 T-0045 다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import func, select

from finnect.db import SessionFactory
from finnect.models import Chunk, UserFile, UserFileStatus
from finnect.wiki import service, storage


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="finnect.wiki", description="사용자 파일 → 원문 청크")
    p.add_argument("paths", nargs="*", type=Path, help="올릴 파일들")
    p.add_argument("--company", required=True, metavar="ID", help="회사 식별자. 격리의 기준이다")
    p.add_argument("--report", action="store_true", help="집계만 찍는다")
    p.add_argument(
        "--show",
        nargs="?",
        const="",
        metavar="파일명조각",
        help="청크를 눈으로 본다. 이름 조각을 주면 그 파일만. **T-0044 가 온톨로지를 "
        "정하려면 실제 청크를 봐야 한다**",
    )
    p.add_argument("--rechunk", action="store_true", help="저장된 텍스트로 다시 쪼갠다")
    p.add_argument("--purge", action="store_true", help="이 회사의 파일과 청크를 통째로 지운다")
    args = p.parse_args(argv)

    if args.purge:
        with SessionFactory() as s:
            n = len(s.scalars(select(UserFile).where(UserFile.company_id == args.company)).all())
            for uf in s.scalars(select(UserFile).where(UserFile.company_id == args.company)):
                s.delete(uf)
            s.commit()
        gone = storage.purge(args.company)
        print(f"{args.company}: 파일 {n}건 삭제 · 원본 디렉터리 {'삭제' if gone else '없음'}")
        return 0

    if args.rechunk:
        with SessionFactory() as s:
            n = service.rechunk(s, args.company)
            s.commit()
        print(f"{args.company}: 청크 {n}개로 다시 쪼갰다")

    if args.show is not None:
        with SessionFactory() as s:
            print(render_chunks(s, args.company, args.show))
        return 0

    if args.paths:
        files = [f for f in args.paths if f.is_file() and f.suffix.lower() != ".md"]
        report = service.ingest_files(SessionFactory, args.company, files)
        print(render_ingest(report))
        print()

    with SessionFactory() as s:
        print(render_status(s, args.company))
    return 0


def render_ingest(r: service.IngestReport) -> str:
    lines = [
        f"[올린 것 {r.files}개] {r.company_id}",
        f"  청크까지 됨   {r.done}",
        f"  이미 있음     {r.duplicate}",
        f"  검토 대기     {r.needs_review}",
        f"  실패          {r.failed}",
        f"  청크          {r.chunks}개",
    ]
    if r.problems:
        lines.append("")
        lines.append("  [못 읽은 것]")
        lines += [f"    {name}  —  {why}" for name, why in r.problems]
    return "\n".join(lines)


def render_status(s, company_id: str) -> str:  # noqa: ANN001
    rows = s.execute(
        select(UserFile.status, func.count(), func.sum(UserFile.chunk_count))
        .where(UserFile.company_id == company_id)
        .group_by(UserFile.status)
    ).all()
    if not rows:
        return f"[{company_id}] 올린 파일이 없어요"

    order = list(UserFileStatus)
    rows = sorted(rows, key=lambda r: order.index(r[0]) if r[0] in order else 99)
    lines = [f"[{company_id} 현황]"]
    for status, n, chunks in rows:
        lines.append(f"  {status:14} {n:3}건   청크 {chunks or 0:4}개")

    total = s.scalar(select(func.count()).select_from(Chunk).where(Chunk.company_id == company_id))
    paged = s.scalar(
        select(func.count())
        .select_from(Chunk)
        .where(Chunk.company_id == company_id, Chunk.page.is_not(None))
    )
    lines.append(f"  {'합계':14} 청크 {total or 0}개 · 그중 쪽 번호 있는 것 {paged or 0}개")
    return "\n".join(lines)

def render_chunks(s, company_id: str, needle: str) -> str:  # noqa: ANN001
    """청크를 사람이 읽게 편다.

    **근거가 문자열이 아니라 연결이라는 것을 눈으로 확인하는 자리다**(ADR-0014).
    이름 조각이 없으면 파일별 요약, 있으면 그 파일의 청크 전문이다.
    """
    files = s.scalars(
        select(UserFile).where(UserFile.company_id == company_id).order_by(UserFile.filename)
    ).all()
    if not files:
        return f"[{company_id}] 올린 파일이 없어요"

    if not needle:
        out = [f"[{company_id}] 파일 {len(files)}개"]
        for uf in files:
            head = s.scalars(
                select(Chunk).where(Chunk.user_file_id == uf.id).order_by(Chunk.ordinal).limit(1)
            ).first()
            mark = "✓" if uf.chunk_count else "✗"
            pg = f" · {uf.page_count}쪽" if uf.page_count else ""
            out.append(f"  {mark} {uf.filename}")
            out.append(
                f"      {uf.parse_status}/{uf.parser or '-'} · 청크 {uf.chunk_count or 0}개"
                f" · {uf.text_chars or 0}자{pg}"
            )
            if head:
                out.append(f"      첫 조각: {head.text.strip()[:60]!r}")
        out.append("")
        out.append("  파일 하나를 펴 보려면: --show <이름 조각>")
        return "\n".join(out)

    hits = [f for f in files if needle in f.filename]
    if not hits:
        return f"[{company_id}] '{needle}' 이 든 파일이 없어요"

    out = []
    for uf in hits:
        out.append(f"─── {uf.filename} · {uf.parser or '-'} · 청크 {uf.chunk_count or 0}개")
        for c in s.scalars(
            select(Chunk).where(Chunk.user_file_id == uf.id).order_by(Chunk.ordinal)
        ):
            where = f"{c.page}쪽" if c.page else f"{c.char_start}~{c.char_end}자"
            out.append(f"\n  [#{c.ordinal}] {where} · {c.chars}자 · 제목 {c.heading or '—'}")
            for line in c.text.strip().split("\n"):
                out.append(f"      {line[:96]}")
        out.append("")
    return "\n".join(out)

if __name__ == "__main__":
    raise SystemExit(main())
