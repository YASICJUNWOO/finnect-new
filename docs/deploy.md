# deploy — 화면은 Vercel, API 와 워커는 자체 서버

> 기준 2026-08-18. 결정은 [ADR-0035](adr/0035-api와-워커를-자체-서버로-내리고-vercel은-화면만-맡는다.md).
> **2026-08-17 구조에서 API 가 내려왔다** — 올리기가 서버리스 읽기 전용 파일시스템에서
> 안 되기 때문이다([ADR-0026](adr/0026-읽기-경로만-vercel에-올린다.md)은 대체됐다).

```
브라우저 ──▶ finnect-web (Vercel · Next.js · HTTPS)
                  │  서버 컴포넌트와 라우트 핸들러가 부른다.
                  │  **브라우저는 API 주소를 모른다** — 그래서 HTTPS 화면이
                  │  HTTP API 를 불러도 mixed content 가 아니다
                  ▼  https://49.247.203.210 + X-Finnect-Token
             Caddy :443 (이 서버 · Docker · 호스트 네트워크)
                  │  Let's Encrypt IP 인증서. :80 은 308 로 넘긴다
                  ▼
             uvicorn 127.0.0.1:8101  (systemd --user · 워커 1)
                  ▼
             Docker PostgreSQL :55433   +   data/user-files/  ·  data/attachments/
```

**스냅숏이 없어졌다.** 수집하는 자리와 서비스하는 자리가 같아져서 Neon 도
`pg_dump` 왕복도 필요 없다. 공고를 새로 받으면 **그 즉시 화면에 보인다.**

| 어디 | 무엇 | 포트 |
|---|---|---|
| Vercel `finnect-web` | 제품 화면 · 운영 조회 화면 넷 | 443 |
| 이 서버 Caddy | 바깥 문. 토큰 검사는 API 가 한다 | **443** (80 은 리다이렉트) |
| 이 서버 uvicorn | 제품 API + 운영 API + 올리기 | 8101 |
| 이 서버 uvicorn (개발) | **배포와 별개다.** 손으로 띄운다 | 8100 |
| 이 서버 PostgreSQL | 유일한 DB | 55433 (로컬만) |

**80·443 은 이미 열려 있다.** Let's Encrypt 가 둘 다로 검증에 성공한 것이 증거다
([ADR-0036](adr/0036-도메인-없이-ip-인증서로-https-를-세운다.md)).

---


## 0. 준비

Vercel 계정에 로그인돼 있어야 한다. CLI 가 없으면 깐다.

```bash
npm i -g vercel
vercel login
```

레포는 GitHub 에 있다 — `YASICJUNWOO/finnect-new`. Git 연동으로 붙이면 푸시마다 프리뷰가 뜬다.

---

## A. 이 서버에 API 를 세운다

**여기가 지금의 1~4장이다.** 아래 1~4장은 API 가 Vercel 에 있던 시절 절차이고
[ADR-0035](adr/0035-api와-워커를-자체-서버로-내리고-vercel은-화면만-맡는다.md)가 대체했다.
지우지 않고 두는 이유는 거기 적힌 함정이 되돌릴 때 다시 필요해서다.

### A-1. 토큰을 만든다

**`.env` 에 넣지 않는다.** 거기 두면 개발 서버(`--port 8100`)도 읽어서 `npm run dev`
가 401 을 받는다. 레포 밖에 두고 systemd 만 읽게 한다.

```bash
mkdir -p ~/.config/finnect
python3 -c "import secrets; print('API_TOKEN=' + secrets.token_urlsafe(32))" \
  > ~/.config/finnect/api.env
chmod 600 ~/.config/finnect/api.env
```

환경변수가 `.env` 보다 우선이라 **이 파일이 있는 프로세스에서만 토큰 검사가 켜진다.**

### A-2. API 를 서비스로 올린다

```bash
cp deploy/finnect-api.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now finnect-api
systemctl --user status finnect-api
```

`linger` 가 켜져 있어야 로그아웃·재부팅 뒤에도 산다. 이미 켜져 있다.

```bash
loginctl show-user "$USER" -p Linger    # Linger=yes
```

