# finnect

가진 파일을 통째로 던지면 **내 사업 위키**가 만들어지고, 그 위키로 **맞는 공고를 골라 주고**, 들어가면 **문서가 이미 써져 있다.**

지금 저장소에 있는 것은 공고 쪽 앞단뿐이다. **두 공공 API에서 공고 목록을 받아 DB에 넣고, 첨부를 내려받아 텍스트를 뽑고, 그걸 화면에 보여주는 것**까지다. 뽑은 텍스트로 아직 아무것도 판단하지 않는다. LLM은 부르지 않는다. **사업 위키는 아직 한 줄도 없다.**

앱이 셋이고 **그중 둘이 한 몸이다.** Next.js 앱(`web/`) 안에 사용자 화면(`/`)과 운영 화면(`/admin`)이 같이 있고, 제품 API(`src/finnect/api/`)가 둘 다 먹인다. 남은 하나(`src/finnect/admin/`)는 **수집 실행 버튼만** 가진 로컬 앱이다([ADR-0023](docs/adr/0023-제품-프론트를-nextjs로-분리한다.md) · [ADR-0027](docs/adr/0027-운영-화면을-nextjs로-옮긴다.md)).

무엇을 만드는지는 [`docs/SPEC.md`](docs/SPEC.md), 어디까지 왔는지는 [`docs/plan/README.md`](docs/plan/README.md)에 있다.

---

## 필요한 것

