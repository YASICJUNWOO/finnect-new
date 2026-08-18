"""환경변수. 시크릿·엔드포인트를 코드에 하드코딩하지 않는다."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://finnect:finnect@127.0.0.1:55433/finnect"

    #: API 를 부를 때 있어야 하는 토큰(ADR-0035). **비어 있으면 검사하지 않는다** —
    #: 로컬은 지금까지처럼 그냥 돈다. 값을 넣는 순간 켜지고, 배포 서버가 그 자리다.
    #:
    #: Vercel 에 있을 때는 Vercel Authentication 이 문을 지켰다. 이 서버로 내려오면서
    #: 그 문이 없어졌고, **`POST /api/wiki/{company_id}/files` 가 인터넷에 열린 업로드
    #: 창구가 된다.** 대체물이 없으면 안 되는 이유가 그 한 경로다.
    api_token: str = ""

    bizinfo_api_key: str = ""
    data_go_kr_api_key: str = ""

    # 상대 서버 부하 조절. API 일 한도가 아니라 예의 문제다.
    request_delay_sec: float = 0.2
    request_timeout_sec: float = 60.0

    # --- 첨부 (plan/07 · ADR-0022) ---

    #: 원본과 추출 텍스트가 사는 곳. 콘텐츠 주소라 DB 를 지워도 파일은 재사용된다.
    attachment_dir: Path = REPO_ROOT / "data" / "attachments"

    #: 해독을 시도할 확장자. **설정으로 관리한다**(T-0004 완료 조건).
    #: 여기 없는 포맷은 unsupported 로 **기록되고** 조용히 건너뛰지 않는다.
    #: 목록을 줄이면 그만큼 미해독이 늘 뿐, 사라지지 않는다.
    attachment_formats: str = "hwp,hwpx,docx,docm,pdf,zip"

    #: 한 파일 최대 크기. 넘으면 안 받고 too_large 로 남긴다.
    attachment_max_mb: int = 100

    # --- 사용자 파일 (plan/12 · ADR-0029) ---

    #: 사용자가 올린 원본. **개인정보다.** 첨부와 다른 뿌리에 두는 이유가 ADR-0029 다 —
    #: 공고 첨부는 공개 파일이고 이쪽은 사업자등록증·재무제표다.
    user_file_dir: Path = REPO_ROOT / "data" / "user-files"

    #: 사용자 파일에서 해독을 시도할 확장자. **첨부와 따로 둔다**(ADR-0029).
    #: 첨부 목록에 xlsx·pptx 를 더하면 plan/07 이 측정한 2,827/3,354 가 근거를 잃는다.
    #: 사용자 파일에는 재무제표(xlsx)와 피치덱(pptx)이 반드시 오므로 여기는 넣는다.
    user_file_formats: str = "hwp,hwpx,docx,docm,pdf,xlsx,pptx,jpg,png"

    #: 올리기 한 개 최대 크기(plan/15). **첨부(100MB)보다 작다** — 저쪽은 우리가 고른
    #: 공고 첨부라 크기를 알고 받지만, 이쪽은 사용자가 던지는 것이라 상한이 방어다.
    user_file_max_mb: int = 50

    #: 사용자 파일에 OCR 을 쓸지(ADR-0030). **첨부는 별도다** — 켜면 plan/07 이
    #: 측정한 값을 다시 재야 하고 총 비용을 아직 모른다.
    user_file_ocr: bool = True

    #: 청크 한 조각의 목표 길이(자). 문단 경계를 넘지 않으려고 넘칠 수 있다.
    chunk_target_chars: int = 900

    #: 이 길이를 넘으면 문단 안에서라도 자른다. 넘어가는 문단이 실제로 있다.
    chunk_max_chars: int = 1600

    # --- 사실 추출 (plan/12 T-0045 · ADR-0031) ---

    #: 어느 추출기를 쓰나. **`stub` 하나뿐이다** — LLM 제공자가 아직 안 정해졌다
    #: (ADR-0021 G). `llm` 을 고르면 NotImplementedError 로 막는다.
    wiki_extractor: str = "stub"

    #: 스텁이 돌려줄 사실 표. **코퍼스에서 손으로 옮긴 것이라 테스트와 같이 산다.**
    #: 레포 밖에서는 파일이 없어 스텁이 아예 안 돈다 — 그게 의도다.
    wiki_stub_facts: Path = REPO_ROOT / "tests" / "fixtures" / "wiki" / "facts.json"

    @property
    def formats(self) -> frozenset[str]:
        return _split(self.attachment_formats)

    @property
    def wiki_formats(self) -> frozenset[str]:
        return _split(self.user_file_formats)


def _split(raw: str) -> frozenset[str]:
    return frozenset(f.strip().lower() for f in raw.split(",") if f.strip())


settings = Settings()
