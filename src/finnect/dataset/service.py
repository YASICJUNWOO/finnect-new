"""현황 · 초기화 · 솎기.

**규칙이 여기 없다.** 무엇을 남길지는 `notice-filter/` 가 목록 파일로 넘겨 주고
이 모듈은 그 파일만 읽는다 — `attach --only` · `match --only` 와 같은 경계다.
여기가 아는 것은 둘뿐이다: 목록에 있나, 표본에 드나.

**되돌릴 수 없는 삭제라 기본이 미리보기다.** `--yes` 없이는 세기만 하고 안 지운다.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from finnect.config import settings
from finnect.dataset.sample import keeps
from finnect.dataset.tables import NOTICE_TABLES, PURGED
from finnect.db import session_scope
from finnect.models import Attachment, AttachmentFile

__all__ = ["Counts", "PruneReport", "PurgeReport", "counts", "prune", "purge", "read_list"]


@dataclass(frozen=True)
class Counts:
    tables: dict[str, int]
    files: int
    bytes_: int

    def render(self) -> str:
        lines = [f"  {k:<18} {v:>7,}" for k, v in self.tables.items()]
        mb = self.bytes_ / 1024 / 1024
        lines.append(f"  {'첨부 원본 파일':<17} {self.files:>7,}  ({mb:,.0f} MB)")
        return "\n".join(lines)


def counts() -> Counts:
    with session_scope() as s:
        tables = {m.__tablename__: _count(s, m) for m in PURGED}
    files, bytes_ = _disk()
    return Counts(tables=tables, files=files, bytes_=bytes_)


def read_list(path: Path) -> set[str]:
    """목록 파일 → 공고번호 집합. 빈 줄과 `#` 주석은 버린다.

    `bizinfo:125069` 처럼 출처가 붙어 와도 받는다 — 뒤쪽만 쓴다. 출처를 섞어
    판단하지 않는 것은 `--source` 가 이미 정해 주기 때문이다.
    """
    out: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        ln = raw.strip()
        if not ln or ln.startswith("#"):
            continue
        out.add(ln.split(":", 1)[1].strip() if ":" in ln else ln)
    if not out:
        raise ValueError(f"{path} 에 공고번호가 하나도 없다")
    return out


# ── 초기화 ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PurgeReport:
    applied: bool
    tables: dict[str, int]
    files: int
    bytes_: int

    def render(self) -> str:
        head = "[초기화]" if self.applied else "[초기화 · 미리보기 — 아직 안 지웠다]"
        mb = self.bytes_ / 1024 / 1024
        lines = [f"{head} 지울 것"]
        lines += [f"  {k:<18} {v:>7,}" for k, v in self.tables.items()]
        lines.append(f"  {'첨부 원본 파일':<17} {self.files:>7,}  ({mb:,.0f} MB)")
        if not self.applied:
            lines.append("\n  실제로 지우려면 --yes 를 붙인다. 그 전에 --dump 로 뜬다.")
        return "\n".join(lines)


def purge(*, apply: bool = False) -> PurgeReport:
    """공고·첨부를 통째로 비운다. **`document`·`draft`·`wiki_*` 는 안 건드린다.**

    첨부 원본은 디렉터리를 통째로 지운다. `attachment_file` 이 0행인데 파일이
    남아 있는 상태가 실제로 있었다 — 옛 레이아웃(`data/attachments/bizinfo/0/…`)
    잔재다. 표를 따라가며 지우면 그것들이 조용히 남는다.
    """
    c = counts()
    if not apply:
        return PurgeReport(applied=False, tables=c.tables, files=c.files, bytes_=c.bytes_)

    with session_scope() as s:
        for model in PURGED:
            s.query(model).delete(synchronize_session=False)

    _rmtree(settings.attachment_dir)
    return PurgeReport(applied=True, tables=c.tables, files=c.files, bytes_=c.bytes_)


# ── 솎기 ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PruneReport:
    source: str
    applied: bool
    before: int
    kept: int
    by_list: int = 0
    by_sample: int = 0
    attachments: int = 0
    files: int = 0
    samples: int = 1
    sampled_ids: list[str] = field(default_factory=list)

    @property
    def removed(self) -> int:
        return self.before - self.kept

    def render(self) -> str:
        head = "[솎기]" if self.applied else "[솎기 · 미리보기 — 아직 안 지웠다]"
        lines = [
            f"{head} {self.source}  {self.before:,} → {self.kept:,}건"
            f"  (뺀 것 {self.removed:,})",
            f"  목록에 없어서   {self.by_list:>7,}",
        ]
        if self.samples > 1:
            lines.append(f"  표본 밖(% {self.samples})  {self.by_sample:>7,}")
        lines.append(f"  딸린 첨부 메타  {self.attachments:>7,}")
        lines.append(f"  지울 원본 파일  {self.files:>7,}")
        if not self.applied:
            lines.append("\n  실제로 지우려면 --yes 를 붙인다.")
        return "\n".join(lines)


def prune(
    source: str, keep: set[str], *, samples: int = 1, apply: bool = False
) -> PruneReport:
    """목록 밖이거나 표본 밖인 공고를 지운다. **멱등하다** — 두 번 돌려도 같다."""
    if source not in NOTICE_TABLES:
        raise ValueError(f"모르는 출처 {source!r} — {sorted(NOTICE_TABLES)} 중 하나여야 한다")
    model, pk = NOTICE_TABLES[source]

    with session_scope() as s:
        ids = [str(v) for v in s.scalars(select(getattr(model, pk)))]
        survivors = {i for i in ids if i in keep and keeps(i, samples)}
        doomed = [i for i in ids if i not in survivors]

        by_list = sum(1 for i in doomed if i not in keep)
        by_sample = len(doomed) - by_list
        urls = _attachment_urls(s, source, doomed)
        paths = _orphan_paths(s, urls)

        rep = PruneReport(
            source=source,
            applied=apply,
            before=len(ids),
            kept=len(survivors),
            by_list=by_list,
            by_sample=by_sample,
            attachments=len(urls),
            files=len(paths),
            samples=samples,
            sampled_ids=sorted(survivors)[:5],
        )
        if not apply or not doomed:
            return rep

        _delete_attachments(s, source, doomed, urls)
        s.query(model).filter(getattr(model, pk).in_(doomed)).delete(synchronize_session=False)

    for p in paths:
        p.unlink(missing_ok=True)
    return rep


# ── 안쪽 ──────────────────────────────────────────────────────────────


def _count(s: Session, model: type) -> int:
    return s.scalar(select(func.count()).select_from(model)) or 0


def _attachment_urls(s: Session, source: str, ids: list[str]) -> list[str]:
    if not ids:
        return []
    keys = [(source, i) for i in ids]
    rows = s.scalars(
        select(Attachment.url).where(tuple_(Attachment.source, Attachment.external_id).in_(keys))
    )
    return [u for u in rows if u]


def _orphan_paths(s: Session, urls: list[str]) -> list[Path]:
    """지워질 `attachment_file` 이 들고 있는 파일 중 **아무도 안 쓰게 되는 것만.**

    저장소가 콘텐츠 주소라 URL 이 달라도 `stored_path` 가 같을 수 있다. 그냥
    지우면 살아남은 공고의 첨부가 사라진다 — 행은 있고 파일은 없는 상태가 된다.
    """
    if not urls:
        return []
    doomed = list(s.scalars(select(AttachmentFile).where(AttachmentFile.url.in_(urls))))
    mine = {p for f in doomed for p in (f.stored_path, f.text_path) if p}
    if not mine:
        return []
    survivors = s.scalars(select(AttachmentFile).where(AttachmentFile.url.notin_(urls)))
    theirs = {p for f in survivors for p in (f.stored_path, f.text_path) if p}
    return [settings.attachment_dir / rel for rel in sorted(mine - theirs)]


def _delete_attachments(s: Session, source: str, ids: list[str], urls: list[str]) -> None:
    if urls:
        s.query(AttachmentFile).filter(AttachmentFile.url.in_(urls)).delete(
            synchronize_session=False
        )
    keys = [(source, i) for i in ids]
    s.query(Attachment).filter(
        tuple_(Attachment.source, Attachment.external_id).in_(keys)
    ).delete(synchronize_session=False)


def _disk() -> tuple[int, int]:
    root = settings.attachment_dir
    if not root.exists():
        return 0, 0
    files = [p for p in root.rglob("*") if p.is_file()]
    return len(files), sum(p.stat().st_size for p in files)


def _rmtree(root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
