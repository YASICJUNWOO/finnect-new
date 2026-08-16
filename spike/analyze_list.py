"""스파이크 2단계 — 수신한 공고 목록의 첨부 현황 분석.

재는 것 둘.
  (1) 공고 중 몇 %에 첨부가 딸려 오는가
  (2) 그 첨부가 어떤 포맷인가 (HWP/HWPX/PDF/기타)
첨부가 없으면 배점을 못 얻는다. 여기가 U2 의 상한선이다.
"""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
items = json.loads((ROOT / "spike" / "data" / "bizinfo_raw.json").read_text(encoding="utf-8"))["jsonArray"]

print(f"표본 {len(items)}건 (전체 {items[0].get('totCnt')}건 중 최신순)\n")

# ── 지원분야 분포 ──────────────────────────────────────────────
print("── 지원분야 대분류 ──")
for name, n in Counter(i.get("pldirSportRealmLclasCodeNm", "?") for i in items).most_common():
    print(f"  {name:24} {n:4}건")

# ── 첨부 유무와 포맷 ───────────────────────────────────────────
def attach_names(item) -> list[str]:
    """fileNm 과 printFileNm 을 합쳐 첨부 파일명 목록을 만든다. 구분자는 @ 다."""
    out = []
    for field in ("fileNm", "printFileNm"):
        raw = (item.get(field) or "").strip()
        if raw:
            out += [n.strip() for n in raw.split("@") if n.strip()]
    return out

has_attach = 0
ext_counter = Counter()
per_item_ext = []

for it in items:
    names = attach_names(it)
    if names:
        has_attach += 1
    exts = set()
    for n in names:
        ext = n.rsplit(".", 1)[-1].lower() if "." in n else "(확장자없음)"
        ext_counter[ext] += 1
        exts.add(ext)
    per_item_ext.append(exts)

print(f"\n── 첨부 유무 ──")
print(f"  첨부 있음  {has_attach:4}건 / {len(items)}건  ({has_attach/len(items)*100:.1f}%)")

print(f"\n── 첨부 파일 확장자 (파일 단위, 총 {sum(ext_counter.values())}개) ──")
for ext, n in ext_counter.most_common(12):
    print(f"  {ext:16} {n:4}개")

parseable = {"hwp", "hwpx", "pdf", "docx", "doc"}
n_parseable = sum(1 for e in per_item_ext if e & parseable)
print(f"\n  파싱 대상 포맷(hwp/hwpx/pdf/doc)을 하나라도 가진 공고: "
      f"{n_parseable}건 ({n_parseable/len(items)*100:.1f}%)")

# ── 창업 관련 공고 추출 ────────────────────────────────────────
KEYS = ("창업", "스타트업", "초기창업", "창업도약", "예비창업")
startup = [i for i in items if any(k in (i.get("pblancNm") or "") for k in KEYS)]
print(f"\n── 창업 키워드 공고 {len(startup)}건 ──")
for i in startup[:15]:
    names = attach_names(i)
    exts = ",".join(sorted({n.rsplit('.',1)[-1].lower() for n in names if '.' in n})) or "첨부없음"
    print(f"  [{exts:12}] {i['pblancNm'][:52]}")

# ── 본문에 배점이 들어 있는지 (첨부 없이 될 가능성) ────────────
import re
SCORE_PAT = re.compile(r"(배점|평가\s*항목|가중치|\d{1,3}\s*점)")
in_body = sum(1 for i in items if SCORE_PAT.search(i.get("bsnsSumryCn") or ""))
print(f"\n── 본문(bsnsSumryCn)에 배점 흔적이 있는 공고 ──")
print(f"  {in_body}건 / {len(items)}건 ({in_body/len(items)*100:.1f}%)")
print("  → 낮으면 '배점은 첨부 안에 있다'는 가설이 맞다는 뜻이다.")
