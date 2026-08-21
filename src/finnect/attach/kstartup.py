"""K-Startup 상세 페이지에서 첨부 목록을 긁는다(plan/13).

**API 가 첨부 필드를 안 준다.** 그래서 공고 31,327건 중 29,789건(95.1%)에 첨부가
0건이었고, 평가 정보가 공고 본문에 0% 라 그 95% 는 자격 요건도 양식도 없는 상태다.
근거는 [2026-08-18 조사](../../../docs/adr/evidence/2026-08-18-kstartup-첨부-조사.md).

**여기서 파일을 받지 않는다.** `attachment` 행만 만들고, 내려받기와 해독은 기존
`attach.service.run()` 이 그대로 한다 — 그쪽은 출처를 안 가린다.

## 재수집이 이걸 안 지운다

`ingest/runner.py` 의 `_flush` 가 갱신 시 `attachment` 를 통째로 지우는데, 지우는
대상이 **"이번 적재에 첨부가 딸려 온 공고"** 로 한정된다(`if r.attachments`).
K-Startup 정규화기는 `attachments=[]` 를 명시하므로 그 목록에 안 들어간다.
**4.4시간 긁은 것이 10분짜리 재수집에 날아가지 않는다.** 테스트가 이걸 막아 둔다.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import dataclass, field

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from finnect.config import settings
from finnect.db import SessionFactory
from finnect.ingest.base import split_ext
from finnect.models import Attachment, AttachmentKind, KstartupNotice, Source

BASE = "https://www.k-startup.go.kr"

#: 브라우저처럼 굴어야 한다. 기업마당과 같은 이유다.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Referer": f"{BASE}/",
}

#: 첨부 한 줄. `file_bg` 의 `title` 이 파일명이고 뒤따르는 `fileDownload/ID` 가 주소다.
#: **링크 텍스트로 이름을 잡으면 안 된다** — 전부 `다운로드` 다.
PAIR = re.compile(
    r'<a[^>]*class="file_bg"[^>]*title="(?:\[첨부파일\]\s*)?([^"]+)"'
    r'.*?href="(/afile/fileDownload/[^"]+)"',
    re.S,
)

#: 마감 공고는 이 주소로 들어가야 첨부가 렌더된다. 실측 29,515/29,789(99.1%)가 마감이라
#: **사실상 전부에 필요하다.** 안 바꾸면 18KB 짜리 빈 껍데기가 온다(첨부 0개).
ONGOING, DEADLINE = "bizpbanc-ongoing.do", "bizpbanc-deadline.do"

#: 첨부가 렌더된 페이지의 최소 크기. 이보다 작으면 껍데기다.
MIN_RENDERED = 40_000


@dataclass(slots=True)
class ScrapeReport:
    total: int = 0
    done: int = 0
    skipped: int = 0  # 이미 첨부를 가진 공고
    with_files: int = 0
    empty: int = 0  # 페이지는 떴는데 첨부가 없다
    shell: int = 0  # 껍데기가 왔다. 첨부가 없는 것과 다르다
    recovered: int = 0  # 껍데기가 와서 반대쪽 주소로 되짚어 살린 건
    failed: int = 0
    attachments: int = 0
    seconds: float = 0.0
    ext: Counter[str] = field(default_factory=Counter)
    problems: list[tuple[str, str]] = field(default_factory=list)

    def render(self) -> str:
        rate = f"{self.seconds / self.done:.2f}초/건" if self.done else "-"
        lines = [
            f"[K-Startup 첨부 긁기] 대상 {self.total}건 · 처리 {self.done}건 · "
            f"건너뜀 {self.skipped}건 · {self.seconds / 60:.1f}분 ({rate})",
            f"  첨부 있음   {self.with_files}건 · {self.attachments}개",
            f"  첨부 없음   {self.empty}건",
            f"  껍데기      {self.shell}건",
            f"  되짚어 살림 {self.recovered}건",
            f"  실패        {self.failed}건",
        ]
        if self.ext:
            top = " · ".join(f"{e or '?'} {n}" for e, n in self.ext.most_common(8))
            lines.append(f"  확장자      {top}")
        if self.problems:
            lines.append("  [실패한 것]")
            lines += [f"    {sn}  —  {why}" for sn, why in self.problems[:20]]
        return "\n".join(lines)


def detail_url(url: str, rcrt_prgs_yn: str | None) -> str:
    """마감이면 주소를 바꾼다. **모집중은 그대로 둔다** — 그쪽은 ongoing 이 정상이다."""
    return url if rcrt_prgs_yn == "Y" else url.replace(ONGOING, DEADLINE)


def flip_url(url: str) -> str:
    """ongoing ↔ deadline. **`rcrt_prgs_yn` 이 낡아서 껍데기가 왔을 때 한 번 더 간다.**

    적재 시점의 값이라 그 뒤에 마감된 공고는 `Y` 인 채로 남는다. 2026-08-19 실측에서
    모집중 50건 중 7건이 그랬고(`178876` 은 접수마감이 `20260817` 이다), 일곱 전부
    deadline 에서 제대로 렌더됐다. **상태를 고쳐 쓰지 않고 주소만 한 번 더 본다** —
    공고 상태는 수집이 정하는 값이지 첨부 긁기가 정할 값이 아니다.
    """
    return url.replace(ONGOING, DEADLINE) if ONGOING in url else url.replace(DEADLINE, ONGOING)


def parse_attachments(html: str) -> list[tuple[str, str]]:
    """(파일명, 절대 URL). 순서는 화면 순서다."""
    return [(name.strip(), BASE + href) for name, href in PAIR.findall(html)]


def _targets(s: Session, *, limit: int | None, redo: bool) -> list[tuple[str, str, str]]:
    have = select(Attachment.external_id).where(Attachment.source == str(Source.KSTARTUP))
    stmt = select(
        KstartupNotice.pbanc_sn, KstartupNotice.detl_pg_url, KstartupNotice.rcrt_prgs_yn
    ).where(KstartupNotice.detl_pg_url.is_not(None))
    if not redo:
        stmt = stmt.where(KstartupNotice.pbanc_sn.not_in(have))
    # 모집중을 먼저 본다. 지금 신청할 수 있는 공고가 제품에 먼저 필요하다.
    stmt = stmt.order_by(KstartupNotice.rcrt_prgs_yn.desc(), KstartupNotice.pbanc_sn.desc())
    if limit is not None:
        stmt = stmt.limit(limit)
    return [(sn, url, prgs) for sn, url, prgs in s.execute(stmt).all()]


def scrape(
    *,
    limit: int | None = None,
    redo: bool = False,
    on_progress=None,  # noqa: ANN001
) -> ScrapeReport:
    """상세 페이지를 돌며 `attachment` 행을 만든다. **파일은 안 받는다.**

    이미 첨부를 가진 공고는 건너뛴다. **첨부가 0개인 공고는 그 사실을 남길 자리가 없어
    다시 돌 때마다 또 받는다** — 실측 15건 중 2건(13%)이 그렇다. 그걸 줄이려면 표가
    하나 더 필요한데, 지금 규모에서는 다시 받는 편이 싸다.
    """
    report = ScrapeReport()

    with SessionFactory() as s:
        targets = _targets(s, limit=limit, redo=redo)
        report.total = len(targets)
        if redo:
            report.skipped = 0

        with httpx.Client(
            headers=HEADERS, follow_redirects=True, timeout=settings.request_timeout_sec
        ) as client:
            def get(u: str) -> httpx.Response:
                """한 번 가져오고 걸린 시간과 예의 지연을 보고에 반영한다."""
                started = time.monotonic()
                try:
                    return client.get(u)
                finally:
                    report.seconds += time.monotonic() - started
                    time.sleep(settings.request_delay_sec)

            for i, (sn, url, prgs) in enumerate(targets, 1):
                first = detail_url(url, prgs)
                try:
                    r = get(first)
                    html = r.text
                except Exception as e:  # noqa: BLE001 — 이 공고만 실패시킨다
                    report.failed += 1
                    report.problems.append((sn, f"{type(e).__name__}: {e}"))
                    continue

                report.done += 1
                if r.status_code != 200:
                    report.failed += 1
                    report.problems.append((sn, f"HTTP {r.status_code}"))
                    continue

                pairs = parse_attachments(html)
                if not pairs and len(html) < MIN_RENDERED:
                    # **껍데기다. 상태가 낡았을 수 있으니 반대쪽을 한 번 더 본다.**
                    try:
                        r2 = get(flip_url(first))
                    except Exception as e:  # noqa: BLE001 — 되짚기 실패는 껍데기로 남긴다
                        report.problems.append((sn, f"되짚기 {type(e).__name__}: {e}"))
                    else:
                        if r2.status_code == 200 and len(r2.text) >= MIN_RENDERED:
                            html = r2.text
                            pairs = parse_attachments(html)
                            report.recovered += 1

                if not pairs:
                    # **껍데기와 '첨부 없음'을 구분한다.** 껍데기는 우리가 주소를 잘못
                    # 고른 것이고, 첨부 없음은 그 공고의 사실이다.
                    if len(html) < MIN_RENDERED:
                        report.shell += 1
                        report.problems.append((sn, f"껍데기 {len(html):,}자"))
                    else:
                        report.empty += 1
                    continue

                _upsert(s, sn, pairs)
                report.with_files += 1
                report.attachments += len(pairs)
                for name, _ in pairs:
                    report.ext[split_ext(name) or "?"] += 1

                if i % 20 == 0:
                    s.commit()
                    if on_progress is not None:
                        on_progress(report)
        s.commit()

    if on_progress is not None:
        on_progress(report)
    return report


def _upsert(s: Session, external_id: str, pairs: list[tuple[str, str]]) -> None:
    """그 공고의 첨부를 통째로 다시 깐다. `ingest/runner.py` 와 같은 방식이다."""
    s.execute(
        delete(Attachment).where(
            Attachment.source == str(Source.KSTARTUP),
            Attachment.external_id == external_id,
        )
    )
    s.execute(
        pg_insert(Attachment),
        [
            {
                "source": str(Source.KSTARTUP),
                "external_id": external_id,
                "position": i,
                # API 가 공고문과 그 밖을 안 가른다. **모르는 것을 아는 척하지 않는다.**
                "kind": str(AttachmentKind.OTHER),
                "filename": name,
                "ext": split_ext(name),
                "url": url,
            }
            for i, (name, url) in enumerate(pairs)
        ],
    )


def coverage(s: Session) -> dict[str, int]:
    total = s.scalar(select(func.count()).select_from(KstartupNotice)) or 0
    scraped = (
        s.scalar(
            select(func.count(func.distinct(Attachment.external_id))).where(
                Attachment.source == str(Source.KSTARTUP)
            )
        )
        or 0
    )
    files = (
        s.scalar(
            select(func.count()).select_from(Attachment).where(
                Attachment.source == str(Source.KSTARTUP)
            )
        )
        or 0
    )
    return {"notices": total, "scraped": scraped, "attachments": files}
