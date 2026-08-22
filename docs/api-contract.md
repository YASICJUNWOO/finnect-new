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

## `GET /api/companies/{company_id}/recommendations`

**추천 세 건.** `DESIGN.md` §6.1 의 두 섹션 중 위쪽이고, 아래쪽(전체 공고 · 마감 임박순)은 `GET /api/notices` 가 그대로 낸다. 경로를 나눈 이유는 **위키가 없어도 그쪽이 떠야** 하기 때문이다.

계획은 [plan/17](plan/17-맞는-공고를-고른다.md), 결정은 [ADR-0013](adr/0013-판정-두-층.md) 이다.

### 응답

```json
{
  "items": [
    {
      "source": "bizinfo",
      "external_id": "PBLN_000000000125473",
      "title": "…",
      "apply_end": "2026-09-30",
      "days_left": 41,
      "reason": "소상공인·판로가 주제예요. 바코드와 QR로 입출고 기록을 자동으로 남겨…",
      "evidence_count": 2
    }
  ],
  "computed": true
}
```

`NoticeOut` 의 필드 전부에 둘이 붙는다.

| 필드 | 무엇 |
|---|---|
| `reason` | 왜 맞는지 한 줄. **템플릿이 만든다** — LLM 이 아니다 |
| `evidence_count` | 이 이유가 위키의 몇 개 사실에서 나왔나. 화면이 "근거 2" 로 쓴다 |
| `computed` | 판정을 돌렸나. **빈 목록과 다르다** |

### 적합도 숫자가 없다

`verdict` · `matched` · `sector_hit` 가 응답에 **없다.** 목록이 이미 적합도순이라 순서가 정보를 담고, 92 와 74 의 차이를 설명할 눈금이 없다(`DESIGN.md` §6). `tests/test_api_recommendations.py` 가 응답 JSON 에 그 이름들이 없는지 검사한다.

### `computed` 가 왜 따로 있는가

```
{"items": [], "computed": false}   아직 판정을 안 돌렸다
{"items": [], "computed": true}    돌렸는데 맞는 것이 없다
```

**404 를 내지 않는다.** 화면이 "파일을 올리면 맞는 공고를 골라 드려요"(빈 화면)와 "맞는 것이 없어요"를 다르게 말해야 하고, 그 둘은 다음 동작이 다르다(`DESIGN.md` §7-5).

### 세 건까지다

`SPEC.md` F4-1 — *"적합도순 **3건.** 전체를 늘어놓지 않는다."* 상한은 `api/service.TOP_N` 에 있다.

### LLM 을 부르지 않는다

`notice_fit` 을 **읽기만 한다.** 판정은 `uv run python -m finnect.match --company <id>` 가 미리 돌린다 — 화면 요청 경로에서 모델을 부르지 않는 것(F6-1 과 같은 원칙)이고, 페이지 열 때마다 열린 공고 1,790건을 정규식으로 훑지 않는 이유도 그것이다.

그래서 **`api/service.py` 가 `match.service` 를 임포트하지 않는다.** 저쪽이 `llm` 을 끌고 오는데 `requirements.txt` 에 httpx 가 없다 — 임포트하면 로컬은 통과하고 배포본만 죽는다.

### 마감이 지난 것은 낸 뒤에 뺀다

판정은 어제 돌았어도 오늘 마감일 수 있다. 정렬은 `match/rank.py` 와 같은 규칙이다 — **분야 일치 → 겹침 수 → 마감 임박.**

---

## `GET /api/notices/{source}/{external_id}?company={id}`

목록 한 줄에 `summary` 와 `attachments` 가 붙는다. 없으면 **404**. 모르는 출처도 404.

**`company` 는 선택이다**([plan/21](plan/21-동선을-끝까지-잇는다.md) T-0120). 주면 `fit`(왜 맞는지)이 같이 오고, 안 주면 `null` 이라 화면이 그 자리를 안 그린다 — 인증이 없어서 부르는 쪽이 누구인지 말한다.

