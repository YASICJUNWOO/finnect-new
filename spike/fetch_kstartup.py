"""스파이크 4단계 — K-Startup(창업진흥원) 공고 수집.

bizinfo 최신 200건은 소상공인·박람회 지원이 대부분이라 모집단이 틀렸다.
이 제품이 겨냥하는 것은 초기창업패키지 같은 창업 지원사업이고 그건 K-Startup 에 있다.
"""

import json
import sys
from pathlib import Path
from urllib.parse import urlencode

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "spike" / "data"

BASE = "https://apis.data.go.kr/B552735/kisedKstartupService01"
PATHS = ["getAnnouncementInformation01", "getAnnouncementInformation"]


def load_env() -> dict:
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def main() -> int:
    key = load_env().get("DATA_GO_KR_API_KEY", "")
    if not key:
        print("DATA_GO_KR_API_KEY 없음", file=sys.stderr)
        return 1

    for path in PATHS:
        for rt in ("json", "JSON"):
            params = {"serviceKey": key, "page": 1, "perPage": 200, "returnType": rt}
            url = f"{BASE}/{path}?{urlencode(params)}"
            try:
                r = requests.get(url, timeout=40)
            except Exception as e:
                print(f"  {path}/{rt}: 실패 {type(e).__name__}")
                continue
            head = r.text[:160].replace("\n", " ")
            print(f"  {path}/{rt}: HTTP {r.status_code}, {len(r.content):,}B | {head[:110]}")
            if r.status_code != 200:
                continue
            try:
                data = r.json()
            except Exception:
                continue
            items = data.get("data") or data.get("body") or []
            if items:
                (OUT / "kstartup_raw.json").write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print(f"\n✓ 공고 {len(items)}건 수신 → spike/data/kstartup_raw.json")
                print(f"  전체 건수: {data.get('totalCount')}")
                print(f"\n항목 필드 {len(items[0])}개:")
                for k, v in list(items[0].items()):
                    print(f"  {k:34} {str(v).replace(chr(10),' ')[:62]}")
                return 0
    print("\n모든 엔드포인트 조합 실패")
    return 2


if __name__ == "__main__":
    sys.exit(main())