**`--workers 1` 을 늘리지 않는다.** `ingest/jobs.py` 의 락이 `threading.Lock` 이라
프로세스 안에서만 산다. 늘리면 같은 회사의 위키 구축이 두 번 동시에 돌고 청크가 두 벌 생긴다.

**8101 이다. 8100 이 아니다** — 8100 은 개발용으로 비워 둔다. 배포 서비스가 떠 있어도
`uv run uvicorn finnect.api.app:app --port 8100` 이 그대로 된다.

### A-3. 문을 연다

```bash
docker compose up -d db proxy
```

### **자기 공인 IP 로 서버 안에서 접속하면 안 된다**

헤어핀 NAT 라 `000` 이 난다. **멀쩡한 서비스를 죽은 것으로 오진하는 자리다.**
루프백으로 붙이되 IP 사이트로 말을 건다.

```bash
C="--connect-to 49.247.203.210:443:127.0.0.1:443"
TOKEN=$(grep '^API_TOKEN=' ~/.config/finnect/api.env | cut -d= -f2-)

curl -s -o /dev/null -w "%{http_code}\n" $C https://49.247.203.210/healthz      # 200
curl -s -o /dev/null -w "%{http_code}\n" $C https://49.247.203.210/api/notices  # 401
curl -s -o /dev/null -w "%{http_code}\n" $C -H "x-finnect-token: $TOKEN" \
  https://49.247.203.210/api/notices                                            # 200
curl -s -o /dev/null -w "%{ssl_verify_result}\n" $C https://49.247.203.210/healthz  # 0
```

**401 이 나와야 정상이다.** 200 이 나오면 토큰이 안 켜진 것이고, 그러면
`POST /api/wiki/{company_id}/files` 가 인터넷에 열린 업로드 창구다.

**`ssl_verify_result` 가 0 이어야 한다.** 공인 CA 로 검증됐다는 뜻이고, 그래야 Vercel 의
Node 가 붙는다.

### 인증서 (ADR-0036)

```
issuer  Let's Encrypt CN=YE2 · SAN  IP Address:49.247.203.210 · 유효 약 6.7일
```

**`default_sni` 가 전역 옵션으로 있어야 한다.** IP 에는 SNI 가 안 실려서, 없으면
인증서를 정상 발급받고도 **아무도 못 붙는다**(`tlsv1 alert internal error`).
`tls` 블록 안에 쓰면 `unknown subdirective` 로 기동이 죽고 재시작 루프에 빠진다.

**Caddy 가 호스트 네트워크로 돈다.** uvicorn 이 `127.0.0.1` 에만 붙어 있어서 다리
네트워크의 `host.docker.internal`(172.17.0.1)로는 안 닿는다 — 502 가 난다.

### A-4. 도메인이 생기면

`deploy/Caddyfile` 의 IP 를 도메인 이름으로 바꾸고 `profile shortlived` 를 뺀다
(도메인은 90일 인증서다). `default_sni` 도 같이 뺄 수 있다.

**평문 구간은 이미 없어졌다**([ADR-0036](adr/0036-도메인-없이-ip-인증서로-https-를-세운다.md)).
도메인은 주소가 예뻐지는 것이지 보안 요건이 아니다.

---

## ~~1. Neon PostgreSQL 을 붙인다~~ (대체됨)

> **[ADR-0035](adr/0035-api와-워커를-자체-서버로-내리고-vercel은-화면만-맡는다.md)로 대체됐다.**
> DB 가 이 서버의 Docker PostgreSQL 하나다. 아래는 되돌릴 때를 위해 남긴다.


Vercel Marketplace 에서 만든다.

```bash
vercel integration add neon
```

만들고 나면 **연결 문자열 두 개**가 생긴다. **pooled 쪽을 쓴다** — 이름에 `-pooler` 가 들어 있는 것이다. 서버리스는 인스턴스가 여럿 뜨므로 직결을 쓰면 커넥션이 마른다.

SQLAlchemy 용으로 스킴을 바꿔야 한다. Neon 이 주는 `postgresql://` 를 **`postgresql+psycopg://`** 로 고친다.

```
postgresql+psycopg://<user>:<pw>@<host>-pooler.<region>.aws.neon.tech/<db>?sslmode=require
```

