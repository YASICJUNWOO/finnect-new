"""T4 층마다 첨부를 열어 '계획서로 심사하는가' 를 실측한다.

층 이름만 보고 빼면 축2에서 한 실수를 반복한다. 그래서 재는 것 셋.
  1) GROWTH 라벨(목표시장·경쟁사·성장전략)이 양식에 있는가  → 있으면 우리 제품이 개입한다
  2) 선정 방식이 무엇인가 (선착순·추첨·요건충족 vs 서류·발표 심사)
  3) '사업계획서' 라는 말이 공고문에 나오는가
"""
import json, pathlib, re, sys, time
import psycopg, requests
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from coverage48 import extract, detect_ext, labels_of, pairs, UA, DSN, GROWTH, BUDGET

HERE = pathlib.Path(__file__).parent
FILES = HERE / "filesT4"; FILES.mkdir(exist_ok=True)

ADMIN = ["기업명","대표자","사업자등록번호","사업자번호","법인등록번호","주소","연락처",
         "업종","설립일","종업원","상시근로자","이메일","담당자","직위","전화"]
EQUIP = ["장비","견적","시제품","설비","규격","수량","납기","모델","제작","시설"]
# 선정 방식
SEL = [("선착순",      r"선착순"),
       ("추첨",        r"추첨|무작위"),
       ("요건충족 전원", r"(요건|조건)\s*(을|를)?\s*충족|충족\s*시\s*(전원|모두)|예산\s*소진"),
       ("서류심사",     r"서류\s*(심사|평가|검토)"),
       ("발표·대면평가", r"(발표|대면|PT)\s*(심사|평가)"),
       ("현장실사",     r"현장\s*(실사|평가|확인)")]
PLAN = re.compile(r"사업계획서|사업 ?계획 ?서")

# 층 대표 표본 — 대분류별로 골고루
SAMPLE = {
 "인력(고용지원금)": ["119137","117056","125381","121424","119201"],
 "금융(보증·보험)":  ["117945","118917","125486","121702"],
 "내수(행사·부스)":  ["125203","124404","125044","124625","120976"],
 "제도(인증)":       ["120566","117800","124837"],
 "정보제공·컨설팅":  ["120487","121175","121634"],
}
ALL = [s for v in SAMPLE.values() for s in v]

def get(url, name):
    p = FILES / re.sub(r"[^\w.가-힣-]", "_", f"{name}")[:120]
    if p.exists() and p.stat().st_size: return p.read_bytes()
    r = requests.get(url, headers=UA, timeout=120); r.raise_for_status()
    p.write_bytes(r.content); time.sleep(0.25); return r.content

with psycopg.connect(DSN) as c, c.cursor() as cur:
    cur.execute('''select "pblancId","pblancNm","pldirSportRealmLclasCodeNm",
                          "pldirSportRealmMlsfcCodeNm","fileNm","flpthNm","printFileNm","printFlpthNm"
                   from bizinfo_notice where right("pblancId",6) = any(%s)''', (ALL,))
    rows = {r[0][-6:]: r for r in cur.fetchall()}

out = []
for layer, sns in SAMPLE.items():
    print(f"\n{'═'*74}\n{layer}\n{'═'*74}")
    for sn in sns:
        if sn not in rows: print(f"  {sn}  ✗ DB 없음"); continue
        pid, nm, lc, mc, fnm, flp, pnm, plp = rows[sn]
        cands = pairs(fnm, flp) + pairs(pnm, plp)
        txt, exts, fails = "", [], []
        for name, url in cands:
            if not url: fails.append(f"{name}: URL없음"); continue
            try:
                blob = get(url, f"{sn}_{name}")
                ext = detect_ext(name, blob)
                if ext is None or ext in ("zip","xlsx","xls","doc","ppt"):
                    fails.append(f"{name}: {ext}"); continue
                p = FILES / re.sub(r"[^\w.가-힣-]","_",f"{sn}_{name}")[:120]
                txt += "\n" + extract(p, ext); exts.append(ext)
            except Exception as e: fails.append(f"{name}: {type(e).__name__}")
        lb = labels_of(txt)
        cnt = lambda ks: len({k for k in ks if any(k in s for s in lb)})
        a,g,b,e = cnt(ADMIN), cnt(GROWTH), cnt(BUDGET), cnt(EQUIP)
        sel = [n for n,p in SEL if re.search(p, txt)]
        rec = dict(sn=sn, layer=layer, title=nm, lclas=lc, mlsfc=mc, chars=len(txt),
                   files=len(cands), exts=exts, A=a, G=g, B=b, E=e,
                   plan=bool(PLAN.search(txt)), sel=sel, fails=fails)
        out.append(rec)
        print(f"  {sn} {nm[:56]}")
        print(f"        {len(txt):>6,}자  A{a:<2} G{g:<2} B{b:<2} E{e:<2}  "
              f"계획서언급 {'있음' if rec['plan'] else '없음':<4}  선정 {', '.join(sel) or '미기재'}")
        if fails: print(f"        실패 {'; '.join(fails)[:100]}")

(HERE/"t4probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n{'═'*74}\n층별 집계\n{'═'*74}")
for layer in SAMPLE:
    g = [x for x in out if x["layer"]==layer]
    if not g: continue
    ok = [x for x in g if x["chars"]>500]
    print(f"  {layer:<18} 표본 {len(g)}  추출성공 {len(ok)}  "
          f"GROWTH≥3 {sum(1 for x in ok if x['G']>=3)}  "
          f"계획서언급 {sum(1 for x in ok if x['plan'])}  "
          f"평균 A{sum(x['A'] for x in ok)/max(1,len(ok)):.0f} G{sum(x['G'] for x in ok)/max(1,len(ok)):.0f}")
