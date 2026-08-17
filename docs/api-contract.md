# api-contract — 제품 API

> 기준 2026-08-17. 정본은 코드다 — `src/finnect/api/schemas.py`.
> 결정: [ADR-0023](adr/0023-제품-프론트를-nextjs로-분리한다.md) 분리 · [ADR-0024](adr/0024-접수-기간-표현.md) 접수 기간

사용자 앱(`web/`)이 부르는 유일한 경계다. **프론트는 DB 를 모른다.**

```bash
uv run uvicorn finnect.api.app:app --reload --port 8100   # /docs 에 OpenAPI
```

**2026-08-17 운영 화면도 이 경계를 쓴다**([ADR-0027](adr/0027-운영-화면을-nextjs로-옮긴다.md)). 접두사가 `/api/admin/` 이고 §운영 경로에 있다. 정본은 `src/finnect/api/admin_schemas.py` 다.

`src/finnect/admin/` 에는 **수집 실행만 남았다.** 그것은 이 계약과 무관하고 `SPEC.md` §6 범위 밖이다.

---

## 규칙

1. **필드 이름을 새로 짓지 않는다.** `views.py` 의 `Notice` 가 쓰는 이름을 그대로 쓴다. 저장 모델이 "API 가 준 이름 그대로"를 지키는 것과 같은 이유다 — 이름이 한 번 더 바뀌면 화면에서 본 값이 DB 의 어느 칸인지 추적이 끊긴다.
2. **파생값은 원문 옆에 두고 원문을 지우지 않는다.** `days_left` 가 있어도 `apply_end` 와 `apply_period_raw` 가 그대로 나간다.
3. **모르는 것을 아는 척하지 않는다.** `null` 은 "값이 없다"가 아니라 대부분 "아직 안 해봤다"이고, 그 구분이 `parse_status` 같은 자리에 산다.
4. **프론트가 문자열을 해석하지 않는다.** 날짜 계산도 HTML 정리도 여기서 끝낸다.

---

## `GET /api/notices`

| 파라미터 | 기본 | 무엇 |
|---|---|---|
| `q` | `""` | 제목 부분 일치 |
| `source` | `""` | `bizinfo` · `kstartup`. 그 외는 무시하고 전체 |
| `page` | `1` | 1부터. 한 쪽 20건 |
| `open_only` | `true` | **마감이 지난 것을 뺀다** |

### `open_only` 가 왜 기본으로 켜져 있는가

**K-Startup 29,789건 중 29,420건이 이미 마감된 과거 공고다.** 그대로 쏟으면 화면이 아카이브가 된다.

**빼는 것은 `apply_end < 오늘` 하나뿐이다.** 날짜가 없는 975건은 빼지 않는다 — 마감했는지 알 수 없고 "예산 소진시까지"는 열려 있을 가능성이 높다. 확인되지 않은 것을 마감으로 처리하지 않는다([ADR-0024](adr/0024-접수-기간-표현.md)).

2026-08-17 기준 `open_only=true` 는 **1,907건**, 끄면 31,327건이다.

### 정렬

고정이다. **정렬 옵션이 없다.**

1. `apply_end` 가 있는 것 — 가까운 마감부터
2. `apply_end` 가 없고 `apply_period_raw` 가 있는 것 — 원문 사전순
3. 둘 다 없는 것 — 맨 뒤

**적합도순이 없다.** 순서를 정할 근거가 없고, 적합도 숫자·막대·열을 두지 않기로 했다(`DESIGN.md` §6).

### 응답

```jsonc
{
  "items": [{
    "source": "bizinfo",
    "external_id": "PBLN_000000000124552",
    "title": "2026년 2차 세종 스타트업 혁신제품 선(先)보급 지원사업 …",
    "organization": "세종창조경제혁신센터",
    "supervisor": "세종특별자치시",
    "category": "창업",

    "apply_start": "2026-07-20",       // 없으면 null
    "apply_end": "2026-08-17",         // 없으면 null. 975건이 여기 해당한다
    "apply_period_raw": "2026-07-20 ~ 2026-08-17",  // "예산 소진시까지" 같은 원문이 온다
    "days_left": 0,                    // apply_end 가 있을 때만. 음수면 지났다

    "detail_url": "https://…",
    "attachment_count": 6
  }],
  "total": 1907, "page": 1, "pages": 96,
  "open_only": true                    // 화면이 "무엇을 안 보여주고 있는지" 말할 수 있어야 한다
}
```

**`apply_end` 가 `null` 이면 `apply_period_raw` 를 그대로 보여 준다.** "마감일 없음"으로 뭉개지 않는다. 원문 34종 중 597건이 "예산 소진시까지"이고 이건 결측이 아니라 정상 상태다.

---

## `GET /api/notices/{source}/{external_id}`

목록 한 줄에 `summary` 와 `attachments` 가 붙는다. 없으면 **404**. 모르는 출처도 404.

```jsonc
{
  // … 목록과 같은 필드 전부 …
  "summary": "KOBACO에서는 1998년부터 …",   // HTML 을 푼 평문. 내용이 없으면 null
  "decoded_count": 5,                        // attachments 중 텍스트가 나온 수
  "attachments": [{
    "position": 0,
    "kind": "공고문",                         // 공고문 | 기타
    "filename": "26년도 할인지원사업 모집공고 포스터.png",
    "ext": "png",                            // 파일명 기준
    "url": "https://…",

    "fetch_status": "ok",                    // null = 아직 안 받아 봤다
    "parse_status": "unsupported",           // null = 아직 안 읽어 봤다
    "text_chars": null,
    "detected_ext": "png"                    // 내용 기준. ext 와 다를 수 있다 — 3,354건 중 7건
  }]
}
```

### `summary` 정리