---

## ~~2. 스키마를 만든다~~ (대체됨)

> API 와 DB 가 이 서버로 내려와 이 단계가 없어졌다. A 장을 본다.

로컬에서 원격 DB 를 향해 alembic 을 돌린다. **`notice` 뷰까지 이 단계가 만든다.**

```bash
DATABASE_URL='postgresql+psycopg://...-pooler.../neondb?sslmode=require' \
  uv run alembic upgrade head
```

### **마이그레이션을 새로 만들면 여기를 다시 돌린다**

**한 번만 하는 단계가 아니다.** `alembic revision` 을 새로 만들 때마다 배포 DB 에도
같은 명령을 돌려야 한다. **안 돌리면 로컬은 멀쩡하고 배포본만 죽는다.**

2026-08-18 실제로 당했다. `document`·`document_item` 을 로컬에만 만들었더니
`/api/notices/{...}/documents` 가 500 이 됐고, **그 500 이 공고 상세 화면을 통째로
죽였다.** 새 표를 읽는 곳은 새 경로 하나뿐인데 화면 전체가 안 떴다.

두 가지를 같이 고쳤다.

1. `web/lib/api.ts` 의 `getNoticeDocuments` 가 **어떤 실패든 null 로 돌려세운다.**
   곁다리 섹션 하나가 본문을 죽이면 안 된다. `null` 은 "양식이 없다"가 아니라
   "모른다"라서 화면이 섹션을 아예 안 그린다
2. 이 문단

**새 표에 데이터도 부어야 한다.** 3장의 덤프 목록에 표를 추가하는 것을 잊지 않는다 —
스키마만 올리면 표는 있고 안이 비어서, 화면이 "양식이 첨부에 없어요"를 **전 공고에**
띄운다. 그게 사실이 아닌데도 그렇게 보인다.

---

## ~~3. 데이터를 붓는다~~ (대체됨)

> API 와 DB 가 이 서버로 내려와 이 단계가 없어졌다. A 장을 본다.

로컬 DB 에서 뜬 덤프를 그대로 넣는다. **여섯 표 전부**다 — 두 공고 표가 `raw_fetch` 에 FK 로 걸려 있어서 뺄 수 없다.

```bash
docker compose exec -T db pg_dump -U finnect -d finnect \
  --data-only --no-owner --no-privileges \
  -t raw_fetch -t bizinfo_notice -t kstartup_notice \
  -t attachment -t attachment_file -t ingest_run \
  | gzip > /tmp/finnect-data.sql.gz

gunzip -c /tmp/finnect-data.sql.gz \
  | psql 'postgresql://...-pooler.../neondb?sslmode=require'
```

실측 — **101MB, gzip 20.3MB, 덤프 2.7초.** Neon 무료 한도 0.5GB 안이다.
`psql` 에 넣을 때는 `+psycopg` 를 **뺀** 원본 URL 을 쓴다. 그건 SQLAlchemy 전용 스킴이다.

확인:

```bash
psql '<원본 URL>' -c 'select source, count(*) from notice group by source'
```

`bizinfo 1538` · `kstartup 29789` 가 나와야 한다.

---

## ~~4. API 를 올린다~~ (대체됨)

> API 와 DB 가 이 서버로 내려와 이 단계가 없어졌다. A 장을 본다.

레포 루트가 프로젝트 루트다. `vercel.json` 과 `requirements.txt` 와 `api/index.py` 가 이미 있다.

```bash
vercel link          # 프로젝트 이름 finnect-api
vercel env add DATABASE_URL preview     # 1단계의 +psycopg URL 을 붙인다
vercel deploy
```

확인:

```bash
curl -s '<배포 URL>/api/notices?page=1' | head -c 200
```

**`api/index.py` 는 경로만 잇는다.** 로직은 `src/finnect/api/app.py` 가 정본이고 로컬에서는 uvicorn 이 같은 앱을 띄운다.

---

## 5. 화면을 올린다

**루트 디렉터리를 `web/` 로 잡는다.** 안 그러면 Next.js 를 못 찾는다.

