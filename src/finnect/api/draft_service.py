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

import datetime as dt

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
from finnect.draft import limits, refs
from finnect.models import (
    Attachment,
    AttachmentFile,
    CompanyValue,
    Document,
    DocumentItem,
    DocumentKind,
    Draft,
    DraftEvidence,
    DraftItem,
    DraftValueEvidence,
    ItemNeed,
    ValueEvidence,
    WikiEvidence,
    WikiFact,
    WikiNode,
)
from finnect.wiki import profile, tree


def notice_draft(
    s: Session,
    company_id: str,
    source: str,
    external_id: str,
    *,
    running: bool = False,
) -> DraftOut:
    """이 회사가 이 공고에 대해 쓴 초안.

    **없으면 빈 목록이다.** 아직 안 쓴 것과 쓸 수 없는 것을 화면이 같은 자리에서
    말해야 하고, 404 는 원인을 안 남긴다.

    `running` 은 부르는 쪽이 준다 — **이 모듈은 `jobs` 를 모른다.** `wiki_service`
    가 진행을 낼 때와 같은 규율이고, 그래야 세션만 있으면 테스트가 돈다.
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
        running=running,
    )


class ItemNotFound(LookupError):
    """이 회사·이 공고의 초안에 그 항목이 없다."""


def edit_item(
    s: Session,
    company_id: str,
    source: str,
    external_id: str,
    document_item_id: int,
    text: str | None,
) -> DraftItemOut:
    """사람이 고친 글을 저장한다 (plan/21 T-0123 · ADR-0055).

    **`body` 를 안 건드린다.** 집필기의 출력은 그대로 두고 `edited_body` 에 얹는다 —
    되돌릴 자리가 남아야 하고, `draft_evidence` 의 문단 번호가 사람 편집을 따라
    어긋나면 안 된다.

    `text` 가 `None` 이면 **되돌리기**다. 빈 문자열은 되돌리기가 아니라
    **일부러 비운 것**이라 그대로 저장한다(ADR-0055 결정 6).

    **`status` 를 안 바꾼다.** 저 표는 집필이 어떻게 됐나를 말한다 — 사람이 고쳤다는
    사실은 `edited_at` 이 든다. 여기서 `drafted` 로 올리면 원래 `blank` 였던 자리가
    **물어볼 목록에서 조용히 빠진다.**
    """
    row = s.execute(
        select(DraftItem, DocumentItem)
        .join(Draft, Draft.id == DraftItem.draft_id)
        .join(DocumentItem, DocumentItem.id == DraftItem.document_item_id)
        .where(
            Draft.company_id == company_id,
            Draft.source == source,
            Draft.notice_id == external_id,
            DraftItem.document_item_id == document_item_id,
        )
    ).first()
    if row is None:
        raise ItemNotFound(f"초안에 없는 항목: {document_item_id}")

    it, di = row
    it.edited_body = text
    it.edited_at = None if text is None else dt.datetime.now(dt.UTC)

    facts = _facts(s, [it.id])
    needs = _needs(s, [di.id])
    return _item(s, it, di, facts, needs, {})


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

    # **`None` 과 `""` 가 다르다**(ADR-0055 결정 6). 빈 문자열은 사람이 일부러
    # 비운 것이라 집필기 글이 다시 나오면 안 된다.
    edited = it.edited_body is not None
    body = it.edited_body if edited else it.body

    texts = body.split("\n\n") if body else []
    check = limits.check(body or "", di.limit_text)
    required = needs.get(di.id, {})

    return DraftItemOut(
        document_item_id=di.id,
        number=di.number,
        title=di.title,
        instruction=di.instruction,
        status=it.status,
        edited=edited,
        # 고친 뒤에는 문단 번호가 근거와 안 맞는다. **행은 DB 에 그대로 있다** —
        # 화면에만 안 낸다(ADR-0055 결정 3)
        evidence_detached=edited and bool(by_para),
        original=it.body if edited else None,
        paragraphs=[
            ParagraphOut(
                ordinal=i, text=t, evidence=[] if edited else by_para.get(i, [])
            )
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


#: 자리 이름을 못 찾았을 때 화면에 낼 말. **영어 키를 그대로 내보내지 않는다.**
#:
#: 여기 떨어지는 것은 `item_need.place` 가 어느 표에도 없는 이름일 때뿐이고, 그건
#: **우리 배관이 어긋났다는 뜻이지 사용자가 알 일이 아니다**(T-0135 전에는 「solution」이
#: 한국어 라벨 자리에 떴다). 자리를 못 부르면 물어볼 수도 없으므로 **못 채운 자리로도
#: 안 센다** — `_missing` 이 이 값을 쓰는 쪽에서 그것까지 판단하지 않는다.
UNKNOWN_PLACE = "분류 안 된 자리"


def _label(place: str) -> str:
    """`wiki/profile.py` 와 `wiki/tree.py` 가 정본이다. **화면이 한국어를 짓지 않는다.**

    들어오는 것이 셋이다 — 매칭 정보 key(`headcount`) · 카테고리(`Customer`) ·
    **노드 경로**(`Financial/매출`). 앞의 둘은 표에서 꺼내고 경로는 **그대로 낸다**:
    마디 이름을 추출기가 한국어로 짓고, 경로가 곧 사용자가 위키에서 보는 자리 이름이다
    (`Spot.path` 와 같은 문자열 — 두 화면이 다르게 부르면 다른 자리로 읽힌다).

    **못 찾은 것만 폴백이다.** 이 함수의 요점이 「우리가 한국어를 짓지 않는다」인데
    폴백이 영어 키를 내면 그 문장이 거짓이 된다 — T-0135 전에는 「solution」이 한국어
    라벨 자리에 떴다.
    """
    spec = profile.PROFILE_KEYS.get(place)
    if spec is not None:
        return spec.label
    if "/" in place:
        return place
    return tree.CATEGORIES.get(place) or UNKNOWN_PLACE


def _facts(s: Session, item_ids: list[int]) -> dict[int, list[tuple[int, EvidenceOut]]]:
    """문단별 근거. **`fact_id` 로 위키까지 잇는다**(F6-13).

    **트랙 둘을 합친다**(plan/22 T-0134). 표가 둘이라 질의도 둘이고, 화면에서는
    한 줄로 섞여 나온다 — 사용자에게 「이건 노드고 저건 매칭 정보다」는 뜻이 없다.
    `fact_id` 는 **재료 공간 id** 라 값이면 음수다(`draft/refs.py`).
    """
    if not item_ids:
        return {}
    rows = s.execute(
        select(
            DraftEvidence.draft_item_id, DraftEvidence.paragraph, DraftEvidence.fact_id,
            DraftEvidence.chunk_id, DraftEvidence.source_type,
            WikiNode.path, WikiFact.text, WikiEvidence.quote,
        )
        .join(WikiFact, WikiFact.id == DraftEvidence.fact_id)
        .join(WikiNode, WikiNode.id == WikiFact.node_id)
        .outerjoin(
            WikiEvidence,
            (WikiEvidence.fact_id == DraftEvidence.fact_id)
            & (WikiEvidence.chunk_id == DraftEvidence.chunk_id),
        )
        .where(DraftEvidence.draft_item_id.in_(item_ids))
        .order_by(DraftEvidence.paragraph, DraftEvidence.id)
    ).all()

    value_rows = s.execute(
        select(
            DraftValueEvidence.draft_item_id, DraftValueEvidence.paragraph,
            DraftValueEvidence.value_id, DraftValueEvidence.chunk_id,
            DraftValueEvidence.source_type,
            CompanyValue.key, CompanyValue.value, CompanyValue.qualifier,
            CompanyValue.as_of, ValueEvidence.quote,
        )
        .join(CompanyValue, CompanyValue.id == DraftValueEvidence.value_id)
        .outerjoin(
            ValueEvidence,
            (ValueEvidence.value_id == DraftValueEvidence.value_id)
            & (ValueEvidence.chunk_id == DraftValueEvidence.chunk_id),
        )
        .where(DraftValueEvidence.draft_item_id.in_(item_ids))
        .order_by(DraftValueEvidence.paragraph, DraftValueEvidence.id)
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
    for iid, para, vid, cid, stype, key, value, qual, as_of, quote in value_rows:
        out.setdefault(iid, []).append((
            para,
            EvidenceOut(
                fact_id=refs.value_ref(vid), place=key, place_label=_label(key),
                text=_value_text(key, value, qual, as_of),
                chunk_id=cid, quote=quote, source_type=stype,
            ),
        ))
    #: **문단 순서로 다시 세운다.** 표 둘을 이어 붙이면 트랙 A 가 전부 앞에 선다
    for iid in out:
        out[iid].sort(key=lambda pair: pair[0])
    return out


def _value_text(key: str, value: str, qualifier: str | None, as_of: dt.date | None) -> str:
    """매칭 정보 한 칸을 근거 줄에 쓸 글자로.

    **`draft/service.py` `_value_text` 와 같은 모양이어야 한다** — 집필이 읽은 문장과
    화면이 보여 주는 문장이 다르면 근거 대조가 눈으로 안 된다.
    """
    spec = profile.PROFILE_KEYS.get(key)
    label = spec.label if spec else key
    body = f"{label} {profile.display(key, value)}"
    if qualifier:
        body = f"{body} ({qualifier})"
    return f"{body} — {as_of.isoformat()} 기준" if as_of else body


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

    #: **재료 공간 id 라 값이면 음수다**(`draft/refs.py`). 표가 둘이라 여기서 가른다
    node_ids, value_ids = refs.split(fact_ids)
    place_of: dict[int, str] = dict(
        s.execute(
            select(WikiFact.id, WikiNode.path)
            .join(WikiNode, WikiNode.id == WikiFact.node_id)
            .where(WikiFact.id.in_(node_ids))
        ).all()
    ) if node_ids else {}
    if value_ids:
        place_of.update({
            refs.value_ref(vid): key
            for vid, key in s.execute(
                select(CompanyValue.id, CompanyValue.key).where(CompanyValue.id.in_(value_ids))
            ).all()
        })
    #: 자리 → 그 자리의 사실을 받은 항목들.
    #:
    #: **경로를 조상 전부에 걸어 둔다**(ADR-0056). `item_need.place` 는 카테고리를
    #: 가리키는데 사실은 `Customer/고객문제` 같은 경로를 든다 — `draft/allot.py` 의
    #: `_index` 와 같은 규칙이라 **한쪽만 고치면 배분과 넘김이 갈린다.**
    holders: dict[str, set[int]] = {}
    for key, ids in allotment.items():
        for fid in ids:
            place = place_of.get(fid)
            if not place:
                continue
            parts = place.split("/")
            for depth in range(len(parts)):
                holders.setdefault("/".join(parts[: depth + 1]), set()).add(int(key))

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
