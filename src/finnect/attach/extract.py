"""해독 디스패치 — 파일 하나를 읽어 보고 **결과를 상태로 돌려준다.**

예외를 밖으로 던지지 않는다. 이 함수의 산출물은 텍스트가 아니라 **판정**이라,
실패도 정상적인 반환값이다. 조용히 건너뛰는 경로가 없어야 T-0004 가 닫힌다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from finnect.attach import formats, hwp, ocr
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

#: 그림에서 글자를 찾는 것은 비용이 세 자릿수 배 다르다. **`ocr=True` 일 때만 돈다**
#: (ADR-0030). `PARSERS` 와 나눠 둔 이유가 그것이다.
OCR_PARSER = "ocr/rapidocr-v5-server"

#: 조각을 나눠 줄 수 있는 포맷. 없으면 통짜 하나다.
#: **`PARSERS` 의 함수가 이걸 이어 붙인 것과 같아야 한다** — 좌표계가 갈리면
#: 근거 오프셋이 전부 어긋난다(wiki/chunk.py `PAGE_SEP`).
PAGERS = {
    "pdf": hwp.pages_from_pdf,
    "pptx": hwp.slides_from_pptx,
    "xlsx": hwp.sheets_from_xlsx,
}


@dataclass(slots=True)
class Parsed:
    status: ParseStatus
    ext: str | None = None
    parser: str | None = None
    text: str | None = None
    error: str | None = None
    contents: list[dict[str, object]] = field(default_factory=list)
    #: 쪽·슬라이드·시트별 텍스트. **`text` 는 이걸 줄바꿈으로 이은 것이다.**
    #: 부르는 쪽이 다시 파싱하지 않게 여기 담는다 — 안 그러면 PDF 를 두 번 읽고,
    #: OCR 이면 그 비용이 쪽당 십수 초씩 두 배가 된다.
    pages: list[str] = field(default_factory=list)


def parse(
    path: Path,
    filename: str | None = None,
    *,
    allowed: frozenset[str] | None = None,
    use_ocr: bool = False,
) -> Parsed:
    """파일 하나를 읽어 본다. **확장자는 파일명이 아니라 내용으로 정한다.**

    `allowed` 는 어느 포맷을 시도할지다. 기본은 첨부 목록이고, 사용자 파일은 자기
    목록을 넘긴다(ADR-0029) — 첨부 목록을 늘리면 plan/07 이 측정한 값이 근거를 잃는다.

    `use_ocr` 는 그림에서 글자를 찾을지다(ADR-0030). **기본이 꺼짐인 이유는 비용이다** —
    텍스트 레이어는 밀리초, OCR 은 쪽당 십수 초다. 켜면 두 곳에서 돈다.

    1. 그림 파일(jpg · png · …)
    2. **텍스트 레이어가 0자인 PDF.** 스캔본이 여기 걸린다
    """
    ext = formats.detect(path, filename)
    allowed = allowed if allowed is not None else formats.supported()

    if ext is None or ext not in allowed:
        # 안 해봤다. 해봤는데 안 된 것과 다르다.
        return Parsed(ParseStatus.UNSUPPORTED, ext)

    if ext in ocr.IMAGE_EXTS:
        if not use_ocr:
            return Parsed(ParseStatus.UNSUPPORTED, ext, error="그림이다. OCR 이 꺼져 있다")
        return _finish(_try(ocr.from_image, path, ext, OCR_PARSER), ext, OCR_PARSER)

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
    pager = PAGERS.get(ext)
    try:
        if pager is not None:
            pages = pager(path)
            text = "\n".join(pages)
        else:
            text = fn(path)
            pages = [text]
    except Exception as e:  # noqa: BLE001
        return Parsed(ParseStatus.FAILED, ext, parser, error=_why(e))

    if not text or not text.strip():
        # 파서는 돌았는데 0바이트다. 스캔 PDF 가 여기 걸린다.
        if use_ocr and ext == "pdf":
            # **텍스트 레이어를 먼저 보고 없을 때만 OCR 로 간다.** 순서를 뒤집으면
            # 읽히는 PDF 에도 쪽당 십수 초를 쓴다.
            return _finish(_try_pages(ocr.pages_from_pdf, path, ext, OCR_PARSER), ext, OCR_PARSER)
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

    return Parsed(ParseStatus.OK, ext, parser, text=text, pages=pages)


def _try(fn, path: Path, ext: str | None, parser: str) -> Parsed:  # noqa: ANN001
    """예외를 상태로 바꾼다. **OCR 이 없어도 실행이 죽지 않는다.**"""
    try:
        text = fn(path)
        return Parsed(ParseStatus.OK, ext, parser, text=text, pages=[text])
    except Exception as e:  # noqa: BLE001
        return Parsed(ParseStatus.FAILED, ext, parser, error=_why(e))


def _try_pages(fn, path: Path, ext: str | None, parser: str) -> Parsed:  # noqa: ANN001
    try:
        pages = fn(path)
        return Parsed(ParseStatus.OK, ext, parser, text="\n".join(pages), pages=pages)
    except Exception as e:  # noqa: BLE001
        return Parsed(ParseStatus.FAILED, ext, parser, error=_why(e))


def _finish(p: Parsed, ext: str | None, parser: str) -> Parsed:
    """OCR 결과도 텍스트 파서와 같은 정제를 거친다. 0자와 NUL 처리가 갈리면 안 된다."""
    if p.status != ParseStatus.OK:
        return p
    text = p.text or ""
    if not text.strip():
        return Parsed(ParseStatus.EMPTY, ext, parser, text="")
    return Parsed(
        ParseStatus.OK,
        ext,
        parser,
        text=text.replace("\x00", " "),
        pages=[pg.replace("\x00", " ") for pg in p.pages],
    )


def _why(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"[:500]
