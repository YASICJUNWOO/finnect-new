"""HWP 5.0 양식의 표 셀을 라벨로 찾아 채우고, 저장하면서 미리보기 스트림을 되살린다.

실측용 버리는 코드다. 확인하려는 것은 셋이다.

1. 라벨로 사실칸을 찾아 채우는 것이 실제 양식에서 몇 칸이나 걸리는가
2. hwplib 으로 저장한 파일이 구조와 서식을 잃지 않는가
3. hwplib 이 버리는 미리보기 스트림을 POI 로 되살릴 수 있는가

hwplib 의 HWPFile 은 PrvText·PrvImage·DocOptions 를 모델에 갖고 있지 않아서
저장할 때마다 통째로 사라진다. PrvText 는 본문에서 재현할 수 있고,
PrvImage 는 렌더링이 필요해 만들 수 없다 — 원본 것을 옮기면 채운 문서에
빈 양식 썸네일이 붙으므로 넣지 않는다.

실행:
    uv run --with hwp-hwpx-editor --with jpype1 --with olefile python spike/hwp_fill.py
"""

from __future__ import annotations

import importlib.util
import re
import shutil
from pathlib import Path

import jpype
import jpype.imports
import olefile

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "신청서"
OUT = ROOT / "data" / "신청서-채움"

# 채워 넣을 값. 테스트 페르소나 c_dasiro 를 손으로 옮긴 것이다.
값 = {
    "기업명": "주식회사 다시로",
    "회사명": "주식회사 다시로",
    "업체명": "주식회사 다시로",
    "성명": "김다시",
    "대표자": "김다시",
    "대표자명": "김다시",
    "대표자성명": "김다시",
    "생년월일": "1991.04.12.",
    "대표자생년월일": "1991.04.12.",
    "사업자등록번호": "123-45-67890",
    "연락처": "031-123-4567",
    "전화번호": "031-123-4567",
    "휴대전화": "010-1234-5678",
    "이메일": "contact@dasiro.kr",
    "email": "contact@dasiro.kr",
    "e-mail": "contact@dasiro.kr",
    "주소": "경기도 성남시 분당구",
    "소재지": "경기도 성남시 분당구",
    "사업장소재지": "경기도 성남시 분당구",
    "개업연월일": "2024. 03. 11.",
    "설립일": "2024. 03. 11.",
    "설립연월일": "2024. 03. 11.",
    "업종": "소프트웨어 개발",
    "주업종": "소프트웨어 개발",
    "상시근로자수": "15",
    "종업원수": "15",
    "직원수": "15",
}

# 라벨 옆이 비어 있어야 채운다. 이런 것이 들어 있으면 빈 칸으로 본다.
빈칸표시 = re.compile(r"^[\s0O·.\-()/년월일도시　]*$")


def _jvm() -> None:
    if jpype.isJVMStarted():
        return
    spec = importlib.util.find_spec("hwp_hwpx_editor")
    if spec is None or not spec.submodule_search_locations:
        raise SystemExit("hwp-hwpx-editor 가 없다. --with hwp-hwpx-editor 로 돌려라")
    pkg = Path(next(iter(spec.submodule_search_locations)))
    jars = sorted(pkg.rglob("*.jar"))
    if not jars:
        raise SystemExit(f"jar 를 못 찾았다: {pkg}")
    jpype.startJVM(classpath=[str(j) for j in jars])


def norm(s: str) -> str:
    return re.sub(r"[\s　:：]", "", s or "").lower()


def para_text(para) -> str:
    tx = para.getText()
    return str(tx.getNormalString(0)) if tx is not None else ""


def cell_text(cell) -> str:
    pl = cell.getParagraphList()
    parts = [para_text(pl.getParagraph(i)) for i in range(pl.getParagraphCount())]
    return " ".join(p for p in parts if p).strip()


