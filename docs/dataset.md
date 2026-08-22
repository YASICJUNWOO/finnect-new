# 데이터셋 — 공고 코퍼스를 초기화하고 다시 채운다

개발용으로 코퍼스를 작게 다시 세우는 절차다. 「공고 초기화하고 다시 채워」가 뜻하는 것이
여기 적힌 일곱 단계다.

> **읽는 순서.** 이 문서는 실행 절차이고, 왜 그렇게 자르는지는 [`notice-filter/README.md`](../notice-filter/README.md),
> 판정 두 층의 근거는 [ADR-0013](adr/0013-판정-두-층.md) 에 있다. 배포 DB 에는 이 절차를 쓰지 않는다.

## 0. 먼저 — 기업마당은 되돌릴 수 없다

**기업마당 공고는 마감되면 API 에서 사라지고 재수집으로 복구되지 않는다.** 08-16 스냅샷
1,538건 대 08-18 라이브 1,524건, 이틀에 14건이 소멸했고 그중 `125201` 하남 이루다+ 는
원문까지 읽어 둔 건이었다([근거](../notice-filter/로직과근거.md) §12).

**우리 DB 가 유일한 사본이다.** 그래서 1단계가 백업이고, 백업 없는 `--purge` 는 삭제가
아니라 소실이다. `--yes` 를 안 붙이면 세기만 하는 것도 같은 이유다.

K-Startup 은 그렇지 않다 — 마감돼도 목록 API 에 남아서 언제든 다시 받는다.

## 절차

### 1. 뜬다

```bash
uv run python -m finnect.dataset --dump out/공고-백업.jsonl
```

공고 2표 + 첨부 2표를 JSON Lines 로 쓴다. 되돌리는 것은 `--restore` 다.

```bash
uv run python -m finnect.dataset --restore out/공고-백업.jsonl   # 대상 표를 비우고 다시 넣는다
```

### 2. 지운다

```bash
uv run python -m finnect.dataset --purge          # 지울 것을 센다. 안 지운다
uv run python -m finnect.dataset --purge --yes    # 지운다
```

공고 2표 · `attachment` · `attachment_file` · `notice_profile` · `notice_fit` 과
**첨부 원본 디렉터리를 통째로** 비운다.

**디렉터리를 통째로 지우는 것이 요점이다.** 표를 따라가며 지우면 `attachment_file` 이
0행일 때 파일이 남는다 — 실제로 그 상태가 있었다(2026-08-22 기준 723개 254MB 가
옛 레이아웃 `data/attachments/bizinfo/0/…` 로 남아 있고 어느 행도 그것을 안 가리켰다).
지금 레이아웃은 `data/attachments/<sha256[:2]>/<sha256>` 다([ADR-0022](adr/0022-첨부-원본을-콘텐츠-주소로-로컬에-둔다.md)).

### 3. 받는다 — 전량이다

```bash
uv run python -m finnect.ingest --source bizinfo    # 1,538건 · 요청 1회
uv run python -m finnect.ingest --source kstartup   # 29,789건 · 요청 149회
```

**수집에 필터를 걸지 않는다.** 좁히는 것은 6단계이고, 이 단계는 규칙이 바뀌어도 안 바뀐다.
`--limit` 을 쓰지 않는다 — 잘린 것을 정본으로 삼으면 뒤 단계가 무엇을 못 본 건지 모른다.

### 4. K-Startup 첨부 목록을 긁는다 — **파일은 안 받는다**

```bash
uv run python -m finnect.attach --scrape-kstartup
```

**5단계보다 먼저 와야 한다.** `notice-filter` 축2d′ 가 「계획서로 심사하지 않는 분야」를
배제하되 **계획서 양식이 첨부에 있으면 되살리는데**, 그 판단이 `attachment` 의
`filename` 과 `ext` 만 본다. 첨부 행이 없으면 구제가 한 건도 안 돌아 과배제된다 —
실측으로 K-Startup 50건에서 배제 26건 중 **23건이 축2d′ 사유**였고 첨부는 0개였다.

파일을 받는 것이 아니라 목록만 긁는 것이라 디스크를 안 쓴다.

### 5. 고른다 — 목록 파일을 만든다

기업마당은 API 응답에서 바로 돈다.

```bash
cd notice-filter
python3 run.py --no-serve --ids out/bizinfo-남길.txt        # 1,524 → 580
```

K-Startup 은 우리 DB 를 덤프해서 넣는다. `notice-filter` 는 DB 를 모른다.

```bash
docker exec finnect-db psql -U finnect -d finnect -t -A -c "
SELECT COALESCE(json_agg(json_build_object(
  'notice', json_build_object(
    'pbanc_sn', k.pbanc_sn, 'biz_pbanc_nm', k.biz_pbanc_nm,
    'aply_trgt_ctnt', k.aply_trgt_ctnt, 'supt_biz_clsfc', k.supt_biz_clsfc,
    'biz_enyy', k.biz_enyy, 'pbanc_ctnt', k.pbanc_ctnt,
    'derived_apply_end', k.derived_apply_end),
  'attachments', COALESCE((SELECT json_agg(json_build_object(
      'filename', a.filename, 'ext', a.ext, 'url', a.url))
    FROM attachment a WHERE a.source='kstartup' AND a.external_id=k.pbanc_sn), '[]'::json)
)), '[]'::json) FROM kstartup_notice k;" > out/kstartup-덤프.json

cd notice-filter
python3 kstartup.py --json ../out/kstartup-덤프.json --ids ../out/kstartup-남길.txt   # 29,789 → 15,643
```

### 6. 솎는다 — K-Startup 은 여기서 1/3 이 된다

