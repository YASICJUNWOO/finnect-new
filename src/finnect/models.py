"""저장 모델 — 출처별 원본 테이블 + 통합 뷰.

**API 가 준 컬럼을 전부 만든다. 이름도 API 필드명 그대로다.** 대소문자까지 지킨다.
Postgres 는 대소문자 섞인 식별자에 따옴표가 필요하지만 SQLAlchemy 가 자동으로 붙인다.

  raw_fetch          응답 통째 (봉투·쿼터 포함)
  bizinfo_notice     기업마당 22컬럼 전부
  kstartup_notice    K-Startup 30컬럼 전부
  notice (뷰)        둘을 공통 8필드로 매핑해 UNION ALL  → views.py
  attachment         첨부 메타. API 가 준 것
  attachment_file    첨부를 받아서 읽어 본 결과. 우리가 한 것 → plan/07 · ADR-0022
  ingest_run         수집 실행 기록. 코퍼스가 아니라 운영 기록이다

전부 TEXT 로 받는다. API 가 날짜도 "20260827" 문자열로 준다.
타입을 여기서 강제하면 이상한 값 하나에 적재가 통째로 깨진다.
파생 값은 derived_ 접두사로 구분한다. API 가 준 값과 우리가 만든 값을 섞지 않는다.

L1(요건·평가·양식), 근거 구간, 신뢰도, 프로필, 판정은 여기 없다.
plan/01 · plan/02 · plan/03 의 몫이다.
"""

from __future__ import annotations

import datetime as dt
import enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Source(enum.StrEnum):
    BIZINFO = "bizinfo"
    KSTARTUP = "kstartup"


class AttachmentStatus(enum.StrEnum):
    """첨부 0건과 '아직 안 봄'을 구분한다.

    기업마당은 목록 API 가 첨부를 알려준다. 첨부 0개가 431/1,538(28%)라
    LISTED + 0건이 정상 상태다.
    K-Startup 은 목록 API 에 첨부 필드 자체가 없다. detl_pg_url 을 긁기 전까지 UNKNOWN 이다.
    """

    LISTED = "listed"
    UNKNOWN = "unknown"


class AttachmentKind(enum.StrEnum):
    NOTICE_DOC = "공고문"  # printFileNm / printFlpthNm
    OTHER = "기타"  # fileNm / flpthNm


class FetchStatus(enum.StrEnum):
    """첨부 파일 하나를 받아 왔는가.

    NOT_HTML 이 따로 있는 이유는 기업마당이 **오류를 HTTP 200 + HTML 로** 주기 때문이다.
    목록 API 가 실패를 200 으로 주는 것과 같은 함정이고, 안 거르면 3KB 짜리 오류 페이지가
    hwp 파일로 저장돼 파서 실패로 둔갑한다.
    """

    OK = "ok"
    NOT_FOUND = "not_found"  # 4xx / 5xx
    NOT_HTML = "not_html"  # 200 인데 내용이 HTML 오류 페이지다
    TOO_LARGE = "too_large"
    FAILED = "failed"  # 네트워크·타임아웃


class ParseStatus(enum.StrEnum):
    """첨부에서 텍스트가 나왔는가.

    **셋을 섞지 않는 것이 이 표의 존재 이유다**(T-0004).
      UNSUPPORTED  안 해봤다   — 지원 목록에 없는 포맷
      FAILED       해봤는데 안 됐다
      EMPTY        해봤는데 0바이트다 — 이미지 PDF 가 여기 걸린다. T-0007 의 입력
    """

    OK = "ok"
    EMPTY = "empty"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"
    CONTAINER = "container"  # ZIP. 안의 목록만 읽었다(ADR-0022 4번)


