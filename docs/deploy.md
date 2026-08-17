# deploy — 읽기 경로를 Vercel에 올린다

> 기준 2026-08-17. 결정은 [ADR-0026](adr/0026-읽기-경로만-vercel에-올린다.md).
> **올라가는 것은 화면 둘과 그걸 먹이는 API 뿐이다.** 수집·해독·운영 도구는 로컬에 남는다.

```
브라우저 ──▶ finnect-web (Vercel · Next.js)
                  │  서버 컴포넌트가 부른다. 브라우저는 API 주소를 모른다
                  ▼
             finnect-api (Vercel · Python Function)
                  │
                  ▼
             Neon PostgreSQL  ◀── 로컬에서 부은 스냅숏
```

**배포본은 스냅숏이다.** 공고가 갱신돼도 저절로 안 따라간다. 4단계를 다시 돌려야 한다.

---

## 0. 준비

Vercel 계정에 로그인돼 있어야 한다. CLI 가 없으면 깐다.

```bash
npm i -g vercel
vercel login
```

레포는 GitHub 에 있다 — `YASICJUNWOO/finnect-new`. Git 연동으로 붙이면 푸시마다 프리뷰가 뜬다.

---

## 1. Neon PostgreSQL 을 붙인다

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

## 2. 스키마를 만든다

로컬에서 원격 DB 를 향해 alembic 을 돌린다. **`notice` 뷰까지 이 단계가 만든다.**

```bash
DATABASE_URL='postgresql+psycopg://...-pooler.../neondb?sslmode=require' \
  uv run alembic upgrade head
```

---

## 3. 데이터를 붓는다

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

## 4. API 를 올린다

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
vercel env add FINNECT_API preview      # 4단계에서 나온 API 배포 URL
vercel deploy
```

`FINNECT_API` 는 `next.config.ts` 가 읽는다. 없으면 `http://127.0.0.1:8100` 으로 떨어져서 **배포본이 로컬을 부르다 실패한다.** 이 값이 이 배포에서 가장 자주 틀리는 자리다.

---

## 6. 잠근다

화면 대부분이 "아직 없어요"로 비어 있어 공개 제품이 아니다. 두 프로젝트 다 켠다.

Vercel 대시보드 > 프로젝트 > Settings > Deployment Protection > **Vercel Authentication** 을 켠다.

---

## 안 올라가는 것

| 무엇 | 왜 |
|---|---|
| `uv run python -m finnect.ingest` | K-Startup 전량이 149회이고 데몬 스레드로 돈다. 응답보다 오래 산다 |
| `uv run python -m finnect.attach` | 30분짜리다. 받은 파일 1.7GB 가 로컬 디스크에 쌓인다 |
| `src/finnect/admin/` | 운영 도구. `SPEC.md` §6 범위 밖이고 인증이 없다 |
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
