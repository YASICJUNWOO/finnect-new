# finnect

내 사업 정보로 **신청 가능한 창업 지원공고를 판정**하고, 그 판정을 **공고가 요구하는 사업계획서 초안**으로 잇는다.

지금 저장소에 있는 것은 그 앞단이다. **두 공공 API에서 공고 목록을 받아 DB에 넣고 화면에서 보는 것**까지다. 첨부는 메타데이터만 담고 내려받지 않는다. LLM은 아직 부르지 않는다.

---

## 필요한 것

| | |
|---|---|
| Python 3.13 | `>=3.13,<3.14`. 3.14는 의존성 휠이 비어 있을 수 있다 |
| [uv](https://docs.astral.sh/uv/) | 의존성과 파이썬 버전 관리 |
| Docker | PostgreSQL 18을 컨테이너로 띄운다 |
| 인증키 2개 | 아래 참고. 둘 다 무료다 |

### 인증키

**기업마당** — [발급 페이지](https://www.bizinfo.go.kr/apiDetail.do?id=bizinfoApi) 하단 신청 폼. 로그인 없이 즉시 발급된다.
신청할 때 적은 IP에서만 동작할 수 있으니 발급 환경과 실행 환경을 맞춘다.

**공공데이터포털** — [data.go.kr](https://www.data.go.kr) 가입 후 마이페이지 > 활용신청 현황 > **일반 인증키(Encoding)**.
K-Startup API(`B552735/kisedKstartupService01`)에 활용신청이 따로 필요하다.

---

## 시작하기

```bash
uv sync                                  # 의존성
cp .env.example .env                     # 인증키를 채운다
docker compose up -d db                  # PostgreSQL (127.0.0.1:55433)
uv run alembic upgrade head              # 스키마
uv run uvicorn finnect.admin.app:app --reload
```

http://127.0.0.1:8000 이 열린다. 화면은 둘이다.

| 경로 | 하는 일 |
|------|--------|
| `/notices` | 공고 목록과 상세. 상세는 출처가 준 컬럼을 하나도 빠짐없이 편다 |
| `/ingest` | 수집 실행. 출처별 저장 건수, 진행률, 실행 기록 |

처음에는 DB가 비어 있다. `/ingest`에서 버튼을 누르면 채워진다.
건수 칸을 비우면 전량, 숫자를 넣으면 그만큼만 받는다(맛보기).

### 명령으로 수집하기

화면 대신 CLI로도 된다. **같은 코드를 타고 실행 기록도 같은 표에 남는다.**

```bash
uv run python -m finnect.ingest --source bizinfo      # 1,538건 · 요청 1회
uv run python -m finnect.ingest --source kstartup     # 29,789건 · 요청 149회
uv run python -m finnect.ingest --source kstartup --only-open   # 모집중 274건만
uv run python -m finnect.ingest --source bizinfo --limit 40     # 맛보기 40건
```

건수는 2026-08-16 실측이다. `--limit`으로 잘라 받으면 **잘렸다는 사실이 실행 기록에 남는다.**

### 검사

```bash
uv run pytest
uv run ruff check src tests
```

`ruff check .`은 `spike/`와 자동 생성 마이그레이션 때문에 아직 통과하지 않는다.
`spike/`는 실측용 버리는 코드라 손대지 않는다.

---

## 무엇이 어디에 저장되나

**API가 준 컬럼을 전부 만든다. 이름도 API 필드명 그대로다**(대소문자까지).

| 테이블 | 담는 것 |
|--------|--------|
| `raw_fetch` | 응답 원문 통째. 봉투와 잔여 쿼터 포함 |
| `bizinfo_notice` | 기업마당 22컬럼 |
| `kstartup_notice` | K-Startup 30컬럼 |
| `notice` (뷰) | 둘을 공통 8필드로 매핑. 매핑 정본은 `src/finnect/views.py` |
| `attachment` | 첨부 메타데이터 |
| `ingest_run` | 수집 실행 기록. 코퍼스가 아니라 운영 기록이다 |

두 출처는 **필드 이름을 하나도 공유하지 않는다**(22 · 30 · 교집합 0). 통합은 전부 수동 매핑이다.
전부 TEXT로 받는다. API가 날짜도 `"20260827"` 문자열로 준다.
처음 보는 필드는 `extra` JSONB로 흘리되 **건수를 보고한다.** 조용히 버리지 않는다.

---

## 알아두면 덜 헤매는 것

**두 API 모두 실패를 HTTP 200으로 준다.** 기업마당은 `reqErr`, K-Startup은 봉투 없는 `{"code":0,"msg":"정상"}`이다. 후자를 `data.get("data") or []`로 받으면 **0건 성공으로 읽고 조용히 넘어간다.** 그래서 봉투 검증(`ingest/envelope.py`)이 방어 코드가 아니라 파싱의 첫 단계다.

**인증키가 틀리면 실패로 끝난다.** 0건 성공이 아니다. 실행 기록에 `failed`로 남는다.

**`postgres:18`은 볼륨을 `/var/lib/postgresql`에 마운트한다.** 17 이하 방식(`/var/lib/postgresql/data`)으로 걸면 컨테이너가 `Exited(1)`로 죽는다.

**포트는 5432가 아니라 55433이다.** 호스트의 기존 PostgreSQL을 건드리지 않으려고 비켰다.

더 있다. [`CLAUDE.md`의 함정 절](CLAUDE.md#함정)에 모아 뒀다.

---

## 문서

전부 [`docs/`](docs/)에 있다.

| | |
|---|---|
| [`docs/SPEC.md`](docs/SPEC.md) | **정본.** 무엇을 만드는가. 충돌하면 이 문서가 이긴다 |
| [`docs/plan/`](docs/plan/README.md) | 계획과 태스크. **진행 상태의 정본이다** |
| [`docs/adr/`](docs/adr/README.md) | 결정 로그. append-only |
| [`docs/design/`](docs/design/README.md) | 화면 토큰·와이어프레임·카피 |

`src/finnect/admin/`은 **운영 도구**다. 제품 화면이 아니라서 `docs/design/`의 토큰을 따르지 않는다.
이 화면의 목적은 운영이 아니라 **L1 추출 스키마 설계를 위한 코퍼스 관찰**이다.
