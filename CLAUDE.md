# finnect

가진 파일을 통째로 던지면 **내 사업 위키**가 만들어지고, 그 위키로 **맞는 공고를 골라 주고**, 들어가면 **문서가 이미 써져 있다.**

## 상태 — 먼저 읽을 것

**2026-08-16 v2로 피봇했다**([ADR-0012](docs/adr/0012-v2-피봇-사업-위키.md)). 폼 입력 → 판정 → 3단계 집필이던 v1 명세는 대체됐다. **`SPEC.md`를 다시 읽어라. 기억하고 있는 F0~F9와 S1~S8은 없다.**

코드는 **공고 수집(F2-1)과 첨부 해독(F2-2 앞부분), 낼 서류·작성 항목 추출(F2-3), 그리고 그걸 보여 주는 화면 두 장(S4·S5)까지 있다.** 제품의 뿌리인 사업 위키(F1)는 **아직 코드가 한 줄도 없다** — 다만 2026-08-18 계획([plan/12](docs/plan/12-사업-위키-구축.md))과 테스트 코퍼스([`tests/fixtures/wiki/`](tests/fixtures/wiki/README.md))가 먼저 생겼다. 무엇이 있고 없는지는 [plan/README](docs/plan/README.md) 한 곳에 있다.

**2026-08-18 [plan/06](docs/plan/06-목록-수집과-조회.md)·[plan/07](docs/plan/07-첨부-내려받기와-해독.md)·[plan/08](docs/plan/08-사용자-화면-공고-조회.md)이 닫혔고 [plan/09](docs/plan/09-사용자-앱-분리.md)·[plan/11](docs/plan/11-작성-항목-추출과-표시.md)·[plan/12](docs/plan/12-사업-위키-구축.md)가 열려 있다.** 공고 31,327건이 적재됐고(기업마당 1,538 · K-Startup 29,789), 첨부 3,354건을 받아 2,827건에서 텍스트가 나왔다([실측](docs/adr/evidence/2026-08-17-첨부-해독-실측.md)).

**앱이 셋이고 그중 둘이 한 몸이다.** `web/` Next.js — `(product)/` 사용자 화면과 `admin/` 운영 조회 화면 · `src/finnect/api/` 제품 API + 운영 API · `src/finnect/admin/` **수집 실행만** 남은 로컬 앱([ADR-0023](docs/adr/0023-제품-프론트를-nextjs로-분리한다.md) · [ADR-0027](docs/adr/0027-운영-화면을-nextjs로-옮긴다.md)).

- 첨부는 **내려받아 텍스트까지 뽑는다**([plan/07](docs/plan/07-첨부-내려받기와-해독.md)). 뽑은 텍스트로 **아직 아무것도 판단하지 않는다**
- LLM은 아직 한 번도 부르지 않는다. **제공자를 정하지 않았다** — [plan/11](docs/plan/11-작성-항목-추출과-표시.md) T-0036 과 [plan/12](docs/plan/12-사업-위키-구축.md) T-0045 가 같은 블로커를 공유하고, **먼저 착수하는 쪽이 정한다**
- **질문 타이밍이 정해졌다**([ADR-0028](docs/adr/0028-초안을-먼저-완성하고-못-채운-자리에서-묻는다.md)). 초안이 먼저 다 나오고, 항목 옆에서 묻고, 답하면 **위키에 먼저 저장한 뒤** 그 항목만 재작성한다. 사용자 답변은 `user_stated` 등급이라 **문서가 자동으로 덮지 않는다**
- 제품 화면은 **S4·S5 둘뿐이다.** 나머지 다섯(S1·S2·S3·S6·S7)은 없다. 화면 대부분이 **"아직 없어요"로 비어 있고 그게 의도다** — 예시 데이터를 넣지 않는다
- API 계약은 [`docs/api-contract.md`](docs/api-contract.md)에 있다. **`web/`은 DB를 모른다**
- **운영 조회 화면 넷은 `web/app/admin/`에 있고 배포본에서도 열린다**([ADR-0027](docs/adr/0027-운영-화면을-nextjs로-옮긴다.md)). 토큰을 입었고 T-0023이 그 커밋에서 닫혔다. `src/finnect/admin/`에는 **수집 실행 버튼만** 남았다 — 데몬 스레드라 안 올라간다. **읽기 화면을 거기 다시 만들지 않는다**
- **`api/admin_service.py`에서 `attach.service`·`ingest.service`를 임포트하지 않는다.** 저 둘이 httpx와 파서를 끌고 오는데 `requirements.txt`가 그것들을 뺐다. 임포트하면 **로컬은 통과하고 배포본만 죽는다.** `tests/test_admin_api.py`가 막아 둔다
- **`DESIGN.md` §4 토큰 실값이 찼다**([ADR-0025](docs/adr/0025-토큰-실값-확정.md)). 값의 유일한 자리는 `web/app/tokens.css`이고 정본은 DESIGN.md §4다
- `spike/`는 실측용 **버리는 코드**다. 기능을 얹거나 리팩터하지 않는다. 다시 돌리려면 `uv sync --group spike`