```jsonc
{
  // … 목록과 같은 필드 전부 …
  "summary": "KOBACO에서는 1998년부터 …",   // HTML 을 푼 평문. 내용이 없으면 null
  "decoded_count": 5,                        // attachments 중 텍스트가 나온 수
  "fit": {                                   // company 를 줬고 판정이 있을 때만. 아니면 null
    "verdict": "애매",                        // 맞다 | 애매. **아니다 는 저장 안 돼서 안 온다**
    "reason": "소상공인 지원이라 …",           // 한 줄. 템플릿이 만든다
    "evidence_count": 2
  },
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

### `fit` 에 자격이 없다

[ADR-0003](adr/0003-판별-비노출.md) 이 **자격 판별을 화면에 노출하지 않기로** 정했다. 못 넘는 공고는 목록에서 빠지는 것으로 이미 답했고, 상세에 요건 대조표를 두면 **우리 일을 사용자에게 떠넘기는 것**이 된다. 그래서 이 객체에 필드가 셋뿐이고 넷째를 더하지 않는다.

**`verdict` 를 화면에 글자로도 안 낸다.** `맞다`·`애매` 를 적으면 그것이 눈금 없는 점수가 된다(`DESIGN.md` §7 · §12.2). 여기 올라온 것 자체가 판정 결과다 — 필드를 주는 이유는 나중에 등급별로 다르게 **거르기** 위해서이지 보여 주기 위해서가 아니다.

**이유가 비면 `fit` 이 통째로 `null` 이다.** `recommendations` 와 같은 조건이다 — CLI 가 셋을 찍는데 상세만 다르게 말하면 안 된다.

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

## `GET /api/notices/{source}/{external_id}/documents`

이 공고에 **무슨 서류를 내야 하고, 그 안에 무엇을 써야 하는가**(plan/11).

```json
{
  "source": "bizinfo",
  "external_id": "PBLN_000000000125496",
  "documents": [
    {
      "id": 1234,
      "title": "붙임 1",
      "kind": "fields",
      "decided_by": "rule/v1",
      "filename": "신청서_….hwp",
      "url": "https://www.bizinfo.go.kr/…",
      "items": [
        {"number": null, "title": "업 체 명", "instruction": null,
         "limit_text": null, "input_kind": "field", "children": []}
      ]
    },
    {
      "id": 4706,
      "title": "서식 3 사업계획서",
      "kind": "narrative",
      "decided_by": "llm/gpt-5.6-luna",
      "filename": "신청서류_….hwp",
      "url": "https://www.bizinfo.go.kr/…",
      "items": [
        {"number": "1", "title": "신청기업 현황", "instruction": null,
         "limit_text": null, "input_kind": "narrative", "children": [
           {"number": "1-1", "title": "일반현황", "instruction": null,
            "limit_text": null, "input_kind": "narrative", "children": []}
         ]}
      ]
    }
  ],
  "submit_hint": [],
  "undecided": 8
}
```

### `items` 는 트리다

**`children` 을 버리면 화면이 틀린 곳에 칸을 만든다.** 쓰는 자리는 **잎**이고 가지는
양식의 묶음이라, `1 신청기업 현황` 의 자식을 안 주면 그것이 잎이 되어 **거기 쓰는 칸이
붙는다** — 그 칸에 쓴 글은 어느 항목의 것도 아니다. 화면이 잎을 세는 곳은
`web/components/FormFill.tsx` 의 `leafKeys` 한 곳이다.

깊이는 실측 3단까지다(plan/11 T-0039). `fields` 는 평평하다 — 라벨이 서로 부모가 아니고,
트리를 만들면 칸 199개짜리 서식이 접힌다.

**항목이 0개인 문서가 있다.** 양식으로는 갈렸는데 목차가 안 나온 것이고(서술형 25건 중
6건 · 2026-08-20), 화면은 그렇게 말한다 — "이 양식에서 항목을 못 뽑았어요".

### `kind` 가 넷인데 둘만 나간다

| 값 | 뜻 | 응답에 나오나 |
|---|---|---|
| `fields` | 칸만 채우는 서식 | **나온다** |
| `narrative` | 글로 쓰는 양식 | 나온다. **2026-08-20 현재 25건** — T-0036 을 예산 안에서 일부만 돌렸다 |
| `none` | 채울 것이 없다 | 안 나온다 |
| `unknown` | 아직 안 갈랐다 | **안 나온다.** `undecided` 로만 센다 |

**`unknown` 을 내보내지 않는 이유가 이 계약의 요점이다.** 서술형 양식과 공고문의 절은
생김새가 같아서 규칙이 네 번 실패했다. 내보내면 화면이 `1. 사업개요 / 2. 신청자격`
(공고문)을 작성 항목으로 보여 준다. **모르는 것을 아는 척하지 않는다.**

`undecided` 는 그 구간이 몇 개인지다. **0 이 아니면 화면이 그렇게 말해야 한다** —
"아직 못 읽은 붙임이 N개 있어요".

### `submit_hint` — 양식이 없을 때만 찬다

`documents` 가 비면 공고문에서 "무슨 서류를 내나" 줄을 최대 넷 건져 준다. **원문 그대로다.**

```
"제출서류는 [신청] 버튼을 클릭하면 국가별 안내사항 확인 가능"
```

층이 둘이라 그렇다. **"무슨 서류를 내나"는 공고문에 있고**, "그 안에 뭘 쓰나"는
양식 파일이 첨부에 있어야 나온다. 양식이 없다고 빈손으로 보내지 않는다(DESIGN.md §7-5).

---

## `GET /api/notices/{source}/{external_id}/draft?company={id}`

이 회사가 이 공고에 대해 쓴 초안([plan/16](plan/16-항목마다-초안을-쓴다.md) · F6).

**읽기만 한다.** 만드는 것은 아래 `POST` 이고, 그쪽이 `finnect.draft` 를 **함수 안에서** 임포트한다([ADR-0054](adr/0054-초안을-만드는-길을-api-에-열고-공고-회사-단위로-잠근다.md) 결정 2) — 최상단에 두면 `llm` 과 `httpx` 가 딸려 와 읽기만 담은 배포본에서 죽는다.

**없으면 빈 목록이고 404 가 아니다.** 아직 안 쓴 것과 쓸 수 없는 것을 화면이 같은 자리에서 말해야 하고, 404 는 원인을 안 남긴다.

```
company_id · source · external_id
pending_documents   서술형 양식은 있는데 초안이 아직 없는 수
documents[]
  document_id · title · filename
  allotted_by       llm/<모델> · none(다툰 것이 없어 안 불렀다)
  items[]           **트리다.** children 으로 접혀 있다
    document_item_id · number · title · instruction
    status          아래 표
    paragraphs[]    ordinal · text · evidence[]
      evidence[]    fact_id · place · place_label · text · chunk_id · quote · source_type
                    **fact_id 가 음수면 매칭 정보다**(트랙 B · plan/22 T-0134).
                    양수는 wiki_fact.id · 음수는 -company_value.id 이고
                    place 도 노드 경로 대신 key 열넷 중 하나가 온다
    missing[]       place · place_label · required
    missing_optional[]
    length          verdict · limit_text · measured · note
    yielded_to[]    그 재료를 맡은 항목 번호들
    error           이 항목만 실패했다
    edited              사람이 고쳤다. **status 와 다른 축이다**(ADR-0055)
    evidence_detached   고쳐서 문단↔근거 대응이 깨졌다. **행은 DB 에 그대로 있다**
    original            집필기가 쓴 글. **고쳤을 때만 찬다** — 되돌릴 자리
