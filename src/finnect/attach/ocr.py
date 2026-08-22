"""그림에서 글자를 찾는다 — RapidOCR (ADR-0030).

**기본으로 안 돈다.** 텍스트 레이어를 읽는 것과 그림에서 글자를 찾는 것은 비용이
세 자릿수 배 다르다 — 밀리초 대 십수 초. 부르는 쪽이 켠다.

임포트를 함수 안에서 하는 이유는 배포본이다. `requirements.txt` 는 읽기 경로만 싣고
(ADR-0026) 서버리스 함수에 ONNX 런타임을 넣을 이유가 없다.

**검출 모델을 `server` 로 못 박은 것이 이 파일의 요점이다.** 기본값(`small`)으로는
사업자등록증의 소재지와 업종이 아예 안 나온다 — 실측 5/8 대 7/8. 그 둘이 자격 판별의
입력이라 5배 느린 것을 받는다.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

log = logging.getLogger(__name__)

#: 그림 파일. PDF 는 여기 없다 — 텍스트 레이어를 먼저 보고 없을 때만 OCR 로 간다.
#:
#: **`heic` 는 PIL 이 기본으로 못 연다**(T-0100). `pillow-heif` 가 붙어야 하고 그것은
#: `ocr` 그룹에 있다 — 없으면 `from_image` 가 이유를 남기고 실패한다. **넣어 두는 이유는
#: 아이폰 사진 기본 포맷이라서다** — 사업자등록증이 거의 사진이고 자격 판별 입력 다섯 중
#: 넷이 거기서 나온다. 빼면 그 파일이 「지원 목록에 없는 포맷」으로 조용히 잘린다.
IMAGE_EXTS = frozenset({"jpg", "png", "gif", "bmp", "tiff", "webp", "heic"})

#: 렌더 해상도. 200 → 300 에서 실측 차이가 없었으나 300 이 안전한 쪽이다.
DPI = 300

#: 그림을 이 정도 긴 변까지 키운 뒤 넣는다. **PDF 경로와 실효 해상도를 맞추는 값이다** —
#: A4 를 300dpi 로 렌더하면 2339px 이 나온다.
#:
#: 안 맞추면 조용히 실패한다. 1400x1050 사진에서 글자를 하나(`Ⅲ`)만 읽고 `ok` 로
#: 기록됐는데, 2배로 키우니 `2025.07.14` 와 `자체QR부착구간` 이 나왔다.
MIN_LONG_SIDE = 2300

#: 확대 상한. 아이콘만 한 그림을 4배 넘게 늘려도 없던 글자가 생기지는 않는다.
MAX_SCALE = 4.0

_engine: Any = None


class OcrUnavailable(RuntimeError):
    """rapidocr 가 없다. **조용히 0자를 돌려주지 않는다.**"""


def available() -> bool:
    try:
        import rapidocr  # noqa: F401
    except ImportError:
        return False
    return True


def engine() -> Any:
    """모델을 한 번만 올린다. 매번 만들면 로딩이 인식보다 오래 걸린다."""
    global _engine
    if _engine is not None:
        return _engine
    try:
        from rapidocr import RapidOCR
        from rapidocr.utils.typings import LangRec, ModelType, OCRVersion
    except ImportError as e:  # pragma: no cover - 설치 여부에 달렸다
        raise OcrUnavailable("rapidocr 가 없다. uv sync --group ocr") from e

    # 인식과 검출을 **둘 다 PP-OCRv5 로** 맞춘다. Rec 만 korean 으로 주면
    # 기본 검출이 PP-OCRv6 이고 그 버전에 한국어 인식 모델이 없어서 터진다.
    _engine = RapidOCR(
        params={
            "Rec.lang_type": LangRec.KOREAN,
            "Rec.model_type": ModelType.MOBILE,
            "Rec.ocr_version": OCRVersion.PPOCRV5,
            "Det.ocr_version": OCRVersion.PPOCRV5,
            "Det.model_type": ModelType.SERVER,  # ← 5/8 을 7/8 로 만드는 한 줄
        }
    )
    return _engine


def _read(img: Any) -> str:
    """인식 결과를 줄바꿈으로 이어 붙인다.

    **신뢰도로 걸러내지 않는다.** 모델이 자기에게 매긴 점수라 눈금이 없고, 실측에서
    맞은 줄과 틀린 줄의 점수가 겹쳤다. 거르면 맞은 것도 같이 버린다.
    """
    res = engine()(img)
    return "\n".join(t for t in (res.txts or []) if t and t.strip())


def upscale(im: PILImage) -> PILImage:
    """작은 그림을 키운다. **PDF 경로가 300dpi 로 렌더하는 것과 같은 일이다.**"""
    from PIL import Image

    long_side = max(im.size)
    if long_side >= MIN_LONG_SIDE:
        return im
    scale = min(MIN_LONG_SIDE / long_side, MAX_SCALE)
    return im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)


_heif: bool | None = None


def heif_ready() -> bool:
    """HEIC 를 PIL 에 붙인다. **한 번만 한다.**

    없어도 다른 그림은 그대로 읽히므로 여기서 멈추지 않는다 — `rapidocr` 이 없는 것과
    다른 사실이다. 저건 OCR 자체가 없는 것이고 이건 포맷 하나를 못 여는 것이다.
    """
    global _heif
    if _heif is None:
        try:
            import pillow_heif

            pillow_heif.register_heif_opener()
            _heif = True
        except ImportError:
            log.info("pillow-heif 가 없다. HEIC 는 못 읽는다 — uv sync --group ocr")
            _heif = False
    return _heif


def from_image(path: Path) -> str:
    import numpy as np
    from PIL import Image, UnidentifiedImageError

    registered = heif_ready()
    try:
        with Image.open(path) as im:
            return _read(np.array(upscale(im.convert("RGB"))))
    except UnidentifiedImageError:
        # **왜 못 열었는지 남긴다.** 그냥 올려보내면 화면이 "cannot identify image file" 을
        # 말하고, 사용자는 파일이 깨진 줄 안다. 실제로는 우리 쪽에 패키지가 없는 것이다.
        if not registered:
            raise OcrUnavailable(
                "HEIC 일 수 있는데 pillow-heif 가 없다 — uv sync --group ocr"
            ) from None
        raise


def pages_from_pdf(path: Path) -> list[str]:
    """스캔 PDF 를 쪽별로. **쪽 번호가 여기서만 살아난다**(ADR-0014)."""
    import numpy as np
    import pypdfium2 as pdfium

    out: list[str] = []
    doc = pdfium.PdfDocument(str(path))
    try:
        for page in doc:
            img = page.render(scale=DPI / 72).to_pil()
            out.append(_read(np.array(img)))
    finally:
        doc.close()
    return out


def from_pdf(path: Path) -> str:
    return "\n".join(pages_from_pdf(path))
