"""K-Startup 공고 필터 — plan/03 T-0054.

`filter.py` 가 기업마당에 하는 일을 K-Startup 29,789건에 한다.
의존성 없다. `filter.py` 의 정규식을 그대로 빌려 쓴다.

    python3 kstartup.py --test        픽스처 14건 (네트워크·DB 불필요)

**축 열셋 중 다섯만 옮겨졌다.** 어느 것이 왜 안 옮겨졌는지는 아래 `옮기지 못한 축` 에
적었고, 조사 기록은 plan/03 T-0054 에 있다.

## 떼는 법

이 파일 하나와 `fixtures_kstartup.json` 을 지우면 끝난다. **`src/finnect/` 와 `web/`
어디에서도 임포트하지 않는다.** 첨부를 고를 때 쓰려면 이 모듈이 URL 목록을 파일로
내보내고 받는 쪽이 그 파일을 읽는다 — 받는 쪽은 이 필터의 존재를 모른다.

## 옮기지 못한 축

| 축 | 왜 |
|---|---|
| 축1 신청 주체 | **정밀도 65%** (무작위 20건 육안). "지원대상 절 끝 명사가 신청자" 는 기업마당 작성 관례다. K-Startup 은 콤마로 여러 대상을 나열하고("…창업기업, 대학, 연구기관") "기술을 **보유한** 창업기업" 이 흔해 `SUPPLIER` 어휘가 오작동한다 |
| 축2·2e 중분류 | 분류 체계가 다르다. 기업마당 24종 · K-Startup 11종이고 **이름 교집합이 0** 이다 |
| 축2g 설비·시설 | 입력이 없다. `pbanc_ctnt` 는 지원내용 절이 아니라 홍보 요약(중앙값 116자)이라 29,789건 중 **1건**만 걸렸다 |
| 축2i 금융 비용 | 〃 **1건** |

`aply_trgt` (신청대상 코드)도 축1 대안으로 재 봤고 **못 쓴다.** 태그가 7종뿐인데
`일반기업` 이 86%에 붙고, 기업 태그가 없는 2,362건을 6건 읽으니 전부 예비창업자
대상 공고였다 — 우리 타겟이다.
"""
from __future__ import annotations

import html
import json
import pathlib
import re
import sys

import filter as F

HERE = pathlib.Path(__file__).parent

# ══════════════════════════════════════════════════════════════════
# 축3 — 업력. **기업마당이 정규식으로 캐던 것을 K-Startup 은 필드로 준다.**
#   `biz_enyy` 는 다중 선택이고 **값은 상한이다.** 집합의 최댓값이 진짜 상한이다.
#   2026-08-19 실측 18건 육안 — '7년미만' 단독은 원문이 "업력 7년 미만 스타트업"
#   이라 2.5년 사업자가 들어가고, '예비창업자,1년미만' 은 "예비창업자 또는 창업
#   1년 미만" 이라 안 든다. 버킷이 구간이 아니라 **누적 상한**이다.
# ══════════════════════════════════════════════════════════════════
CEILING = {"1년미만": 1, "2년미만": 2, "3년미만": 3, "5년미만": 5, "7년미만": 7, "10년미만": 10}

# ══════════════════════════════════════════════════════════════════
# 축2d′ — 계획서로 심사하지 않는 분류. **분류로 빼되 양식이 있으면 되살린다.**
#
#   분류별로 '사업계획서 양식' 첨부가 붙어 있는 비율을 67,300개 파일명으로 쟀다.
#     시설ㆍ공간ㆍ보육 27.4% · 사업화 18.3% · 글로벌 15.7% · 정책자금 13.3%
#     ───────────────────────────────────────────────────────────
#     행사ㆍ네트워크 5.4% · 멘토링 5.0% · 창업교육 4.1% · 융자ㆍ보증 0.0%
#   3~5배로 깨끗하게 갈린다.
#
#   **`시설ㆍ공간ㆍ보육` 을 안 뺀 것이 요점이다.** 7,353건으로 제일 큰 덩어리인데
#   대부분 창업보육센터 입주기업 모집이고 계획서 첨부율이 **가장 높다**(27.4%).
#   `filter.py` 축2g 커밋이 적어 둔 그대로다 — "분류로 빼지 않고 주는 물건으로 뺐다".
# ══════════════════════════════════════════════════════════════════
NO_PLAN_CLSFC = {"창업교육", "행사ㆍ네트워크", "멘토링ㆍ컨설팅ㆍ교육", "융자ㆍ보증", "인력"}

