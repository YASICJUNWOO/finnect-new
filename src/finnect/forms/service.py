"""초안을 원본 양식에 넣어 채운 파일을 만든다 (plan/24 T-0154·T-0155 · ADR-0060).

레포 첫 줄이 「들어가면 **문서가 이미 써져 있다**」인데, 그 문서가 파일로 나가는
자리가 여기다.

## 저장하지 않는다

읽을 때마다 만든다. 위키 마크다운을 저장하지 않기로 한 것과 같은 이유다 — 초안이
바뀌면 파일이 낡는데, 둘 중 어느 쪽이 정본인지 정할 근거가 없다. 채우는 데 드는
시간은 파일 하나를 여닫는 정도다(LLM 을 안 부른다).

## 못 채운 것을 세서 같이 준다

**조용히 남기면 사용자가 `000-0000-0000` 을 그대로 제출한다.** hwp 는 안내문이 든
칸을 못 덮어써서 못 채우는 자리가 많다 — 그 수를 화면이 말해야 한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from finnect.attach import store
from finnect.models import (
    Attachment,
    AttachmentFile,
    Document,
    DocumentItem,
    Draft,
    DraftItem,
)


@dataclass(slots=True)
class FillReport:
    """채운 결과. **화면이 이걸 그대로 말한다.**"""

    document_id: int
    ext: str
    filled: int = 0
    #: 값은 있는데 못 넣었다. hwp 에서 안내문이 든 칸이 여기 온다
    refused: int = 0
    #: 값은 있는데 좌표가 없다. 라벨이 겹쳤거나 파일에 구간이 여럿이다
    no_anchor: int = 0
    #: 못 넣은 칸의 이름. **사용자가 손으로 옮겨야 하는 자리다**
    left: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.refused and not self.no_anchor


def fill_document(
    s: Session,
    company_id: str,
    source: str,
    external_id: str,
    document_id: int,
    out_path: str,
) -> FillReport:
    """이 회사의 초안을 그 문서의 원본에 넣어 `out_path` 에 쓴다.

    **좌표가 있는 칸만 건드린다.** 없는 칸은 세어서 돌려준다 — 라벨로 다시 찾는
    길은 열지 않는다(`spike/anchor_check.py` 가 부러뜨린 방식이다).
    """
    from finnect.forms import open_form

    doc = s.get(Document, document_id)
    if doc is None:
        raise LookupError(f"모르는 문서: {document_id}")

    ext = s.scalar(
        select(AttachmentFile.detected_ext)
        .join(Attachment, Attachment.url == AttachmentFile.url)
        .where(
            AttachmentFile.sha256 == doc.sha256,
            Attachment.source == source,
            Attachment.external_id == external_id,
        )
        .limit(1)
    )
    report = FillReport(document_id=document_id, ext=ext or "?")

    rows = s.execute(
        select(DocumentItem, DraftItem)
        .join(DraftItem, DraftItem.document_item_id == DocumentItem.id)
        .join(Draft, Draft.id == DraftItem.draft_id)
        .where(
            DocumentItem.document_id == document_id,
            Draft.company_id == company_id,
            Draft.source == source,
            Draft.notice_id == external_id,
        )
        .order_by(DocumentItem.ordinal)
    ).all()

    form = open_form(str(store.abs_path(store.rel_path(doc.sha256))), ext or "")
    for di, it in rows:
        # **사람이 고친 글이 이긴다**(ADR-0055). `None` 과 `""` 가 다르다 —
        # 빈 문자열은 일부러 비운 것이라 집필기 글이 되살아나면 안 된다.
        body = it.edited_body if it.edited_body is not None else it.body
        if not body or not body.strip():
            continue
        if not di.anchor:
            report.no_anchor += 1
            report.left.append(di.title)
            continue
        from finnect.forms import Anchor

        if form.fill(Anchor.parse(di.anchor), body.strip()):
            report.filled += 1
        else:
            report.refused += 1
            report.left.append(di.title)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    form.save(out_path)
    return report
