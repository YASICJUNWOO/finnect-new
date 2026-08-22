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
  user_file          사용자가 올린 파일 하나        → plan/12 · ADR-0029
  chunk              그 파일에서 나온 원문 조각      → plan/12 · ADR-0014

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
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


#: JSONB 를 SQLite 에서만 낮춘다. **Postgres DDL 은 그대로라 마이그레이션이 안 바뀐다.**
#:
#: 있는 이유는 테스트다. 위키 테스트 · 초안 테스트가 **DB 없이 돌아야 하는데**
#: SQLite 가 JSONB 를 못 만들어서, 그 표 하나 때문에 전체를 못 세운다.
_JSON = JSONB().with_variant(JSON, "sqlite")


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
    #: `_JSON` 을 쓰는 이유는 테스트다 — plan/17 대조 테스트가 이 표를 SQLite 에
    #: 세워야 한다(지원분야 중분류가 뷰에 없어 출처별 표에서 읽는다).
    #: **Postgres DDL 은 그대로라 마이그레이션이 안 바뀐다**
    extra: Mapped[dict] = mapped_column(_JSON, default=dict)

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
    contents: Mapped[dict] = mapped_column(_JSON, default=dict)


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


class DocumentKind(enum.StrEnum):
    """구간 하나가 무엇인가.

    **UNKNOWN 이 기본이다.** 서술형 양식과 공고문의 절은 생김새가 같아서
    규칙으로 못 가른다 — 네 번 실패했다. 그 판정은 LLM 이 하고(plan/11 T-0036),
    붙기 전까지는 '모른다'로 남는다. **모르는 것을 아는 척하지 않는다.**
    """

    #: 채워 내는 서식. 규칙으로 갈린다 — 끝에 '신청합니다 / 귀하 / (인)' 이 온다
    FIELDS = "fields"
    #: 글로 쓰는 양식. **T-0036 이 붙어야 채워진다**
    NARRATIVE = "narrative"
    #: 채울 것이 없다. 공고문·안내문·지침
    NONE = "none"
    #: 아직 안 갈랐다
    UNKNOWN = "unknown"


class Document(Base):
    """공고가 요구하는 문서 한 벌. **첨부 텍스트 안의 한 구간이다**(plan/11 T-0035).

    **파일 하나가 문서 하나가 아니다.** 한 파일에 공고문 → 붙임1 신청서 →
    붙임2 동의서가 이어 붙는다.

    키가 `sha256` 인 이유는 `attachment_file` 과 같다(ADR-0022). 공고를 다시 수집하면
    `attachment` 행이 통째로 갈리는데(기업마당은 조회수가 해시 재료라 **매번 1,538건
    전부**), 공고에 매달면 재수집 한 번에 날아간다. 공고와의 연결은 표를 만들지 않고
    `attachment → attachment_file → sha256` 조인으로 푼다.

    덤으로 **같은 양식이 여러 공고에 붙어도 한 번만 저장되고 한 번만 판정된다.**
    """

    __tablename__ = "document"
    __table_args__ = (
        UniqueConstraint("sha256", "seq", name="uq_document_sha_seq"),
        Index("ix_document_kind", "kind"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    #: 첨부 파일 내용의 주소. `attachment_file.sha256` 과 같다
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    #: 그 파일 안에서 몇 번째 구간인가
    seq: Mapped[int] = mapped_column(Integer)

    #: 구간 표지 원문. `[붙임2] 사업계획서`
    title: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(16))

    #: 원문 텍스트에서의 자리. **나중에 붙일 수 없다**(ADR-0014)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)

    #: 무엇이 판정했나. `rule/v1` · `llm/<모델>`. 다시 판정할 때 무엇이 바뀌었는지 본다
    decided_by: Mapped[str] = mapped_column(String(32))
    extracted_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DocumentItem(Base):
    """문서 안의 작성 항목 하나.

    지금은 `fields`(칸 채우기)만 찬다. 서술형 항목은 T-0036 이 붙어야 생긴다.
    """

    __tablename__ = "document_item"
    __table_args__ = (Index("ix_document_item_doc", "document_id", "ordinal"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("document.id", ondelete="CASCADE"), index=True
    )
    #: 트리. 서술형에서 쓴다
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("document_item.id", ondelete="CASCADE")
    )
    ordinal: Mapped[int] = mapped_column(Integer)

    #: `2-1`. **절마다 1부터 다시 시작하므로 이것만으로는 트리가 안 선다**(plan/11 T-0039)
    number: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    #: 양식이 쓴 "무엇을 쓰라". **우리가 고쳐 쓰지 않는다**
    instruction: Mapped[str | None] = mapped_column(Text)
    #: `50페이지 내외` 처럼 양식이 준 분량 제한
    limit_text: Mapped[str | None] = mapped_column(Text)
    input_kind: Mapped[str] = mapped_column(String(16))

    #: 근거 위치. 원문에서 잘라 보여 줄 수 있다
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)

    # --- 양식 읽기 (plan/16 T-0063). **NULL 이면 아직 안 물어봤다** ---

    #: 다른 항목을 압축하는 자리인가. `요약` · `사업 개요` 가 그렇다.
    #: **중복 점검이 이걸 안 보면 정상 항목을 때린다**(T-0067)
    summary_of_others: Mapped[bool | None] = mapped_column(Boolean)
    #: 무엇이 읽었나. `llm/<모델>`. 다시 읽을 때 무엇이 바뀌었는지 본다
    needs_decided_by: Mapped[str | None] = mapped_column(String(32))