## 스택

Python 3.13 · uv · FastAPI · Jinja2 · PostgreSQL 18 · SQLAlchemy 2.0 · Alembic ([ADR-0020](docs/adr/0020-스택-확정.md)).
제품 프론트는 **Next.js 16 · TypeScript · CSS Modules** ([ADR-0023](docs/adr/0023-제품-프론트를-nextjs로-분리한다.md)). ADR-0020이 비워 둔 자리를 채운 것이라 뒤집는 게 아니다.

**v2가 여기 없는 것을 요구한다.** 오브젝트 스토리지(원본 파일), 큐와 워커(파일별 비동기 상태머신), 벡터 저장(근거 청크 검색), HWP 파서, OCR.

**이걸 미리 고르지 않는다**([ADR-0021](docs/adr/0021-인프라-선정을-미룬다.md)). 전부 아직 없는 코드의 것이라, 각각을 실제로 필요로 하는 작업에서 정하고 ADR로 남긴다. 파일을 처음 받는 작업이 저장 위치와 격리 정책을 함께 정한다.

## 명령

```bash
uv sync                                          # 의존성
docker compose up -d db                          # PostgreSQL (127.0.0.1:55433)
uv run alembic upgrade head                      # 스키마
uv run python -m finnect.ingest --source bizinfo    # 1,538건 · 요청 1회
uv run python -m finnect.ingest --source kstartup   # 29,789건 · 요청 149회
uv run python -m finnect.ingest --source bizinfo --limit 40   # 맛보기. 잘림이 기록에 남는다
uv run python -m finnect.attach                  # 첨부 3,354건 · 약 2GB · 30분 남짓
uv run python -m finnect.attach --redo           # 파서를 고쳤을 때. 파일은 다시 안 받는다
uv run python -m finnect.attach --report         # 해독 집계만
uv run uvicorn finnect.admin.app:app --reload    # 수집 실행 :8000 (/ingest 하나뿐이다)
uv run uvicorn finnect.api.app:app --port 8100   # API :8100 — 제품 + 운영. /docs 에 OpenAPI
cd web && npm run dev                            # 화면 :3000. API 가 먼저 떠 있어야 한다
                                                 #   /         제품 목록·상세
                                                 #   /admin     운영 조회 화면 넷
uv run pytest
uv run ruff check src tests   # `.` 은 spike/ 와 자동 생성 마이그레이션 때문에 안 통과한다
cd web && npm run lint && npm run typecheck && npm run build
```

## 저장 모델

**API가 준 컬럼을 전부 만든다. 이름도 API 필드명 그대로다**(대소문자까지).

| | |
|---|---|
| `raw_fetch` | 응답 통째 (봉투·쿼터 포함) |
| `bizinfo_notice` | 기업마당 22컬럼 |
| `kstartup_notice` | K-Startup 30컬럼 |
| `notice` (뷰) | 둘을 공통 8필드로 매핑. 매핑 정본은 `src/finnect/views.py`. **제품 목록만 이 뷰를 쓴다** — 운영 상세는 출처별 표에서 직접 읽는다 |
| `attachment` | 첨부 메타. **API가 준 것** |
| `attachment_file` | 첨부를 받아서 읽어 본 결과. **우리가 한 것** ([ADR-0022](docs/adr/0022-첨부-원본을-콘텐츠-주소로-로컬에-둔다.md)) |
| `document` | 공고가 요구하는 문서 한 벌. **첨부 텍스트 안의 한 구간이다** — 파일 하나가 문서 하나가 아니다. 키가 `sha256` 인 이유는 `attachment_file` 과 같다 ([plan/11](docs/plan/11-작성-항목-추출과-표시.md)) |
| `document_item` | 그 문서 안의 작성 항목. 원문 지시문을 **우리가 고쳐 쓰지 않는다** |
| `ingest_run` | 수집 실행 기록. **코퍼스가 아니라 운영 기록이다** ([ADR-0011](docs/adr/0011-수집-실행-화면.md)) |