#: 구제는 **문서 포맷일 때만**. 파일명에 '사업계획서' 가 있어도 png 면 포스터다.
#: 실측 — 포맷 무관 구제 542건 중 20건이 그림이었고, 무작위 12건을 읽으니 오구제가
#: 3건에서 0건이 됐다.
FORM_EXT = {"hwp", "hwpx", "docx", "doc", "pdf", "zip"}


def u(x: str | None) -> str:
    """K-Startup 은 `&apos;` · `&amp;` 를 그대로 준다. 안 풀면 정규식이 헛돈다."""
    return html.unescape(x or "")


def ceiling(biz_enyy: str | None) -> float:
    """업력 상한(년). 예비창업자만 있으면 0 — 기창업자는 못 낸다."""
    return max((CEILING[b] for b in u(biz_enyy).split(",") if b in CEILING), default=0)


def target_clause(aply_trgt_ctnt: str | None) -> str:
    """K-Startup 은 `aply_trgt_ctnt` 자체가 지원대상 절이다. ☞ 분리가 필요 없다.

    `filter.py` 의 `first_clause` 를 그대로 쓰면 안 된다 — 그쪽은 `☞`(U+261E)를
    찾는데 K-Startup 에는 없어서 22,711건 전부가 빈 문자열이 된다.
    """
    s = re.sub(r"<[^>]+>", " ", u(aply_trgt_ctnt)).replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", re.split(r"※|\n", s)[0]).strip(" -·ㆍ□○◆■")


def has_plan_form(attachments: list[dict]) -> bool:
    """계획서 **양식**이 첨부에 있나. 이름만 보고 포맷을 같이 본다."""
    return any(
        F.PLAN_FN.search(u(a.get("filename")))
        and (a.get("ext") or "").lower() in FORM_EXT
        for a in attachments
    )


def filter_notice(n: dict, attachments: list[dict] | None = None,
                  biz_years: float = 2.5, staff: int = 4) -> dict:
    """K-Startup 공고 하나를 판정한다. 통과 여부와 근거를 함께 돌려준다.

    n            `kstartup_notice` 행 하나 (API 필드명 그대로)
    attachments  그 공고의 첨부. `filename` 과 `ext` 만 본다. 없으면 축2d′ 구제가 안 돈다
    biz_years    신청자 업력(년). 2.5 = 3년 미만 사업자
    staff        신청자 상시근로자 수
    """
    attachments = attachments or []
    cl = target_clause(n.get("aply_trgt_ctnt"))
    title = F.strip_paren(u(n.get("biz_pbanc_nm")))
    clsfc = u(n.get("supt_biz_clsfc"))
    ceil = ceiling(n.get("biz_enyy"))
    form = has_plan_form(attachments)

    task = [k for k, p in F.TASK if p.search(title)]
    sole = bool(F.SOLE_TARGET.search(cl)) and not F.BIZ_MENTION.search(cl)
    special = bool(F.SPECIAL_ORG.search(cl)) and not F.GENERAL_BIZ.search(cl)
    sfloor = F.parse_staff_floor(cl)

    reasons = []
    if ceil < biz_years:
        reasons.append(f"축3 업력 상한 {ceil or '예비창업자 전용'}")
    if task:
        reasons.append("축2b 과업 " + ",".join(task))
    if sole:
        reasons.append("축2c 소상공인 전용 — 지원대상 절에 기업 언급이 없다")
    if special:
        reasons.append("축2h 특정 법인격 전용")
    if sfloor > staff:
        reasons.append(f"축2f 상시근로자 {sfloor}인 이상 요구")
    if clsfc in NO_PLAN_CLSFC and not form:
        reasons.append(f"축2d′ 계획서로 심사하지 않는 분야({clsfc}) + 양식 첨부 없음")

    return {
        "id": n.get("pbanc_sn"), "title": u(n.get("biz_pbanc_nm")),
        "pass": not reasons, "reasons": reasons,
        "ceiling": ceil, "clsfc": clsfc, "plan_form": form,
        "task": task, "sole_proprietor": sole, "special_org": special,
        "staff_floor": sfloor, "eligibility": cl,
    }