class RunStatus(enum.StrEnum):
    """수집 실행의 끝.

    INTERRUPTED 가 따로 있는 이유는 **RUNNING 인 채로 프로세스가 죽으면 아무도 못 고치기**
    때문이다. 그 행을 그대로 두면 화면에서 영원히 '수집 중'으로 보인다.
    죽은 것을 성공으로도 실패로도 부르지 않는다.
    """

    RUNNING = "running"
    OK = "ok"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class RawFetch(Base):
    """응답 원문 한 건. 봉투까지 통째로 남긴다."""

    __tablename__ = "raw_fetch"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(16), index=True)
    request_url: Mapped[str] = mapped_column(Text)  # 인증키는 마스킹해서 넣는다
    page: Mapped[int | None] = mapped_column(Integer)
    fetched_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    payload: Mapped[dict] = mapped_column(JSONB)
    item_count: Mapped[int] = mapped_column(Integer)
    byte_size: Mapped[int] = mapped_column(Integer)
    # K-Startup 은 x-ratelimit-remaining 을 매 응답에 준다. 기업마당은 안 준다.
    ratelimit_remaining: Mapped[int | None] = mapped_column(Integer)


class _NoticeMixin:
    """출처 테이블 공통 부가 컬럼. API 필드가 아니라 우리가 붙이는 것이다."""

    # API 에 없던 필드가 오면 여기 담고 건수를 보고한다. 조용히 사라지지 않게.
    extra: Mapped[dict] = mapped_column(JSONB, default=dict)

    # 파생 값. API 가 준 값과 섞지 않으려고 접두사를 단다.
    derived_apply_start: Mapped[dt.date | None] = mapped_column(Date)
    derived_apply_end: Mapped[dt.date | None] = mapped_column(Date)

    # K-Startup 은 수정일시 필드가 없다. 변경 감지 수단이 해시뿐이다.
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    first_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    changed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    raw_fetch_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("raw_fetch.id", ondelete="SET NULL")
    )


class BizinfoNotice(_NoticeMixin, Base):
    """기업마당 공고. API 22컬럼 전부, 이름 그대로."""

    __tablename__ = "bizinfo_notice"
    __table_args__ = (Index("ix_bizinfo_notice_apply_end", "derived_apply_end"),)

    # PK 는 API 자연키. 실측 1,538/1,538 유일, 빈 값 0.
    pblancId: Mapped[str] = mapped_column(String(64), primary_key=True)

    bsnsSumryCn: Mapped[str | None] = mapped_column(Text)
    creatPnttm: Mapped[str | None] = mapped_column(Text)
    excInsttNm: Mapped[str | None] = mapped_column(Text)
    fileNm: Mapped[str | None] = mapped_column(Text)
    flpthNm: Mapped[str | None] = mapped_column(Text)
    hashtags: Mapped[str | None] = mapped_column(Text)
    inqireCo: Mapped[str | None] = mapped_column(Text)
    jrsdInsttNm: Mapped[str | None] = mapped_column(Text)
    pblancNm: Mapped[str | None] = mapped_column(Text)
    pblancUrl: Mapped[str | None] = mapped_column(Text)
    pldirSportRealmLclasCodeNm: Mapped[str | None] = mapped_column(Text)
    pldirSportRealmMlsfcCodeNm: Mapped[str | None] = mapped_column(Text)
    printFileNm: Mapped[str | None] = mapped_column(Text)
    printFlpthNm: Mapped[str | None] = mapped_column(Text)
    rceptEngnHmpgUrl: Mapped[str | None] = mapped_column(Text)
    refrncNm: Mapped[str | None] = mapped_column(Text)
    reqstBeginEndDe: Mapped[str | None] = mapped_column(Text)
    reqstMthPapersCn: Mapped[str | None] = mapped_column(Text)
    totCnt: Mapped[str | None] = mapped_column(Text)  # 응답 메타가 item 마다 반복된다
    trgetNm: Mapped[str | None] = mapped_column(Text)
    updtPnttm: Mapped[str | None] = mapped_column(Text)

    #: 이 출처의 API 필드 목록. 적재기가 미지 필드를 가려내는 데 쓴다.
    API_FIELDS: frozenset[str] = frozenset(
        {
            "bsnsSumryCn", "creatPnttm", "excInsttNm", "fileNm", "flpthNm",
            "hashtags", "inqireCo", "jrsdInsttNm", "pblancId", "pblancNm",
            "pblancUrl", "pldirSportRealmLclasCodeNm", "pldirSportRealmMlsfcCodeNm",
            "printFileNm", "printFlpthNm", "rceptEngnHmpgUrl", "refrncNm",
            "reqstBeginEndDe", "reqstMthPapersCn", "totCnt", "trgetNm", "updtPnttm",
        }
    )  # fmt: skip