**`attachment`에 해독 상태를 붙이지 않는다.** 공고가 갱신되면 그 행이 통째로 지워지고 다시 깔린다(`ingest/runner.py` `_flush`). 상태는 URL을 키로 하는 `attachment_file`에 산다. 원본 파일은 `data/attachments/<sha256[:2]>/<sha256>`.

두 출처는 **필드 이름을 하나도 공유하지 않는다**(22 · 30 · 교집합 0). 전부 수동 매핑이다.
전부 TEXT로 받는다. 파생 값은 `derived_` 접두사로 API 값과 구분한다.
처음 보는 필드는 `extra` JSONB로 흘리되 **건수를 보고한다.** 조용히 버리지 않는다.

필드 설명은 `src/finnect/fields.py`가 정본이고 **공식 문서에서 옮긴 것만 담는다.** 기업마당 20/22 · K-Startup 28/30이고 나머지는 '문서에 없음'으로 화면에 적는다. 이름으로 뜻을 추측해 채우지 않는다.

## 문서

실행 방법은 [`README.md`](README.md)에 있다. 나머지는 전부 `docs/`다.

- [`docs/SPEC.md`](docs/SPEC.md) — **정본.** 무엇을 만드는가. 현재 진실이고, 충돌 시 이 문서가 이긴다. 구현 중 검수 기준으로 참조하되 임의로 고치지 않는다
- [`DESIGN.md`](DESIGN.md) — **시각 방향의 정본**(레포 루트). 여기에 한해서는 SPEC보다 이 문서가 이긴다([ADR-0018](docs/adr/0018-디자인-방향-이관.md))
- [`docs/api-contract.md`](docs/api-contract.md) — 제품 API 계약. `web/`과 `src/finnect/api/` 사이의 유일한 경계다. **정본은 코드**(`api/schemas.py`)이고 이 문서가 뜻을 적는다
- [`docs/deploy.md`](docs/deploy.md) — 배포 절차. **올라가는 것은 읽기 경로뿐이다**([ADR-0026](docs/adr/0026-읽기-경로만-vercel에-올린다.md)). 수집·해독·admin은 로컬에 남는다
- [`docs/plan/`](docs/plan/README.md) — 계획과 태스크. **진행 상태의 정본이다.** 무엇이 막혀 있는지는 `plan/README.md` 한 곳에만 적는다
- [`docs/adr/`](docs/adr/README.md) — 결정 로그. **append-only. 기존 파일 본문을 수정하지 않는다**
- [`docs/adr/evidence/2026-08-16-v2-기획문서/`](docs/adr/evidence/2026-08-16-v2-기획문서/) — **기획이 넘긴 v2 원본 일곱.** SPEC이 이걸 흡수했다. 문서끼리 안 맞는 곳이 있으니 SPEC §9를 먼저 본다
- [`docs/adr/evidence/2026-08-18-전체-구상도.md`](docs/adr/evidence/2026-08-18-전체-구상도.md) — **기획이 넘긴 시스템 전체 구상도**의 전사본. 어디를 다르게 가는지는 [plan/12](docs/plan/12-사업-위키-구축.md)의 `구상도와의 차이`에 있다
- ~~`docs/design/`~~ — **v1 산출물. 대체됐다**([ADR-0018](docs/adr/0018-디자인-방향-이관.md)). Primer 팔레트와 S1~S8 와이어프레임이 들어 있다. 현재 설계로 읽지 않는다
- `docs/archive/` — 폐기된 방향. **구 방향(청년 정책 추천) 기준이다.** 현재 설계로 착각하지 않는다

## 규칙

**사실 주장에는 근거 링크를 붙인다.** 근거 없는 주장은 `SPEC.md` §8에 날짜와 함께 올리거나, 올릴 수 없으면 쓰지 않는다.

**자동 판정 수치를 육안 검증 없이 쓰지 않는다.** 실측에서 배점 탐지기가 30% → 45% → 25%로 갔고 앞의 둘은 오탐이었다. 추출·판정 정확도를 보고할 때 몇 건을 눈으로 봤는지 함께 적는다.

**배점에 기대지 않는다.** 주요 공고가 항목별 배점을 공개하지 않는다(명시율 25%). 집필의 축은 **양식 목차와 항목별 작성 지침**이다([ADR-0019](docs/adr/0019-집필의-축을-양식으로.md)). 배점 순 정렬과 배점 기반 분량 배분을 만들지 않는다. **배점은 공고가 줄 때만 쓴다.**

