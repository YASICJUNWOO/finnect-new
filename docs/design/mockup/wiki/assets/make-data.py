#!/usr/bin/env python3
"""`data.js` 를 다시 만든다. **레포 루트에서 돌린다.**

    uv run python docs/design/mockup/wiki/assets/make-data.py

`tests/fixtures/wiki/facts.json` 118건을 `src/finnect/wiki/topics.py` 의 라우팅
(SLOT_ALIASES · TOPIC_NODE · ORBIT)으로 자리 열다섯에 앉히고, 원본 파일을 실제로
파싱해 파서 이름·쪽수·청크 수·근거의 쪽 번호를 얻는다.

**지어내는 값이 없다.** `page` 는 앵커를 해독 텍스트에서 찾아 얻은 것이고, 못 찾으면
`null` 이다 — hwpx·docx·xlsx 에는 쪽이라는 것이 아예 없어서 그게 정상이다.

**스캔본 둘만 손으로 맞춘다.** 이 스크립트를 돌리는 서버에 `uv sync --group ocr` 이
없으면 `사업자등록증_스캔.pdf` 와 `현장사진_파일럿매장.jpg` 가 `empty`·`unsupported`
로 나오는데, 제품은 사용자 파일에 OCR 이 켜져 있다(`USER_FILE_OCR` · ADR-0030).
안 맞추면 화면에 「안 읽혔어요 · 근거 1」 이라는 스스로 모순된 줄이 뜬다.
OCR 이 깔려 있으면 이 보정은 저절로 안 걸린다.

`data.js` 의 머리말과 꼬리(그룹 함수들)는 이 스크립트가 들고 있다 — **JS 를 손으로
고치고 이걸 다시 돌리면 그 수정이 날아간다.** 고칠 일이 있으면 여기를 고친다.
"""

from __future__ import annotations

import json
import pathlib

from finnect.attach import extract
from finnect.config import settings
from finnect.wiki import chunk as chunker
from finnect.wiki import topics as T

ROOT = pathlib.Path(__file__).resolve().parents[4]
FIX = ROOT / "tests/fixtures/wiki"
OUT = ROOT / "docs/design/mockup/wiki/data.js"

#: 쪽 번호를 갖는 포맷. `service.py` 의 `NUMBERED` 와 같은 판정이다 —
#: **쪽 수가 아니라 포맷으로 정한다.** 1쪽짜리 PDF 도 그 1쪽이 어딘지 안다
NUMBERED = {"pdf", "pptx"}


def squash(s: str) -> str:
    """공백을 지운 대조용 문자열. `tests/test_wiki_extract.py` 와 같은 규칙이다."""
    return "".join(s.split())


def build() -> dict:
    table = json.loads((FIX / "facts.json").read_text(encoding="utf-8"))
    slot_home = {s: k for k, o in T.ORBIT.items() for s in o.slots}
    node_home = {o.node: k for k, o in T.ORBIT.items() if o.node}

    files: list[dict] = []
    facts: list[dict] = []

    for entry in table["files"]:
        path = FIX / entry["filename"]
        ext = path.suffix.lstrip(".").lower()
        parsed = extract.parse(
            path, entry["filename"], allowed=settings.wiki_formats, use_ocr=settings.user_file_ocr
        )
        pages = parsed.pages or [parsed.text or ""]
        numbered = ext in NUMBERED
        pieces = chunker.split(pages, numbered=numbered or None)
        page_text = [(p.page, squash(p.text)) for p in pieces] if numbered else []

        status = str(getattr(parsed.status, "value", parsed.status))
        parser = parsed.parser
        chunk_count = len(pieces)
        # OCR 이 없는 서버에서 돌린 경우의 보정. 위 docstring 참조
        if status != "ok" and (entry.get("facts") or []):
            status, parser, chunk_count = "ok", "ocr/rapidocr", 1

        files.append({
            "filename": entry["filename"],
            "ext": ext,
            "as_of": entry.get("as_of"),
            "parser": parser,
            "parse_status": status,
            "page_count": len(pages) if numbered else None,
            "chunk_count": chunk_count,
        })

        for fact in entry.get("facts") or []:
            anchor = squash(fact["anchor"])
            page = next((pg for pg, txt in page_text if pg and anchor in txt), None)

            if fact["kind"] == "slot":
                slot = T.slot_of(fact.get("key"))
                spec = T.SLOTS.get(slot) if slot else None
                rec = {
                    "kind": "slot",
                    "home": slot_home.get(slot) if slot else None,
                    "slot": slot,
                    "label": spec.label if spec else fact.get("key"),
                    "qualifier": fact.get("qualifier"),
                    "value": fact.get("value"),
                    "display": T.display(slot, fact["value"]) if slot else fact.get("value"),
                    "eligibility": bool(spec and spec.eligibility),
                    "dated": bool(spec and spec.dated),
                }
            else:
                rec = {
                    "kind": "node",
                    "home": node_home.get(T.node_of(fact.get("topic"))),
                    "fact_key": fact.get("fact_key"),
                    "topic": fact.get("topic"),
                }

            rec["home"] = rec["home"] or T.UNCATEGORIZED
            rec.update({
                "text": fact["text"],
                "anchor": fact["anchor"],
                "file": entry["filename"],
                "page": page,
                "as_of": fact.get("as_of") or entry.get("as_of"),
                "raw_key": fact.get("key"),
            })
            facts.append(rec)

    return {
        "sectors": T.SECTORS,
        "orbit": [
            {"key": k, "label": o.label, "kind": o.kind, "sector": o.sector,
             "slots": list(o.slots), "node": o.node}
            for k, o in T.ORBIT.items()
        ],
        "slots": {
            k: {"label": v.label, "dated": v.dated, "qualified": v.qualified,
                "eligibility": v.eligibility, "unit": v.unit}
            for k, v in T.SLOTS.items()
        },
        "files": files,
        "facts": facts,
    }


def main() -> None:
    data = build()
    text = OUT.read_text(encoding="utf-8")
    head, _, rest = text.partition("  var D = ")
    _, _, tail = rest.partition("\n  ;\n") if "\n  ;\n" in rest else ("", "", None)
    if tail is None:
        # 꼬리를 `;\n\n  /* 오늘.` 로 찾는다 — data.js 의 구조에 맞춘 것이다
        idx = rest.index(";\n\n  /* 오늘.")
        tail = rest[idx + 1:]
    body = json.dumps(data, ensure_ascii=False, indent=1)
    OUT.write_text(head + "  var D = " + body + ";" + tail, encoding="utf-8")

    placed = sum(1 for f in data["facts"] if f["home"] != T.UNCATEGORIZED)
    pages = sum(1 for f in data["facts"] if f["page"])
    print(f"파일 {len(data['files'])} · 사실 {len(data['facts'])} "
          f"· 자리 배치 {placed} · 못 찾음 {len(data['facts']) - placed} · 쪽수 붙은 근거 {pages}")
    print(f"→ {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