기업마당 `bsnsSumryCn` 은 **HTML 통째**로 온다(`<p>`, `<br>`, `style=`, `&nbsp;`). `api/text.py` 가 태그를 지우고 엔티티를 풀고 문단을 줄바꿈으로 바꾼다. **원문은 DB 에 그대로 있고 읽을 때만 편다.**

내용이 없으면 빈 문자열이 아니라 `null` 이다. 화면이 빈 문단을 그리지 않아야 한다.

### 첨부 상태를 둘로 나눠 주는 이유

`fetch_status` 는 받아 왔는가, `parse_status` 는 읽혔는가다. **못 읽은 것을 안 읽은 척하지 않는다.**

| `parse_status` | 뜻 |
|---|---|
| `ok` | 텍스트가 나왔다 |
| `empty` | 파서는 돌았는데 0바이트다 — 스캔본 |
| `unsupported` | 지원 목록에 없는 포맷. **시도하지 않았다** |
| `failed` | 시도했고 실패했다 |
| `container` | ZIP. 안의 목록만 읽었다 |
| `null` | 아직 안 해봤다 |

`unsupported` 와 `failed` 와 `null` 을 화면에서 한 덩어리로 뭉개지 않는다. 셋을 가른 것이 [T-0004](plan/07-첨부-내려받기와-해독.md#t-0004-지원-포맷-목록-정의)의 존재 이유다.

---

## 운영 경로 — `/api/admin/*`

> 정본은 `src/finnect/api/admin_schemas.py`. 결정은 [ADR-0027](adr/0027-운영-화면을-nextjs로-옮긴다.md).

`web/app/admin/` 이 부른다. **제품 경로와 목적이 반대다.**

| | 제품 (`/api/notices`) | 운영 (`/api/admin/notices`) |
|---|---|---|
| 무엇을 내는가 | 사용자가 볼 값만 **고른다** | 출처가 준 컬럼을 **하나도 안 고른다** |
| 마감된 공고 | 기본으로 뺀다(`open_only`) | **안 뺀다.** 31,327건이 모집단 |
| 한 페이지 | 20건 | 50건 |
| 정렬 | 마감순 하나(ADR-0024) | 셋 — 마감 임박 · 최근 수집 · 이름 |
| 어디서 읽는가 | `notice` 뷰 | **출처별 표에서 직접.** 뷰를 안 거친다 |

접두사를 가른 것은 그래서다. 한 이름 아래 섞이면 어느 쪽 계약인지 알 수 없다.

| 경로 | 무엇 |
|---|---|
| `GET /api/admin/notices` | 목록. `source` · `q` · `sort` · `page` |
| `GET /api/admin/notices/{source}/{external_id}` | 상세. 컬럼 전부 + 설명 + 첨부 + 원문 응답 |
| `GET /api/admin/attachments` | 해독 현황 집계와 OCR 후보 |
| `GET /api/admin/ingest` | 수집 실행 기록과 출처별 저장 건수 |

### 운영 상세가 더 주는 것

- **`api_fields` 와 `ours` 를 가른다.** 출처가 준 컬럼(기업마당 22 · K-Startup 30)과 우리가 붙인 컬럼이다
- **`description` 은 공식 문서에서만 온다.** `null` 이면 문서에 없다는 뜻이고 화면이 "문서에 없음"으로 적는다. 이름으로 추측해 채우지 않는다
- **`extra` 가 비어 있지 않으면 API 가 늘어났다는 뜻이다.** 조용히 버리지 않는다
- **`raw`** — 응답 원문. `envelope`(공고 배열 뺀 나머지)과 `item`(이 공고)을 갈라 준다. 기업마당 응답 하나가 1,538건 · 3.67MB 라 통째로는 못 쓴다. **인증키는 저장 전에 마스킹된다**(`ingest/base.py` `mask()`)

### 여기 없는 것 — 수집 실행

`POST` 가 없다. 수집은 응답보다 오래 사는 데몬 스레드이고 진행률은 그 프로세스 안에서만 산다. 로컬 `:8000` 에 남았다.

```bash
uv run uvicorn finnect.admin.app:app --reload    # :8000 /ingest — 버튼과 진행률
```

**`/api/admin/ingest` 는 기록만 읽는다.** `running`·`progress` 필드가 없는 것이 그 뜻이다. 없는 것을 있는 척하지 않는다.

---

## 아직 없는 것

화면에 자리는 있지만 API 가 못 주는 값들이다. **`null` 로도 안 준다 — 필드 자체가 없다.**

| 무엇 | 없는 이유 |
|---|---|
| 적합도와 순서 | F3-2 없음. 위키가 있어야 판단한다 |
| 왜 맞는지 | F1 사업 위키 없음 |
| 자격 충족 여부 | 프로필 없음 |
| 심사 항목 · 놓치기 쉬운 것 | F2-3 추출 안 함. **첨부 텍스트는 있다** |
| 지원 형태 · 금액 | **두 API 모두 안 준다.** 공고문에서 뽑아야 한다 |
| ★ 저장 · 신청 상태 | 저장 개념 없음 |

화면은 이 자리를 비워 두고 **"아직 없어요"로 버틴다**([plan/09](plan/09-사용자-앱-분리.md)). 예시 데이터를 넣지 않는다.

---

## 안 정한 것

**인증이 없다.** 계정과 로그인은 `SPEC.md` §6 범위 밖이고 지금 API 에 사용자 개념이 없다.

**CORS 는 로컬 고정이다.** `localhost:3000` 만 열려 있다. 원격 배포를 정할 때 다시 본다([ADR-0023](adr/0023-제품-프론트를-nextjs로-분리한다.md) "안 정한 것").

**쓰기가 없다.** 전부 `GET` 이다.