**확률을 말하지 않는다.** 합격 가능성을 예측하지 않고 적합도 점수를 화면에 숫자나 막대로 두지 않는다. 92와 74의 차이를 설명할 눈금이 없다. 순서가 정보를 담는다.

**자격과 적합도를 섞지 않는다.** 자격은 결정론이고 못 넘으면 화면에서 뺀다. 적합도는 의미 판단이고 순서를 정하며 **이유와 함께만** 내보낸다([ADR-0013](docs/adr/0013-판정-두-층.md)).

**모든 값에 출처를 매단다.** 노드는 근거 청크를 직접 들고, 집필은 그 청크만 꺼내 쓴다. **나중에 붙이는 것은 불가능하다** — 위치정보는 파싱 단계에서만 심을 수 있다([ADR-0014](docs/adr/0014-통합-그래프와-근거-청크.md)).

**결정은 ADR에 남긴다.** ADR에 없는 결정은 결정이 아니라 관성이다. 뒤집을 때는 본문을 고치지 않고 상태를 `대체됨`으로 바꾸고 새 번호를 만든다.

**틀린 문서를 미리 쓰지 않는다.** 계층별 상세 사양(노드 스키마, 추출 스키마, 요건 표현식, 프롬프트)은 코퍼스를 보고 나서 쓴다.

화면 카피는 **해요체**로 쓴다. 문서는 지금 문체 그대로다. 규칙은 [`DESIGN.md`](DESIGN.md) §8. 대행한다고 말하지 않는다.

### 스펙 동기화

- 구현 중 `SPEC.md`와 다르게 해야 할 이유를 발견하면 **임의로 진행하지 말고 먼저 알린다**
- 승인되면 코드와 문서를 **같은 커밋에** 함께 고친다
- 되돌리기 어려운 기술 결정은 `docs/adr/`에 새 파일로 추가한다
- 계획의 태스크 여럿이 동시에 무의미해지면 태스크를 땜질하지 말고 **그 계획이 틀렸다고 보고**한다
- 태스크는 계획 파일 안에 산다. 별도 트리를 만들지 않는다

### 완료 판정

작업을 마쳤다고 말하기 전에 해당 계획의 `검증` 절 항목을 실행하고 **출력을 근거로 제시**한다.

**00~05의 `검증` 절은 아직 `<!-- TODO -->`이고 04·05는 폐기됐다.** 명령이 없으면 지어내지 말고, 검증할 수단이 없다는 사실을 그대로 보고한다. 검증 없이 "완료"라고 하지 않는다. plan/06의 `검증` 절에는 실행 가능한 명령이 있다.

## 함정