| | |
|---|---|
| Python 3.13 | `>=3.13,<3.14`. 3.14는 의존성 휠이 비어 있을 수 있다 |
| [uv](https://docs.astral.sh/uv/) | 의존성과 파이썬 버전 관리 |
| Docker | PostgreSQL 18을 컨테이너로 띄운다 |
| Node 22+ | 사용자 화면(`web/`)에만 필요하다. 수집·해독은 Node 없이 돈다 |
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

http://127.0.0.1:8000 이 열리고 **화면이 하나다.**

| 경로 | 하는 일 |
|------|--------|
| `/ingest` | 수집 실행. 버튼과 진행률 |

처음에는 DB가 비어 있다. 여기서 버튼을 누르면 채워진다.
건수 칸을 비우면 전량, 숫자를 넣으면 그만큼만 받는다(맛보기). CLI도 같은 일을 한다.

```bash
uv run python -m finnect.ingest --source bizinfo
```

**조회 화면은 여기 없다.** 공고 목록·상세·해독 현황은 아래 사용자 앱의 `/admin`에 있고 배포본에서도 열린다([ADR-0027](docs/adr/0027-운영-화면을-nextjs로-옮긴다.md)). 이 앱에 남은 것은 **옮길 수 없는 것 하나**다 — 수집은 응답보다 오래 사는 데몬 스레드이고 진행률은 그 프로세스 안에서만 산다.

### 사용자 화면

**프로세스 둘이 같이 떠야 한다.** API가 JSON을 내고 Next.js가 그걸 그린다([ADR-0023](docs/adr/0023-제품-프론트를-nextjs로-분리한다.md)).

```bash
uv run uvicorn finnect.api.app:app --reload --port 8100   # 터미널 1 — API
cd web && npm install && npm run dev                       # 터미널 2 — 화면
```

http://localhost:3000 이 사용자 화면, http://127.0.0.1:8100/docs 가 API 문서다.

| 화면 | 하는 일 |
|------|--------|
| `/` | 공고 목록(S4). **마감된 공고는 빼고** 마감 임박순으로 보여 준다 |
| `/notices/{출처}/{id}` | 공고 상세(S5). 개요·접수 기간·낼 서류와 **해독 여부** |
| `/admin/notices` | **운영** 공고 목록과 상세. 마감된 것까지 전량, 출처가 준 컬럼을 하나도 빠짐없이 편다 |
| `/admin/attachments` | **운영** 첨부 해독 현황. 포맷별 해독률과 못 읽은 건수 |
| `/admin/ingest` | **운영** 수집 실행 기록. 버튼은 없다 — 위 `:8000`에 있다 |

`/admin`은 운영 도구고 `SPEC.md` §6 범위 밖이다. 제품 헤더를 안 쓰고 자기 내비를 쓴다.

**화면 대부분이 "아직 없어요"로 비어 있다.** 추천·자격·심사 항목은 사업 위키(F1)와 추출(F2-3)이 있어야 채워진다. 예시 데이터를 넣지 않기로 했다 — 가짜 값으로 완성돼 보이는 것보다 낫다.

계약은 [`docs/api-contract.md`](docs/api-contract.md)에 있다. **`web/`은 DB를 모른다.**

### 명령으로 수집하기

화면 대신 CLI로도 된다. **같은 코드를 타고 실행 기록도 같은 표에 남는다.**

```bash
uv run python -m finnect.ingest --source bizinfo      # 1,538건 · 요청 1회
uv run python -m finnect.ingest --source kstartup     # 29,789건 · 요청 149회
uv run python -m finnect.ingest --source kstartup --only-open   # 모집중 274건만
uv run python -m finnect.ingest --source bizinfo --limit 40     # 맛보기 40건
```

건수는 2026-08-16 실측이다. `--limit`으로 잘라 받으면 **잘렸다는 사실이 실행 기록에 남는다.**

### 첨부 내려받기와 해독

목록을 받은 뒤에 돈다. 화면 버튼은 없고 CLI뿐이다.

```bash
uv run python -m finnect.attach --limit 40   # 맛보기
uv run python -m finnect.attach              # 전량 3,354건 · 약 2GB · 30분 남짓
uv run python -m finnect.attach --redo       # 파서를 고쳤을 때. 파일은 다시 안 받는다
uv run python -m finnect.attach --report     # 집계만. 아무것도 안 받는다
```

원본은 `data/attachments/`에 **내용 해시로** 쌓인다([ADR-0022](docs/adr/0022-첨부-원본을-콘텐츠-주소로-로컬에-둔다.md)).
그래서 `--redo`가 파일을 다시 안 받고 해독만 다시 한다.

**해독은 4포맷만 한다**(hwp · hwpx · docx · pdf). ZIP은 안의 목록만 읽고 풀지 않는다.
나머지는 **`unsupported`로 기록된다.** 조용히 건너뛰지 않는 것이 이 명령의 존재 이유다.
목록은 `ATTACHMENT_FORMATS` 환경변수로 바꾼다.

### 사용자 파일로 위키 세우기

공고와 별개다. 사용자가 가진 파일을 던지면 **청크 → 사실 → 노드까지** 만들고, 노드에서 원문이 열린다.

**추출기가 아직 스텁이다**([ADR-0031](docs/adr/0031-사실-추출을-포트-뒤로-미루고-스텁으로-배관을-먼저-세운다.md)). LLM 제공자를 안 정하고 포트만 팠고, 스텁은 `tests/fixtures/wiki/` 일곱 건에서 손으로 옮긴 사실을 돌려준다. **그 밖의 파일을 넣으면 청크까지만 가고 이유가 따라 나온다.**

```bash
uv sync --group ocr   # OCR(ADR-0030). 기본 의존성이 아니다 — onnxruntime 이 무겁다
uv run python -m finnect.wiki --company c_dasiro tests/fixtures/wiki/*
uv run python -m finnect.wiki --company c_dasiro --wiki       # 세워진 위키를 본다
uv run python -m finnect.wiki --company c_dasiro --show 회사소개  # 원문 청크를 본다
uv run python -m finnect.wiki --company c_dasiro --report     # 집계만
uv run python -m finnect.wiki --company c_dasiro --rechunk    # 청킹 규칙을 고쳤을 때
uv run python -m finnect.wiki --company c_dasiro --rebuild    # 추출기를 바꿨을 때. 청크는 안 건드린다
uv run python -m finnect.wiki --company c_dasiro --purge      # 탈퇴. 원본까지 지운다
```

`tests/fixtures/wiki/`에 예시 파일 일곱이 있다. **`uv sync --group ocr`을 하면 일곱 전부 읽힌다.**
OCR을 안 깔면 이미지와 스캔 PDF 둘이 각각 `unsupported`·`empty`로 남는다 — 조용히 사라지지 않는다. 무엇을 심어 뒀는지는
[픽스처 README](tests/fixtures/wiki/README.md)에 있다.

원본은 `data/user-files/<company_id>/`에 쌓인다([ADR-0029](docs/adr/0029-사용자-파일을-회사-단위-콘텐츠-주소로-로컬에-둔다.md)).
**개인정보라 git에 안 들어가고 배포본에도 안 올라간다.** 격리를 경로에서 걸었으므로
탈퇴는 디렉터리 하나를 지우는 일이다. **회사 사이 중복 제거를 하지 않는다** —
같은 정부 양식을 두 회사가 올리면 두 벌 저장되고, 그게 의도다.

### 검사

```bash
uv run pytest
uv run ruff check src tests
cd web && npm run lint && npm run typecheck && npm run build
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
| `attachment` | 첨부 메타데이터. API가 준 것 |
| `attachment_file` | 첨부를 받아서 읽어 본 결과. **우리가 한 것** |
| `ingest_run` | 수집 실행 기록. 코퍼스가 아니라 운영 기록이다 |

**`attachment`와 `attachment_file`이 갈려 있는 이유가 있다.** 공고가 갱신되면 그 공고의 `attachment` 행이 통째로 지워지고 다시 깔린다. 해독 상태를 거기 얹으면 재수집 한 번에 전부 날아간다. 그래서 URL을 키로 하는 표를 따로 뒀다.

두 출처는 **필드 이름을 하나도 공유하지 않는다**(22 · 30 · 교집합 0). 통합은 전부 수동 매핑이다.
전부 TEXT로 받는다. API가 날짜도 `"20260827"` 문자열로 준다.
처음 보는 필드는 `extra` JSONB로 흘리되 **건수를 보고한다.** 조용히 버리지 않는다.

---

## 알아두면 덜 헤매는 것

**두 API 모두 실패를 HTTP 200으로 준다.** 기업마당은 `reqErr`, K-Startup은 봉투 없는 `{"code":0,"msg":"정상"}`이다. 후자를 `data.get("data") or []`로 받으면 **0건 성공으로 읽고 조용히 넘어간다.** 그래서 봉투 검증(`ingest/envelope.py`)이 방어 코드가 아니라 파싱의 첫 단계다.

**인증키가 틀리면 실패로 끝난다.** 0건 성공이 아니다. 실행 기록에 `failed`로 남는다.

**첨부는 `HEAD`가 403이고 `GET`만 200이다.** 브라우저 UA와 Referer가 필요하다. 그리고 기업마당은 **오류도 HTTP 200 + HTML로** 준다. 안 거르면 3KB짜리 오류 페이지가 hwp로 저장돼 '파서 실패'로 둔갑한다.

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

`web/app/admin/`은 **운영 도구**다. 이 화면의 목적은 운영이 아니라 **L1 추출 스키마 설계를 위한 코퍼스 관찰**이다.
`DESIGN.md` 토큰을 쓰지만 구성은 표 중심 그대로다 — §5 "쓰지 않는 구성"의 금지 조합은 제품 화면 기준이고 admin은 예외다(plan/08 T-0023).
