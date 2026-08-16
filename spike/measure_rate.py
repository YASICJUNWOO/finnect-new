"""스파이크 8단계 — 창업 사업화 공고 모집단에서 배점 명시율 실측.

앞 단계에서 초기창업패키지·창업도약패키지 본공고에 배점 숫자가 없다는 것을 확인했다.
그것이 두 건의 예외인지 일반적인 상태인지를 여기서 가른다.

명시 등급
  TABLE  '배점' 이라는 말과 함께 항목별 점수가 3개 이상 = 배점표가 있다
  CUT    커트라인·가점 같은 단일 점수만 있다 (배점표 아님)
  NAMED  평가항목 이름만 있고 점수가 없다   ← 초기창업패키지가 여기다
  NONE   평가 관련 서술 자체가 없다
  FAIL   텍스트 추출 실패
"""

import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hwp_text import extract  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "spike" / "data"
FILES = DATA / "files"

PARSEABLE = {"hwp", "hwpx", "pdf"}
LIMIT = 40

RE_BAEJEOM = re.compile(r"배\s*점")
RE_ITEM = re.compile(r"평가\s*항목|심사\s*항목|평가\s*지표|심사\s*기준|평가\s*기준")
RE_SCORE = re.compile(r"(\d{1,3})\s*점")


def grade(text: str) -> tuple[str, dict]:
    if not text or len(text.strip()) < 300:
        return "FAIL", {"chars": len(text or "")}

    has_item = bool(RE_ITEM.search(text))
    scores = [int(m) for m in RE_SCORE.findall(text) if 1 <= int(m) <= 100]
    info = {"chars": len(text), "n_scores": len(scores)}

    # 배점표 판정: '배점' 이라는 말 주변 900자 안에 5~50 사이 점수가 3개 이상
    for m in RE_BAEJEOM.finditer(text):
        win = text[max(0, m.start() - 300): m.end() + 600]
        near = [int(x) for x in RE_SCORE.findall(win) if 5 <= int(x) <= 50]
        # 표 안의 숫자는 '점' 없이 나오기도 한다
        bare = [int(x) for x in re.findall(r"(?<!\d)([1-4]?\d)(?!\d)", win)]
        cand = near if len(near) >= 3 else [b for b in bare if 5 <= b <= 40]
        if len(set(cand)) >= 3:
            info["scores_near_baejeom"] = sorted(set(cand), reverse=True)[:8]
            return "TABLE", info

    if scores and has_item:
        info["sample_scores"] = sorted(set(scores), reverse=True)[:8]
        return "CUT", info
    if has_item:
        return "NAMED", info
    return "NONE", info


def main() -> int:
    items = json.loads((DATA / "bizinfo_startup.json").read_text(encoding="utf-8"))
    print(f"기업마당 창업 분야 모집단 {len(items)}건 (전량 1,538건 중)\n")

    picked = []
    for it in items:
        for field_n, field_u in (("printFileNm", "printFlpthNm"), ("fileNm", "flpthNm")):
            names = [n.strip() for n in (it.get(field_n) or "").split("@") if n.strip()]
            urls = [u.strip() for u in (it.get(field_u) or "").split("@") if u.strip()]
            done = False
            for nm, u in zip(names, urls):
                ext = nm.rsplit(".", 1)[-1].lower() if "." in nm else ""
                if ext in PARSEABLE:
                    picked.append((it, nm, u, ext)); done = True; break
            if done:
                break
    picked = picked[:LIMIT]
    print(f"표본 {len(picked)}건 (공고당 대표 첨부 1개)\n")

    results = []
    for i, (it, nm, url, ext) in enumerate(picked, 1):
        pid = it["pblancId"]
        dest = FILES / f"su_{pid}.{ext}"
        try:
            if not dest.exists():
                r = requests.get(url, timeout=90); r.raise_for_status()
                dest.write_bytes(r.content); time.sleep(0.3)
            text, _ = extract(dest)
            g, info = grade(text)
        except Exception as e:
            text, g, info = "", "FAIL", {"err": f"{type(e).__name__}"}
        results.append({"id": pid, "title": it.get("pblancNm"), "ext": ext, "grade": g, **info})
        mark = {"TABLE": "◎", "CUT": "○", "NAMED": "△", "NONE": "·", "FAIL": "✗"}[g]
        print(f"  {i:2}. {mark} {g:5} [{ext:4}] {(it.get('pblancNm') or '')[:48]}")

    (DATA / "rate_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    c = Counter(r["grade"] for r in results)
    n = len(results)
    print("\n" + "=" * 64)
    print("창업 사업화 공고 — 배점 명시 등급 분포")
    for g, desc in [("TABLE", "배점표 있음 (항목별 점수)"), ("CUT", "단일 점수만 (커트라인·가점)"),
                    ("NAMED", "평가항목 이름만"), ("NONE", "평가 서술 없음"), ("FAIL", "추출 실패")]:
        print(f"  {g:6} {c[g]:3}건 {c[g]/n*100:5.1f}%   {desc}")
    ok = n - c["FAIL"]
    print(f"\n  텍스트 추출 성공률      {ok}/{n} = {ok/n*100:.1f}%")
    print(f"  배점표(TABLE) 명시율    {c['TABLE']}/{n} = {c['TABLE']/n*100:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
