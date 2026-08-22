"""사업 위키 조회(S7). **읽기만 한다.**

`wiki/build.py` 가 이미 DB → `NodeView` 를 하고 있어서 여기는 그걸 응답 모양으로 옮기는
얇은 층이다. 조인을 여기서 다시 짜지 않는다 — 두 벌이 되면 한쪽만 고쳐지는 날이 온다.

**`attach.service` · `ingest.service` 를 임포트하지 않는다.** 저 둘이 httpx 와 파서를
끌고 오는데 `requirements.txt` 가 그것들을 뺐다. `wiki.build` 는 `wiki.markdown` 과
`wiki.topics` 만 끌고 오고 둘 다 순수 파이썬이다 — `wiki.service`(해독)는 파서를 쓰므로
**여기서 부르면 안 된다.**
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finnect.api.wiki_schemas import (
    EvidenceOut,
    FileProgressOut,
    ProfileKeyOut,
    ProfileOut,
    ProgressOut,
    StatementOut,
    StepOut,
    ValueOut,
    WikiFileOut,
    WikiNodeOut,
    WikiOut,
)
from finnect.models import (
    Chunk,
    CompanyValue,
    UserFile,
    ValueEvidence,
    WikiEvidence,
    WikiFact,
    WikiNode,
)
from finnect.wiki import build, export, markdown, profile, progress, tree


def get_wiki(session: Session, company_id: str) -> WikiOut:
    """S7 한 장(트랙 A). **위키가 없어도 카테고리 열이 온다**(ADR-0056).

    빈 화면을 "데이터 없음"으로 끝내지 않는 것이 `DESIGN.md` §7-5 다. 자리가 있어야
    사용자가 무엇이 없는지 알고, 무엇을 올려야 하는지 안다.
    """
    nodes = build.read_nodes(session, company_id)
    pages = {p.path: p for p in export.render(nodes, company_id)}
    files = build.read_files(session, company_id)

    review = session.scalar(
        select(func.count())
        .select_from(WikiFact)
        .join(WikiNode, WikiNode.id == WikiFact.node_id)
        .where(WikiFact.company_id == company_id, WikiNode.path == tree.REVIEW_PATH)
    )
    extractor = session.scalar(
        select(WikiFact.extractor).where(WikiFact.company_id == company_id).limit(1)
    )

    return WikiOut(
        company_id=company_id,
        nodes=[_node(n, pages.get(n.path)) for n in nodes],
        files=[
            WikiFileOut(
                filename=uf.filename,
                ext=uf.ext,
                byte_size=uf.byte_size,
                status=uf.status,
                parse_status=uf.parse_status,
                parser=uf.parser,
                parse_error=uf.parse_error,
                chunk_count=uf.chunk_count,
                page_count=uf.page_count,
                spots=made,
            )
            for uf, made in files
        ],
        categories=dict(tree.CATEGORIES),
        filled=sum(n.filled for n in nodes),
        total=len(nodes),
        review=review or 0,
        extractor=extractor,
    )


def get_profile(session: Session, company_id: str) -> ProfileOut:
    """회사 정보 한 장(트랙 B · `/company`). **열넷이 항상 온다.**

    **빈 칸이 물어볼 자리다**(ADR-0028). 열넷이 고정이라 못 채운 것을 셀 수 있고,
    셀 수 있어서 물어볼 수 있다 — 트랙 A 는 정답지가 없어 이걸 못 한다.
    """
    views = build.read_profile(session, company_id)

    rows = session.execute(
        select(ValueEvidence.value_id, UserFile.filename, Chunk.page, ValueEvidence.quote)
        .join(Chunk, Chunk.id == ValueEvidence.chunk_id)
        .join(UserFile, UserFile.id == ValueEvidence.user_file_id)
        .where(ValueEvidence.company_id == company_id)
        .order_by(UserFile.filename, Chunk.ordinal)
    ).all()
    by_value: dict[int, list[EvidenceOut]] = {}
    for vid, filename, page, quote in rows:
        by_value.setdefault(vid, []).append(
            EvidenceOut(filename=filename, page=page, quote=quote)
        )

    def out(v) -> ValueOut:  # noqa: ANN001
        return ValueOut(
            value=v.value,
            display=profile.display(v.key, v.value),
            qualifier=v.qualifier,
            as_of=v.as_of.isoformat() if v.as_of else None,
            status=v.status,
            evidence=by_value.get(v.id, []),
        )

    keys = [
        ProfileKeyOut(
            key=view.key,
            label=view.label,
            eligibility=view.eligibility,
            current=[out(v) for v in view.current],
            history=[out(v) for v in view.history],
            conflicted=view.conflicted,
        )
        for view in views
    ]
    return ProfileOut(
        company_id=company_id,
        keys=keys,
        filled=sum(1 for k in keys if k.current),
        total=len(keys),
        conflicts=sum(1 for k in keys if k.conflicted),
    )


def get_markdown(session: Session, company_id: str) -> str | None:
    """위키 전부를 마크다운 한 덩어리로. 아무것도 없으면 `None`.

    **저장된 파일을 읽는 것이 아니다.** 매번 만든다 — `wiki/markdown.py` 참고.
    """
    pages = export.render(build.read_nodes(session, company_id), company_id)
    if not pages:
        return None
    return export.bundle(pages, company_id)


def _node(n: build.NodeView, page: export.Page | None) -> WikiNodeOut:
    """노드 하나를 응답 모양으로. **빈 뼈대는 장이 없다.**"""
    return WikiNodeOut(
        path=n.path,
        name=n.name,
        category=n.category,
        parent=n.parent,
        depth=n.depth,
        statements=[_statement(f) for f in n.facts],
        source_count=n.source_count,
        filled=n.filled,
        grade=page.grade if page else export.GRADE_UNKNOWN,
        source=list(page.sources) if page else [],
        source_path=list(page.source_paths) if page else [],
        updated_at=page.updated_at if page else None,
        markdown=page.body if page else "",
    )


def _statement(s: markdown.Statement) -> StatementOut:
    return StatementOut(text=s.text, topic=s.topic, evidence=[_evidence(e) for e in s.evidence])


def _evidence(e: markdown.Evidence) -> EvidenceOut:
    return EvidenceOut(filename=e.filename, page=e.page, quote=e.quote)


def get_progress(session: Session, company_id: str, *, running: bool) -> ProgressOut:
    """구축 진행 한 장(S1 · SPEC F1-1-9 · plan/15 T-0060).

    **`running` 을 인자로 받는다.** 값은 `ingest.jobs` 의 락에서 오는데 그것은 쓰기 경로의
    것이고 여기는 읽기 경로다. 이 모듈이 락을 직접 들여다보면 조회가 실행에 묶인다 —
    부르는 쪽(`api/app.py`)이 알려 준다.

    **아무것도 안 올렸어도 200 이고 단계 다섯이 온다.** 처음 온 사람도 무엇이 일어날지
    먼저 볼 수 있어야 한다(DESIGN.md §7-5).
    """
    files = build.read_files(session, company_id)
    #: **자리 셈을 S7 과 같은 표로 한다.** 여기가 다른 것을 세면 같은 위키가 화면 둘에서
    #: 다른 진도로 보인다
    nodes = build.read_nodes(session, company_id)

    # **칸마다 무엇이 나왔는지 같이 낸다**(plan/15 T-0062). 넷은 컬럼에서 오는데
    # 사실 수만 근거에서 온다 — `wiki_evidence` 가 파일과 사실을 잇는 유일한 자리다.
    # `distinct` 인 것은 한 사실이 같은 파일의 청크 여럿을 근거로 들 수 있기 때문이다.
    facts = dict(
        session.execute(
            select(WikiEvidence.user_file_id, func.count(func.distinct(WikiEvidence.fact_id)))
            .where(WikiEvidence.company_id == company_id)
            .group_by(WikiEvidence.user_file_id)
        ).all()
    )

    rows: list[FileProgressOut] = []
    for uf, made in files:
        stage = progress.stage_of(
            uf.status,
            running=running,
            failed=bool(uf.extract_error),
            #: **자리를 셈의 기준으로 쓴다.** 사실 수가 아니다 — 사실은 파일 사이에
            #: 겹치지만 자리는 "이 파일이 위키에 무엇을 보탰나" 다
            empty=not made,
        )
        rows.append(
            FileProgressOut(
                filename=uf.filename,
                ext=uf.ext,
                byte_size=uf.byte_size,
                status=uf.status,
                reached=stage.reached,
                label=stage.label,
                moving=stage.moving,
                ok=stage.ok,
                #: **해독 실패가 먼저다.** 글자를 못 얻었으면 사실을 못 뽑은 것은 그
                #: 결과다. 둘 다 비면 null 이고, 그때는 `label` 이 전부 말한다
                detail=uf.parse_error or uf.extract_error or None,
                chunk_count=uf.chunk_count,
                page_count=uf.page_count,
                text_chars=uf.text_chars,
                parser=uf.parser,
                fact_count=facts.get(uf.id, 0),
                spots=made,
            )
        )

    #: **충돌은 트랙 B 의 것이다**(ADR-0056). 트랙 A 는 값이 없어 충돌 판정을 안 한다
    conflicts = session.scalar(
        select(func.count())
        .select_from(CompanyValue)
        .where(CompanyValue.company_id == company_id, CompanyValue.status == "conflict")
    )
    extractor = session.scalar(
        select(WikiFact.extractor).where(WikiFact.company_id == company_id).limit(1)
    )

    return ProgressOut(
        company_id=company_id,
        steps=[StepOut(key=s.key, label=s.label) for s in progress.STEPS],
        files=rows,
        spot_titles={n.path: n.name for n in nodes},
        total=len(rows),
        done=sum(f.ok for f in rows),
        moving=sum(f.moving for f in rows),
        # **글자가 안 나온 것과 못 읽은 것을 갈라 센다.** 스캔본은 OCR 이 붙으면 읽히고
        # 포맷이 없는 것은 안 읽힌다 — 사용자가 할 일이 다르다.
        needs_review=sum(f.status == "needs_review" for f in rows),
        stuck=sum(not f.ok and not f.moving and f.status != "needs_review" for f in rows),
        running=running,
        filled=sum(n.filled for n in nodes),
        slots=len(nodes),
        conflicts=conflicts or 0,
        extractor=extractor,
    )