class KstartupNotice(_NoticeMixin, Base):
    """K-Startup 공고. API 30컬럼 전부, 이름 그대로."""

    __tablename__ = "kstartup_notice"
    __table_args__ = (Index("ix_kstartup_notice_apply_end", "derived_apply_end"),)

    # PK 는 API 자연키. 실측 4,000/4,000 유일, 빈 값 0.
    pbanc_sn: Mapped[str] = mapped_column(String(64), primary_key=True)

    aply_excl_trgt_ctnt: Mapped[str | None] = mapped_column(Text)
    aply_mthd_eml_rcpt_istc: Mapped[str | None] = mapped_column(Text)
    aply_mthd_etc_istc: Mapped[str | None] = mapped_column(Text)
    aply_mthd_fax_rcpt_istc: Mapped[str | None] = mapped_column(Text)
    aply_mthd_onli_rcpt_istc: Mapped[str | None] = mapped_column(Text)
    aply_mthd_pssr_rcpt_istc: Mapped[str | None] = mapped_column(Text)
    aply_mthd_vst_rcpt_istc: Mapped[str | None] = mapped_column(Text)
    aply_trgt: Mapped[str | None] = mapped_column(Text)
    aply_trgt_ctnt: Mapped[str | None] = mapped_column(Text)
    biz_aply_url: Mapped[str | None] = mapped_column(Text)
    biz_enyy: Mapped[str | None] = mapped_column(Text)  # 업력. F2 자격 판별
    biz_gdnc_url: Mapped[str | None] = mapped_column(Text)
    biz_pbanc_nm: Mapped[str | None] = mapped_column(Text)
    biz_prch_dprt_nm: Mapped[str | None] = mapped_column(Text)
    biz_trgt_age: Mapped[str | None] = mapped_column(Text)  # 연령. F2
    detl_pg_url: Mapped[str | None] = mapped_column(Text)  # 첨부는 여기를 긁어야 나온다
    id: Mapped[str | None] = mapped_column(Text)  # API 가 주는 행 번호. 안정적이지 않다
    intg_pbanc_biz_nm: Mapped[str | None] = mapped_column(Text)  # HTML 엔티티가 섞여 온다
    intg_pbanc_yn: Mapped[str | None] = mapped_column(Text)
    pbanc_ctnt: Mapped[str | None] = mapped_column(Text)
    pbanc_ntrp_nm: Mapped[str | None] = mapped_column(Text)
    pbanc_rcpt_bgng_dt: Mapped[str | None] = mapped_column(Text)
    pbanc_rcpt_end_dt: Mapped[str | None] = mapped_column(Text)
    prch_cnpl_no: Mapped[str | None] = mapped_column(Text)
    prfn_matr: Mapped[str | None] = mapped_column(Text)
    rcrt_prgs_yn: Mapped[str | None] = mapped_column(Text)  # 모집중 여부. 검증된 서버측 필터
    sprv_inst: Mapped[str | None] = mapped_column(Text)
    supt_biz_clsfc: Mapped[str | None] = mapped_column(Text)
    supt_regin: Mapped[str | None] = mapped_column(Text)  # 지역. F2

    API_FIELDS: frozenset[str] = frozenset(
        {
            "aply_excl_trgt_ctnt", "aply_mthd_eml_rcpt_istc", "aply_mthd_etc_istc",
            "aply_mthd_fax_rcpt_istc", "aply_mthd_onli_rcpt_istc",
            "aply_mthd_pssr_rcpt_istc", "aply_mthd_vst_rcpt_istc", "aply_trgt",
            "aply_trgt_ctnt", "biz_aply_url", "biz_enyy", "biz_gdnc_url",
            "biz_pbanc_nm", "biz_prch_dprt_nm", "biz_trgt_age", "detl_pg_url", "id",
            "intg_pbanc_biz_nm", "intg_pbanc_yn", "pbanc_ctnt", "pbanc_ntrp_nm",
            "pbanc_rcpt_bgng_dt", "pbanc_rcpt_end_dt", "pbanc_sn", "prch_cnpl_no",
            "prfn_matr", "rcrt_prgs_yn", "sprv_inst", "supt_biz_clsfc", "supt_regin",
        }
    )  # fmt: skip


