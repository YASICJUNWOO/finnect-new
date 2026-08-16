"""스파이크 5단계 — 올바른 모집단 만들기.

앞의 20% 는 bizinfo 최신 200건 기준이라 소상공인·박람회가 대부분이었다.
이 제품이 겨냥하는 것은 '경쟁 평가가 있는 창업 사업화 공고'다.
그 모집단을 따로 만들어 배점 명시율을 다시 잰다.

  bizinfo  전량(1,538건) → 창업 분야만 추출. 첨부 URL 이 붙어 있다.
  K-Startup 페이징      → 초기창업패키지 본공고 탐색. U1·U2·U3 확인용.
"""

import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "spike" / "data"


def load_env() -> dict:
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


ENV = load_env()


def pull_bizinfo_all() -> list:
    """기업마당 전량. searchCnt 를 크게 줘서 한 번에 받는다."""
    url = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do?" + urlencode(
        {"crtfcKey": ENV["BIZINFO_API_KEY"], "dataType": "json", "searchCnt": "2000"}
    )
    r = requests.get(url, timeout=90)
    items = r.json().get("jsonArray", [])
    (OUT / "bizinfo_all.json").write_text(
        json.dumps(items, ensure_ascii=False), encoding="utf-8"
    )
    print(f"기업마당 전량 {len(items)}건 수신")
    return items


def pull_kstartup_pages(pages: int = 20) -> list:
    """K-Startup 페이징. 초기창업패키지 본공고를 찾을 때까지 훑는다."""
    base = "https://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01"
    all_items = []
    for p in range(1, pages + 1):
        url = base + "?" + urlencode(
            {"serviceKey": ENV["DATA_GO_KR_API_KEY"], "page": p,
             "perPage": 200, "returnType": "json"}
        )
        try:
            r = requests.get(url, timeout=40)
            chunk = r.json().get("data", [])
        except Exception as e:
            print(f"  page {p}: 실패 {type(e).__name__}")
            break
        if not chunk:
            break
        all_items += chunk
        if p % 5 == 0:
            print(f"  ... {p}페이지 / 누적 {len(all_items)}건")
        time.sleep(0.25)
    (OUT / "kstartup_all.json").write_text(
        json.dumps(all_items, ensure_ascii=False), encoding="utf-8"
    )
    print(f"K-Startup {len(all_items)}건 수신")
    return all_items


def main() -> int:
    biz = pull_bizinfo_all()
    startup_biz = [
        i for i in biz
        if i.get("pldirSportRealmLclasCodeNm") == "창업"
        or any(k in (i.get("pblancNm") or "") for k in ("창업", "스타트업", "벤처"))
    ]
    print(f"  └ 창업 분야: {len(startup_biz)}건")
    (OUT / "bizinfo_startup.json").write_text(
        json.dumps(startup_biz, ensure_ascii=False), encoding="utf-8"
    )

    ks = pull_kstartup_pages()
    TARGET = ("초기창업패키지", "창업도약패키지", "예비창업패키지")
    named = [
        i for i in ks
        if any(t in (i.get("biz_pbanc_nm") or "") for t in TARGET)
    ]
    print(f"\n── 패키지 본공고 후보 {len(named)}건 ──")
    for i in named[:25]:
        print(f"  [{i.get('supt_biz_clsfc','?'):12}] {i['biz_pbanc_nm'][:58]}")
        print(f"      {i.get('detl_pg_url','')[:96]}")
    (OUT / "kstartup_packages.json").write_text(
        json.dumps(named, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
