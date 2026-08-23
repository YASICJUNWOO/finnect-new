"""구조로 서류 경계를 찾는 것이 표지 규칙보다 얼마나 나은가 (ADR-0061 결정 1).

**버리는 코드다**(CLAUDE.md — `spike/` 규율). 결과는 `docs/adr/evidence/` 에 남긴다.

    uv run python spike/segment_check.py            # hwp 전량
    uv run python spike/segment_check.py --ext hwpx --limit 40

`segment.doc_titles` 가 파일 구조에서 서류 제목을 뽑고, `segment.split(titles=…)` 이
그것을 원문에서 대조해 자른다. 표지 규칙(`붙임`·`서식` 낱말)만 쓴 결과와 견준다.

**JVM 은 한 프로세스에 한 번만 뜬다**(jpype). 그래서 파일마다 프로세스를 새로
띄우지 않고 여기서 다 돈다.
"""

from __future__ import annotations

import argparse
import time
from collections import defaultdict
from pathlib import Path

from sqlalchemy import text as sql

from finnect.attach import store
from finnect.db import SessionFactory
from finnect.extract import segment


def titles_of(path: Path, ext: str) -> list[str]:
    """파일 구조에서 서류 제목을. **못 열면 빈 목록이다.**"""
    from finnect.forms import open_form

    form = open_form(path, ext)
    by_table: dict[tuple[int, int], list[str]] = defaultdict(list)
    for c in form.cells():
        by_table[(c.anchor.section, c.anchor.table)].append(c.text)
    paras = [p.text for p in form.paragraphs()]
    return segment.doc_titles(list(by_table.values()), paras)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="segment_check")
    p.add_argument("--ext", default="hwp")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--sample", type=int, default=25, help="육안용 표본 간격")
    args = p.parse_args(argv)

    with SessionFactory() as s:
        rows = s.execute(
            sql(
                """
                select sha256, text_path, stored_path, server_filename
                from attachment_file
                where detected_ext = :ext
                  and text_path is not null and stored_path is not null
                order by sha256
                """
            ),
            {"ext": args.ext},
        ).all()
    if args.limit:
        rows = rows[: args.limit]

    n = failed = grew = 0
    old_total = new_total = 0
    bad_offset: list[str] = []
    samples: list[tuple[str, int, int, list[str]]] = []
    t0 = time.time()

    for i, (sha, tpath, spath, fname) in enumerate(rows):
        try:
            text = store.abs_path(tpath).read_text(errors="ignore").replace("\x00", " ")
            titles = titles_of(store.abs_path(spath), args.ext)
        except Exception as e:  # noqa: BLE001 — 한 파일이 나머지를 안 죽인다
            failed += 1
            if failed <= 3:
                print(f"  못 열었다: {(fname or sha)[:40]} — {type(e).__name__}: {e}")
            continue

        n += 1
        old = segment.split(text)
        new = segment.split(text, titles=titles)
        old_total += len(old)
        new_total += len(new)
        if len(new) > len(old):
            grew += 1
        # **오프셋이 깨지면 근거 청크를 못 연다**(ADR-0014). 전부 봐야 한다
        if any(text[x.start : x.end] != x.text for x in new):
            bad_offset.append(sha[:12])
        if len(new) > len(old) and i % args.sample == 0:
            samples.append((fname or sha[:12], len(old), len(new), [x.title for x in new]))

    dt = time.time() - t0
    print()
    print(f"[{args.ext} {n}개 · {dt:.1f}초 · 못 연 것 {failed}개]")
    print(f"  구간 합계   표지 {old_total:,}  →  구조까지 {new_total:,}"
          f"  (+{new_total - old_total:,})")
    print(f"  늘어난 파일 {grew}/{n} = {grew / max(n, 1) * 100:.1f}%")
    print(f"  오프셋 깨짐 {len(bad_offset)}건 {bad_offset[:5]}")
    print()
    print(f"=== 육안 표본 {len(samples)}건 (번호 % {args.sample} == 0) ===")
    for fname, o, nn, titles in samples:
        print(f"  {fname[:52]}  {o} → {nn}")
        for t in titles:
            print(f"        · {t[:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