```bash
cd web
vercel link          # 프로젝트 이름 finnect-web
vercel env add FINNECT_API production        # https://49.247.203.210
vercel env add FINNECT_API_TOKEN production  # ~/.config/finnect/api.env 의 값
vercel deploy
```

### 값 둘 (2026-08-18 · [ADR-0035](adr/0035-api와-워커를-자체-서버로-내리고-vercel은-화면만-맡는다.md))

```
FINNECT_API        = https://49.247.203.210
FINNECT_API_TOKEN  = <~/.config/finnect/api.env 의 API_TOKEN 과 같은 값>
```

**둘의 성질이 다르다. 여기서 자주 틀린다.**

| | 어디서 읽나 | 바꾸면 |
|---|---|---|
| `FINNECT_API` | `next.config.ts` 의 `env` — **빌드 시점에 박힌다** | **재배포해야 한다** |
| `FINNECT_API_TOKEN` | `web/lib/api.ts` 가 런타임에 읽는다 | 재배포 없이 바로 먹는다 |

토큰이 `env` 에 없는 것은 **의도다.** 시크릿을 번들에 박지 않고, 돌릴 때 빌드를 안 기다린다.

**`FINNECT_API_BYPASS` 는 이제 아무것도 안 한다.** Vercel Authentication 이 지키던
API 가 없어졌다. 지워도 되고 둬도 무해하다 — `authHeaders()` 가 값이 있으면 헤더를
붙이지만 받는 쪽이 무시한다.

**https 다.** 도메인 없이 Let's Encrypt IP 인증서를 받았다
([ADR-0036](adr/0036-도메인-없이-ip-인증서로-https-를-세운다.md)). `http://` 를 넣으면
308 로 넘어가긴 하지만 리다이렉트를 한 번 더 타므로 `https://` 로 적는다.

### `FINNECT_API` 에 **Vercel 배포 URL을 넣지 않는다** (옛 함정)

> API 가 이 서버로 내려와 이 함정은 지나갔다. 되돌릴 때를 위해 남긴다.

`vercel deploy` 가 찍어 주는 `finnect-<해시>-<팀>.vercel.app` 은 **그 배포에 못 박힌 불변 주소다.** 넣으면 그날은 돌고, **API 에 새 경로가 생겨도 웹은 영원히 못 본다.**

2026-08-17 이걸로 한 번 넘어졌다. 운영 화면을 올린 뒤([ADR-0027](adr/0027-운영-화면을-nextjs로-옮긴다.md)) `/admin/notices` 가 500 이었고 원인이 이랬다.

```
finnect-api.vercel.app/api/admin/notices      200   ← 새 배포에는 있다
웹이 부르던 옛 배포 URL/api/admin/notices      404   ← 거기엔 없다
```

**`/` 는 정상이었다.** `/api/notices` 는 옛 배포에도 있어서다. 그래서 "웹이 멀쩡한데 새 화면만 깨진" 모양이 됐고, 이 조합이 가장 늦게 발견된다.

**프로젝트 프로덕션 도메인을 쓴다.**

```
FINNECT_API = https://finnect-api.vercel.app
```

이 주소는 **항상 최신 프로덕션 배포를 가리킨다.** `finnect-api` 의 Vercel Authentication 이 `all_except_custom_domains` 라서 이 도메인은 보호에서 빠지고, `finnect-api-<팀>.vercel.app` 쪽은 막힌다 — 그래서 이 값이어야 `FINNECT_API_BYPASS` 없이도 돈다.

**값을 바꾼 뒤에는 웹을 다시 배포해야 한다.** `next.config.ts` 의 `env` 는 **빌드 시점에 문자열로 박아 넣는다.** 환경변수만 고치고 재배포하지 않으면 옛 값이 그대로 산다.

`FINNECT_API` 는 `next.config.ts` 가 읽는다. 없으면 `http://127.0.0.1:8100` 으로 떨어져서 **배포본이 로컬을 부르다 실패한다.** 이 값이 이 배포에서 가장 자주 틀리는 자리다.

**`FINNECT_ADMIN` 은 없어졌다**([ADR-0027](adr/0027-운영-화면을-nextjs로-옮긴다.md)). 운영 화면이 같은 앱으로 들어와서 상단 '운영 도구' 링크가 `/admin/notices` 상대 경로가 됐다. 넣어 뒀으면 지운다 — 아무것도 안 읽는다.