def set_cell(cell, value: str) -> bool:
    """비어 있는 셀에만 값을 넣는다. 이미 글자가 있으면 손대지 않고 False 를 준다.

    한/글로 눈으로 확인해서 정한 경계다(15번 파일, 판본 A~G).

    - 빈 셀에 `createText()` 로 새로 만들어 넣는 것은 안전하다. 17번 16칸이 그랬고
      레이아웃이 원본과 같았다.
    - 기존 글자를 갈아 끼우면 한/글에서 배치가 무너진다. `getCharList().clear()` 가
      문단 끝 문자와 개체 앵커까지 지우는 것이 처음 원인이었는데, 그 둘을 지키고
      일반 글자만 바꿔도, 심지어 **원래와 똑같은 값을 다시 써넣어도** 표가 밀렸다.
      줄 나눔 캐시(`LineSeg`)를 지워 봐도 마찬가지였다.

    그래서 플레이스홀더(`000`·`OOOO`·`000-0000-0000`)를 지우지 못한다. 그 칸은
    사람이 손으로 지워야 한다. hwplib 이슈 #72 가 아직 열려 있는 자리이기도 하다.
    """
    para = cell.getParagraphList().getParagraph(0)
    if para.getText() is not None:
        return False
    para.createText()
    para.getText().addString(value)
    return True


def tables(hwp_file):
    body = hwp_file.getBodyText().getSectionList()
    for si in range(body.size()):
        sec = body.get(si)
        for i in range(sec.getParagraphCount()):
            cl = sec.getParagraph(i).getControlList()
            if cl is None:
                continue
            for k in range(cl.size()):
                c = cl.get(k)
                if str(c.getClass().getSimpleName()) == "ControlTable":
                    yield c


def fill(hwp_file) -> tuple[list[tuple[str, str, int]], list[tuple[str, str]]]:
    """라벨 셀을 찾아 그 오른쪽 첫 빈 셀에 값을 넣는다.

    셋째 값은 그 셀의 글자 수가 몇 자 늘었나다. 빈 칸이 아니라 플레이스홀더
    (`000-0000-0000` 같은 것)를 덮어쓰는 자리가 있어서, 넣은 값의 길이와
    실제로 늘어난 글자 수가 다르다.
    """
    채움: list[tuple[str, str, int]] = []
    포기: list[tuple[str, str]] = []
    for t in tables(hwp_file):
        rows = t.getRowList()
        for ri in range(rows.size()):
            cells = rows.get(ri).getCellList()
            for ci in range(cells.size()):
                라벨 = norm(cell_text(cells.get(ci)))
                if 라벨 not in 값:
                    continue
                for cj in range(ci + 1, cells.size()):
                    옆 = cells.get(cj)
                    본문 = cell_text(옆)
                    if norm(본문) == 라벨:  # 병합 셀이라 라벨이 반복된다
                        continue
                    if not 빈칸표시.match(본문):
                        break
                    if set_cell(옆, 값[라벨]):
                        채움.append((라벨, 값[라벨], len(cell_text(옆)) - len(본문)))
                    else:
                        포기.append((라벨, 본문))
                    break
    return 채움, 포기


def build_prvtext(hwp_file, limit: int = 1023) -> bytes:
    """한/글이 만드는 미리보기 텍스트를 본문에서 재현한다.

    문단은 그대로 쓰고, 표는 행마다 셀을 <…> 로 감싸 이어 붙인다.
    원본을 뜯어 확인한 형식이고 길이는 1,023자에서 잘린다.
    """
    lines: list[str] = []
    body = hwp_file.getBodyText().getSectionList()
    for si in range(body.size()):
        sec = body.get(si)
        for i in range(sec.getParagraphCount()):
            p = sec.getParagraph(i)
            t = para_text(p)
            if t:
                lines.append(t)
            cl = p.getControlList()
            if cl is None:
                continue
            for k in range(cl.size()):
                c = cl.get(k)
                if str(c.getClass().getSimpleName()) != "ControlTable":
                    continue
                rows = c.getRowList()
                for ri in range(rows.size()):
                    cells = rows.get(ri).getCellList()
                    lines.append(
                        "".join(f"<{cell_text(cells.get(ci))}>" for ci in range(cells.size()))
                    )
    return "\r\n".join(lines)[:limit].encode("utf-16-le")


def graft(target: Path, streams: dict[str, bytes]) -> None:
    """저장이 끝난 HWP 에 OLE 스트림을 붙인다. hwplib 이 안 쓰는 것들이다."""
    from java.io import ByteArrayInputStream, FileInputStream, FileOutputStream
    from org.apache.poi.poifs.filesystem import POIFSFileSystem

    fs = POIFSFileSystem(FileInputStream(str(target)))
    root = fs.getRoot()
    for name, data in streams.items():
        parts = name.split("/")
        node = root
        for p in parts[:-1]:
            node = node.getEntry(p) if node.hasEntry(p) else node.createDirectory(p)
        if node.hasEntry(parts[-1]):
            node.getEntry(parts[-1]).delete()
        signed = [b - 256 if b > 127 else b for b in data]
        node.createDocument(parts[-1], ByteArrayInputStream(jpype.JArray(jpype.JByte)(signed)))
    tmp = target.with_suffix(".tmp")
    out = FileOutputStream(str(tmp))
    fs.writeFilesystem(out)
    out.close()
    shutil.move(tmp, target)


