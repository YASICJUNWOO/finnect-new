# ADR-0027: 운영 조회 화면을 Next.js로 옮기고 수집 실행만 로컬에 남긴다

- 상태: 채택됨
- 날짜: 2026-08-17
- 뒤집는 것: [ADR-0026](0026-읽기-경로만-vercel에-올린다.md)의 **"`src/finnect/admin/` 은 안 올라간다" 한 줄만.** 수집·해독·첨부 원본은 그대로 로컬에 남는다
- 좁히는 것: [ADR-0023](0023-제품-프론트를-nextjs로-분리한다.md)의 "앱이 셋이다" — 셋 중 둘이 한 앱 안의 두 층이 됐다
- 실행하는 것: [plan/08 T-0023](../plan/08-사용자-화면-공고-조회.md#t-0023-운영-도구에-토큰을-입힌다) — 토큰을 입히는 방법이 "옮기면서 입힌다"가 됐다

## 맥락

운영 화면 넷(`/notices` · 상세 · `/attachments` · `/ingest`)이 FastAPI + Jinja2 로 로컬 `:8000` 에 살았다. [ADR-0026](0026-읽기-경로만-vercel에-올린다.md)이 "운영 도구. `SPEC.md` §6 범위 밖이고 인증이 없다"를 이유로 안 올리기로 했다.

**그 결정의 대가가 눈에 보이는 형태로 나왔다.** 제품 헤더에 운영 도구로 가는 버튼을 달았더니(커밋 `aacf7f6` · `f3bf0b9`) 배포본에서 그 버튼이 `http://127.0.0.1:8000` 을 가리켰다. 브라우저가 그 주소를 **누른 사람 자기 기기로** 푸니까, 로컬에 admin 을 띄워 둔 사람에게만 열리고 다른 사람에게는 아무것도 안 열렸다. 죽은 버튼이다.

### 두 가지가 그동안 바뀌었다

1. **DB 가 원격에 있다.** ADR-0026 이 Neon 을 붙이고 여섯 표를 통째로 부었다. `notice 31,327` · `attachment 3,354` · `attachment_file 3,354` · `ingest_run 2` · `raw_fetch 151`. **운영 화면이 읽는 값이 전부 거기 있다.** 안 올릴 이유였던 "로컬 DB"가 사라졌다.
2. **토큰 실값이 찼다**([ADR-0025](0025-토큰-실값-확정.md)). T-0023 이 "admin 에 토큰을 입힌다"를 기다리고 있었고, Jinja2 `base.html` 은 `#0645ad` 링크색과 14px 본문으로 돌았다. **어차피 다시 그려야 하는 화면이었다.**

## 결정

**조회 화면 넷을 `web/app/admin/` 으로 옮긴다. 값은 `GET /api/admin/*` 넷이 낸다.**

```
브라우저 ──▶ finnect-web (Vercel · Next.js)
              ├── (product)/   제품 화면. 3축 내비
              └── admin/       운영 화면. 자기 내비
                    │  서버 컴포넌트가 부른다
                    ▼
             finnect-api (Vercel · Python Function)
                    │  GET /api/notices · GET /api/admin/*
                    ▼
             Neon PostgreSQL
```

**수집 실행은 안 옮긴다.** `src/finnect/admin/` 에 `/ingest` 와 `POST /ingest/run/{source}` 만 남는다.

| 옮긴 것 | 어디로 |
|---|---|
| `/notices` 목록 | `/admin/notices` |
| `/notice/{source}/{id}` 상세 | `/admin/notices/{source}/{id}` |
| `/attachments` 해독 현황 | `/admin/attachments` |
| `/ingest` **실행 기록 표와 카드** | `/admin/ingest` |

| 안 옮긴 것 | 왜 |
|---|---|
| `POST /ingest/run/{source}` 수집 버튼 | 응답보다 오래 사는 데몬 스레드다. K-Startup 전량이 요청 149회 |
| 진행률 막대 · '수집 중' 표시 | `jobs.Progress` 가 **수집을 돌리는 프로세스 안에서만** 산다. 서버리스가 알 수 없다 |
| `runs.reap()` 정리 | 쓰기 동작이다. 읽기 경로가 할 일이 아니다 |
| `data/attachments/` 원본 1.7GB | 화면은 메타와 해독 상태만 쓴다 |

### 세 가지를 함께 정했다

**1. 루트 레이아웃에서 제품 헤더를 뺀다.**

`web/app/layout.tsx` 가 `html` · `body` · 토큰만 갖고, 제품 헤더는 `app/(product)/layout.tsx` 로, 운영 내비는 `app/admin/layout.tsx` 로 내려갔다. **운영 화면 위에 '지원사업 / 내 사업 / 신청 현황'이 뜨면 그게 제품처럼 읽힌다.**

**2. API 에서 `attach.service` 와 `ingest.service` 를 임포트하지 않는다.**

`requirements.txt` 가 **의도적으로** httpx·pdfplumber·olefile 을 뺐다. 저 두 모듈이 그것들을 끌고 오므로 임포트하면 **로컬에서는 통과하고 배포본만 `ModuleNotFoundError` 로 죽는다.** 그래서 집계 질의를 `api/admin_service.py` 에 다시 썼다.

베낀 질의는 갈린다. `tests/test_admin_api.py` 가 `attach/service.py` 의 것과 나란히 놓고 대조하고, 금지 모듈을 막은 채 `finnect.api.app` 을 import 해 본다.

`SourceInfo` · `SOURCES` 는 베끼지 않고 `finnect/sources.py` 로 떼어 냈다. `ingest/service.py` 가 다시 import 해서 부르는 쪽 이름은 안 바뀌었다.

**3. 읽기 화면을 Jinja2 에 남기지 않는다.**

같은 화면이 두 벌이면 갈리고, **갈린 것을 아무도 모른다.** `list.html` · `detail.html` · `attachments.html` 을 지웠다.

## 이 결정이 사는 값

**ADR-0026 이 안 올리는 이유로 든 것 둘 중 하나만 풀렸다.** 정직하게 적는다.

| ADR-0026 의 이유 | 지금 |
|---|---|
| "`SPEC.md` §6 범위 밖이다" | **그대로다.** 범위 밖인 것과 배포되는 것은 다른 축이었다 |
| "인증이 없다" | **그대로다.** 아래 참고 |

**인증이 없는 화면이 공개된다.** 무엇이 보이는지 세어 봤다.

- 공고 31,327건과 첨부 메타 — **둘 다 정부 공개 데이터다.** 출처 사이트에 그대로 있다
- 해독 현황 집계 — 우리가 뭘 읽었는지. 새면 곤란한 값이 아니다
- `raw_fetch` 응답 원문과 요청 URL — **인증키는 `ingest/base.py` `mask()` 가 저장 전에 지운다.** `crtfcKey=***` 로 남는 것을 눈으로 확인했고 `tests/test_admin_api.py` 가 잠근다
- `ingest_run` 실행 기록 — pid, 걸린 시간, 잔여 쿼터

**시크릿은 없다.** 그래도 운영 기록이 공개되는 것 자체가 좋은 상태는 아니다. 잠그려면 Vercel Authentication 을 `finnect-web` 에 다시 켜면 되고, 그건 프로젝트 단위 설정이다 — 2026-08-17 사용자가 시연을 위해 껐다.

**막지 않은 것을 막았다고 적지 않는다.** `/admin` 은 `robots: noindex` 뿐이고 그건 접근 제어가 아니다.

## 결과

- 배포본에서 운영 화면 넷이 열린다. 로컬 `:8000` 을 띄우지 않아도 된다
- **T-0023 이 이 커밋에서 닫힌다.** 토큰·포커스·`tabular-nums` 가 들어갔고 구성·컬럼·문체는 안 바꿨다
- `FINNECT_ADMIN` 환경변수가 없어졌다. 링크가 같은 앱 안의 상대 경로다
- **수집을 화면에서 돌리려면 로컬 `:8000` 을 띄워야 한다.** `/admin/ingest` 가 그 명령을 화면에 적는다
- `web/` 이 라우트 둘에서 **일곱으로** 늘었다. `ignoreCommand` 가 `web/` 변경마다 웹을 다시 빌드하므로 배포 빈도가 는다
- 운영 화면이 늘 때 **Python 엔드포인트와 TS 타입을 같이 고쳐야 한다.** Jinja2 시절에는 한 파일이었다. 이것이 이 결정의 값이다

## 안 정한 것

- **인증.** 지금은 없다. 켤지 말지는 시연이 끝난 뒤에 정한다
- **`ingest_run` 의 `running` 상태를 배포본이 어떻게 읽을지.** `reap()` 이 로컬에서만 도니까 죽은 프로세스의 `running` 이 배포 화면에 남을 수 있다. 실행 기록이 2건이라 아직 안 겪었다
- **수집 실행을 언제 올릴지.** 큐와 워커가 필요하고 그건 [ADR-0021](0021-인프라-선정을-미룬다.md) B 가 미뤄 둔 결정이다