- **두 API 모두 실패를 HTTP 200으로 준다.** 기업마당은 `reqErr`, K-Startup은 봉투 없는 `{"code":0,"msg":"정상"}`. 후자는 `data.get("data") or []`로 받으면 **0건 성공으로 읽고 조용히 넘어간다.** 봉투 검증은 방어 코드가 아니라 파싱의 첫 단계다(`ingest/envelope.py`)
- **K-Startup의 서버측 날짜 필터는 틀린 값을 준다.** `cond[...::GTE]` 계열이 조건을 위반하는 레코드를 섞어 준다. 코드값 `EQ`와 이름 `LIKE`만 검증됐다. 전량이 149회(일 한도 10,000)라 아낄 이유가 없다
- K-Startup 페이징 종료는 **`matchCount`** 기준이다. `totalCount`는 필터와 무관하게 29,789 고정이다
- K-Startup은 **수정일시 필드가 없다.** 변경 감지는 콘텐츠 해시뿐이다
- **기업마당 접수 기간의 57%는 날짜가 아니다**(예산 소진시까지 597 · 상시 접수 123 등). 날짜가 없는 것이 정상 상태다
- K-Startup은 첨부 필드를 API로 주지 않는다. 상세 페이지를 긁어야 하고, 마감 공고는 `bizpbanc-deadline.do`로 들어가야 첨부가 렌더된다
- **"기업마당 첨부 0개 431건"을 첨부가 없는 공고로 읽으면 틀린다.** `fileNm`만 센 값이고, **공고문(`printFileNm`)은 1,538건 전부에 붙는다.** 저장된 첨부가 0개인 기업마당 공고는 없다 — [실측 정정](docs/adr/evidence/2026-08-16-목록-API-실측.md)
- `postgres:18`은 볼륨을 `/var/lib/postgresql`에 마운트한다. 17 이하 방식(`/data`)으로 걸면 컨테이너가 `Exited(1)`로 죽는다
- **평가 정보는 공고 본문에 0%다**(기업마당 0/200, K-Startup 0/200). 첨부를 열지 않으면 아무것도 없다
- 창업진흥원은 사업계획서 양식을 HWP와 DOCX **두 벌**로 붙인다. 포맷 하나를 빠뜨리면 그 공고 판단이 통째로 틀릴 수 있다
- **첨부 파싱은 이미 된다. 전량으로 확인했다** — 3,354건 중 2,827건 해독(지원 4포맷 모수 94.6%) · HWP·HWPX·DOCX 100%. 기획 문서가 이걸 아직 조사 과제로 두고 있다 — [06_해야할일](docs/adr/evidence/2026-08-16-v2-기획문서/06_해야할일.md) §3. 다시 조사하지 말고 [실측](docs/adr/evidence/2026-08-17-첨부-해독-실측.md)을 넘겨준다
- **마이그레이션을 새로 만들면 배포 DB 에도 돌려야 한다.** `alembic upgrade head` 는 한 번만 하는 단계가 아니다. 2026-08-18 `document`·`document_item` 을 로컬에만 만들었더니 `/api/notices/{...}/documents` 가 500 이 됐고 **그 500 이 공고 상세를 통째로 죽였다** — 새 표를 읽는 곳은 새 경로 하나뿐인데 화면 전체가 안 떴다. 절차는 [deploy.md](docs/deploy.md) §2. **새 표에 데이터도 부어야 한다** — 스키마만 올리면 화면이 "양식이 첨부에 없어요"를 전 공고에 띄운다
- **`FINNECT_API` 에 배포 URL(`finnect-<해시>-<팀>.vercel.app`)을 넣으면 안 된다.** 그 주소는 불변이라 **API 에 새 경로가 생겨도 웹이 영원히 못 본다.** 2026-08-17 운영 화면을 올린 뒤 `/admin/*` 만 500 이었고 `/` 는 멀쩡해서 늦게 잡혔다 — 옛 배포에도 `/api/notices` 는 있었기 때문이다. 값은 `https://finnect-api.vercel.app` 이고, **고친 뒤 웹을 재배포해야 한다**(`next.config.ts` 의 `env` 는 빌드 때 박힌다) — [deploy.md](docs/deploy.md)
- **PDF 추출률은 91%가 아니라 86.1%다.** 91%는 표본 22개였고 1,167개로 다시 재니 낮아졌다. 차이 5%p가 전부 스캔본이다
- **"스캔 PDF는 매뉴얼뿐이라 OCR 실익이 없다"는 스파이크 결론은 틀렸다.** 표본 3건에서 나온 말이고, 158건에서는 **34건이 그 공고의 유일한 근거**다
- **사업자등록증은 거의 사진이라 OCR이 필요하다.** 위키의 자격 판별 입력 다섯 중 넷이 여기서 나온다. **OCR로 가기로 정했고**(2026-08-17) 엔진과 범위는 T-0007이 정한다
- **첨부 URL은 `HEAD`가 403이고 `GET`만 200이다.** 브라우저 UA와 Referer가 필요하고, 기업마당은 **오류도 HTTP 200 + HTML로** 준다. 안 거르면 오류 페이지가 hwp로 저장돼 '파서 실패'로 둔갑한다
- **확장자를 파일명으로 판정하지 않는다.** 3,354건 중 7건이 파일명과 내용이 다르다(`.hwpx`인데 HWP 5건 등). 판정은 `attach/formats.py`가 내용으로 한다
- **ZIP 166개 안에 읽을 수 있는 문서가 799개 있다.** 지금은 목록만 읽고 안 푼다. 풀지 말지는 이 숫자를 보고 정한다
- **기업마당은 재수집마다 1,538건 전부가 '변경'으로 잡힌다.** 콘텐츠 해시 재료에 조회수(`inqireCo`)가 들어 있다. 그래서 `attachment` 행이 매번 통째로 갈리고, 해독 상태가 `attachment_file`에 따로 사는 이유가 이것이다
- **재무제표는 표 구조와 셀 좌표를 보존해야 한다.** 뭉개면 연도-항목-값 대응이 깨진다
- v2 문서군끼리 안 맞는 곳이 있다. 가장 큰 것은 **질문을 언제 하는가**다. `SPEC.md` §9에 전부 올려 뒀다

<!-- omd:start v=1 hash=672475c77b07 -->
# Design System (oh-my-design)

The authoritative brand & UI spec is **@./DESIGN.md**.
Read before any UI/styling/microcopy/motion work.

Preference log (pending corrections): @./.omd/preferences.md

Precedence: DESIGN.md > preferences.md > your defaults.
<!-- omd:end -->
