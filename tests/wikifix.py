"""테스트가 위키 사실을 손으로 세울 때 쓰는 헬퍼(ADR-0056).

**트랙이 둘로 갈리면서 사실 하나를 만드는 데 표 둘이 필요해졌다** — 서술은 노드가
있어야 하고, 값은 `company_value` 로 간다. 그 배관을 테스트마다 적으면 어휘가 바뀔 때
스무 곳을 고쳐야 한다.

`conftest.py` 가 아니라 보통 모듈인 이유는 **픽스처가 아니라 함수라서다.** 부르는 쪽이
세션을 들고 있고 여기는 행만 만든다.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from finnect.models import CompanyValue, FactKind, WikiFact, WikiNode
from finnect.wiki import tree


def node(s: Session, company_id: str, path: str) -> WikiNode:
    """노드 하나와 **조상 전부**를 만든다. 이미 있으면 그것을 준다."""
    got = None
    for cur in tree.ancestors(path):
        got = s.scalar(
            select(WikiNode).where(WikiNode.company_id == company_id, WikiNode.path == cur)
        )
        if got is None:
            got = WikiNode(
                company_id=company_id,
                path=cur,
                category=tree.category_of(cur),
                name=tree.name_of(cur),
                parent=tree.parent_of(cur),
                norm_path=tree.norm_path(cur),
            )
            s.add(got)
            s.flush()
    assert got is not None
    return got


def fact(
    s: Session,
    company_id: str,
    path: str,
    text: str,
    *,
    key: str | None = None,
    extractor: str = "stub/v1",
) -> WikiFact:
    """노드에 앉는 사실 하나(트랙 A)."""
    n = node(s, company_id, path)
    k = key or text[:40]
    row = WikiFact(
        company_id=company_id,
        node_id=n.id,
        kind=str(FactKind.EVENT),
        key=k,
        norm_key=tree.norm(k),
        dedupe_key=f"event|{path}|{k}",
        text=text,
        extractor=extractor,
    )
    s.add(row)
    s.flush()
    return row


def value(
    s: Session,
    company_id: str,
    key: str,
    val: str,
    *,
    as_of: dt.date | None = None,
    qualifier: str | None = None,
    status: str = "current",
    extractor: str = "stub/v1",
) -> CompanyValue:
    """회사 정보 한 칸(트랙 B). **트리에 안 앉는다.**"""
    row = CompanyValue(
        company_id=company_id,
        key=key,
        value=val,
        qualifier=qualifier,
        as_of=as_of,
        status=status,
        dedupe_key=f"value|{key}|{qualifier or ''}|{as_of or ''}|{val}",
        extractor=extractor,
    )
    s.add(row)
    s.flush()
    return row
