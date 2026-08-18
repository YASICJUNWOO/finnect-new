"""해독 디스패치 — 파일 하나를 읽어 보고 **결과를 상태로 돌려준다.**

예외를 밖으로 던지지 않는다. 이 함수의 산출물은 텍스트가 아니라 **판정**이라,
실패도 정상적인 반환값이다. 조용히 건너뛰는 경로가 없어야 T-0004 가 닫힌다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from finnect.attach import formats, hwp
from finnect.models import ParseStatus

#: 확장자 → (함수, 파서 이름). 여기 있어도 설정 목록에 없으면 안 돈다.
PARSERS = {
    "hwp": (hwp.from_hwp, "hwp/ole"),
    "hwpx": (hwp.from_hwpx, "hwpx/zip"),
    "docx": (hwp.from_docx, "docx/zip"),
    "docm": (hwp.from_docx, "docx/zip"),
    "pdf": (hwp.from_pdf, "pdf/plumber"),
    # 사용자 파일 전용(plan/12 T-0042). 첨부 목록에 없으면 여기 있어도 안 돈다.
    "xlsx": (hwp.from_xlsx, "xlsx/openpyxl"),
    "pptx": (hwp.from_pptx, "pptx/python-pptx"),
}


@dataclass(slots=True)
class Parsed:
    status: ParseStatus
    ext: str | None = None
    parser: str | None = None
    text: str | None = None
    error: str | None = None
    contents: list[dict[str, object]] = field(default_factory=list)


def parse(
    path: Path,
    filename: str | None = None,
    *,
    allowed: frozenset[str] | None = None,
) -> Parsed:
    """파일 하나를 읽어 본다. **확장자는 파일명이 아니라 내용으로 정한다.**

    `allowed` 는 어느 포맷을 시도할지다. 기본은 첨부 목록이고, 사용자 파일은 자기
    목록을 넘긴다(ADR-0029) — 첨부 목록을 늘리면 plan/07 이 측정한 값이 근거를 잃는다.
    """
    ext = formats.detect(path, filename)
    allowed = allowed if allowed is not None else formats.supported()

    if ext is None or ext not in allowed:
        # 안 해봤다. 해봤는데 안 된 것과 다르다.
        return Parsed(ParseStatus.UNSUPPORTED, ext)

    if ext == "zip":
        try:
            return Parsed(ParseStatus.CONTAINER, ext, "zip/list", contents=hwp.zip_listing(path))
        except Exception as e:  # noqa: BLE001 — 어떤 예외든 상태로 남긴다
            return Parsed(ParseStatus.FAILED, ext, "zip/list", error=_why(e))

    entry = PARSERS.get(ext)
    if entry is None:
        # 설정에는 있는데 파서가 없다. 설정을 잘못 넣으면 여기로 온다.
        return Parsed(ParseStatus.UNSUPPORTED, ext, error="지원 목록에 있으나 파서가 없다")

    fn, parser = entry
    try:
        text = fn(path)
    except Exception as e:  # noqa: BLE001
        return Parsed(ParseStatus.FAILED, ext, parser, error=_why(e))

    if not text or not text.strip():
        # 파서는 돌았는데 0바이트다. 스캔 PDF 가 여기 걸린다 — T-0007 의 입력이다.
        return Parsed(ParseStatus.EMPTY, ext, parser, text="")

    # 저장할 수 없는 텍스트는 여기서 실패로 잡는다. 저장 단계에서 터지면 실행이 통째로
    # 죽고, 그때까지 받은 파일의 상태가 안 남는다. **조용히 고치지도 않는다.**
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as e:
        return Parsed(ParseStatus.FAILED, ext, parser, error=f"UTF-8 로 저장할 수 없다: {e}")

    # NUL 이 섞여 온다. PostgreSQL 의 text 가 못 받는다.
    # **지우지 않고 공백으로 바꾼다** — 길이가 달라지면 근거 오프셋이 어긋난다(ADR-0014).
    text = text.replace("\x00", " ")

    return Parsed(ParseStatus.OK, ext, parser, text=text)


def _why(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"[:500]