# ─────────────────────── 픽스처 ───────────────────────
def _units() -> list[tuple[str, bool]]:
    """**축 순서와 무관하게 함수를 직접 잰다.**

    `filter.py` 가 겪은 것과 같은 함정이다 — 축이 늘면 앞 축이 공고를 먼저 잡아
    뒤 축의 회귀 테스트가 죽는다. 실제로 `178883`(업력 7년미만 통과 사례)이
    축2d′ 로 넘어갔다. 그래서 업력 판정은 공고가 아니라 `ceiling()` 으로 잰다.
    """
    return [
        ("'7년미만' 단독의 상한은 7이다 — 구간이 아니라 누적", ceiling("7년미만") == 7),
        ("집합의 최댓값이 상한이다", ceiling("예비창업자,1년미만,2년미만,3년미만") == 3),
        ("예비창업자만 있으면 0 — 기창업자는 못 낸다", ceiling("예비창업자") == 0),
        ("상한 2년은 2.5년 사업자를 배제한다", ceiling("1년미만,2년미만") < 2.5),
        ("빈 값도 0", ceiling(None) == 0),
        ("양식은 문서 포맷일 때만 — png 는 포스터다",
         not has_plan_form([{"filename": "포스터_사업계획서.png", "ext": "png"}])),
        ("hwp 양식은 구제한다",
         has_plan_form([{"filename": "[별첨2] 사업계획서 양식.hwp", "ext": "hwp"}])),
        ("대상절은 ☞ 없이 그대로 읽는다 — first_clause 를 쓰면 빈 문자열이 된다",
         target_clause("○ 창업 3년 이내 기업") == "창업 3년 이내 기업"),
    ]


def run_tests() -> int:
    """**전부 실제 공고이고 기대값은 원문을 눈으로 읽어 정했다.**"""
    cases = json.loads((HERE / "fixtures_kstartup.json").read_text(encoding="utf-8"))
    ok = 0
    for c in cases:
        r = filter_notice(c["notice"], c["attachments"])
        got = "통과" if r["pass"] else "배제"
        good = got == c["expect"]
        ok += good
        bad = "  ⚠ 오배제" if c.get("known_bad") else ""
        print(f"{'✓' if good else '✗'}  {r['id']}  기대 {c['expect']}   실제 {got}{bad}   {c['why']}")
        if not good:
            print(f"      근거: {r['reasons'] or '없음(통과)'}")
    for why, got in _units():
        ok += got
        print(f"{'✓' if got else '✗'}  단위    {why}")
    total = len(cases) + len(_units())
    kb = sum(1 for c in cases if c.get("known_bad"))
    print(f"\n{ok}/{total} 통과   (공고 {len(cases)} + 단위 {len(_units())})")
    if kb:
        print(f"**알려진 오배제 {kb}건이 픽스처에 박혀 있다.** 통과했다고 옳은 판정이 아니다")
    return 0 if ok == total else 1


#: 데모용 표본. **접수중은 전부 넣고 나머지는 번호로 솎는다.**
#:
#:   제품 API 가 기본으로 마감된 공고를 뺀다(`open_only=True`). 그래서 접수중이
#:   아닌 공고는 **화면에 아예 안 뜬다** — 데모에서 실제로 보이는 것은 접수중뿐이라
#:   그 122건은 하나도 빼지 않는다. 나머지는 적합도·집필의 재료라 표본이면 된다.
#:
#:   36 은 기업마당 통과분(563 공고 · 읽는 포맷 1,235개)에 맞춘 값이다 —
#:   591 공고 · 1,308개가 나온다. **무작위 시드를 안 쓴다.** 공고 번호를 나눈
#:   나머지라 언제 돌려도 같은 집합이 나오고, 표본을 넓히려면 나눗수만 줄이면 된다.
DEMO_MODULUS = 36


