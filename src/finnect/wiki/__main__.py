"""사업 위키 CLI — 파일을 던지면 위키가 선다(plan/12).

    uv run python -m finnect.wiki --company c_001 tests/fixtures/wiki/*
    uv run python -m finnect.wiki --company c_001 --build       # 청크 → 사실 → 자리
    uv run python -m finnect.wiki --company c_001 --wiki        # 세워진 위키를 본다
    uv run python -m finnect.wiki --company c_001 --show 회사소개  # 원문 청크를 본다
    uv run python -m finnect.wiki --company c_001 --rechunk     # 청킹 규칙을 고쳤을 때
    uv run python -m finnect.wiki --company c_001 --rebuild     # 추출기를 바꿨을 때
    uv run python -m finnect.wiki --company c_001 --purge       # 탈퇴. 원본까지 지운다

**추출기가 아직 스텁이다**(ADR-0031). LLM 제공자가 안 정해져서 픽스처 7건만 돈다 —
그 밖의 파일을 넣으면 청크까지만 가고 이유가 따라 나온다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import func, select

from finnect.db import SessionFactory
from finnect.models import Chunk, UserFile, UserFileStatus, WikiEvidence, WikiFact, WikiPlace
from finnect.wiki import build, export, service, storage, topics


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="finnect.wiki", description="사용자 파일 → 원문 청크")
    p.add_argument("paths", nargs="*", type=Path, help="올릴 파일들")
    p.add_argument(
        "--company", default="", metavar="ID",
        help="회사 식별자. 격리의 기준이다. **`--score` 말고는 필수**",
    )
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
    p.add_argument(
        "--build",
        action="store_true",
        help="청크에서 사실을 뽑아 노드를 세운다. 파일을 올리면 자동으로 같이 돈다",
    )
    p.add_argument(
        "--rebuild",
        action="store_true",
        help="세운 위키를 지우고 다시 세운다. **원본과 청크는 안 건드린다**",
    )
    p.add_argument("--wiki", action="store_true", help="세워진 위키를 본다")
    p.add_argument(
        "--export",
        metavar="폴더",
        type=Path,
        help="기획 트리 모양으로 파일을 떨어뜨린다(ADR-0048 · F1-6). **폴더를 덮어쓴다**",
    )
    p.add_argument("--purge", action="store_true", help="이 회사의 파일과 청크를 통째로 지운다")
    p.add_argument(
        "--score",
        action="store_true",
        help="추출 정확도를 픽스처 118개와 대조해 잰다(ADR-0037). **DB 를 안 쓴다**",
    )
    args = p.parse_args(argv)

    if args.score:
        # **DB 도 회사도 필요 없다.** 정답지와 추출기만 있으면 된다
        from finnect.wiki import score

        try:
            print(score.run().render())
        except Exception as e:  # noqa: BLE001 — 키 문제는 사용자 실수지 우리 버그가 아니다
            if type(e).__name__ not in ("MissingKey", "LlmError"):
                raise
            print(e, file=sys.stderr)
            return 2
        return 0

    # `--score` 말고는 회사가 격리의 기준이라 없으면 안 된다(ADR-0029).
    if not args.company:
        p.error("--company 는 필수예요. (--score 만 예외예요)")

    if args.purge:
        with SessionFactory() as s:
            n, facts = service.purge(s, args.company)
            s.commit()
        gone = storage.purge(args.company)
        print(
            f"{args.company}: 파일 {n}건 · 사실 {facts}건 삭제 · "
            f"원본 디렉터리 {'삭제' if gone else '없음'}"
        )
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

    if args.wiki:
        with SessionFactory() as s:
            print(render_wiki(s, args.company))
        return 0

    if args.export:
        with SessionFactory() as s:
            print(render_export(s, args.company, args.export))
        return 0

    if args.paths:
        files = [f for f in args.paths if f.is_file() and f.suffix.lower() not in {".md", ".json"}]
        report = service.ingest_files(SessionFactory, args.company, files)
        print(render_ingest(report))
        print()

    if args.rebuild:
        with SessionFactory() as s:
            n = build.clear(s, args.company)
            s.commit()
        print(f"{args.company}: 세웠던 사실 {n}건을 지웠어요. 원본과 청크는 그대로예요")

    if args.paths or args.build or args.rebuild:
        # **거절을 트레이스백으로 보여 주지 않는다.** 사용자 실수지 우리 버그가 아니다
        try:
            with SessionFactory() as s:
                print(render_build(build.build_company(s, args.company)))
                s.commit()
        except build.BuildBusy as e:
            print(f"[못 세웠어요] {e}")
            return 1
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



def render_build(r: build.BuildReport) -> str:
    """사실을 세운 결과. **건너뛴 것과 버린 것을 같이 적는다** — 조용히 넘어가지 않는다."""
    lines = [
        f"[위키를 세웠어요] {r.company_id}",
        f"  읽은 파일      {r.built} / {r.files}",
        f"  사실           {r.facts}건   (이미 있어서 근거만 더 붙은 것 {r.merged}건)",
        f"  근거 연결      {r.evidence}개",
        f"  value topic   {r.value_topics}개",
        f"  event orbit   {r.event_orbits}개",
    ]
    if r.conflicts:
        lines.append(f"  충돌           {r.conflicts}건  ← 값이 갈려요. 물어봐야 해요")
    if r.uncategorized:
        lines.append(f"  검토 대기      {r.uncategorized}건  ← 갈 자리를 못 찾았어요")
    if r.problems:
        lines.append("")
        lines.append("  [못 세운 것]")
        lines += [f"    {name}  —  {why}" for name, why in r.problems]
    return "\n".join(lines)


def render_export(s, company_id: str, dest: Path) -> str:  # noqa: ANN001
    """기획 트리 모양으로 파일을 떨어뜨린다(ADR-0048 결정 4 · F1-6).

    **빈 자리도 파일로 낸다.** 자리를 지우면 사용자가 무엇이 없는지 모른다. 대신
    프론트매터에 왜 비는지 적혀 있어서 열어 보면 안다.
    """
    nodes = build.read_orbit(s, company_id)
    pages = export.render(nodes)
    root = dest / company_id
    for page in pages:
        target = root / page.spot.file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page.body, encoding="utf-8")

    filled = sum(1 for p in pages if p.values or p.statements)
    folded = sum(1 for p in pages if p.spot.instanced or p.spot.folded)
    return "\n".join(
        [
            f"[{company_id}] {root} 에 {len(pages)}장 썼어요",
            f"  채워진 자리 {filled} · 빈 자리 {len(pages) - filled}",
            f"  접힌 자리 {folded} — 회사마다 개수가 다른 자리예요. 아직 한 장으로 모아 둬요",
        ]
    )


def render_wiki(s, company_id: str) -> str:  # noqa: ANN001
    """세워진 위키를 편다. **근거가 어느 파일 몇 쪽인지까지 나와야 한다**(ADR-0014)."""
    slots = build.read_values(s, company_id)
    if not any(v.current or v.history for v in slots):
        return f"[{company_id}] 아직 위키가 없어요. 파일을 올리고 --build 를 해 보세요"

    out = [f"[{company_id} 사업 위키]", "", "─── 사업체 정보 (정형)"]
    for v in slots:
        mark = "!" if v.conflicted else ("·" if v.current else " ")
        need = " *" if v.eligibility else "  "
        if not v.current:
            out.append(f"  {mark}{need} {v.label:14} —  아직 몰라요")
            continue
        for f in v.current:
            when = f" ({f.as_of})" if f.as_of else ""
            qual = f" [{f.qualifier}]" if f.qualifier else ""
            out.append(f"  {mark}{need} {v.label:14} {f.value}{qual}{when}   {_ev(s, f)}")
            mark, need = " ", "  "
        for f in v.history:
            when = f" ({f.as_of})" if f.as_of else ""
            qual = f" [{f.qualifier}]" if f.qualifier else ""
            out.append(f"      {'':14} └ 이전  {f.value}{qual}{when}   {_ev(s, f)}")

    out += [
        "",
        "  * 는 자격 판별에 쓰는 자리예요. ! 는 값이 갈린 자리예요",
        "",
        "─── 사업 내용 (서술)",
    ]
    for name, label in topics.EVENT_ORBITS.items():
        facts = s.scalars(
            select(WikiFact)
            .where(
                WikiFact.company_id == company_id,
                WikiFact.place_kind == WikiPlace.EVENT,
                WikiFact.place == name,
            )
            .order_by(WikiFact.id)
        ).all()
        if not facts:
            out.append(f"  ○ {label}   —  아직 없어요")
            continue
        out.append(f"  ● {label}   사실 {len(facts)}개")
        for f in facts:
            out.append(f"      {f.text}")
            out.append(f"        {_ev(s, f)}")

    un = s.scalars(
        select(WikiFact)
        .where(WikiFact.company_id == company_id, WikiFact.place_kind == WikiPlace.UNCATEGORIZED)
        .order_by(WikiFact.id)
    ).all()
    if un:
        out += ["", f"─── 검토 대기 {len(un)}건 — 갈 자리를 못 찾았어요. 버리지는 않았어요"]
        out += [f"  ? {f.text}" for f in un]
    return "\n".join(out)


def _ev(s, fact) -> str:  # noqa: ANN001
    """근거를 `파일명 3쪽` 꼴로. **문자열이 아니라 연결이다** — 청크를 조인해서 만든다."""
    rows = s.execute(
        select(UserFile.filename, Chunk.page)
        .join(WikiEvidence, WikiEvidence.chunk_id == Chunk.id)
        .join(UserFile, UserFile.id == WikiEvidence.user_file_id)
        .where(WikiEvidence.fact_id == fact.id)
        .order_by(UserFile.filename)
    ).all()
    if not rows:
        return "근거 없음"
    where = [f"{name}{f' {page}쪽' if page else ''}" for name, page in rows]
    return f"근거 {len(rows)} — " + " · ".join(where)

if __name__ == "__main__":
    raise SystemExit(main())
