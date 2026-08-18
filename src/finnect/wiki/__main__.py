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


if __name__ == "__main__":
    raise SystemExit(main())
