"""글자만 있는 파일 — `txt` · `md` · `csv` (T-0101).

**이 모듈이 있는 이유는 인코딩이다.** 다른 파서는 포맷이 인코딩을 정해 준다 — DOCX 와
HWPX 는 XML 이라 UTF-8 이고, HWP 는 UTF-16LE 다. 글자만 있는 파일은 아무도 안 정해 줘서
**우리가 판정해야 한다.**

한국 사용자의 `.txt` 는 CP949 가 흔하다. 윈도 메모장이 오래 그것을 기본으로 썼고 엑셀의
「CSV(쉼표로 분리)」도 한국어 윈도에서 그쪽으로 저장한다. UTF-8 만 보고 `errors="replace"`
로 받으면 **깨진 글자가 `ok` 로 앉는다** — `hwp._reject_flags` 가 막는 「107자짜리 해독
성공」과 같은 계열이고, 이쪽이 더 나쁘다. 저건 안내문이라 눈에 띄지만 이건 사람이 읽을
수 없는 글자가 사실 추출까지 흘러간다.

**확장자를 내용으로 못 판정한다.** 글자만 있는 파일에는 시그니처가 없어서
`formats.detect` 가 파일명으로 물러난다. 이 모듈에 한해서는 그것이 정상이다.
"""

from __future__ import annotations

import codecs
import csv
import io
from pathlib import Path

#: BOM → 인코딩. **BOM 이 있으면 그것이 답이고 더 안 본다.**
#:
#: 메모장의 저장 형식 셋이 여기 온다 — 「UTF-8(BOM)」 · 「유니코드」(UTF-16LE) ·
#: 「유니코드 big endian」. UTF-32 는 안 넣는다. 메모장이 안 만들고, 그 BOM 이
#: UTF-16LE BOM 으로 시작해서 **순서를 틀리면 조용히 반대로 읽힌다.**
BOMS: tuple[tuple[bytes, str], ...] = (
    (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
)

#: BOM 이 없을 때 시도할 순서. **엄격한 쪽이 먼저다.**
#:
#: **둘이 한글에서 거의 안 겹친다.** UTF-8 한글은 3바이트(EA~ED + 계속바이트 둘)인데
#: 계속바이트 `0x80` 대가 CP949 의 뒷바이트로 못 쓰이는 값이라 대개 예외가 난다 —
#: 표본 10개를 재 보니 **10개 다 예외**였다(UTF-8 로 쓴 한글을 CP949 로 읽어 봤다).
#: 거꾸로 CP949 한글의 첫 바이트는 UTF-8 에서 앞이 없는 계속바이트라 역시 안 읽힌다.
#:
#: 그래서 실무에서는 순서가 거의 안 걸린다. **그래도 UTF-8 을 먼저 둔다** — 겹치는
#: 바이트열이 원리적으로 있고, 겹칠 때 나오는 것이 예외가 아니라 **틀린 성공**이라
#: 조용히 지나간다. 값이 싼 쪽으로 실패하게 둔다.
#:
#: EUC-KR 을 따로 안 넣는 이유는 CP949 가 그 확장이라 EUC-KR 로 쓴 것을 전부 읽어서다.
ENCODINGS: tuple[str, ...] = ("utf-8", "cp949")


def from_text(path: Path) -> str:
    """`txt` · `md`. **못 읽으면 실패로 남기고 대체 문자로 안 채운다.**"""
    raw = path.read_bytes()

    for bom, enc in BOMS:
        if raw.startswith(bom):
            try:
                return raw[len(bom) :].decode(enc)
            except UnicodeDecodeError as e:
                # BOM 이 무엇인지 말했는데 그대로 안 읽힌다. 파일이 깨진 것이다.
                raise ValueError(f"BOM 은 {enc} 인데 그 인코딩으로 안 읽힌다") from e

    for enc in ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue

    raise ValueError(f"인코딩을 못 정했다 — {' · '.join(ENCODINGS)} 가 다 아니다")


def from_csv(path: Path) -> str:
    """쉼표로 나뉜 표. **`sheets_from_xlsx` 와 같은 규약이다** — 행이 줄, 셀이 탭.

    재무제표를 회계 프로그램에서 내보내면 이 모양으로 온다. 규약을 맞추는 이유는
    **좌표 때문이다** — 뭉개면 `매출액 24,100,000 86,400,000` 의 두 값이 각각 어느
    해인지 알 수 없어져 연도-항목-값 대응이 통째로 깨진다.

    직접 쪼개지 않고 `csv` 를 쓰는 이유는 인용부호다. `"성남시 분당구, 3층"` 을
    쉼표로 자르면 칸이 하나 늘어 **그 줄부터 열이 통째로 밀린다.**
    """
    out: list[str] = []
    for row in csv.reader(io.StringIO(from_text(path), newline="")):
        cells = [c.strip() for c in row]
        while cells and not cells[-1]:
            cells.pop()  # 오른쪽 빈 칸은 버린다. 탭만 남은 줄이 생긴다
        if any(cells):
            out.append("\t".join(cells))
    return "\n".join(out)
