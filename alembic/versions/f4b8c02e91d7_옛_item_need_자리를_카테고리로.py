"""옛 item_need 자리를 카테고리로 — plan/22 T-0135

`item_need.place` 가 옛 orbit 이름으로 적혀 있는데 [ADR-0056](
../../docs/adr/0056-위키를-동적-노드-트리로-바꾸고-매칭-정보를-따로-뽑는다.md) 이 자리
이름을 카테고리 열로 바꿨다. **한 글자도 안 겹친다.**

    옛  problem · solution · team · roadmap · identity · customer · market · region ·
        traction · finance                                          (소문자 영어)
    새  Company · Product · Market · Competitor · Customer ·
        BusinessModel · Financial · Custom · Plan · Events            (대문자 영어)

`c7f2a91b4d38` 이 `wiki_fact` 만 옮기고 여기를 안 건드렸다. **양식 읽기는 캐시라
저절로 안 갱신된다** — `read_forms` 가 `needs_decided_by` 가 있으면 건너뛴다. 그대로
두면 배포본의 모든 항목이 `blank` 이 된다.

## 셋은 한 행이 둘이 된다

표를 손으로 짜지 않고 **옛 `TOPIC_ORBIT` 과 새 `FIXTURE_PATH` 를 topic 으로 합성해**
뽑았다. 그랬더니 orbit 열 중 셋이 카테고리 둘로 흩어졌다.

    solution   솔루션과 기술  →  Product · Custom
    market     시장과 경쟁    →  Market · Competitor
    traction   매출과 성과    →  BusinessModel · Financial

**둘 다 만든다.** 하나만 고르면 「솔루션과 기술」을 요구했던 항목이 기술·특허·인증을
통째로 못 받는다 — 재료를 잃는 쪽이 넓어지는 쪽보다 나쁘다. 넓어진 대가는 T-0136 이
잰다.

## 값 키 열넷은 안 건드린다

`headcount`·`location` 같은 이름이 **하나도 안 바뀌었다**(옛 `VALUE_SPECS` 와 새
`PROFILE_KEYS` 의 대칭차가 0). 옮길 것이 없다.

**표를 코드에서 임포트하지 않고 여기 얼린다.** `c7f2a91b4d38` 과 같은 이유다 — 다음
사람이 이 파일을 돌릴 때 코드가 또 바뀌어 있을 수 있다.

Revision ID: f4b8c02e91d7
Revises: e2d5a71c0f43
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4b8c02e91d7"
down_revision: str | Sequence[str] | None = "e2d5a71c0f43"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: 옛 orbit → 새 카테고리 열. **값이 목록인 이유는 셋이 갈려서다.**
ORBIT_CATEGORIES: dict[str, tuple[str, ...]] = {
    "identity": ("Company",),
    "team": ("Company",),
    "region": ("Company",),
    "problem": ("Customer",),
    "customer": ("Customer",),
    "roadmap": ("Plan",),
    "finance": ("Financial",),
    "solution": ("Product", "Custom"),
    "market": ("Market", "Competitor"),
    "traction": ("Financial", "BusinessModel"),
}


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, document_item_id, place, required FROM item_need")
    ).fetchall()

    for row_id, item_id, place, required in rows:
        cats = ORBIT_CATEGORIES.get(place)
        if cats is None:
            #: 값 키 열넷이거나 이미 카테고리다. **손대지 않는다**
            continue

        #: **갈아 끼우지 않고 넣고 지운다.** `UPDATE ... SET place = 'Product'` 는 같은
        #: 항목이 이미 `Product` 를 요구하고 있으면 `(document_item_id, place)` 유니크에
        #: 걸려 마이그레이션 전체가 죽는다 — 옛 `solution` 과 새 어휘가 한 항목에 섞여
        #: 있는 것은 **드문 일이 아니라 이 표의 정상 상태다**(양식을 두 번 읽었으면 그렇다).
        for cat in cats:
            exists = conn.execute(
                sa.text("SELECT 1 FROM item_need WHERE document_item_id = :d AND place = :p"),
                {"d": item_id, "p": cat},
            ).first()
            if exists:
                continue
            conn.execute(
                sa.text(
                    "INSERT INTO item_need (document_item_id, place, place_kind, required) "
                    "VALUES (:d, :p, 'event', :r)"
                ),
                {"d": item_id, "p": cat, "r": required},
            )
        conn.execute(sa.text("DELETE FROM item_need WHERE id = :i"), {"i": row_id})


def downgrade() -> None:
    """**되돌리지 않는다.** 한 행이 둘이 된 것을 다시 하나로 접으면 어느 쪽이 원래
    행이었는지 알 방법이 없다 — 옛 orbit 이름이 어디에도 안 남아 있다."""
    raise NotImplementedError(
        "item_need 자리 매핑은 되돌릴 수 없다 — 옛 orbit 이름이 안 남는다"
    )
