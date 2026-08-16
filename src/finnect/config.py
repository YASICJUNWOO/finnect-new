"""환경변수. 시크릿·엔드포인트를 코드에 하드코딩하지 않는다."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://finnect:finnect@127.0.0.1:55433/finnect"

    bizinfo_api_key: str = ""
    data_go_kr_api_key: str = ""

    # 상대 서버 부하 조절. API 일 한도가 아니라 예의 문제다.
    request_delay_sec: float = 0.2
    request_timeout_sec: float = 60.0


settings = Settings()