def 원본스트림(path: Path, names: list[str]) -> dict[str, bytes]:
    o = olefile.OleFileIO(str(path))
    있는것 = {"/".join(s) for s in o.listdir()}
    got = {n: o.openstream(n).read() for n in names if n in 있는것}
    o.close()
    return got


def 통계(hwp_file) -> dict:
    di = hwp_file.getDocInfo()
    표 = 셀 = 글자 = 문단 = 0
    body = hwp_file.getBodyText().getSectionList()
    for si in range(body.size()):
        sec = body.get(si)
        문단 += sec.getParagraphCount()
        for i in range(sec.getParagraphCount()):
            글자 += len(para_text(sec.getParagraph(i)))
    for t in tables(hwp_file):
        표 += 1
        rows = t.getRowList()
        for ri in range(rows.size()):
            cells = rows.get(ri).getCellList()
            for ci in range(cells.size()):
                셀 += 1
                글자 += len(cell_text(cells.get(ci)))
    return dict(
        문단=문단,
        표=표,
        셀=셀,
        글자=글자,
        서식=(
            di.getCharShapeList().size(),
            di.getParaShapeList().size(),
            di.getStyleList().size(),
            di.getBorderFillList().size(),
        ),
    )


def main() -> None:
    _jvm()
    from kr.dogfoot.hwplib.reader import HWPReader
    from kr.dogfoot.hwplib.writer import HWPWriter

    OUT.mkdir(parents=True, exist_ok=True)
    files = sorted(SRC.glob("*.hwp"))
    if not files:
        raise SystemExit(f"{SRC} 에 hwp 가 없다")

    print(f"{'파일':<34} {'채움':>4} {'포기':>4} {'셀':>5} {'스트림':>7} {'용량':>16}  검증")
    print("-" * 92)
    합계 = 포기합계 = 0
    for p in files:
        f = HWPReader.fromFile(str(p))
        before = 통계(f)
        채움, 포기 = fill(f)
        합계 += len(채움)
        포기합계 += len(포기)

        dst = OUT / p.name
        HWPWriter.toFile(f, str(dst))

        # hwplib 이 버린 것 중 되살릴 수 있는 것만 붙인다.
        # PrvText 는 채운 내용으로 새로 만들고, PrvImage 는 만들 수 없어 넣지 않는다.
        살릴것 = 원본스트림(p, ["DocOptions/_LinkDoc"])
        살릴것["PrvText"] = build_prvtext(HWPReader.fromFile(str(dst)))
        graft(dst, 살릴것)

        g = HWPReader.fromFile(str(dst))
        after = 통계(g)
        늘어난글자 = after["글자"] - before["글자"]
        기대 = sum(d for _, _, d in 채움)
        구조ok = all(before[k] == after[k] for k in ("문단", "표", "셀", "서식"))
        글자ok = 늘어난글자 == 기대

        s1 = len(olefile.OleFileIO(str(p)).listdir())
        s2 = len(olefile.OleFileIO(str(dst)).listdir())
        비율 = round(dst.stat().st_size / p.stat().st_size * 100)
        표시 = "OK" if (구조ok and 글자ok) else ("구조 깨짐" if not 구조ok else f"글자 {늘어난글자}≠{기대}")
        print(
            f"{p.name[:32]:<34} {len(채움):>4} {len(포기):>4} {before['셀']:>5} "
            f"{s1:>3}→{s2:<3} {p.stat().st_size:>7,}→{dst.stat().st_size:<7,} ({비율:>3}%)  {표시}"
        )

    print(f"\n채운 칸 {합계}개 · 글자가 이미 있어 포기한 칸 {포기합계}개 · 결과 {OUT}")
    print("PrvImage 는 넣지 않았다 — 렌더링이 필요해 만들 수 없고, 원본 것을 옮기면")
    print("값을 채운 문서에 빈 양식 썸네일이 붙는다.")


if __name__ == "__main__":
    main()