def is_open(n: dict, today: str) -> bool:
    """접수 마감이 오늘 이후인가. **모르면 마감으로 친다** — 데모에 안 넣는다."""
    end = (n.get("derived_apply_end") or "").strip()
    return bool(end) and end >= today


def demo_pick(items: list[dict], today: str, modulus: int = DEMO_MODULUS) -> list[dict]:
    """접수중 전부 + 번호가 `modulus` 로 나누어떨어지는 것."""
    out = []
    for it in items:
        sn = str(it["notice"].get("pbanc_sn") or "")
        if is_open(it["notice"], today) or (sn.isdigit() and int(sn) % modulus == 0):
            out.append(it)
    return out


def run(dump: pathlib.Path, urls_out: pathlib.Path | None = None,
        demo: int | None = None, today: str = "", read_only: bool = False) -> int:
    """덤프 하나를 통째로 돌려 퍼널을 찍는다. **DB 를 모른다.**

    덤프는 `[{"notice": {...}, "attachments": [...]}, ...]` 다. 만드는 법은
    README 에 있다 — 우리 DB 에서 한 줄로 뜬다. `run.py` 가 `--raw` 로 기업마당
    원문을 받아 두는 것과 같은 자리다.

    `--urls` 를 주면 통과한 공고의 첨부 URL 만 한 줄에 하나씩 쓴다. **받는 쪽은
    그 파일만 읽고 이 필터의 존재를 모른다** — 그래서 뗄 때 지울 것이 이 폴더뿐이다.
    """
    items = json.loads(dump.read_text(encoding="utf-8"))
    passed, why = [], {}
    total_in = len(items)
    for it in items:
        r = filter_notice(it["notice"], it.get("attachments") or [])
        (passed.append(it) if r["pass"] else None)
        for reason in r["reasons"]:
            why[reason.split(" —")[0].split("(")[0].strip()] = why.get(
                reason.split(" —")[0].split("(")[0].strip(), 0) + 1
    n = len(passed)
    print(f"전량 {total_in:,}건 → 통과 {n:,}건 ({n / total_in * 100:.0f}%)\n")
    print("배제 사유 (한 공고가 여럿에 걸릴 수 있어 합이 안 맞는다)")
    for k, v in sorted(why.items(), key=lambda x: -x[1]):
        print(f"  {v:6,}  {k}")

    if demo is not None:
        opened = sum(1 for it in passed if is_open(it["notice"], today))
        passed = demo_pick(passed, today, demo)
        print(f"\n[데모 표본 % {demo}] 통과 {n:,} → {len(passed):,}건"
              f"  (접수중 {opened:,}건은 전부 넣었다)")

    att = [a for it in passed for a in (it.get("attachments") or [])]
    if read_only:
        before = len(att)
        att = [a for a in att if (a.get("ext") or "").lower() in FORM_EXT]
        print(f"[읽는 포맷만] 첨부 {before:,} → {len(att):,}개"
              f"  (jpg·png·txt 는 지금 한 글자도 못 읽는다)")
    forms = sum(1 for it in passed if has_plan_form(it.get("attachments") or []))
    print(f"\n공고 {len(passed):,}건 · 첨부 {len(att):,}개 · 계획서 양식 보유 {forms:,}건")
    if urls_out is not None:
        urls = [a["url"] for a in att if a.get("url")]
        urls_out.write_text("\n".join(urls) + "\n", encoding="utf-8")
        print(f"  → {urls_out} 에 URL {len(urls):,}개")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--test" in a:
        sys.exit(run_tests())
    if "--json" in a:
        import datetime
        d = pathlib.Path(a[a.index("--json") + 1])
        o = pathlib.Path(a[a.index("--urls") + 1]) if "--urls" in a else None
        dm = None
        if "--demo" in a:
            nxt = a[a.index("--demo") + 1] if len(a) > a.index("--demo") + 1 else ""
            dm = int(nxt) if nxt.isdigit() else DEMO_MODULUS
        t = a[a.index("--today") + 1] if "--today" in a else datetime.date.today().isoformat()
        sys.exit(run(d, o, demo=dm, today=t, read_only="--read-only" in a))
    print(__doc__)
