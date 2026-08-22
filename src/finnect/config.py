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
    #:
    #: **그림은 `ocr.IMAGE_EXTS` 여섯과 같아야 한다**(T-0097). 2026-08-22 까지 여기가
    #: `jpg`·`png` 둘이라 나머지 넷이 OCR 분기에 닿기도 전에 잘렸다 — 파서가 있는데
    #: 설정이 막고 있었다. tiff 는 스캐너·팩스 기본 출력이고 webp 는 웹에서 저장한 그림의
    #: 기본이라 실제로 온다. **첨부 쪽은 안 연다** — 여는 순간 plan/07 을 다시 재야 한다.
    #: **글자만 있는 셋(`txt`·`md`·`csv`)은 시그니처가 없다.** `formats.detect` 가
    #: 파일명으로 물러나는 유일한 정상 경로다 — 인코딩은 `attach/text.py` 가 판정한다.
    user_file_formats: str = (
        "hwp,hwpx,docx,docm,pdf,xlsx,pptx,txt,md,csv,jpg,png,gif,bmp,tiff,webp,heic"
    )

    #: 올리기 한 개 최대 크기(plan/15). **첨부(100MB)보다 작다** — 저쪽은 우리가 고른
    #: 공고 첨부라 크기를 알고 받지만, 이쪽은 사용자가 던지는 것이라 상한이 방어다.
    user_file_max_mb: int = 50

    #: 묶음 하나에서 꺼낼 파일 수와 푼 총합(T-0102). **개별 상한(`user_file_max_mb`)만으로는
    #: 못 막는다** — 50MB 묶음 하나가 풀리면 수십 GB 가 될 수 있다. 상한에 걸리면 조용히
    #: 자르지 않고 **몇 개를 못 풀었는지 센다.**
    user_zip_max_files: int = 200
    user_zip_max_mb: int = 200

    #: 사용자 파일에 OCR 을 쓸지(ADR-0030). **첨부는 별도다** — 켜면 plan/07 이
    #: 측정한 값을 다시 재야 하고 총 비용을 아직 모른다.
    user_file_ocr: bool = True

    #: 청크 한 조각의 목표 길이(자). 문단 경계를 넘지 않으려고 넘칠 수 있다.
    chunk_target_chars: int = 900

    #: 이 길이를 넘으면 문단 안에서라도 자른다. 넘어가는 문단이 실제로 있다.
    chunk_max_chars: int = 1600

    # --- LLM (ADR-0037) ---

    #: **이것 하나만 넣으면 켜진다.** 없으면 `llm` 추출기가 무엇이 없는지 말하고 멈춘다
    #: — 조용히 스텁으로 물러나지 않는다(ADR-0037 결정 4).
    openai_api_key: str = ""

    #: ADR-0037 이 여기서부터 재기로 한 모델. 부족하면 `gpt-5.6-terra` · `sol` 로 올린다.
    openai_model: str = "gpt-5.6-luna"
    openai_timeout_sec: float = 120.0

    # --- 사실 추출 (plan/12 T-0045 · ADR-0031 · ADR-0037) ---

    #: 어느 추출기를 쓰나. `stub` 또는 `llm`.
    #:
    #: **`llm` 이 기본이 아닌 이유는 키다.** 키 없이 `llm` 을 고르면 멈추는데, 기본값이면
    #: 레포를 처음 받은 사람이 아무것도 못 한다. `stub` 은 픽스처 7건에서 항상 돈다.
    wiki_extractor: str = "stub"

    #: 스텁이 돌려줄 사실 표. **코퍼스에서 손으로 옮긴 것이라 테스트와 같이 산다.**
    #: 레포 밖에서는 파일이 없어 스텁이 아예 안 돈다 — 그게 의도다.
    wiki_stub_facts: Path = REPO_ROOT / "tests" / "fixtures" / "wiki" / "facts.json"

    # --- 양식 구간 판별 (plan/11 T-0036 · ADR-0037) ---

    #: 어느 판정기를 쓰나. `rule` 또는 `llm`.
    #:
    #: **여기는 `llm` 이 기본이다.** `wiki_extractor` 와 반대인 이유가 있다 — 규칙은
    #: 이미 분할 때 한 번 돌았고 네 번 실패했다. `rule` 로 이 판정을 돌리면 아무것도
    #: 안 바뀌는데, 그 결과가 "LLM 도 못 가른다" 처럼 보인다.
    document_classifier: str = "llm"

    # --- 초안 집필 (plan/16 T-0069) ---

    #: 항목을 몇 개씩 동시에 쓰나. **상한은 rate limit 이다** — 크게 잡으면 429
    #: 재시도가 늘어 오히려 느려진다. 8 에서 시작해 재 본다.
    draft_workers: int = 8

    # --- 맞는 공고 고르기 (plan/17 T-0070) ---

    #: 공고를 몇 개씩 동시에 정규화하나. `draft_workers` 와 같은 이유로 8 이다.
    #: **③④⑤ 에는 워커가 없다** — LLM 을 안 부르고 1,790건에 0.02초다
    match_workers: int = 8

    # --- 관측 (Langfuse) ---

    #: **둘 다 있어야 켜진다.** 하나만 있으면 오타일 가능성이 높다.
    #: 없으면 추적이 그냥 꺼진다 — 이건 정확성 기능이 아니라 보는 기능이라
    #: 없다고 멈추면 안 된다(`wiki_extractor` 와 성질이 다르다).
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    #: 자체 호스팅이면 바꾼다. `https://us.cloud.langfuse.com` 도 있다.
    langfuse_base_url: str = "https://cloud.langfuse.com"

    @property
    def formats(self) -> frozenset[str]:
        return _split(self.attachment_formats)

    @property
    def wiki_formats(self) -> frozenset[str]:
        return _split(self.user_file_formats)


def _split(raw: str) -> frozenset[str]:
    return frozenset(f.strip().lower() for f in raw.split(",") if f.strip())


settings = Settings()