# ─────────────────────────────────────────────────────────────────
# 사업 위키 (plan/12 · F1)
#
# **이름을 `Document` 로 못 쓴다.** ADR-0014 의 그림은 올린 파일을 `Document` 라고
# 불렀지만 그 이름은 이미 공고 첨부 안의 구간이 쓰고 있다(plan/11). 개념은 ADR-0014
# 그대로이고 이름만 `UserFile` 이다 — 배포 DB 에 데이터가 있는 표를 개명하는 것보다
# 이쪽이 싸다.
# ─────────────────────────────────────────────────────────────────


#: SQLite 는 BIGINT 기본키를 자동증가시키지 않는다. 이 별칭이 **Postgres DDL 은 그대로
#: 두고** SQLite 에서만 INTEGER 로 낮춘다. 위키 테스트가 DB 없이 돌아야 해서다 —
#: 나머지 128건이 전부 DB 를 안 쓰는데 여기서 그 성질을 깨지 않는다.
_PK = BigInteger().with_variant(Integer, "sqlite")



class UserFileStatus(enum.StrEnum):
    """파일 하나의 상태. **파일별로 독립이다**(SPEC F1-1-8).

    SPEC 이 적은 것은 `uploaded → parsing → extracting → linking → needs_review/done/failed`
    다. 여기에 **CHUNKED 를 하나 더 뒀다** — plan/12 T-0043 이 청크까지만 만들고
    추출(T-0045)이 아직 없어서, '해독은 됐고 사실은 안 뽑았다'를 말할 자리가 필요하다.
    PARSING 에 얹으면 진행 표시(F1-1-9)가 거짓이 된다.
    """

    UPLOADED = "uploaded"
    PARSING = "parsing"
    #: 청크까지 됐다. 사실 추출은 아직이다
    CHUNKED = "chunked"
    EXTRACTING = "extracting"
    LINKING = "linking"
    NEEDS_REVIEW = "needs_review"
    DONE = "done"
    #: 읽을 수 없었다. **나머지 파일은 그대로 간다**
    FAILED = "failed"


