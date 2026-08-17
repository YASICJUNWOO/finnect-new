"""환경변수. 시크릿·엔드포인트를 코드에 하드코딩하지 않는다."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://finnect:finnect@127.0.0.1:55433/finnect"

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

    @property
    def formats(self) -> frozenset[str]:
        return frozenset(f.strip().lower() for f in self.attachment_formats.split(",") if f.strip())


settings = Settings()