class Attachment(Base):
    """첨부 메타데이터. 이 슬라이스는 내려받지도 파싱하지도 않는다(plan/02).

    출처 테이블이 둘이라 FK 를 걸지 않고 (source, external_id) 로 가리킨다.
    """

    __tablename__ = "attachment"
    __table_args__ = (
        Index("ix_attachment_owner", "source", "external_id"),
        Index("ix_attachment_ext", "ext"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(16))
    external_id: Mapped[str] = mapped_column(String(64))
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(16))
    filename: Mapped[str] = mapped_column(Text)
    ext: Mapped[str | None] = mapped_column(String(16))
    url: Mapped[str | None] = mapped_column(Text)


class AttachmentFile(Base):
    """첨부 하나를 받아서 읽어 본 결과. **URL 이 키다**(ADR-0022).

    `attachment` 에 컬럼을 붙이지 않은 이유가 있다. 공고가 갱신되면 그 공고의 `attachment`
    행이 **통째로 지워지고 다시 깔린다**(ingest/runner.py `_flush`). 상태를 거기 얹으면
    재수집 한 번에 3,354건의 해독 결과가 날아간다.

    `attachment` 는 API 가 준 메타이고 여기는 우리가 한 일이다. 둘을 섞지 않는다.
    여기 값은 API 가 준 것이 아니라 우리가 잰 것이라 derived_ 접두사 규칙의 대상이 아니다.
    """

    __tablename__ = "attachment_file"
    __table_args__ = (
        Index("ix_attachment_file_status", "fetch_status", "parse_status"),
        Index("ix_attachment_file_sha256", "sha256"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    #: 내려받기 단위. 실측 3,354/3,354 유일.
    url: Mapped[str] = mapped_column(Text, unique=True)
    source: Mapped[str] = mapped_column(String(16))

    # --- 받아 오기 ---
    fetch_status: Mapped[str] = mapped_column(String(16))
    fetched_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    http_status: Mapped[int | None] = mapped_column(Integer)
    byte_size: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64))
    #: attachment_dir 기준 상대 경로. 저장소를 옮길 때 바뀌는 유일한 경계다.
    stored_path: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(Text)
    #: Content-Disposition 이 준 이름. URL 에는 파일명이 없다.
    server_filename: Mapped[str | None] = mapped_column(Text)
    fetch_error: Mapped[str | None] = mapped_column(Text)

    # --- 읽어 보기 ---
    #: 아직 안 해본 것은 NULL 이다. '안 해봤다'와 '해봤는데 안 됐다'를 구분한다.
    parse_status: Mapped[str | None] = mapped_column(String(16))
    parsed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    #: 어느 파서를 썼나. 파서를 바꿔 다시 돌릴 때 무엇이 바뀌었는지 보는 단서다.
    parser: Mapped[str | None] = mapped_column(String(32))
    #: 파일 내용에서 판정한 확장자. API 파일명이 준 것과 다를 수 있다.
    detected_ext: Mapped[str | None] = mapped_column(String(16))
    text_chars: Mapped[int | None] = mapped_column(Integer)
    text_path: Mapped[str | None] = mapped_column(Text)
    parse_error: Mapped[str | None] = mapped_column(Text)
    #: ZIP 안의 파일 목록. 풀지는 않는다. 166건 안에 무엇이 있는지 보려고 남긴다.
    contents: Mapped[dict] = mapped_column(JSONB, default=dict)


