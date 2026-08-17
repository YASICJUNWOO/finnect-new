"""해독된 텍스트를 구간으로 쪼개고 칸을 꺼내 저장한다(plan/11 T-0035·T-0037·T-0038).

**같은 파일을 두 번 하지 않는다.** 키가 `sha256` 이라 같은 양식이 여러 공고에 붙어도
한 번만 돈다.

`attach` 와 달리 네트워크를 쓰지 않는다. 파일은 이미 디스크에 있다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from finnect.attach import store
from finnect.db import engine
from finnect.extract import fields as fx
from finnect.extract import segment as sg
from finnect.models import AttachmentFile, Document, DocumentItem, DocumentKind, ParseStatus

#: 무엇이 판정했는지 남긴다. LLM 이 붙으면 `llm/<모델>` 로 덮인다(T-0036).
DECIDER = "rule/v1"


@dataclass(slots=True)
class ExtractReport:
    files: int = 0
    segments: int = 0
    fields_docs: int = 0
    items: int = 0
    skipped: int = 0
    kinds: dict[str, int] = field(default_factory=dict)

    def line(self) -> str:
        k = " · ".join(f"{v} {n}" for n, v in sorted(self.kinds.items(), key=lambda x: -x[1]))
        return (
            f"파일 {self.files:,} · 구간 {self.segments:,} · "
            f"칸 서식 {self.fields_docs:,} · 칸 {self.items:,} · 건너뜀 {self.skipped:,}\n"
            f"구간 종류: {k or '없음'}"
        )


def run(*, limit: int | None = None, redo: bool = False) -> ExtractReport:
    report = ExtractReport()

    with Session(engine) as s:
        q = select(AttachmentFile).where(
            AttachmentFile.parse_status == str(ParseStatus.OK),
            AttachmentFile.text_path.is_not(None),
            AttachmentFile.sha256.is_not(None),
        )
        rows = s.scalars(q).all()

        done: set[str] = set()
        seen: set[str] = set()
        if not redo:
            done = set(s.scalars(select(Document.sha256).distinct()).all())

        for row in rows:
            sha = row.sha256
            assert sha is not None
            if sha in seen:
                continue  # 같은 내용의 파일이 여러 URL 로 온다
            seen.add(sha)
            if sha in done:
                report.skipped += 1
                continue

            try:
                text = store.abs_path(row.text_path).read_text(errors="ignore")  # type: ignore[arg-type]
            except FileNotFoundError:
                report.skipped += 1
                continue

            # 이미 디스크에 있는 텍스트에는 NUL 이 남아 있다. `attach/extract.py` 가
            # 앞으로는 안 넣지만 다시 해독하기 전까지는 여기서 막는다.
            # **지우지 않고 공백으로 바꾼다** — 길이가 달라지면 오프셋이 어긋난다.
            text = text.replace("\x00", " ")

            _replace(s, sha, text, report)
            report.files += 1
            if limit is not None and report.files >= limit:
                break

        s.commit()
    return report


def _replace(s: Session, sha: str, text: str, report: ExtractReport) -> None:
    """이 파일의 구간을 다시 깐다. **부분 갱신을 하지 않는다** — 파서가 바뀌면 경계가 바뀐다."""
    old = s.scalars(select(Document.id).where(Document.sha256 == sha)).all()
    if old:
        s.execute(delete(DocumentItem).where(DocumentItem.document_id.in_(old)))
        s.execute(delete(Document).where(Document.id.in_(old)))

    for seg in sg.split(text):
        kind = _classify(seg.text)
        doc = Document(
            sha256=sha,
            seq=seg.seq,
            title=seg.title[:300],
            kind=str(kind),
            char_start=seg.start,
            char_end=seg.end,
            decided_by=DECIDER,
        )
        s.add(doc)
        s.flush()

        report.segments += 1
        report.kinds[str(kind)] = report.kinds.get(str(kind), 0) + 1

        if kind is not DocumentKind.FIELDS:
            continue

        report.fields_docs += 1
        for i, label in enumerate(fx.labels(seg.text)):
            s.add(
                DocumentItem(
                    document_id=doc.id,
                    ordinal=i,
                    number=None,
                    title=label,
                    instruction=None,
                    input_kind="field",
                )
            )
            report.items += 1


def _classify(text: str) -> DocumentKind:
    """**규칙으로 갈리는 것만 가른다.**

    칸 채우기는 신호가 뚜렷하다. 서술형은 공고문의 절과 생김새가 같아서
    규칙이 네 번 실패했으므로 `UNKNOWN` 으로 남긴다 — T-0036 이 채운다.
    **모르는 것을 `NONE` 이라고 하지 않는다.** 그러면 나중에 다시 볼 대상이 사라진다.
    """
    if fx.is_fields(text):
        return DocumentKind.FIELDS
    return DocumentKind.UNKNOWN