```bash
uv run python -m finnect.dataset --prune out/bizinfo-남길.txt  --source bizinfo
uv run python -m finnect.dataset --prune out/kstartup-남길.txt --source kstartup --sample 3
```

**`--yes` 를 안 붙이면 세기만 한다.** 숫자를 보고 붙인다.

```bash
uv run python -m finnect.dataset --prune out/bizinfo-남길.txt  --source bizinfo  --yes
uv run python -m finnect.dataset --prune out/kstartup-남길.txt --source kstartup --sample 3 --yes
```

`--source` 가 필수인 이유는 **두 출처의 공고번호가 같은 자릿수**라서다
(`125069` 대 `174036`). 목록 하나로 양쪽을 솎으면 우연히 겹친 번호가 살아남는다.

### 7. 첨부를 받는다 — 남은 것만

```bash
uv run python -m finnect.attach                       # 기업마당
uv run python -m finnect.attach --only 목록.txt --source kstartup
```

K-Startup 전량 첨부는 55.3GB 이고 이 서버 여유가 24GB 다. URL 목록은
`kstartup.py --urls` 가 낸다([README](../notice-filter/README.md) «데모 표본»).

## 멱등하다

**같은 목록으로 몇 번을 솎아도 같은 DB 가 선다.** 표본이 `공고번호 % N == 0` 이고
무작위 시드를 안 쓴다(`dataset/sample.py`). `notice-filter/kstartup.py` 의
`DEMO_MODULUS = 36` 이 같은 원리로 이미 돌고 있다.

**`hash()` 를 쓰지 않는다.** `PYTHONHASHSEED` 가 프로세스마다 달라 실행마다 다른 집합이
나온다 — [plan/12](plan/12-사업-위키-구축.md) T-0094 의 락 키와 똑같은 함정이고,
**둘 다 테스트를 통과한다.** 한 프로세스 안에서는 일관되기 때문이다.

숫자를 먼저 보는 것도 의도다. `174036 % 3 == 0` 은 사람이 눈으로 검산한다 —
해시로만 하면 왜 그 공고가 남았는지 설명할 길이 없어진다.

`--sample` 을 끄는 값은 `None` 이 아니라 **1** 이다. 나머지가 늘 0 이라 전부 남는다.

## 안 건드리는 것

| | 왜 |
|---|---|
| `document` · `document_item` | 키가 `sha256` 라 **콘텐츠 주소**다. 같은 첨부를 다시 받으면 같은 행이 다시 선다 |
| `draft` 계열 | `document` 를 가리킨다. 공고를 지운다고 써 둔 초안을 버릴 이유가 없다 |
| `wiki_*` · `chunk` · `user_file` | 사용자가 올린 파일에서 나온 것이라 공고 코퍼스와 무관하다 |
| `raw_fetch` | 응답 통째. 수집이 무엇을 받았는지의 기록이라 코퍼스를 지웠다고 지우지 않는다 |
| `ingest_run` | 운영 기록이지 코퍼스가 아니다([ADR-0011](adr/0011-수집-실행-화면.md)) |

**`document` 가 남으면 잠깐 뜬 행이 생긴다** — 다시 안 받는 첨부의 `sha256` 을 가리키는
행이다. 읽는 쪽이 `attachment_file` 을 조인하므로 화면에 안 나오지만, 세는 쿼리에는 든다.

## 함정

- **빈 목록 파일로 솎으면 전량 삭제다.** `read_list` 가 한 줄도 없으면 거절한다.
  그래도 **필터가 0건을 낸 목록은 거절 못 한다** — 6단계 미리보기 숫자를 보고 붙인다
- **4단계를 건너뛰면 K-Startup 이 과배제된다.** 위 4단계 참조
- **`filter.py --ids` 가 아니라 `run.py --ids` 다.** `filter.py` 는 규칙 모듈이라
  `--test` 밖에 없다. `match/service.py` 주석이 `filter.py --ids` 로 적어 둔 것은
  2026-08-22 까지 **존재하지 않는 명령**이었다
- **`sn` 이 공고번호가 아니다.** `filter.py` 가 내는 `sn` 은 화면용 뒤 6자리이고
  DB 키는 `id`(`pblancId`) 다. `--ids` 가 `id` 를 쓴다
- **첨부 원본은 여럿이 한 파일을 본다.** 저장소가 콘텐츠 주소라 URL 이 달라도
  `stored_path` 가 같을 수 있다. 솎기가 **아무도 안 쓰게 되는 파일만** 지운다 —
  안 그러면 살아남은 공고가 «행은 있고 파일은 없는» 상태가 되고, 근거를 열 때가
  되어서야 걸린다
- **배포 DB 에 이 절차를 쓰지 않는다.** 절차가 아니라 도구가 없다 — `dataset` CLI 는
  로컬 DB 를 본다([deploy.md](deploy.md))

## 검증

```bash
uv run pytest tests/test_dataset.py         # 25건
cd notice-filter && python3 filter.py --test && python3 kstartup.py --test   # 69/69 · 22/22
uv run python -m finnect.dataset --report
```

2026-08-22 실측 — 이 문서의 명령을 그대로 돌린 결과다.

```
[현황]
  attachment           3,354
  bizinfo_notice       1,538
  kstartup_notice         50
  첨부 원본 파일             723  (254 MB)

기업마당  목록 500개 → --sample 3 → 160건
K-Startup 50건 → 필터 24건 → --sample 3 → 8건
```

**K-Startup 이 50건인 것은 `--limit 50` 맛보기 실행 때문이다**(`ingest_run` id=2 ·
`item_limit=50` · `expected=29789`). 전량 29,789건에 대고 잰 값이 아니다.