class IngestRun(Base):
    """수집 실행 한 건. CLI 와 관리 화면 버튼이 **같은 표에** 남긴다.

    코퍼스가 아니라 운영 기록이다. 여기 있는 값은 API 가 준 것이 아니라 우리가 센 것이라
    derived_ 접두사 규칙의 대상이 아니다.

    **실패한 실행도 행으로 남는다.** 적재 트랜잭션이 롤백돼도 이 행은 별도 세션에 커밋된다.
    두 API 모두 실패를 HTTP 200 으로 주기 때문에, 실패가 화면에서 '아무 일도 없었음'과
    구분되지 않으면 이 표는 없느니만 못하다.
    """

    __tablename__ = "ingest_run"
    __table_args__ = (Index("ix_ingest_run_source_started", "source", "started_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(16))
    only_open: Mapped[bool] = mapped_column(Boolean, default=False)
    trigger: Mapped[str] = mapped_column(String(16))  # cli | admin
    status: Mapped[str] = mapped_column(String(16))

    # 실행은 프로세스 안에서만 산다. 스케줄러도 잡 큐도 아니다(ADR-0011).
    # 죽은 프로세스의 RUNNING 행을 골라내는 유일한 단서라 같이 남긴다.
    pid: Mapped[int] = mapped_column(Integer)

    started_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    # 요청한 건수 제한. NULL 이면 전량이다.
    item_limit: Mapped[int | None] = mapped_column(Integer)
    # 출처가 말한 전량(기업마당 totCnt · K-Startup matchCount). 잘라 받아도 이 값은 안 변한다.
    expected: Mapped[int | None] = mapped_column(Integer)

    pages: Mapped[int] = mapped_column(Integer, default=0)
    items: Mapped[int] = mapped_column(Integer, default=0)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    changed: Mapped[int] = mapped_column(Integer, default=0)
    unchanged: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    attachments: Mapped[int] = mapped_column(Integer, default=0)
    ratelimit_remaining: Mapped[int | None] = mapped_column(Integer)

    # 처음 보는 필드 {이름: 건수}. 조용히 사라지지 않게 화면까지 들고 간다.
    unknown_fields: Mapped[dict] = mapped_column(JSONB, default=dict)

    report: Mapped[str | None] = mapped_column(Text)  # CLI 가 찍는 것과 같은 문자열
    error: Mapped[str | None] = mapped_column(Text)  # 실패 이유. 비어 있으면 안 된다

    @property
    def elapsed(self) -> str:
        """걸린 시간. 아직 도는 중이면 지금까지."""
        if self.started_at is None:
            return ""
        end = self.finished_at or dt.datetime.now(dt.UTC)
        secs = int((end - self.started_at).total_seconds())
        return f"{secs}초" if secs < 60 else f"{secs // 60}분 {secs % 60}초"

    @property
    def truncated(self) -> bool:
        """전량을 다 받지 않은 실행.

        **이걸 표시하지 않으면 맛보기 수집이 전량 수집으로 오인된다.** 건수만 보고
        '29,789건이어야 하는데 500건이네'를 실패로 읽거나, 반대로 맛보기 결과를
        모집단으로 믿게 된다. 둘 다 계획이 경고한 사고다.
        """
        if self.status != str(RunStatus.OK):
            return False
        if self.item_limit is not None and self.expected is not None:
            return self.item_limit < self.expected
        return self.item_limit is not None
