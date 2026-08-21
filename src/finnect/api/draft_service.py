"""초안 조회 (plan/16 · F6).

**`finnect.draft.service` 를 임포트하지 않는다.** 그 모듈은 쓰기 경로라 `llm` ·
`trace` 를 끌고 오고, `requirements.txt` 가 `httpx` 를 뺐다. 임포트하면 **로컬은
통과하고 배포본만 죽는다** — `api/admin_service.py` 가 `attach.service` 를 안 부르는
것과 같은 규율이고 `tests/test_admin_api.py` 가 막아 둔다.

여기서 쓰는 것은 표 셋(`draft` · `draft_item` · `draft_evidence`)과 `draft/limits.py`
하나다. 그 파일은 `re` 밖에 안 쓴다.

## 분량을 저장하지 않고 계산한다

`limit_text` 는 `document_item` 에, 본문은 `draft_item` 에 있다. 둘로 계산되는 값이라
**읽을 때마다 만드는 뷰**다 — 들고 있으면 둘 중 하나가 먼저 낡는다(위키 마크다운과
같은 이유).

## 자리 이름을 화면이 짓지 않는다

`place_label` 을 같이 보낸다. `topics.display()` 가 단위를 한 자리에서 붙이는 것과
같은 이유다 — 화면과 API 가 각자 한국어를 지으면 갈리고, 갈린 순간 어느 쪽이 맞는지
알 수 없다.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from finnect.api.schemas import (
    DraftDocumentOut,
    DraftItemOut,
    DraftOut,
    EvidenceOut,
    LengthOut,
    MissingOut,
    ParagraphOut,
)
from finnect.draft import limits
from finnect.models import (
    Attachment,
    AttachmentFile,
    Document,
    DocumentItem,
    DocumentKind,
    Draft,
    DraftEvidence,
    DraftItem,
    ItemNeed,
    WikiEvidence,
    WikiFact,
)
from finnect.wiki import topics


def notice_draft(s: Session, company_id: str, source: str, external_id: str) -> DraftOut:
    """이 회사가 이 공고에 대해 쓴 초안.

    **없으면 빈 목록이다.** 아직 안 쓴 것과 쓸 수 없는 것을 화면이 같은 자리에서
    말해야 하고, 404 는 원인을 안 남긴다.
    """
    drafts = s.scalars(
        select(Draft).where(
            Draft.company_id == company_id,
            Draft.source == source,
            Draft.notice_id == external_id,
        )
    ).all()
    done = {d.document_id for d in drafts}

    # 이 공고에 붙은 서술형 양식 — **초안이 없는 것을 세려고** 본다
    narrative = set(
        s.scalars(
            select(Document.id)
            .join(AttachmentFile, AttachmentFile.sha256 == Document.sha256)
            .join(Attachment, Attachment.url == AttachmentFile.url)
            .where(
                Attachment.source == source,
                Attachment.external_id == external_id,
                Document.kind == str(DocumentKind.NARRATIVE),
            )
        ).all()
    )

    return DraftOut(
        company_id=company_id,
        source=source,
        external_id=external_id,
        documents=[_document(s, d) for d in drafts],
        pending_documents=len(narrative - done),
    )


def _document(s: Session, draft: Draft) -> DraftDocumentOut:
    doc = s.get(Document, draft.document_id)
    filename = s.scalar(
        select(Attachment.filename)
        .join(AttachmentFile, AttachmentFile.url == Attachment.url)
        .where(AttachmentFile.sha256 == doc.sha256)
        .limit(1)
    )

    rows = s.execute(
        select(DraftItem, DocumentItem)
        .join(DocumentItem, DocumentItem.id == DraftItem.document_item_id)
        .where(DraftItem.draft_id == draft.id)
        .order_by(DraftItem.ordinal)
    ).all()

    facts = _facts(s, [r[0].id for r in rows])
    needs = _needs(s, [r[1].id for r in rows])
    taken = _who_took(s, draft, rows, needs)

    made = {di.id: _item(s, it, di, facts, needs, taken) for it, di in rows}
    return DraftDocumentOut(
        document_id=doc.id,
        title=doc.title,
        filename=filename or "",
        allotted_by=draft.allotted_by,
        items=_tree(made, [di for _, di in rows]),
    )


def _item(  # noqa: PLR0913
    s: Session,
    it: DraftItem,
    di: DocumentItem,
    facts: dict[int, list[tuple[int, EvidenceOut]]],
    needs: dict[int, dict[str, bool]],
    taken: dict[int, list[str]],
) -> DraftItemOut:
    del s
    by_para: dict[int, list[EvidenceOut]] = {}
    for para, ev in facts.get(it.id, []):
        by_para.setdefault(para, []).append(ev)

    texts = it.body.split("\n\n") if it.body else []
    check = limits.check(it.body or "", di.limit_text)
    required = needs.get(di.id, {})

    return DraftItemOut(
        document_item_id=di.id,
        number=di.number,
        title=di.title,
        instruction=di.instruction,
        status=it.status,
        paragraphs=[
            ParagraphOut(ordinal=i, text=t, evidence=by_para.get(i, []))
            for i, t in enumerate(texts)
        ],
        missing=[_missing(p, required.get(p, True)) for p in (it.missing or [])],
        missing_optional=[_missing(p, False) for p in (it.missing_optional or [])],
        length=LengthOut(
            verdict=check.verdict,
            limit_text=check.limit.raw if check.limit else None,
            measured=check.measured,
            note=check.note,
        ),
        yielded_to=taken.get(di.id, []),
        error=it.error,
    )


def _missing(place: str, required: bool) -> MissingOut:  # noqa: FBT001
    return MissingOut(place=place, place_label=_label(place), required=required)


def _label(place: str) -> str:
    """`topics.py` 가 정본이다. **화면이 한국어를 짓지 않는다.**"""
    spec = topics.SLOTS.get(place)
    if spec is not None:
        return spec.label
    return topics.EVENT_ORBITS.get(place, place)


def _facts(s: Session, item_ids: list[int]) -> dict[int, list[tuple[int, EvidenceOut]]]:
    """문단별 근거. **`fact_id` 로 위키까지 잇는다**(F6-13)."""
    if not item_ids:
        return {}
    rows = s.execute(
        select(
            DraftEvidence.draft_item_id, DraftEvidence.paragraph, DraftEvidence.fact_id,
            DraftEvidence.chunk_id, DraftEvidence.source_type,
            WikiFact.place, WikiFact.text, WikiEvidence.quote,
        )
        .join(WikiFact, WikiFact.id == DraftEvidence.fact_id)
        .outerjoin(
            WikiEvidence,
            (WikiEvidence.fact_id == DraftEvidence.fact_id)
            & (WikiEvidence.chunk_id == DraftEvidence.chunk_id),
        )
        .where(DraftEvidence.draft_item_id.in_(item_ids))
        .order_by(DraftEvidence.paragraph, DraftEvidence.id)
    ).all()

    out: dict[int, list[tuple[int, EvidenceOut]]] = {}
    for iid, para, fid, cid, stype, place, text, quote in rows:
        out.setdefault(iid, []).append((
            para,
            EvidenceOut(
                fact_id=fid, place=place, place_label=_label(place), text=text,
                chunk_id=cid, quote=quote, source_type=stype,
            ),
        ))
    return out


def _needs(s: Session, item_ids: list[int]) -> dict[int, dict[str, bool]]:
    """`missing` 이 필수인지 선택인지 여기서 온다."""
    if not item_ids:
        return {}
    out: dict[int, dict[str, bool]] = {}
    for iid, place, req in s.execute(
        select(ItemNeed.document_item_id, ItemNeed.place, ItemNeed.required).where(
            ItemNeed.document_item_id.in_(item_ids)
        )
    ).all():
        out.setdefault(iid, {})[place] = req
    return out


def _who_took(
    s: Session, draft: Draft, rows: list, needs: dict[int, dict[str, bool]]
) -> dict[int, list[str]]:  # noqa: ANN001
    """`yielded` 인 항목이 원했던 자리를 **누가 맡았나.**

    **못 받은 항목의 배분은 비어 있다.** 그래서 "이 항목이 받은 사실" 로는 못 찾고,
    **이 항목이 원했던 자리(`ItemNeed`)** 에서 출발해 그 자리의 사실을 누가 받았는지
    거꾸로 찾는다.

    **저장하지 않는다** — 배분에서 계산되는 값이다.

    이것이 없으면 화면이 "못 채웠어요" 라고만 말하는데, 그건 물어볼 자리가 아니다.
    **"그 얘기는 6번에 썼어요" 라고 말할 자리다.**
    """
    label = {di.id: (di.number or di.title[:12]) for _, di in rows}
    allotment = draft.allotment or {}
    fact_ids = {f for v in allotment.values() for f in v}
    if not fact_ids:
        return {}

    place_of = dict(
        s.execute(select(WikiFact.id, WikiFact.place).where(WikiFact.id.in_(fact_ids))).all()
    )
    #: 자리 → 그 자리의 사실을 받은 항목들
    holders: dict[str, set[int]] = {}
    for key, ids in allotment.items():
        for fid in ids:
            place = place_of.get(fid)
            if place:
                holders.setdefault(place, set()).add(int(key))

    out: dict[int, list[str]] = {}
    for it, di in rows:
        if it.status != "yielded":
            continue
        others = {
            label[o]
            for place in needs.get(di.id, {})
            for o in holders.get(place, set())
            if o != di.id and o in label
        }
        if others:
            out[di.id] = sorted(others)
    return out


def _tree(made: dict[int, DraftItemOut], rows: list[DocumentItem]) -> list[DraftItemOut]:
    """부모-자식으로 접는다. **평평하게 내보내면 화면이 트리를 다시 세운다.**"""
    top: list[DraftItemOut] = []
    for di in rows:
        node = made[di.id]
        parent = made.get(di.parent_id) if di.parent_id else None
        (parent.children if parent is not None else top).append(node)
    return top
