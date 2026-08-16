"""스파이크 1단계 — 기업마당(bizinfo) 공고 목록 수집.

목적은 수집 자체가 아니다. 공고 목록에 첨부 링크가 실제로 딸려 오는지,
그 첨부가 HWP 인지 PDF 인지를 보는 것이다.
버리는 코드다. 제품 코드로 승격하지 않는다.
"""

import json
import sys
from pathlib import Path
from urllib.parse import urlencode

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "spike" / "data"
OUT.mkdir(parents=True, exist_ok=True)

ENDPOINT = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"


def load_env() -> dict:
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def mask(url: str, key: str) -> str:
    """crtfcKey 는 쿼리스트링으로 나간다. 로그에 남기지 않는다."""
    return url.replace(key, "***") if key else url


def main() -> int:
    key = load_env().get("BIZINFO_API_KEY", "")
    if not key:
        print("BIZINFO_API_KEY 없음", file=sys.stderr)
        return 1

    params = {"crtfcKey": key, "dataType": "json", "searchCnt": "200"}
    url = f"{ENDPOINT}?{urlencode(params)}"
    print(f"GET {mask(url, key)}")

    r = requests.get(url, timeout=30)
    print(f"HTTP {r.status_code}  {len(r.content):,} bytes  {r.headers.get('content-type','')}")

    # .env.example 경고: 인증 실패가 HTTP 200 + reqErr 로 온다. item 수보다 먼저 본다.
    body = r.text
    if "reqErr" in body or "인증" in body[:500]:
        print("\n⚠️ 인증 오류로 보인다. 응답 앞부분:")
        print(body[:600])
        return 2

    try:
        data = r.json()
    except json.JSONDecodeError:
        print("\nJSON 아님. 응답 앞부분:")
        print(body[:600])
        return 3

    (OUT / "bizinfo_raw.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 응답 구조를 모르므로 먼저 형태부터 본다.
    print(f"\n최상위 타입: {type(data).__name__}")
    if isinstance(data, dict):
        print(f"최상위 키: {list(data.keys())}")

    items = data.get("jsonArray") if isinstance(data, dict) else data
    if not isinstance(items, list):
        print("\n목록을 못 찾았다. 구조 덤프:")
        print(json.dumps(data, ensure_ascii=False)[:1500])
        return 4

    print(f"공고 {len(items)}건 수신 → spike/data/bizinfo_raw.json")
    if items:
        print(f"\n항목 필드 {len(items[0])}개:")
        for k, v in items[0].items():
            s = str(v).replace("\n", " ")[:70]
            print(f"  {k:22} {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
