"""스파이크 3단계 — 첨부 내려받아 배점표가 뽑히는지 실측.

재는 것 둘.
  (a) 기술: HWP/HWPX/PDF 에서 텍스트가 기계적으로 나오는가
  (b) 비율: 공고 중 몇 %의 첨부에 배점표가 실제로 적혀 있는가

판정 등급
  FAIL   텍스트 추출 실패
  NONE   텍스트는 나왔으나 배점 흔적 없음
  WEAK   배점 관련 키워드만 있음 (표는 확인 안 됨)
  STRONG 배점 키워드 + 점수 숫자 다수 = 배점표로 보임
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
FILES.mkdir(parents=True, exist_ok=True)

SAMPLE_SIZE = 30
PARSEABLE = {"hwp", "hwpx", "pdf"}

KEYWORD = re.compile(r"배\s*점|평가\s*항목|심사\s*항목|평가\s*지표|심사\s*기준|평가\s*기준|가\s*점")
SCORE = re.compile(r"(\d{1,3})\s*점")


def pairs(item, name_field, path_field):
    names = [n.strip() for n in (item.get(name_field) or "").split("@") if n.strip()]
    urls = [u.strip() for u in (item.get(path_field) or "").split("@") if u.strip()]
    return list(zip(names, urls))


def classify(text: str) -> tuple[str, dict]:
    if not text or len(text.strip()) < 200:
        return "FAIL", {"chars": len(text or "")}

    kw = KEYWORD.findall(text)
    scores = [int(m) for m in SCORE.findall(text) if 0 < int(m) <= 100]
    info = {"chars": len(text), "kw": len(kw), "scores": len(scores)}

    if not kw:
        return "NONE", info
    # 배점표라면 항목별 점수가 여럿 나오고 합이 100 근처인 경우가 많다.
    if len(scores) >= 3:
        info["score_values"] = sorted(set(scores), reverse=True)[:10]
        return "STRONG", info
    return "WEAK", info


def main() -> int:
    items = json.loads((DATA / "bizinfo_raw.json").read_text(encoding="utf-8"))["jsonArray"]

    # 공고문(printFileNm)이 있는 건을 우선한다. 배점은 양식이 아니라 공고문에 있다.
    cand = []
    for it in items:
        for nm, url in pairs(it, "printFileNm", "printFlpthNm") + pairs(it, "fileNm", "flpthNm"):
            ext = nm.rsplit(".", 1)[-1].lower() if "." in nm else ""
            if ext in PARSEABLE:
                cand.append((it, nm, url, ext))
                break  # 공고당 대표 첨부 1개
    sample = cand[:SAMPLE_SIZE]
    print(f"표본 {len(sample)}건 (첨부 파싱 대상 포맷 보유 공고 {len(cand)}건 중)\n")

    results = []
    for idx, (it, nm, url, ext) in enumerate(sample, 1):
        pid = it["pblancId"]
        dest = FILES / f"{pid}.{ext}"
        title = (it.get("pblancNm") or "")[:44]

        try:
            if not dest.exists():
                r = requests.get(url, timeout=60)
                r.raise_for_status()
                dest.write_bytes(r.content)
                time.sleep(0.4)  # 예의상 간격
            text, how = extract(dest)
            grade, info = classify(text)
            err = ""
        except Exception as e:
            text, how, grade, info = "", "-", "FAIL", {}
            err = f"{type(e).__name__}: {str(e)[:60]}"

        results.append({
            "pblancId": pid, "title": it.get("pblancNm"), "file": nm,
            "ext": ext, "grade": grade, "how": how, "err": err, **info,
        })
        if text:
            (FILES / f"{pid}.txt").write_text(text, encoding="utf-8")

        mark = {"STRONG": "◎", "WEAK": "△", "NONE": "·", "FAIL": "✗"}[grade]
        print(f"  {idx:2}. {mark} [{ext:4}] {grade:6} {title}")
        if err:
            print(f"        └ {err}")

    (DATA / "spike_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n" + "=" * 62)
    print("판정 분포")
    c = Counter(r["grade"] for r in results)
    n = len(results)
    for g in ("STRONG", "WEAK", "NONE", "FAIL"):
        print(f"  {g:7} {c[g]:3}건  {c[g]/n*100:5.1f}%")

    print("\n확장자별 추출 성공률 (FAIL 이 아닌 비율)")
    by_ext = {}
    for r in results:
        by_ext.setdefault(r["ext"], []).append(r["grade"] != "FAIL")
    for ext, oks in sorted(by_ext.items()):
        print(f"  {ext:5} {sum(oks)}/{len(oks)}  ({sum(oks)/len(oks)*100:.0f}%)")

    print(f"\n배점표 명시율(STRONG): {c['STRONG']}/{n} = {c['STRONG']/n*100:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
