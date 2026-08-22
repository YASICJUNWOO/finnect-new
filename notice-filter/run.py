"""수집 → 필터 → 산출물 → 로컬 서버. 의존성 없다.

    python run.py                       API 에서 받아 필터하고 :8765 로 띄운다
    python run.py --key <crtfcKey>       키를 인자로 (없으면 BIZINFO_API_KEY 환경변수)
    python run.py --raw out/raw.json     저장해 둔 원문으로. 키 없이도 된다
    python run.py --save-raw             받은 원문을 out/raw.json 에 남긴다
    python run.py --no-serve             파일만 만들고 끝낸다
    python run.py --port 9000            포트 지정
    python run.py --today 2026-08-18     기준일 고정 (마감 판정 재현용)

화면은 DESIGN.md §4 토큰을 따른다. 값의 정본은 web/app/tokens.css 다.
"""
from __future__ import annotations

import argparse
import http.server
import json
import os
import pathlib
import socketserver
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from filter import run as run_filter  # noqa: E402

HERE = pathlib.Path(__file__).parent
OUT = HERE / "out"
ENDPOINT = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"


def fetch(key: str) -> list[dict]:
    """전량 1회. searchCnt 가 그대로 건수 제한이다.
    인증 실패가 HTTP 200 + reqErr 로 오므로 그것을 먼저 본다."""
    url = ENDPOINT + "?" + urllib.parse.urlencode(
        {"crtfcKey": key, "dataType": "json", "searchCnt": "2000"})
    with urllib.request.urlopen(url, timeout=90) as r:
        body = r.read().decode("utf-8")
    if "reqErr" in body[:400]:
        raise SystemExit(f"인증 실패로 보입니다 (reqErr). 응답 앞부분:\n  {body[:200]}")
    items = json.loads(body).get("jsonArray")
    if not isinstance(items, list):
        raise SystemExit(f"jsonArray 가 없습니다. 응답 앞부분:\n  {body[:200]}")
    return items


