"""스파이크 7단계 — 초기창업패키지(일반형) 본공고 첨부 확보 및 U1·U2·U3 확인.

마감 공고는 bizpbanc-deadline.do 로 들어가야 첨부가 렌더된다.
확인 대상
  U1 심사 단계 (서류평가 · 심층인터뷰 · 발표평가 3단계인가)
  U2 서류평가 배점 (문제인식 30 · 실현가능성 30 · 성장전략 25 · 팀구성 15 인가)
  U3 탈락 사유 (지정 양식 미준수 · 제출 후 수정 불가)
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
    "176019": "초기창업패키지(일반형)",
    "176065": "창업도약패키지(일반형)",
}


def sniff_ext(blob: bytes, hint: str = "") -> str | None:
    m = re.search(r"\.(hwpx|hwp|pdf|docx|doc)\b", hint, re.I)
    if m:
        return m.group(1).lower()
    if blob[:4] == b"PK\x03\x04":
        return "hwpx"   # zip 계열. hwpx 또는 docx
    if blob[:4] == b"%PDF":
        return "pdf"
    if blob[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "hwp"
    return None


def main() -> int:
    s = requests.Session()
    s.headers.update(UA)

    for sn, label in TARGETS.items():
        url = f"{BASE}/web/contents/bizpbanc-deadline.do?schM=view&pbancSn={sn}"
        print(f"\n{'='*72}\n{label}  (pbancSn={sn})")
        r = s.get(url, timeout=60)
        soup = BeautifulSoup(r.text, "html.parser")

        links = []
        for a in soup.find_all("a", href=True):
            if "fileDownload" in a["href"]:
                nm = " ".join(a.get_text(" ", strip=True).split())
                links.append((nm, urljoin(BASE, a["href"])))
        # 중복 URL 제거
        seen, uniq = set(), []
        for nm, u in links:
            if u not in seen:
                seen.add(u); uniq.append((nm, u))
        print(f"첨부 {len(uniq)}개")

        for i, (nm, u) in enumerate(uniq):
            try:
                fr = s.get(u, timeout=120)
                fr.raise_for_status()
                blob = fr.content
                cd = fr.headers.get("content-disposition", "")
                ext = sniff_ext(blob, nm + " " + cd)
                if not ext:
                    print(f"  [{i}] ? 포맷 불명 {len(blob):,}B  {nm[:52]}")
                    continue
                dest = FILES / f"choki_{sn}_{i}.{ext}"
                dest.write_bytes(blob)
                try:
                    text, how = extract(dest)
                except Exception:
                    if ext == "hwpx":  # docx 일 수 있다
                        continue
                    raise
                (FILES / f"choki_{sn}_{i}.txt").write_text(text, encoding="utf-8")
                flag = "◎배점있음" if re.search(r"배\s*점", text) else "         "
                print(f"  [{i}] {ext:4} {len(blob):>9,}B → {len(text):>7,}자 {flag} {nm[:46]}")
            except Exception as e:
                print(f"  [{i}] ✗ {type(e).__name__}: {str(e)[:60]}  {nm[:40]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