running             지금 쓰고 있다. 빈 목록이 「안 눌렀다」인지 「기다리는 중」인지 가른다
```

### `status` 가 여섯이고 **물어볼 자리는 하나다**

| 값 | 뜻 | 화면이 할 일 |
|---|---|---|
| `drafted` | 문서 근거로 썼다 | 본문 + 문단별 근거 |
| `answered` | 사용자 답변이 들어간 문단이 있다 | 근거 줄에서 **글자로** 가른다. 색을 새로 주지 않는다 |
| `blank` | **위키에 없어서 못 썼다** | **여기만 묻는다.** `missing[]` 이 무엇을 물을지 말한다 (F6-6) |
| `no_needs` | 쓸 자리가 아니다 — 상위 묶음이거나 사업 내용을 안 쓰는 자리 | 제목만. **초안 자리로 그리지 않는다** |
| `yielded` | 위키에는 있는데 **다른 항목이 그 재료를 맡았다** | `yielded_to` 로 **"그 얘기는 6번에 썼어요"** |
| `unwritten` | 재료는 받았는데 글이 안 나왔다 | **집필 실패다.** 다시 쓰기를 권한다 |
| `stale` | 근거가 된 사실이 바뀌었다 | 낡았다고 표시만. **자동으로 안 고친다**(F1-5-5) |

**여섯을 섞으면 화면이 사용자에게 이미 아는 것을 묻는다.** 실측에서 항목 16개 중 `못 채움` 이 7개로 보였는데, 갈라 보니 상위 묶음 3 · 배분에서 못 받음 4 였고 **진짜 물어볼 자리는 0개**였다.

### `place_label` 을 API 가 붙이는 이유

`place` 는 `problem` 같은 영문 키다. 사람이 읽는 이름은 `wiki/topics.py` 가 정본이고, **화면이 한국어를 지으면 갈린다** — `topics.display()` 가 단위를 한 자리에서 붙이는 것과 같은 규율이다.

### `length` 를 저장하지 않는다

`limit_text` 는 `document_item` 에, 본문은 `draft_item` 에 있다. 둘로 계산되는 값이라 읽을 때마다 만드는 **뷰**다 — 위키 마크다운과 같은 이유다.

**`verdict` 가 `unmeasurable` 인 경우가 둘이다.** 쪽 수 제한(`50페이지 내외`)은 글자로 환산하지 않고, `내외` 는 초과 판정을 안 한다. 환산율의 근거가 없다 — **틀린 숫자를 내는 것보다 못 잰다고 말하는 것이 낫다.**

### `yielded_to` 를 저장하지 않는다

`draft.allotment` 와 `item_need` 로 계산된다. 못 받은 항목의 배분은 비어 있으니 **이 항목이 원했던 자리에서 출발해 그 자리의 사실을 누가 받았는지 거꾸로 찾는다.**


## `POST /api/notices/{source}/{external_id}/draft?company={id}`

초안을 쓰기 시작한다([plan/21](plan/21-동선을-끝까지-잇는다.md) T-0121 · [ADR-0054](adr/0054-초안을-만드는-길을-api-에-열고-공고-회사-단위로-잠근다.md)). **202 다.**

```jsonc
{
  "started": true,     // 거절이면 false. **오류가 아니다**
  "reason": "",        // 못 시작한 이유. 시작했으면 빈 문자열
  "draft": { … }       // 위 GET 과 같은 모양. 누른 직후를 화면이 그대로 그린다
}
```

**거절도 202 다.** 409 로 올리면 화면이 오류 상태를 그리는데, 두 번 누른 사람에게 보여 줄 것은 오류가 아니라 **지금 돌고 있다는 사실**이다.

**락이 `(회사, 공고)` 다.** 위키 빌드는 회사 단위로 잠그는데(사실이 회사 하나의 표에 병합된다) 여기는 `draft` 유니크 키가 `(회사, 공고, 문서)` 라 **같은 회사가 공고 둘을 같이 쓰는 것을 막을 이유가 없다.**

**503 을 안 낸다.** 올리기의 503([ADR-0034](adr/0034-업로드를-같은-api-에-두고-못-쓰는-곳에서는-503-으로-답한다.md))은 로컬 디스크가 없어서였고, 초안은 디스크를 안 쓰고 DB 와 LLM 만 쓴다. 키가 없으면 `started: false` 에 그 이유가 실린다 — **조용히 빈 초안을 만들지 않는다.**

**진행을 볼 별도 경로가 없다.** 올리기와 다르다 — 저쪽은 파일마다 단계 다섯이 있어 진행이 응답 하나를 채우지만, 초안은 항목이 다 써진 뒤에야 볼 것이 생긴다. `GET …/draft` 의 `running` 한 값이면 「쓰는 중」과 「다 썼다」가 갈린다.

---

## `PUT /api/notices/{source}/{external_id}/draft/items/{document_item_id}?company={id}`

사람이 고친 글을 저장한다([plan/21](plan/21-동선을-끝까지-잇는다.md) T-0123 · [ADR-0055](adr/0055-사람이-고친-글을-집필-출력-위에-덮지-않는다.md)). 응답은 그 항목 하나(`items[]` 의 한 원소)다.

```jsonc
{ "text": "고쳐 쓴 글" }   // 문단은 \n\n 으로 가른다
{ "text": null }           // **되돌리기.** 집필기의 글이 다시 보인다
{ "text": "" }             // **일부러 비운 것.** 되돌리기가 아니다
```

**`body` 를 안 덮는다.** 집필기의 출력은 그대로 두고 `edited_body` 에 얹는다 — 되돌릴 자리가 남아야 하고, `draft_evidence` 의 문단 번호가 사람 편집을 따라 어긋나면 안 된다.

**`null` 과 `""` 를 뭉개지 않는다.** 섞으면 지운 항목에 초안이 다시 나타난다.

**`status` 가 안 바뀐다.** 저 표는 집필이 어떻게 됐나를 말한다 — `blank` 였던 자리가 사람 편집으로 `drafted` 가 되면 **물어볼 목록에서 조용히 빠진다**(F6-6).

**404 를 낸다.** 조회와 반대다 — 없는 항목에 쓰라는 요청이라 원인이 요청 쪽에 있다. 다른 회사의 항목도 404 다.

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

## `GET /api/wiki/{company_id}`

사업 위키 한 장(S7). **정본은 [`api/wiki_schemas.py`](../src/finnect/api/wiki_schemas.py) 다.**

**위키가 없어도 200 이고 자리 마흔일곱이 온다**([ADR-0052](adr/0052-위키-자리를-기획-트리로-바꾸고-구획을-폴더로-세운다.md)). 404 나 빈 목록으로 답하면 화면이 "데이터 없음"으로 끝난다 — `DESIGN.md` §7-5 가 빈 화면에 첫 동작을 안내하라고 한 자리다. 자리가 있어야 사용자가 무엇이 없는지 안다.

```json
{
  "company_id": "c_dasiro",
  "nodes": [
    {
      "path": "Financial/자금계획.md", "title": "자금 계획", "folder": "Financial",
      "eligibility": false,
      "values": [
        {
          "slot": "funding", "label": "조달액",
          "value": "300000000", "display": "300,000,000원",
          "qualifier": "시드", "as_of": "2025-09-30", "status": "conflict",
          "evidence": [
            {"filename": "재무제표_2025.xlsx", "page": null,
             "quote": "자본잉여금 3억원은 2025.09 시드 라운드 유치액입니다"}
          ]
        }
      ],
      "statements": [
        {"text": "2025년말 현금 1억 8,270만원…", "topic": "cost",
         "evidence": [{"filename": "피치덱_2026H2.pptx", "page": 11, "quote": "…"}]}
      ],
      "groups": [
        {"topic": "cost", "label": "비용 구조",
         "statements": [{"text": "2025년말 현금 1억 8,270만원…", "topic": "cost", "evidence": [{"…": "…"}]}]},
        {"topic": "funding", "label": "자금 조달", "statements": []}
      ],
      "grouped": true,
      "source_count": 4, "filled": true, "conflicted": true,
      "ours": false, "gap": "", "collapsed": null,
      "grade": "1차",
      "source": ["재무제표_2025.xlsx", "피치덱_2026H2.pptx"],
      "source_path": ["c_dasiro/9e/9eaf74…", "c_dasiro/e8/e843d0…"],
      "base_date": "2025-09-30", "updated_at": "2026-08-22",
      "markdown": "---\npath: Financial/자금계획.md\n…"
    }
  ],
  "files": [
    {"filename": "재무제표_2025.xlsx", "ext": "xlsx", "byte_size": 10700,
     "status": "done", "parse_status": "ok", "parser": "xlsx/openpyxl",
     "parse_error": null, "chunk_count": 4, "page_count": null,
     "nodes": ["Company/회사소개.md", "Financial/자금계획.md", "Financial/매출.md"]}
  ],
  "categories": {"Company": "회사", "Product": "제품", "…": "…"},
  "filled": 20, "total": 47, "conflicts": 2, "uncategorized": 1,
  "extractor": "stub/v1"
}
```

| 필드 | 뜻 |
|---|---|
| `nodes` | **노드 전부.** 순서가 기획 문서 §2 의 순서이고 곧 배치 순서다 — 프론트가 이 순서로 각도를 나눈다 |
| `path` | **자리의 이름이다**(기획 §4-3 「경로가 곧 노드 제목이다」). 화면·기획 문서·집필 에이전트가 같은 문자열을 쓴다 |
| `folder` | 최상위 폴더 키 = **각도 구획**. 라벨은 `folders` 가 준다. `sector` 여섯을 대신한다([ADR-0052](adr/0052-위키-자리를-기획-트리로-바꾸고-구획을-폴더로-세운다.md)) |
| `gap` | 채울 topic 이 **아예 없는** 자리의 사유. 있으면 파일을 더 올려도 안 찬다 — 「아직 비었다」와 다른 말이다 |
| `collapsed` | 접혔으면 원래 경로. **조용히 접지 않는다** — `Competitor/{업체명}.md` |
| `grade` | 자료 등급. **`실측`·`1차`·`미정` 셋만 온다** — `2차`·`가정` 은 추출기가 출처를 판정하지 않아 못 낸다([ADR-0052](adr/0052-위키-자리를-기획-트리로-바꾸고-구획을-폴더로-세운다.md) 결정 4) |
| `source` / `source_path` | 근거 파일 이름과 저장 위치. **순서가 같다** — 짝이 어긋나면 위치가 거짓말이 된다 |
| `updated_at` | 사실이 바뀐 시각. **만든 시각이 아니다** — 같은 DB 면 같은 값이라 두 응답을 바이트로 비교할 수 있다 |
| `value` / `display` | 저장값과 표시값. **둘 다 준다** — 프론트가 단위를 붙이면 규칙이 두 벌이 되고 갈린다 |
| `status` | `current` 지금 값 · `superseded` 더 늦은 값이 있다 · `conflict` 값이 갈렸다. **셋 다 화면에 남는다** — 지우지 않는다(F1-1-7) |
| `evidence` | **출처는 문자열이 아니라 연결이다**(SPEC F1-3). `filename` 과 `page` 를 따로 주는 것은 화면이 "3쪽"을 다르게 쓸 수 있어서다 |
| `page` | PDF · PPTX 만 찬다. **다른 포맷에는 쪽이라는 것이 없다** |
| `groups` | `statements` 를 **event topic 별로 묶은 것**([ADR-0048](adr/0048-노드-층을-없애고-topic-을-orbit-에-직접-매단다.md)). 순서는 서버의 표(`export.TREE`)가 정하고 **빈 것도 온다** — 화면이 "무엇이 없는지"를 말할 수 있어야 한다 |
| `groups[].label` | topic 한국어 이름. **화면이 한국어를 짓지 않는다** — `display` 와 같은 규율이다 |
| `grouped` | 절 제목을 보일 자리인가. **event topic 이 둘 이상인 자리만 `true`** 다. `false` 면 화면이 `statements` 를 통째로 뿌린다. **판정을 서버가 하는 이유는 규칙을 두 곳에 적지 않으려는 것이다** |
| `source_count` | 근거로 쓰인 **파일 수**. 근거 개수가 아니다 |
| `markdown` | 그 자리 한 장. **저장된 것이 아니라 매번 만든 것이다** |
| `files[].spots` | 그 파일이 근거가 된 자리들의 **경로**(F1-4-7). **어느 파일을 지우면 무엇이 사라지는지** |
| `extractor` | 무엇이 사실을 뽑았나. `stub/v1` 이면 픽스처 밖에서는 안 돈 것이다([ADR-0031](adr/0031-사실-추출을-포트-뒤로-미루고-스텁으로-배관을-먼저-세운다.md)). **화면이 이걸 숨기지 않는다** |

**`statements` 와 `groups` 가 같은 것을 두 번 준다.** `groups` 는 묶기만 한 것이고 사실은 같다 — 프론트가 묶는 규칙을 다시 구현하지 않게 하려고 서버가 두 모양을 다 준다.

**`confidence` 가 없다.** 구상도는 사실마다 0.9 를 붙이는데 0.9 와 0.7 을 가를 눈금이 없다. 대신 근거 유무 · `status` · `source_count` 셋으로 말한다.

**`company_id` 를 경로로 받는다.** 인증이 아직 없어서 세션에서 꺼낼 자리가 없다 — 지금은 부르는 쪽이 누구인지 말한다. **격리가 이 인자 하나에 걸려 있고, 이 API 는 누구의 위키든 열어 준다.**

---

## `GET /api/wiki/{company_id}/markdown`

위키 전부를 마크다운 한 덩어리로. `text/markdown; charset=utf-8` 이다.

**저장된 파일을 읽는 것이 아니라 매번 만든다.** 마크다운은 저장소가 아니라 뷰다([plan/12](plan/12-사업-위키-구축.md) `구상도와의 차이`) — 사실이 `wiki_fact` 에 있는데 같은 내용을 마크다운으로도 들고 있으면 둘 중 하나가 먼저 낡는다.

**아직 아무것도 없으면 404 다.** 빈 문서를 내려 주면 화면이 빈 `<pre>` 를 그린다. 위와 반대인 이유는 여기는 자리가 없기 때문이다 — 그래프는 빈 자리도 뜻이 있고 마크다운은 그렇지 않다.

노드마다 `.md` 파일로 떨어뜨리는 것(F1-6 밖으로 꺼내기)은 아직 없다.

---

## `POST /api/wiki/{company_id}/files`

파일을 통째로 받는다(SPEC F1-1-1). `multipart/form-data` 이고 필드 이름은 `files` 다. 여러 개를 한 번에 보낸다.

**`202` 다. 저장까지만 하고 답한다.** 해독과 구축은 응답을 보낸 뒤 서버 스레드가 하고, 화면은 아래 `progress` 로 따라온다. 붙여 두면 OCR 이 걸린 파일 하나에 요청이 몇 분씩 묶인다.

**분류해서 올리라고 요구하지 않는다.** 못 읽는 포맷도 받아서 상태로 남긴다 — 거절하면 사용자는 그 파일이 왜 안 쓰이는지 영영 모른다.

| 거절하는 것 | 언제 |
|---|---|
| 빈 파일 | 0바이트 |
| 크기 초과 | `USER_FILE_MAX_MB`(기본 50MB) |

```jsonc
{
  "received": 7,          // 이번에 새로 받은 것
  "duplicate": 0,         // 이미 있어서 안 받은 것. **회사 안에서만 본다** (ADR-0029)
  "rejected": [],         // [파일명, 사유]. 저장조차 못 한 것
  "started": true,        // 뒤에서 구축을 시작했나. 이미 돌고 있었으면 false
  "reason": "",           // 시작 못 했으면 왜인지
  "progress": { … }       // 아래와 같은 모양
}
```

### 파일을 못 쓰는 서버에서는 503 이다

경로는 어디에나 있고, 쓸 수 없는 곳에서 부르면 `{"detail": "이 서버는 파일을 못 받아요…"}` 가 온다([ADR-0034](adr/0034-업로드를-같은-api-에-두고-못-쓰는-곳에서는-503-으로-답한다.md)). **경로를 지우면 404 가 돌아오는데 "없는 주소"와 "여기서는 못 하는 일"은 사용자가 할 일이 다르다.**

**지금은 안 걸린다.** [ADR-0035](adr/0035-api와-워커를-자체-서버로-내리고-vercel은-화면만-맡는다.md)가 API 를 Vercel 에서 자체 서버로 내렸고 거기서는 `data/user-files/` 에 쓸 수 있다. 가드가 남아 있는 것은 서버리스로 되돌아가거나 디스크가 찰 때를 위해서다.

---

## `GET /api/wiki/{company_id}/progress`

구축이 어디까지 왔나(SPEC F1-1-9). **파일별로 따로 말한다**(F1-1-8) — 다섯 중 하나가 실패해도 넷으로 위키가 서기 때문에 진행률 하나로 뭉치면 그 사실이 사라진다.

**아무것도 안 올렸어도 200 이고 단계 다섯이 온다.** 처음 온 사람도 무엇이 일어날지 먼저 볼 수 있어야 한다(`DESIGN.md` §7-5). 위키 조회가 빈 자리를 돌려주는 것과 같은 이유다.

```jsonc
{
  "company_id": "c_dasiro",
  // 단계 다섯. **순서가 곧 진행 순서다.** 이름을 프론트가 짓지 않는다
  "steps": [{"key": "receive", "label": "파일 받기"}, … ],
  // 자리 경로 → 제목. `files[].spots` 가 경로라서 이게 없으면 화면에 경로가 그대로 뜬다.
  // **S7 과 같은 표다** — 두 화면이 같은 자리를 다르게 부르면 안 된다(ADR-0052)
  "spot_titles": {"Company/회사소개.md": "회사 소개", "Company/팀.md": "팀", … },
  "files": [{
    "filename": "사업자등록증_스캔.pdf",
    "ext": "pdf",
    "byte_size": 103867,
    "status": "done",        // DB 의 원래 상태. `uploaded` · `parsing` · `chunked` · … 여덟 가지
    "reached": 5,            // 끝낸 칸 수. **백분율이 아니다**
    "label": "다 됐어요",     // 사람이 읽는 한 마디
    "moving": false,         // 아직 움직이나
    "ok": true,              // 끝났고 성공인가. 움직이는 중이면 항상 false — **아직 모른다**
    "detail": null,          // 왜 못 했나. **해독 실패(`parse_error`) 또는 추출 실패(`extract_error`)** 가 남긴 말
    "chunk_count": 1,
    "page_count": 1,
    "text_chars": 281,       // 해독 글자 수. **0 이면 스캔본이다**
    "parser": "ocr/rapidocr-v5-server",   // **`ocr/` 로 시작하면 사진에서 읽은 것이다**
    "fact_count": 7,         // 이 파일이 근거가 된 사실 수. **파일 사이에 겹친다**
    "nodes": ["Company/회사소개.md", "Company/비전.md", "Company/팀.md"]   // 이 파일이 채운 자리
  }],
  "total": 7, "done": 7, "moving": 0, "needs_review": 0, "stuck": 0,
  "running": false,          // **화면이 계속 물어볼지를 이 값으로 정한다**
  "filled": 15, "slots": 15, "conflicts": 2,
  "extractor": "stub/v1"
}
```

### `running` 이 왜 따로 있는가

**`chunked` 하나가 두 가지 뜻을 갖는다.** 파일을 막 넣었을 때는 "사실을 뽑을 차례"이고, 빌드가 끝난 뒤에도 `chunked` 면 "추출기가 몰라서 되돌려놨다"다(`wiki/build.py` `_shelve`). 행만 봐서는 구분이 안 된다.

그래서 상태를 단계로 옮길 때 이 값을 같이 본다(`wiki/progress.py`). 없으면 화면이 `chunked` 에서 **영원히 물어본다.**

값은 DB 가 아니라 `ingest/jobs.py` 의 락에서 온다. 컬럼을 만들면 배포 DB 에도 마이그레이션을 돌려야 하고, 이건 프로세스가 죽으면 같이 죽는 게 맞는 종류다.

### `needs_review` 와 `stuck` 을 갈라 세는 이유

**사용자가 할 일이 다르다.** 글자가 안 나온 것(`needs_review`)은 스캔본이라 OCR 이 붙으면 읽히고, 못 읽은 것(`stuck`)은 포맷이 없거나 추출기가 모르는 것이다. 넷을 더하면 `total` 이 된다 — 겹치지도 새지도 않는다.

### 칸마다 무엇이 나왔나

화면이 칸 다섯을 펼치고 **그 칸이 낸 것을 옆에 적는다**(plan/15 T-0062). 점 다섯만 있을 때는 `●●●✕○` 를 보고 **몇 번째 칸이 멈춘 것인지 세어야 했다.**

| 칸 | 무엇으로 말하나 |
|---|---|
| 파일 받기 | `byte_size` |
| 글자 읽기 | `page_count`(PDF·PPTX 만) · `text_chars` · `parser` 가 `ocr/` 로 시작하면 "사진에서 읽었어요" |
| 조각 내기 | `chunk_count` |
| 사실 뽑기 | `fact_count` |
| 자리에 놓기 | `spots` |

**끝났거나 멈춘 칸만 숫자를 갖는다.** 도는 칸에 `0` 을 쓰면 "세어 봤더니 없다"로 읽히는데 실제로는 "아직 안 셌다"다. 실제로 `chunk_count` 는 실패한 파일에도 `0` 이 적혀 있다.

**`parser` 의 구현 이름은 화면에 안 나온다.** `pdf/plumber` 는 우리 사정이고 사용자가 조작하는 대상이 아니다(`DESIGN.md` §8.3-1). 화면이 보는 것은 `ocr/` 접두사 하나뿐이고, 사진에서 읽은 글자는 굵은 제목이 깨져서(ADR-0030) 위키 값이 이상할 때 사용자가 이유를 알아야 한다.

**`fact_count` 를 다 더해도 위키의 사실 수가 아니다.** 병합된 사실은 근거가 여럿이라 두 파일에서 각각 한 번 세어진다. 이 값이 답하는 질문은 "이 파일이 몇 개의 사실에 근거를 댔나"다.

**칸별 시각은 없다.** `uploaded_at` 과 `parsed_at` 둘뿐이다. 조각·사실·자리의 시각을 말하려면 컬럼을 세 개 만들어야 하고 그러면 배포 DB 에도 마이그레이션이 붙는다 — 화면이 소요 시간을 안 쓰는 이유다.


---

## 아직 없는 것

화면에 자리는 있지만 API 가 못 주는 값들이다. **`null` 로도 안 준다 — 필드 자체가 없다.**

| 무엇 | 없는 이유 |
|---|---|
| ~~적합도와 순서~~ | **찼다** (2026-08-21 · [plan/17](plan/17-맞는-공고를-고른다.md)). `/api/companies/{id}/recommendations` |
| ~~왜 맞는지~~ | **찼다** (2026-08-22 · [plan/21](plan/21-동선을-끝까지-잇는다.md) T-0120). 상세의 `fit` |
| ~~자격 충족 여부~~ | **안 만든다.** [ADR-0003](adr/0003-판별-비노출.md) 이 그 화면을 금지했다 — 못 넘는 공고는 목록에서 빠지는 것으로 이미 답했다. **기다리던 것이 사실은 만들면 안 되는 것이었다** |
| 심사 항목 · 놓치기 쉬운 것 | F2-3 추출 안 함. **첨부 텍스트는 있다** |
| 지원 형태 · 금액 | **두 API 모두 안 준다.** 공고문에서 뽑아야 한다 |
| ★ 저장 · 신청 상태 | 저장 개념 없음 |

화면은 이 자리를 비워 두고 **"아직 없어요"로 버틴다**([plan/09](plan/09-사용자-앱-분리.md)). 예시 데이터를 넣지 않는다.

---

## 안 정한 것

**인증이 없다.** 계정과 로그인은 `SPEC.md` §6 범위 밖이고 지금 API 에 사용자 개념이 없다.

**CORS 는 로컬 고정이다.** `localhost:3000` 만 열려 있다. 원격 배포를 정할 때 다시 본다([ADR-0023](adr/0023-제품-프론트를-nextjs로-분리한다.md) "안 정한 것").

~~**쓰기가 없다.** 전부 `GET` 이다.~~ ~~**2026-08-18 올리기 하나가 붙었다.**~~ **2026-08-22 셋이 됐다**([plan/21](plan/21-동선을-끝까지-잇는다.md)).

| 쓰기 | 무엇 | 근거 |
|---|---|---|
| `POST /api/wiki/{company_id}/files` | 파일 올리기 | [ADR-0034](adr/0034-업로드를-같은-api-에-두고-못-쓰는-곳에서는-503-으로-답한다.md). **못 쓰는 서버에서 503 이다** |
| `POST …/draft` | 초안 만들기 | [ADR-0054](adr/0054-초안을-만드는-길을-api-에-열고-공고-회사-단위로-잠근다.md) |
| `PUT …/draft/items/{id}` | 초안 고치기 | [ADR-0055](adr/0055-사람이-고친-글을-집필-출력-위에-덮지-않는다.md) |

**나머지는 그대로 전부 `GET` 이다.** `tests/test_draft_start.py` 가 이 셋뿐임을 잠가 둔다 — 늘어나면 거기가 먼저 깨지고, **그때 이 표를 같은 커밋에 고친다.**