# ────────────────────────── 화면 ──────────────────────────
# DESIGN.md §4 토큰. 색 리터럴을 컴포넌트에 쓰지 않고 여기 :root 에만 둔다.
CSS = """
:root{
 --s1:4px;--s2:8px;--s3:12px;--s4:16px;--s5:24px;--s6:32px;--s7:48px;
 --canvas:#f7f7f8;--surface:#fff;--quiet:#f4f5f6;
 --ink:#16181b;--ink-2:#5f656d;--ink-3:#949aa2;--ink-4:#cbd0d6;
 --line:#e9eaec;--line-2:#dfe2e6;
 --urgent:#d92d20;--urgent-bg:#fff5f4;--urgent-line:#f7d4d0;
 --r-sm:10px;--r:16px;--r-pill:999px;
 --t-caption:12px;--t-small:13px;--t-body:16px;--t-lead:19px;--t-title:24px;--t-display:32px;
 --font:Pretendard,-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;
 --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:var(--canvas);color:var(--ink);font-family:var(--font);
 font-size:var(--t-body);line-height:1.6;font-weight:400;-webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:0 var(--s5)}
header{padding:var(--s7) 0 var(--s5)}
h1{font-size:var(--t-display);font-weight:700;letter-spacing:-.02em;margin:0 0 var(--s3);line-height:1.25}
.sub{color:var(--ink-2);margin:0 0 var(--s4);max-width:60ch}
.meta{display:flex;flex-wrap:wrap;gap:var(--s2) var(--s5);font-size:var(--t-small);color:var(--ink-3);
 font-variant-numeric:tabular-nums}
h2{font-size:var(--t-title);font-weight:700;letter-spacing:-.02em;margin:var(--s7) 0 var(--s3)}
h3{font-size:var(--t-lead);font-weight:600;margin:var(--s6) 0 var(--s3)}
p{margin:0 0 var(--s3)}
a{color:var(--ink)}
code{font-family:var(--mono);font-size:var(--t-small)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:var(--s5)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:var(--s3);margin:var(--s4) 0}
.cards button{all:unset;cursor:pointer;background:var(--surface);border:1px solid var(--line);
 border-radius:var(--r);padding:var(--s4);display:block}
.cards button:hover{border-color:var(--line-2);background:var(--quiet)}
.cards button[aria-pressed=true]{background:var(--ink);border-color:var(--ink)}
.cards button[aria-pressed=true] .k,.cards button[aria-pressed=true] .v,
.cards button[aria-pressed=true] .d{color:var(--surface)}
.k{font-size:var(--t-caption);color:var(--ink-3);display:block}
.v{font-size:var(--t-title);font-weight:700;letter-spacing:-.02em;display:block;margin:var(--s1) 0;
 font-variant-numeric:tabular-nums}
.d{font-size:var(--t-small);color:var(--ink-2);display:block;line-height:1.45}
.funnel{margin:var(--s4) 0}
.fr{display:grid;grid-template-columns:2rem 1fr auto;gap:var(--s3);align-items:baseline;
 padding:var(--s3) 0;border-bottom:1px solid var(--line)}
.fr:last-child{border-bottom:0}
.fr .n{font-family:var(--mono);font-size:var(--t-small);color:var(--ink-3)}
.fr .lbl small{display:block;color:var(--ink-3);font-size:var(--t-small);margin-top:2px}
.fr .num{font-family:var(--mono);font-size:var(--t-lead);font-weight:600;
 font-variant-numeric:tabular-nums}
.bar{display:flex;flex-wrap:wrap;gap:var(--s2);align-items:center;margin:var(--s4) 0 var(--s3)}
select,input[type=search]{font-family:var(--font);font-size:var(--t-small);padding:var(--s2) var(--s3);
 border:1px solid var(--line-2);border-radius:var(--r-sm);background:var(--surface);color:var(--ink)}
input[type=search]{min-width:16rem}
button.plain{font-family:var(--font);font-size:var(--t-small);padding:var(--s2) var(--s3);
 border:1px solid var(--line-2);border-radius:var(--r-sm);background:var(--surface);
 color:var(--ink-2);cursor:pointer}
button.plain:hover{background:var(--quiet)}
.count{margin-left:auto;font-size:var(--t-small);color:var(--ink-2);font-variant-numeric:tabular-nums}
.count b{font-size:var(--t-lead);color:var(--ink)}
.tw{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);overflow:hidden}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:var(--t-small)}
th{text-align:left;font-weight:600;font-size:var(--t-caption);color:var(--ink-3);
 padding:var(--s3) var(--s4);border-bottom:1px solid var(--line-2);white-space:nowrap;
 background:var(--quiet)}
td{padding:var(--s3) var(--s4);border-bottom:1px solid var(--line);vertical-align:top;line-height:1.5}
tr:last-child td{border-bottom:0}
tr:hover td{background:var(--quiet)}
td.t{min-width:22rem}
td.t a{font-size:var(--t-body);font-weight:600;text-decoration:none;display:block;margin-bottom:2px}
td.t a:hover{text-decoration:underline}
td.t .el{color:var(--ink-3);font-size:var(--t-caption);display:block;line-height:1.5}
td.num{font-family:var(--mono);white-space:nowrap;font-variant-numeric:tabular-nums;color:var(--ink-2)}
.chip{display:inline-block;font-size:var(--t-caption);padding:1px var(--s2);border-radius:var(--r-pill);
 border:1px solid var(--line-2);color:var(--ink-2);white-space:nowrap;margin-right:var(--s1)}
.chip.due{background:var(--urgent-bg);border-color:var(--urgent-line);color:var(--urgent)}
.tier{display:inline-block;font-family:var(--mono);font-size:var(--t-caption);
 padding:1px var(--s2);border-radius:var(--r-sm);border:1px solid var(--line-2);color:var(--ink-2)}
.tier.t1{background:var(--ink);border-color:var(--ink);color:var(--surface)}
pre{background:var(--quiet);border:1px solid var(--line);border-radius:var(--r-sm);
 padding:var(--s4);overflow-x:auto;font-family:var(--mono);font-size:var(--t-small);line-height:1.6}
ul{margin:var(--s3) 0;padding-left:var(--s5)}
li{margin-bottom:var(--s2);color:var(--ink-2)}
li b{color:var(--ink)}
footer{padding:var(--s6) 0 var(--s7);color:var(--ink-3);font-size:var(--t-small)}
:focus-visible{outline:2px solid var(--ink);outline-offset:3px}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""

JS = r"""
const D=%%DATA%%, T=%%TODAY%%;
const $=s=>document.querySelector(s);
const uq=k=>[...new Set(D.map(x=>x[k]).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'ko'));
const esc=s=>(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function fill(id,arr,label){$(id).innerHTML='<option value="">'+label+'</option>'
  +arr.map(v=>`<option>${esc(v)}</option>`).join('')}
fill('#fl',uq('lclas'),'분야 전체');fill('#fm',uq('mlsfc'),'세부 분야 전체');
fill('#fr',uq('region'),'지역 전체');
function soon(e){if(!e)return false;const d=(new Date(e)-new Date(T))/86400000;return d>=0&&d<=7}
function chips(x){
  let o='';
  if(x.eligible_pre) o+='<span class="chip">예비창업 가능</span>';
  if(x.ceil===null&&x.floor===0) o+='<span class="chip">업력 제한 없음</span>';
  else{ if(x.ceil!==null)o+=`<span class="chip">${x.ceil}년 이내</span>`;
        if(x.floor>0)o+=`<span class="chip">${x.floor}년 이상</span>`; }
  if(x.axis1!=='타겟') o+='<span class="chip">중견기업도 함께 지원해요</span>';
  if(x.staff_floor>0) o+=`<span class="chip">직원 ${x.staff_floor}인 이상</span>`;
  if(x.planForm) o+='<span class="chip">사업계획서 서식 있어요</span>';
  return o;
}
function render(){
  const t=$('#ft').value,s=$('#fs').value,l=$('#fl').value,m=$('#fm').value,
        r=$('#fr').value,d=$('#fd').value,q=$('#fq').value.trim().toLowerCase();
  const ts=t===''?[1,2,3,4]:t==='12'?[1,2]:[+t];
  const rows=D.filter(x=>ts.includes(x.tier)
   &&(!s||(s==='pre'?x.eligible_pre:!x.eligible_pre))
   &&(!l||x.lclas===l)&&(!m||x.mlsfc===m)&&(!r||x.region===r)
   &&(!d||(d==='rolling'?x.rolling:!x.rolling))
   &&(!q||(x.title+' '+x.eligibility+' '+x.support+' '+(x.exc||'')+' '+(x.jrsd||''))
        .toLowerCase().includes(q)));
  $('#cnt').innerHTML=`<b>${rows.length}</b> / ${D.length}건`;
  $('#tb').innerHTML=rows.map(x=>`<tr>
    <td class="num"><span class="tier t${x.tier}">T${x.tier}</span></td>
    <td class="num">${esc(x.sn)}</td>
    <td class="t"><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a>
      <span class="el">${esc((x.eligibility||'').slice(0,150))}</span>
      <span class="el">${chips(x)}</span></td>
    <td class="num">${esc(x.lclas)}<br><span style="color:var(--ink-3)">${esc(x.mlsfc)}</span></td>
    <td class="num">${esc(x.region)}</td>
    <td class="num">${x.rolling
        ? esc((x.period||'상시').slice(0,16))
        : (soon(x.end)?`<span class="chip due">${esc(x.end)}</span>`:esc(x.end))}</td>
    <td>${esc(x.exc||x.jrsd||'')}</td></tr>`).join('')
   ||'<tr><td colspan="7" style="padding:var(--s6);color:var(--ink-3)">조건에 맞는 공고가 없어요</td></tr>';
  document.querySelectorAll('.cards button').forEach(b=>
    b.setAttribute('aria-pressed', String(b.dataset.t===t)));
}
['#ft','#fs','#fl','#fm','#fr','#fd'].forEach(i=>$(i).addEventListener('change',render));
$('#fq').addEventListener('input',render);
$('#reset').addEventListener('click',()=>{['#ft','#fs','#fl','#fm','#fr','#fd']
  .forEach(i=>$(i).value='');$('#fq').value='';render()});
document.querySelectorAll('.cards button').forEach(b=>b.addEventListener('click',()=>{
  $('#ft').value=b.dataset.t;render();$('#list').scrollIntoView({behavior:'smooth'})}));
render();
"""


def build_html(res: dict) -> str:
    kept, F = res["kept"], res["funnel"]
    C = Counter(x["tier"] for x in kept)
    n = len(kept)
    pre = sum(1 for x in kept if x["eligible_pre"])
    noage = sum(1 for x in kept if x["ceil"] is None and x["floor"] == 0)
    mx = max(F.values()) or 1

    def fr(num, lbl, sub, v):
        return (f'<div class="fr"><span class="n">{num}</span>'
                f'<span class="lbl">{lbl}<small>{sub}</small></span>'
                f'<span class="num">{v:,}</span></div>')

    funnel = "".join([
        fr("①", "전량", "기업마당 오픈API 응답 그대로", F["①전량"]),
        fr("②", "신청 주체가 기업인가", f'지원대상 절의 끝 명사 · −{F["①전량"]-F["②축1"]}', F["②축1"]),
        fr("③", "세부 분야 제외",
           f'융자·시험/인증·인력 · 국가 R&D 과제 · −{F["②축1"]-F["③축2"]}', F["③축2"]),
        fr("④", "계획서로 심사하지 않는 것 제외",
           f'행사 부스·고용 지원금·보증·인증 · −{F["③축2"]-F["④계획서없음"]}', F["④계획서없음"]),
        fr("⑤", "타겟 신호가 하나도 없는 것 제외",
           f'미검증 분야 + 키움 어휘 없음 + 업력 조건 없음 · −{F["④계획서없음"]-F["⑤신호없음"]}',
           F["⑤신호없음"]),
        fr("⑥", "설비·시설 지원 제외",
           f'방지시설·측정기기·스마트공장 구축 — 사업장이 있어야 내요 · −{F["⑤신호없음"]-F["⑥설비시설"]}',
           F["⑥설비시설"]),
        fr("⑦", "금융 비용 보전 제외",
           f'보증료·보험료·대출이자 — 사업에 쓸 돈이 아니에요 · −{F["⑥설비시설"]-F["⑦금융비용"]}',
           F["⑦금융비용"]),
        fr("⑧", "정부 과업 수행 배제",
           f'주관·운영·수행기관 모집 · 현장실증 · −{F["⑦금융비용"]-F["⑧과업배제"]}',
           F["⑧과업배제"]),
        fr("⑨", "소상공인 전용 제외",
           f'창업기업·중소기업도 대상이면 남겨요 · −{F["⑧과업배제"]-F["⑨소상공인제외"]}',
           F["⑨소상공인제외"]),
        fr("⑩", "특정 법인격 전용 제외",
           f'사회적경제·마을기업·장애인기업만 받는 것 · −{F["⑨소상공인제외"]-F["⑩특정법인"]}',
           F["⑩특정법인"]),
        fr("⑪", "직원 수 요건 제외",
           f'5인 이상을 요구하면 빼요 · −{F["⑩특정법인"]-F["⑪규모"]}', F["⑪규모"]),
        fr("⑫", "마감 지난 것 제외",
           f'상시 접수는 남겨요 · −{F["⑪규모"]-F["⑫마감전"]}', F["⑫마감전"]),
        fr("⑬", "업력 상한·하한",
           f'3년 미만이 배제되는 것만 빼요 · −{F["⑫마감전"]-F["⑬업력"]}', F["⑬업력"]),
    ])
    cards = "".join([
        f'<button data-t="" aria-pressed="true"><span class="k">전체</span>'
        f'<span class="v">{n}</span><span class="d">3년 미만이 지원할 수 있는 전부예요</span></button>',
        f'<button data-t="12"><span class="k">T1+T2 먼저 볼 것</span>'
        f'<span class="v">{C[1]+C[2]}</span><span class="d">키우는 사업이거나 업력 조건이 있어요</span></button>',
        f'<button data-t="1"><span class="k">T1</span><span class="v">{C[1]}</span>'
        f'<span class="d">제목에 육성·창업·경진대회가 있어요</span></button>',
        f'<button data-t="2"><span class="k">T2</span><span class="v">{C[2]}</span>'
        f'<span class="d">업력 조건이 적혀 있거나 창업 분야예요</span></button>',
        f'<button data-t="3"><span class="k">T3</span><span class="v">{C[3]}</span>'
        f'<span class="d">신호가 없을 뿐 빠진 건 아니에요</span></button>',
    ])
    data = json.dumps(kept, ensure_ascii=False, separators=(",", ":"))
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>공고 후보 {n}건 — 기업마당 필터</title>
<style>{CSS}</style></head><body>
<div class="wrap">
<header>
  <h1>3년 미만 창업가가<br>지원할 수 있는 공고 {n}건</h1>
  <p class="sub">기업마당 {F["①전량"]:,}건에서 정부 과업형을 걷어내고, 업력 조건이 우리를 막는 것만 뺐어요.
     그중 예비창업자도 지원할 수 있는 건 {pre}건이에요.</p>
  <div class="meta"><span>기준일 {res["generated"]}</span>
    <span>업력 제한 없는 공고 {noage}건</span><span>상시 접수 {sum(1 for x in kept if x["rolling"])}건</span></div>
</header>

<h2>어떻게 골랐나요</h2>
<div class="card funnel">{funnel}</div>
<p class="sub">여덟 조건을 모두 통과한 것만 남겨요. 순서는 결과를 바꾸지 않아요.
  판정은 전부 규칙이고 <b>사람이 다시 읽거나 AI 가 판단하지 않아요</b>.
  자세한 근거는 같은 폴더의 <code>로직과근거.md</code> 에 있어요.</p>

<h2>어떤 순서인가요</h2>
<p class="sub">버리지 않고 순서만 정해요. 카드를 누르면 아래 목록이 바뀌어요.</p>
<div class="cards">{cards}</div>

<h2 id="list">공고 목록</h2>
<div class="bar">
  <select id="ft"><option value="">순서 전체</option><option value="12">T1+T2</option>
    <option value="1">T1</option><option value="2">T2</option>
    <option value="3">T3</option></select>
  <select id="fs"><option value="">대상 전체</option><option value="pre">예비창업 가능</option>
    <option value="biz">사업자만</option></select>
  <select id="fl"></select><select id="fm"></select><select id="fr"></select>
  <select id="fd"><option value="">마감 전체</option><option value="date">날짜가 있어요</option>
    <option value="rolling">상시·예산 소진까지</option></select>
  <input id="fq" type="search" placeholder="공고명·지원대상·기관으로 찾기">
  <button class="plain" id="reset">처음으로</button>
  <span class="count" id="cnt"></span>
</div>
<div class="tw"><div class="scroll"><table>
  <thead><tr><th>순서</th><th>번호</th><th>공고 · 지원대상</th><th>분야</th><th>지역</th>
    <th>마감</th><th>수행기관</th></tr></thead>
  <tbody id="tb"></tbody></table></div></div>

<h2>아직 못 하는 것</h2>
<ul>
  <li><b>사업계획서로 심사하는지는 몰라요.</b> 첨부 서식을 열어야 알 수 있어요. 여기서는 파일 이름만 봐요.</li>
  <li><b>업력 조건이 없는 공고가 {noage}건이에요.</b> 조건이 없어서인지 첨부에만 적혀 있어서인지 구분하지 못해요.</li>
  <li><b>T3 {C[3]}건을 사람이 확인하지 않았어요.</b> 신호가 없다는 뜻이고 빠져야 한다는 뜻이 아니에요.</li>
  <li><b>오배제를 한 건 알고 있어요.</b> <code>민관 공동 전략형 상생협력사업(창의트랙)</code>은
      사업계획서와 발표로 심사하는데, 첨부를 열지 않으면 다른 컨설팅 공고와 구분되지 않아 함께 빠졌어요.</li>
  <li><b>지원대상 필드(<code>trgetNm</code>)는 쓰지 않아요.</b> 틀린 사례를 두 건 찾았어요.</li>
</ul>

<footer>
  기업마당 오픈API 응답 필드만 써요 · 첨부를 내려받지 않아요 · AI 를 부르지 않아요<br>
  금액 · 평가 배점 · 제출서류 · 제외 업종은 어느 응답 필드에도 없어요. 첨부 원문에만 있어요.
</footer>
</div>
<script>{JS.replace("%%DATA%%", data).replace("%%TODAY%%", json.dumps(res["generated"]))}</script>
</body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser(description="기업마당 공고 필터")
    ap.add_argument("--key", default=os.environ.get("BIZINFO_API_KEY", ""))
    ap.add_argument("--raw", help="저장해 둔 원문 JSON 으로 돌린다")
    ap.add_argument("--save-raw", action="store_true")
    ap.add_argument("--no-serve", action="store_true")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--today", default=date.today().isoformat())
    ap.add_argument("--ids", metavar="파일",
                    help="통과한 공고의 pblancId 를 한 줄에 하나씩 쓴다. "
                         "받는 쪽은 이 파일만 읽고 필터의 존재를 모른다")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    if a.raw:
        items = json.loads(pathlib.Path(a.raw).read_text(encoding="utf-8"))
        if isinstance(items, dict):
            items = items.get("jsonArray") or items.get("items") or []
        print(f"원문 {len(items):,}건 — {a.raw}")
    else:
        if not a.key:
            print("기업마당 인증키가 없습니다.\n"
                  "  BIZINFO_API_KEY=... python run.py     또는  python run.py --key ...\n"
                  "  발급: https://www.bizinfo.go.kr/apiDetail.do?id=bizinfoApi (로그인 불필요)\n"
                  "  키 없이 보려면: python run.py --raw out/raw.json", file=sys.stderr)
            return 2
        items = fetch(a.key)
        print(f"기업마당에서 {len(items):,}건 받았습니다 (요청 1회)")
        if a.save_raw:
            (OUT / "raw.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
            print(f"  원문 저장 → {OUT/'raw.json'}")

    res = run_filter(items, today=a.today)
    print("\n퍼널")
    prev = None
    for k, v in res["funnel"].items():
        print(f"  {k:<10}{v:>6}" + (f"  (−{prev-v})" if prev is not None else ""))
        prev = v
    kept = res["kept"]
    print(f"\n최종 {len(kept)}건")
    print("  순서:", dict(sorted(Counter(x['tier'] for x in kept).items())))
    print("  예비창업 가능:", sum(x["eligible_pre"] for x in kept))
    print("  업력 제한 없음:", sum(1 for x in kept if x["ceil"] is None and x["floor"] == 0))

    (OUT / "data.json").write_text(json.dumps(
        {"generated": res["generated"], "funnel": res["funnel"],
         "count": len(kept), "items": kept}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "index.html").write_text(build_html(res), encoding="utf-8")
    print(f"\n→ {OUT/'data.json'}\n→ {OUT/'index.html'}")

    if a.ids:
        # `sn` 이 아니라 `id` 다. `sn` 은 화면용 뒤 6자리라 DB 키가 아니다.
        ids = [x["id"] for x in kept if x.get("id")]
        p = pathlib.Path(a.ids)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(ids) + "\n", encoding="utf-8")
        print(f"→ {p} 에 공고번호 {len(ids):,}개")

    if a.no_serve:
        return 0

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *ar, **kw):
            super().__init__(*ar, directory=str(OUT), **kw)

        def log_message(self, *_):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", a.port), H) as srv:
        print(f"\n  http://127.0.0.1:{a.port}   (Ctrl+C 로 종료)")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\n종료했습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