그 값이 있던 동안 배포본의 버튼은 `http://127.0.0.1:8000`, 곧 **누른 사람의 자기 기기**를 가리켰다. 로컬에 admin 을 띄워 둔 사람에게만 열렸고 나머지에게는 죽은 버튼이었다. 그 대가를 없애려고 옮긴 것이다.

---

## 5-1. Git 연동 (2026-08-17 붙였다)

두 프로젝트 다 `YASICJUNWOO/finnect-new` 에 붙어 있다. **master 에 푸시하면 둘이 같이 프로덕션으로 배포된다.** 위 4·5단계의 `vercel deploy` 는 이제 손으로 올릴 때만 쓴다.

| 프로젝트 | Root Directory | Production Branch |
|---|---|---|
| `finnect-api` | `.` (레포 루트) | `master` |
| `finnect-web` | **`web`** | `master` |

**기본 브랜치가 `main` 이 아니라 `master` 다.** Production Branch 를 `main` 으로 잡으면 푸시해도 프로덕션이 안 바뀐다.

### 레포 루트 `vercel.json` 이 웹 빌드까지 먹는다

프로젝트 둘이 레포 하나를 보는데 `vercel.json` 은 레포 루트에 한 벌뿐이다. **Root Directory 를 `web` 으로 잡아도 이 파일의 최상위 설정이 웹 빌드에 적용된다.**

여기 `"framework": null` 이 들어 있어서 첫 Git 배포가 죽었다. 그 값은 "감지 안 함"이 아니라 **Other 프리셋을 고르는 값**이다. 빌드는 `web/` 에서 `next build` 까지 정상으로 갔는데, Vercel 이 산출물을 Next.js 가 아니라 정적 사이트로 보고 `public/` 을 찾다 실패했다.

```
Error: No Output Directory named "public" found after the Build completed.
```

**그래서 `framework` 키를 뺐다.** 두 프로젝트 다 프리셋을 Vercel 프로젝트 설정에서 받는다 — 웹은 `nextjs`, API 는 없음이다. `buildCommand`·`outputDirectory` 의 `null` 은 "자동"이라 남겨 뒀다.

**루트 `vercel.json` 에 프런트 관련 최상위 키를 새로 넣지 않는다.** 넣으면 웹 빌드가 같이 끌려간다.

### 안 바뀐 것은 안 빌드한다

`docs/` 만 고친 커밋에도 프로젝트 둘이 다 돌던 것을 끊었다.

```json
"ignoreCommand": "git diff --quiet HEAD^ HEAD ./"
```

**루트 한 벌인데 프로젝트마다 다르게 동작한다.** `./` 이 상대 경로라 각 프로젝트의 Root Directory 로 풀리기 때문이다.

| 프로젝트 | `./` | 결과 |
|---|---|---|
| `finnect-web` | `web/` | web/ 이 안 바뀌면 **건너뛴다** |
| `finnect-api` | 레포 전체 | 항상 바뀜 → **항상 빌드한다** |

**exit 0 이 '건너뛴다'다.** 반대로 알면 배포가 조용히 멈춘다.

API 쪽에 제외 목록(`':!web'` 같은 것)을 쓰지 않는다. 손으로 관리하는 목록은 낡고, 낡은 것을 아무도 모른다. API 빌드는 5초라서 그 위험을 살 이유가 없다.

`HEAD^` 가 없거나 명령이 깨지면 exit 이 0 이 아니라서 **빌드하는 쪽으로 넘어진다.** 틀리는 방향이 안전한 쪽이다.

### 재배포도 이 명령을 탄다

**대시보드의 Redeploy 도 `ignoreCommand` 를 먼저 돌린다.** 그래서 `web/` 을 안 건드린 커밋을 재배포하면 **웹은 건너뛰어지고 `CANCELED` 로 끝난다.**

2026-08-17 이걸로 두 번 헛돌았다. `FINNECT_API` 를 고친 뒤 재배포했는데 마지막 커밋이 `docs/` 와 `CLAUDE.md` 만 건드린 것이라, **새 환경변수를 집는 빌드가 아예 안 돌았다.** 화면은 계속 옛 번들을 서비스했다.

