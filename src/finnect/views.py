"""통합 뷰 — 두 출처를 공통 8필드로 매핑한다.

**매핑이 여기 한 곳에만 있다.** 두 출처는 필드 이름을 하나도 공유하지 않으므로
(기업마당 22개 · K-Startup 30개 · 교집합 0) 전부 수동 대응이다.

물리 테이블이 아니라 뷰인 이유는 원본 두 벌과의 동기화 문제를 없애기 위해서다.
매핑을 고칠 때 재적재가 아니라 뷰 정의만 바꾸면 된다.

키는 (source, external_id) 두 개 조합이다. 각 출처 테이블이 자기 PK 를 따로 갖는다.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from finnect.models import Base

CREATE_NOTICE_VIEW = """
CREATE OR REPLACE VIEW notice AS
SELECT
    'bizinfo'                                   AS source,
    b."pblancId"                                AS external_id,
    b."pblancNm"                                AS title,
    b."excInsttNm"                              AS organization,
    b."jrsdInsttNm"                             AS supervisor,
    b."pldirSportRealmLclasCodeNm"              AS category,
    b.derived_apply_start                       AS apply_start,
    b.derived_apply_end                         AS apply_end,
    b."reqstBeginEndDe"                         AS apply_period_raw,
    b."pblancUrl"                               AS detail_url,
    b."bsnsSumryCn"                             AS summary,
    'listed'                                    AS attachment_status,
    b.content_hash                              AS content_hash,
    b.first_seen_at                             AS first_seen_at,
    b.last_seen_at                              AS last_seen_at,
    b.changed_at                                AS changed_at
FROM bizinfo_notice b
UNION ALL
SELECT
    'kstartup',
    k.pbanc_sn,
    k.biz_pbanc_nm,
    k.pbanc_ntrp_nm,
    k.sprv_inst,
    k.supt_biz_clsfc,
    k.derived_apply_start,
    k.derived_apply_end,
    -- 둘 중 하나가 NULL 이어도 남는 쪽은 살린다
    NULLIF(concat_ws(' ~ ', k.pbanc_rcpt_bgng_dt, k.pbanc_rcpt_end_dt), ''),
    k.detl_pg_url,
    k.pbanc_ctnt,
    'unknown',
    k.content_hash,
    k.first_seen_at,
    k.last_seen_at,
    k.changed_at
FROM kstartup_notice k
"""

DROP_NOTICE_VIEW = "DROP VIEW IF EXISTS notice"


class Notice(Base):
    """읽기 전용. 뷰라서 Alembic 이 테이블로 만들지 않도록 표시한다."""

    __tablename__ = "notice"
    __table_args__ = {"info": {"is_view": True}}

    source: Mapped[str] = mapped_column(String(16), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str | None] = mapped_column(Text)
    organization: Mapped[str | None] = mapped_column(Text)
    supervisor: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    apply_start: Mapped[dt.date | None] = mapped_column(Date)
    apply_end: Mapped[dt.date | None] = mapped_column(Date)
    apply_period_raw: Mapped[str | None] = mapped_column(Text)
    detail_url: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    attachment_status: Mapped[str | None] = mapped_column(String(16))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    first_seen_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    changed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