class UserFile(Base):
    """사용자가 올린 파일 하나. 원본은 `data/user-files/<company_id>/...` 에 있다.

    **키가 (company_id, sha256) 이다.** 회사 사이 중복 제거를 하지 않기로 한 결과다
    (ADR-0029 4번). 같은 회사가 같은 파일을 다시 올리면 이 제약이 막고, 다른 회사가
    같은 파일을 올리면 각자 한 행씩 갖는다.
    """

    __tablename__ = "user_file"
    __table_args__ = (
        UniqueConstraint("company_id", "sha256", name="uq_user_file_company_sha"),
        Index("ix_user_file_company_status", "company_id", "status"),
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    #: 격리의 기준. 경로에도 들어간다(ADR-0029 3번)
    company_id: Mapped[str] = mapped_column(String(64), index=True)
    sha256: Mapped[str] = mapped_column(String(64))

    #: 사용자가 준 이름. **판정에 쓰지 않는다** — 확장자와 내용이 다른 파일이 실재한다
    filename: Mapped[str] = mapped_column(Text)
    byte_size: Mapped[int] = mapped_column(Integer)
    #: `attach/formats.py` 가 **내용으로** 판정한 것
    ext: Mapped[str | None] = mapped_column(String(16))

    status: Mapped[str] = mapped_column(String(16))
    uploaded_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # --- 해독 ---
    parse_status: Mapped[str | None] = mapped_column(String(16))
    parser: Mapped[str | None] = mapped_column(String(32))
    parse_error: Mapped[str | None] = mapped_column(Text)
    parsed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    #: 해독 글자 수. 0 이면 스캔본이다 — OCR 이 붙어야 찬다(T-0042)
    text_chars: Mapped[int | None] = mapped_column(Integer)
    #: PDF 만 안다. 다른 포맷에는 쪽이라는 것이 없다
    page_count: Mapped[int | None] = mapped_column(Integer)
    chunk_count: Mapped[int | None] = mapped_column(Integer)
    #: **사실을 못 뽑은 이유**([plan/12](../../docs/plan/12-사업-위키-구축.md) T-0093).
    #:
    #: `parse_error` 와 다른 단계다 — 저기는 글자를 못 얻은 것이고 여기는 글자는 얻었는데
    #: 사실이 안 나온 것이다. **한 컬럼에 섞으면 어느 쪽인지 못 가른다.**
    #:
    #: `build._shelve` 가 쓰고 추출이 성공하면 지운다. 이 값이 있으면 `chunked` 가
    #: "사실을 뽑을 차례" 가 아니라 **"못 뽑았다"** 라는 뜻이다 — `wiki/progress.py` 가
    #: 그것으로 두 뜻을 가른다.
    extract_error: Mapped[str | None] = mapped_column(Text)


class Chunk(Base):
    """원문 조각 하나. **노드가 나중에 이걸 가리킨다**(ADR-0014).

    **위치정보는 여기서만 심을 수 있다.** 파싱이 끝난 뒤에는 "이 문장이 몇 쪽이었나"를
    되찾을 방법이 없다. 그래서 이 표가 plan/12 의 축이고, 전체 구상도가 이 계층을
    빠뜨린 것이 가장 큰 차이였다.

    `company_id` 를 여기 한 번 더 두는 것은 의도다. 근거 청크를 꺼낼 때 `user_file`
    조인 없이 격리를 걸 수 있어야 하고, **그 조인을 빠뜨리는 것이 정확히 막고 싶은
    버그다.**
    """

    __tablename__ = "chunk"
    __table_args__ = (
        UniqueConstraint("user_file_id", "ordinal", name="uq_chunk_file_ordinal"),
        Index("ix_chunk_company", "company_id"),
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    user_file_id: Mapped[int] = mapped_column(
        _PK, ForeignKey("user_file.id", ondelete="CASCADE"), index=True
    )
    #: 비정규화. 위 docstring 의 이유다
    company_id: Mapped[str] = mapped_column(String(64))
    ordinal: Mapped[int] = mapped_column(Integer)

    text: Mapped[str] = mapped_column(Text)
    chars: Mapped[int] = mapped_column(Integer)

    #: 해독 텍스트 전체에서의 자리. **항상 있다**
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    #: 1-based. **PDF 만 찬다** — HWPX·DOCX 에는 쪽이 없다
    page: Mapped[int | None] = mapped_column(Integer)
    #: 이 조각 위에 있던 제목. 규칙으로 잡은 것이라 **최선 추정이다**
    heading: Mapped[str | None] = mapped_column(Text)


class WikiPlace(enum.StrEnum):
    """사실 하나가 간 자리(plan/12 T-0045).

    **셋을 섞지 않는 것이 이 컬럼의 존재 이유다.** 병합 키가 다르다 —
    value 는 (이름, 한정어, 시점)이 키고, event 는 키가 없어 근거만 쌓이며,
    분류 못 한 것은 **버리지 않고** 검토 큐에 선다(구상도 ④ 예외).
    """

    VALUE = "value"
    EVENT = "event"
    UNCATEGORIZED = "uncategorized"


class SourceType(enum.StrEnum):
    """이 값이 어디서 왔나(ADR-0028 5번).

    **문서가 `user_stated` 를 자동으로 덮지 않는다.** 사용자가 직접 답한 값은
    문서 추출보다 세다 — 사용자가 자기 사업을 문서보다 잘 안다.
    """

    DOCUMENT = "document"
    USER_STATED = "user_stated"


class WikiFact(Base):
    """위키에 선 사실 하나. **값이 아니라 주장이다** — 충돌하면 둘 다 남는다(F1-1-7).

    ADR-0014 가 "모든 값에 출처를 매단다"고 한 그 값이 이 표다. 근거는 `wiki_evidence`
    로 나가고, **근거가 하나도 없는 행은 만들지 않는다.**

    `dedupe_key` 가 병합의 전부다. value 는 `value|이름|한정어|시점|값` 이라 문서 넷이
    같은 사업자등록번호를 말하면 **행 하나에 근거 넷**이 된다. 서술은
    `event|이름|fact_key` 라, 같은 사실이 문서마다 다른 문장으로 쓰여 있어도 묶인다.
    """

    __tablename__ = "wiki_fact"
    __table_args__ = (
        UniqueConstraint("company_id", "dedupe_key", name="uq_wiki_fact_company_key"),
        Index("ix_wiki_fact_place", "company_id", "place_kind", "place"),
        Index("ix_wiki_fact_status", "company_id", "status"),
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    #: 격리의 기준. `chunk` 와 같은 이유로 여기 한 번 더 둔다
    company_id: Mapped[str] = mapped_column(String(64), index=True)

    place_kind: Mapped[str] = mapped_column(String(16))
    #: 슬롯 이름(`headcount`) 또는 노드 이름(`solution`). uncategorized 면 빈 문자열
    place: Mapped[str] = mapped_column(String(32))
    #: 병합 키. 위 docstring 참고
    dedupe_key: Mapped[str] = mapped_column(Text)

    #: LLM 이 붙인 라벨. **목적지가 아니다** — 목적지는 `wiki/topics.py` 의 표가 정했다
    topic: Mapped[str] = mapped_column(String(32))
    #: 사람이 읽는 문장. 서술 노드는 이게 내용이다
    text: Mapped[str] = mapped_column(Text)

    # --- 정형 슬롯일 때만 찬다 ---
    #: 문서가 쓴 이름. `상시 근로자` · `종업원 수`. **슬롯 이름과 다르다**
    slot_key: Mapped[str | None] = mapped_column(Text)
    value: Mapped[str | None] = mapped_column(Text)
    #: `시드` · `정책자금` · `예비창업패키지`
    qualifier: Mapped[str | None] = mapped_column(Text)
    #: 언제 기준의 값인가. **시점 없는 슬롯은 항상 NULL 이다**(merge.as_of_for)
    as_of: Mapped[dt.date | None] = mapped_column(Date)
    #: current | superseded | conflict. **서술 노드는 NULL 이다**
    status: Mapped[str | None] = mapped_column(String(16))

    source_type: Mapped[str] = mapped_column(String(16), default=str(SourceType.DOCUMENT))
    #: `stub/v1` · `llm/<모델>`. 무엇이 뽑았는지 남긴다 — 바꿔 돌릴 때 차이를 본다
    extractor: Mapped[str] = mapped_column(String(32))

    first_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WikiEvidence(Base):
    """사실 하나가 어느 원문 조각에서 나왔나. **이 표가 없으면 위키가 거짓말이 된다.**

    ADR-0014: 집필은 노드가 든 근거 청크만 꺼내 쓴다. 값만 들고 문단을 쓰면 모델이
    나머지를 지어낸다. **나중에 붙이는 것은 불가능하다** — 위치정보는 파싱 단계에서만
    심을 수 있고, 그 자리가 `chunk` 다.
    """

    __tablename__ = "wiki_evidence"
    __table_args__ = (
        UniqueConstraint("fact_id", "chunk_id", name="uq_wiki_evidence_fact_chunk"),
        Index("ix_wiki_evidence_company", "company_id"),
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    company_id: Mapped[str] = mapped_column(String(64))
    fact_id: Mapped[int] = mapped_column(
        _PK, ForeignKey("wiki_fact.id", ondelete="CASCADE"), index=True
    )
    chunk_id: Mapped[int] = mapped_column(_PK, ForeignKey("chunk.id", ondelete="CASCADE"))
    #: 편의용 비정규화. "어느 파일 몇 쪽" 을 청크 조인 없이 세는 자리가 많다
    user_file_id: Mapped[int] = mapped_column(_PK, ForeignKey("user_file.id", ondelete="CASCADE"))
    #: 청크 안에서 근거가 된 조각. 청크 전문을 보여 주기 전에 이걸 먼저 보여 준다
    quote: Mapped[str] = mapped_column(Text)


# ─────────────────────────────────────────────────────────────────
# 초안 집필 (plan/16 · F6 · G 계층)
#
# **양식 쪽과 위키 쪽을 잇는 자리다.** ADR-0028 이 결과 절에 "이 매핑은 아직
# 없다 … 둘을 잇는 일은 아직 계획이 없다" 고 적어 둔 그것이다.
# ─────────────────────────────────────────────────────────────────


class ItemNeed(Base):
    """이 항목을 쓰려면 위키의 **어느 자리**가 필요한가 (plan/16 T-0063).

    **회사와 무관하다.** `document` 가 콘텐츠 주소(sha256)라 한 번 계산하면 그 양식을
    쓰는 **모든 공고·모든 회사가 쓴다.** 그래서 `company_id` 가 없다 — 넣으면 같은
    양식을 회사 수만큼 다시 물어야 한다.

    여기서 F6-6(못 채운 곳)이 계산된다. `place` 중에 위키가 못 채운 것이 곧
    "이 항목에 필요한데 없는 것" 이다.
    """

    __tablename__ = "item_need"
    __table_args__ = (
        UniqueConstraint("document_item_id", "place", name="uq_item_need_item_place"),
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    document_item_id: Mapped[int] = mapped_column(
        _PK, ForeignKey("document_item.id", ondelete="CASCADE"), index=True
    )
    #: `wiki/topics.py` 의 슬롯 이름 또는 노드 이름. **그 표 밖의 값을 넣지 않는다**
    place: Mapped[str] = mapped_column(String(32))
    #: `slot` 또는 `node`. 화면이 "값이 비었다" 와 "글이 비었다" 를 다르게 말한다
    place_kind: Mapped[str] = mapped_column(String(16))
    #: 없으면 이 항목을 아예 못 쓰는가. 있으면 좋은 것과 가른다
    required: Mapped[bool] = mapped_column(Boolean, default=True)


class ItemOverlap(Base):
    """같은 이야기를 부를 항목 쌍 (plan/16 T-0063).

    포항시 양식의 `2-1 사업수행 배경 및 목적`과 `2-2 지원필요성`이 그 예다 —
    **두 지시문에 "필요성" 이 둘 다 있다.** 항목을 독립으로 쓰면 같은 문단이 두 번 나온다.

    **금지 대상은 사실 공유가 아니라 서사 재사용이다.** 그래서 "쓰지 마라" 가 아니라
    "겹칠 수 있다" 만 적어 두고, 무엇을 누가 맡을지는 회사 사실을 보고 T-0064 가 정한다.
    """

    __tablename__ = "item_overlap"
    __table_args__ = (UniqueConstraint("a_item_id", "b_item_id", name="uq_item_overlap_pair"),)

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        _PK, ForeignKey("document.id", ondelete="CASCADE"), index=True
    )
    #: **항상 작은 id 가 a 다.** 안 그러면 같은 쌍이 두 줄로 들어온다
    a_item_id: Mapped[int] = mapped_column(
        _PK, ForeignKey("document_item.id", ondelete="CASCADE")
    )
    b_item_id: Mapped[int] = mapped_column(
        _PK, ForeignKey("document_item.id", ondelete="CASCADE")
    )
    #: 무엇이 겹치나. 사람이 읽고 판단하는 자리다
    note: Mapped[str] = mapped_column(Text)


class Draft(Base):
    """한 회사가 공고 하나에 대해 쓴 초안 한 벌 (plan/16 T-0065).

    **배분 결과를 여기 든다.** 안 들면 항목 하나를 재작성할 때 배분을 잊고 다시
    겹친다(T-0064). `allotment` 는 `{항목 id: [사실 id]}` 이고, **사람이 읽을 것이
    아니라 재작성이 읽을 것**이라 JSON 으로 둔다.

    공고와 문서를 둘 다 든다. 문서(양식)는 콘텐츠 주소라 여러 공고에 붙고, 초안은
    **공고 하나에 대한 것**이다 — 같은 양식이라도 공고가 다르면 넣을 금액과 마감이
    다르다.
    """

    __tablename__ = "draft"
    __table_args__ = (
        UniqueConstraint("company_id", "notice_id", "document_id", name="uq_draft_target"),
        Index("ix_draft_company", "company_id"),
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    company_id: Mapped[str] = mapped_column(String(64), index=True)
    #: `notice` 뷰의 공고 식별자. **뷰라서 FK 를 못 건다**
    notice_id: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(16))
    document_id: Mapped[int] = mapped_column(
        _PK, ForeignKey("document.id", ondelete="CASCADE"), index=True
    )

    #: `{항목 id: [사실 id]}`. **재작성이 읽는다**
    allotment: Mapped[dict] = mapped_column(_JSON, default=dict)
    #: 무엇이 배분했나. `llm/<모델>` · `none`(다툰 것이 없어 안 불렀다)
    allotted_by: Mapped[str | None] = mapped_column(String(32))

    started_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DraftItemStatus(enum.StrEnum):
    """항목 하나의 상태. **넷이다**(ADR-0028 결과 절 · plan/16).

    `STALE` 이 이 표의 요점이다. 답변 하나가 여러 항목을 낡게 만드는데, 물어본
    항목만 고치면 나머지에 `[확인 필요]` 가 남아 모순이 되고, 전부 자동으로 고치면
    F1-5-5("자동으로 고치지 않는다")를 어긴다. **낡았다고 표시만 하고 제안한다.**
    """

    #: 위키에 재료가 없어 못 썼다. **F6-6 이 가리키는 자리** — 여기만 물어본다
    BLANK = "blank"
    #: 쓸 자리가 아니다. 상위 묶음이거나 사업 내용을 안 쓰는 자리다 —
    #: T-0063 이 필요한 자리를 0개로 읽었다. **`blank` 와 섞으면 화면이 묶음을
    #: 가리키며 "알려주세요" 라고 한다**(실측: 못 채움 7 중 3이 이것이었다)
    NO_NEEDS = "no_needs"
    #: 위키에는 있는데 **다른 항목이 그 사실을 맡았다**(T-0064 배분).
    #: 물어볼 자리가 아니다 — "그 얘기는 6번에 썼어요" 라고 말할 자리다
    YIELDED = "yielded"
    #: **재료는 받았는데 글이 안 나왔다.** 모델이 빈 답을 냈거나, 낸 문단이
    #: 전부 버려졌다(근거를 안 적었거나 재료 밖 값만 있었다).
    #: 물어볼 자리가 아니다 — **집필이 실패한 자리다.** `blank` 와 섞으면
    #: 사용자에게 이미 준 정보를 또 달라고 한다
    UNWRITTEN = "unwritten"
    #: 문서 근거로 썼다
    DRAFTED = "drafted"
    #: 사용자 답변(`user_stated`)이 들어간 문단이 있다
    ANSWERED = "answered"
    #: 근거가 된 사실이 바뀌었다. **자동으로 안 고친다**
    STALE = "stale"


class DraftItem(Base):
    """항목 하나의 초안 (plan/16 T-0065).

    **`wiki_fact` 와 같은 자리다.** 재작성·실패·질문의 단위가 전부 항목이라
    (ADR-0028 3번 · ADR-0015 결과 절) 문서 단위로 들면 셋 다 안 된다.

    `body` 가 비어 있어도 행을 만든다. **`blank` 인 항목이 화면에서 사라지면
    적립 루프의 입구가 없어진다** — 못 쓴 자리를 보여 주는 것이 F6-6 이다.
    """

    __tablename__ = "draft_item"
    __table_args__ = (
        UniqueConstraint("draft_id", "document_item_id", name="uq_draft_item_target"),
        Index("ix_draft_item_status", "draft_id", "status"),
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    draft_id: Mapped[int] = mapped_column(
        _PK, ForeignKey("draft.id", ondelete="CASCADE"), index=True
    )
    document_item_id: Mapped[int] = mapped_column(
        _PK, ForeignKey("document_item.id", ondelete="CASCADE")
    )
    ordinal: Mapped[int] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String(16), default=str(DraftItemStatus.BLANK))
    #: 문단을 `\n\n` 으로 이은 본문. **비어 있어도 행은 남는다**
    body: Mapped[str] = mapped_column(Text, default="")

    #: 필요한데 위키에 없는 자리. **F6-6 이 이걸 읽는다**
    missing: Mapped[list] = mapped_column(_JSON, default=list)
    #: 있으면 좋은데 없는 자리. 물어볼 목록의 뒷줄
    missing_optional: Mapped[list] = mapped_column(_JSON, default=list)

    #: `llm/<모델>`. 무엇이 썼나
    written_by: Mapped[str | None] = mapped_column(String(32))
    #: 이 항목만 실패했다. **나머지는 남는다**(ADR-0015)
    error: Mapped[str | None] = mapped_column(Text)
    written_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DraftEvidence(Base):
    """문단 하나가 어디서 나왔나 (plan/16 T-0065 · F6-13).

    **`wiki_evidence` 를 그대로 베꼈다.** 이름만 다르다.

    `fact_id` 를 드는 것이 요점이다. 그 사실이 갱신될 때 **어느 항목이 낡았는지
    계산된다** — [ADR-0028](../../docs/adr/0028-초안을-먼저-완성하고-못-채운-자리에서-묻는다.md)
    4번의 파급 관리가 이 컬럼 하나에 달려 있다. **나중에 붙일 수 없다**(ADR-0014).

    `chunk_id` 는 [T-0067](../draft/dedupe.py) 이 읽는다. 두 항목이 같은 청크를
    근거로 들면 **코드가 중복을 안다** — 검사기를 따로 안 만드는 이유다.
    """

    __tablename__ = "draft_evidence"
    __table_args__ = (
        UniqueConstraint(
            "draft_item_id", "paragraph", "fact_id", name="uq_draft_evidence_para_fact"
        ),
        Index("ix_draft_evidence_chunk", "chunk_id"),
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    draft_item_id: Mapped[int] = mapped_column(
        _PK, ForeignKey("draft_item.id", ondelete="CASCADE"), index=True
    )
    #: 몇 번째 문단인가. 0부터
    paragraph: Mapped[int] = mapped_column(Integer)

    fact_id: Mapped[int] = mapped_column(_PK, ForeignKey("wiki_fact.id", ondelete="CASCADE"))
    #: 그 사실의 근거 청크. **없을 수 있다** — 사용자 답변(`user_stated`)은 청크가 없다
    chunk_id: Mapped[int | None] = mapped_column(
        _PK, ForeignKey("chunk.id", ondelete="CASCADE")
    )
    #: `document` · `user_stated`. 화면이 근거 줄에서 **글자로** 가른다(ADR-0028 결과 절)
    source_type: Mapped[str] = mapped_column(String(16), default=str(SourceType.DOCUMENT))


# ─────────────────────────────────────────────────────────────────
# 맞는 공고 고르기 (plan/17 · F3 · M 계층)
#
# **LLM 이 회사 쪽을 안 본다.** `notice_profile` 에 `company_id` 가 없는 것이
# 이 세 표의 전부다 — 공고를 한 번 읽으면 회사 수와 무관하게 모두가 쓴다.
# ─────────────────────────────────────────────────────────────────


class NoticeProfile(Base):
    """공고 하나가 **누구를 찾나** (plan/17 T-0070).

    **회사와 무관하다.** `item_need` 가 `company_id` 를 안 드는 것과 같은 이유고,
    그래서 LLM 호출이 회사 수와 무관해진다 — 회사가 1,000개여도 709회다.

    ## 캐시 키가 `content_hash` 가 아니다

    기업마당은 조회수(`inqireCo`)가 `content_hash` 재료라 **재수집마다 1,538건
    전부가 '변경'** 이다. 거기 걸면 매번 전량을 다시 뽑는다. `body_hash` 는
    **판정에 실제로 쓰는 본문만** 해싱한 값이라 조회수가 올라도 안 바뀐다.

    ## 제목의 지역 태그를 안 담는다

    실측으로 틀렸다 — `[경기]` 46건 중 성남시가 **2건**이고 나머지는 김포·화성·
    안양·시흥·안산·용인이다. 그리고 태그 없는 205건 안에 수성알파시티(대구)와
    제주형 그린바이오가 섞여 있다. **광역 태그는 시·군 사업을 가리고, 태그 없음은
    전국을 뜻하지 않는다.** 그래서 지역을 본문에서 뽑는다.
    """

    __tablename__ = "notice_profile"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_notice_profile_notice"),
        Index("ix_notice_profile_body", "body_hash"),
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(16))
    external_id: Mapped[str] = mapped_column(String(64))
    #: 판정에 쓰는 본문만의 해시. **`content_hash` 가 아니다** — 위 docstring 참고
    body_hash: Mapped[str] = mapped_column(String(64))

    #: 신청 가능한 지역. **시·군까지.** 빈 배열이면 제한 없음(전국)
    regions: Mapped[list] = mapped_column(_JSON, default=list)
    #: 요구하는 업종. 빈 배열이면 무관
    industries: Mapped[list] = mapped_column(_JSON, default=list)
    #: 그 밖의 요구. `만 39세 이하` · `프로토타입 필요` · `기수혜 제외`
    conditions: Mapped[list] = mapped_column(_JSON, default=list)
    #: 취지 키워드. **⑤ 가 사업 내용 노드와 겹쳐 본다**
    keywords: Mapped[list] = mapped_column(_JSON, default=list)
    #: 하려는 일 한 문장. 이유 템플릿의 앞부분이 된다
    purpose: Mapped[str] = mapped_column(Text, default="")

    #: `llm/<모델>`. 무엇이 뽑았나 — 바꿔 돌릴 때 차이를 본다
    decided_by: Mapped[str] = mapped_column(String(32))
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class FitVerdict(enum.StrEnum):
    """적합도 등급. **셋뿐이고 점수가 없다.**

    연속값을 만들면 화면에 안 내도 **설명할 눈금이 없는 순서**가 된다.
    `Fact` 에 `confidence` 를 안 넣은 것과 같은 이유다(plan/12 구상도와의 차이).
    """

    #: 취지 키워드가 사업 내용 노드와 겹쳤다
    MATCH = "맞다"
    #: 분야는 맞는데 취지가 안 겹쳤다
    MAYBE = "애매"
    #: 겹친 것이 없다. **추천에 안 올린다**
    MISS = "아니다"
    #: `notice_profile` 이 없어 판정하지 않았다. **`아니다` 와 섞으면 안 된다** —
    #: 저쪽은 봤는데 안 맞는 것이고 이쪽은 아직 안 본 것이다(`SPEC.md` F3-1-5)
    UNKNOWN = "확인 필요"


class NoticeFit(Base):
    """이 회사에게 이 공고가 맞나 (plan/17 T-0074).

    **자격(M1)은 여기 없다.** 못 넘은 공고는 행을 만들지 않는다 — 재계산이
    29,789건에 0.36초라 저장이 손해다. 여기 앉는 것은 **이유 문장과 근거 링크**뿐이다.
    """

    __tablename__ = "notice_fit"
    __table_args__ = (
        UniqueConstraint("company_id", "source", "external_id", name="uq_notice_fit_target"),
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    #: **유니크 제약의 첫 열이라 인덱스를 따로 안 만든다.** 회사로 훑는 질의가
    #: 그 제약의 앞부분만 써도 인덱스를 탄다
    company_id: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(16))
    external_id: Mapped[str] = mapped_column(String(64))

    verdict: Mapped[str] = mapped_column(String(16))
    #: 화면에 나가는 한 줄. **템플릿이 만든다**(T-0074). 비면 추천에 안 올린다
    reason: Mapped[str] = mapped_column(Text, default="")
    #: ④ 분야 대조가 맞았나. 같은 등급 안의 순서를 이걸로 먼저 가른다
    sector_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    #: 겹친 취지 키워드. **화면에 안 쓴다** — 왜 그 순서인지 되짚을 때 읽는다
    matched: Mapped[list] = mapped_column(_JSON, default=list)

    computed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class NoticeFitEvidence(Base):
    """그 이유가 어느 사실에서 나왔나 (plan/17 T-0074).

    **`fact_id` 를 드는 것이 요점이다.** 그 사실이 갱신될 때 어느 추천이 낡았는지
    계산된다 — `draft_evidence` 와 같은 자리고 **나중에 붙일 수 없다**(ADR-0014).
    """

    __tablename__ = "notice_fit_evidence"
    __table_args__ = (
        UniqueConstraint("fit_id", "fact_id", name="uq_notice_fit_evidence_fact"),
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    fit_id: Mapped[int] = mapped_column(
        _PK, ForeignKey("notice_fit.id", ondelete="CASCADE"), index=True
    )
    fact_id: Mapped[int] = mapped_column(_PK, ForeignKey("wiki_fact.id", ondelete="CASCADE"))