| 무엇 | 결과 |
|---|---|
| 환경변수만 고친다 | **아무 일도 안 일어난다.** `env` 는 빌드 때 박힌다 |
| 그 상태로 재배포한다 | `web/` 이 안 바뀌었으면 **`CANCELED`** |
| `web/` 을 건드린 커밋을 푸시한다 | 빌드가 돌고 새 값이 박힌다 |

**환경변수를 고친 뒤에는 `web/` 안의 무엇이든 함께 바뀌어야 한다.** 프로젝트 설정에서 Root Directory 를 잠깐 비우거나 `ignoreCommand` 를 지우는 방법도 있지만, 그건 이 규칙을 끄는 것이라 다시 켜는 것을 잊는다.

---

## 6. 잠근다

화면 대부분이 "아직 없어요"로 비어 있어 공개 제품이 아니다.

Vercel 대시보드 > 프로젝트 > Settings > Deployment Protection > **Vercel Authentication**.

**프로젝트별 설정이다.** 계정 단위 스위치가 아니라서 프로젝트마다 켜야 하고, 새 프로젝트는 켜진 상태로 시작한다.

**2026-08-17 `finnect-web` 쪽은 껐다.** 시연 URL 을 로그인 없이 열어야 했다. `finnect-api` 는 `all_except_custom_domains` 로 켜져 있고, 그래서 `finnect-api.vercel.app` 은 열리고 `finnect-api-<team>.vercel.app` 은 막힌다.

**끈 상태에서는 운영 화면 넷도 같이 공개된다**([ADR-0027](adr/0027-운영-화면을-nextjs로-옮긴다.md)). 시크릿은 안 나간다 — 인증키는 저장 전에 마스킹되고, 공고와 첨부는 정부 공개 데이터다. 다만 `ingest_run` 실행 기록과 `raw_fetch` 원문이 보인다. 잠그려면 이걸 다시 켠다.

`/admin` 에 `robots: noindex` 가 붙어 있지만 **그것은 접근 제어가 아니다.**

---

## 안 올라가는 것

| 무엇 | 왜 |
|---|---|
| `uv run python -m finnect.ingest` | K-Startup 전량이 149회이고 데몬 스레드로 돈다. 응답보다 오래 산다 |
| `uv run python -m finnect.attach` | 30분짜리다. 받은 파일 1.7GB 가 로컬 디스크에 쌓인다 |
| `POST /ingest/run/{source}` 수집 버튼 | 데몬 스레드로 돈다. 진행률은 그 프로세스 안에서만 산다. **조회 화면 넷은 올라간다**(ADR-0027) |
| `data/attachments/` 원본 1.7GB | 화면은 **메타와 해독 상태만** 쓴다. 파일 링크는 출처 원본을 가리킨다 |

**인증키(`BIZINFO_API_KEY` · `DATA_GO_KR_API_KEY`)를 Vercel 에 넣지 않는다.** 배포본은 수집을 안 한다. 기업마당 키는 신청한 IP 에 묶일 수 있어서 넣어도 안 도는 게 정상이다.

---

## 공고를 갱신하려면

배포본은 스냅숏이다. 새 공고를 반영하려면 **로컬에서 받아서 다시 붓는다.**

```bash
uv run python -m finnect.ingest --source bizinfo
uv run python -m finnect.ingest --source kstartup
uv run python -m finnect.attach
# 그다음 3단계를 다시 돌린다
```

붓기 전에 원격 표를 비워야 한다. `--data-only` 덤프는 기존 행을 안 지운다.

```bash
psql '<원본 URL>' -c 'truncate attachment_file, attachment, kstartup_notice, bizinfo_notice, ingest_run, raw_fetch cascade'
```

**이 절차가 번거로운 것이 [ADR-0026](adr/0026-읽기-경로만-vercel에-올린다.md)이 적어 둔 대가다.** 배포본에서 수집을 돌리려면 큐와 워커를 정해야 하고, 그건 [ADR-0021](adr/0021-인프라-선정을-미룬다.md) B 가 미뤄 둔 결정이다.
