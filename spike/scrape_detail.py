"""스파이크 6단계 — K-Startup 상세 페이지에서 첨부를 찾아 내려받는다.

K-Startup OpenAPI 에는 첨부 필드가 없다. 상세 페이지를 긁어야 한다.
목표는 초기창업패키지(일반형) 본공고의 첨부에서 U1·U2·U3 를 확인하는 것이다.
"""

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hwp_text import extract  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FILES = ROOT / "spike" / "data" / "files"
FILES.mkdir(parents=True, exist_ok=True)

BASE = "https://www.k-startup.go.kr"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122 Safari/537.36"}

TARGETS = {
    "176019": "2026년도 초기창업패키지(일반형) 창업기업 모집공고",
    "176065": "2026년도 창업도약패키지(일반형) 창업기업 모집공고",
    "175854": "2026년도 초기창업패키지(딥테크 특화형) 창업기업 모집공고",
}


def fetch_detail(sn: str) -> str:
    url = f"{BASE}/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={sn}"
    r = requests.get(url, headers=UA, timeout=40)
    r.raise_for_status()
    return r.text


def find_attachments(html: str) -> list[tuple[str, str]]:
    """(파일명, 절대URL) 목록. 첨부 링크는 보통 fileDownload / atchFile 계열이다."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = " ".join(a.get_text(" ", strip=True).split())
        if re.search(r"(fileDown|file_down|atchFile|fileId|download)", href, re.I) or \
           re.search(r"\.(hwp|hwpx|pdf|zip|docx?)\b", text, re.I):
            out.append((text or "(이름없음)", urljoin(BASE, href)))
    # onclick 기반 다운로드도 흔하다
    for tag in soup.find_all(attrs={"onclick": True}):
        oc = tag["onclick"]
        m = re.search(r"""['"]([^'"]*(?:fileDown|atchFile)[^'"]*)['"]""", oc, re.I)
        if m:
            text = " ".join(tag.get_text(" ", strip=True).split())
            out.append((text or "(onclick)", urljoin(BASE, m.group(1))))
    # 중복 제거
    seen, uniq = set(), []
    for nm, u in out:
        if u not in seen:
            seen.add(u)
            uniq.append((nm, u))
    return uniq


def main() -> int:
    for sn, title in TARGETS.items():
        print(f"\n{'='*70}\n{title}\n  pbancSn={sn}")
        try:
            html = fetch_detail(sn)
        except Exception as e:
            print(f"  상세 페이지 실패: {type(e).__name__}: {e}")
            continue
        print(f"  HTML {len(html):,}B")

        atts = find_attachments(html)
        print(f"  첨부 후보 {len(atts)}개")
        for nm, u in atts[:12]:
            print(f"    - {nm[:64]}")
            print(f"      {u[:100]}")

        for idx, (nm, u) in enumerate(atts[:8]):
            ext = None
            m = re.search(r"\.(hwpx|hwp|pdf|docx|doc)\b", nm, re.I)
            if m:
                ext = m.group(1).lower()
            try:
                r = requests.get(u, headers=UA, timeout=90)
                r.raise_for_status()
                blob = r.content
                if ext is None:
                    cd = r.headers.get("content-disposition", "")
                    m2 = re.search(r"\.(hwpx|hwp|pdf|docx|doc)", cd, re.I)
                    ext = m2.group(1).lower() if m2 else None
                if ext is None:
                    if blob[:4] == b"PK\x03\x04":
                        ext = "hwpx"
                    elif blob[:4] == b"%PDF":
                        ext = "pdf"
                    elif blob[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
                        ext = "hwp"
                    else:
                        print(f"    [{idx}] 포맷 판별 실패 ({len(blob)}B, {blob[:8]!r})")
                        continue
                dest = FILES / f"ks_{sn}_{idx}.{ext}"
                dest.write_bytes(blob)
                text, how = extract(dest)
                (FILES / f"ks_{sn}_{idx}.txt").write_text(text, encoding="utf-8")
                print(f"    [{idx}] ✓ {ext:4} {len(blob):>9,}B → 텍스트 {len(text):>7,}자  ({how})")
            except Exception as e:
                print(f"    [{idx}] ✗ {type(e).__name__}: {str(e)[:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
