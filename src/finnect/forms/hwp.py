"""hwp 어댑터 — **바이트로 읽고 쓴다. JVM 이 안 붙는다** ([ADR-0070](
../../../docs/adr/0070-hwp-를-바이트로-읽고-쓴다.md)).

포맷 지식은 `forms/hwp5.py` 에 있고 여기는 그것을 `Form` 프로토콜에 맞춘다.
hwplib 경로는 `forms/hwplib.py` 로 옮겨 **폴백으로만** 남았다.

## 저장이 스트림을 안 잃는다

`BodyText/Section*` 말고는 손을 안 댄다. hwplib 은 `HWPFile` 모델에 없는 스트림을
저장할 때마다 버려서 `PrvText` 를 다시 만들고 `DocOptions/_LinkDoc` 를 POI 로 옮기고
`PrvImage` 는 포기해야 했는데(ADR-0060 결정 4), **모델을 안 거치면 버릴 것이 없다.**

## 못 하는 것 둘

**① 개체 앵커가 든 문단.** hwplib 과 같은 이유다 — 그림이 닻을 내린 문단의 글을
갈아 끼우면 닻이 없어지고 한/글이 손상으로 본다(판본 B).

**② 되쓴 본문이 원본 스트림 크기 안에 안 들어가는 파일.** `olefile` 이 CFB 를 새로
못 만들어서 **같은 크기 덮어쓰기만** 된다. 한/글이 낮은 압축률로 저장해서 보통은
남지만(실측 600건 중 96.7%), 이미 촘촘히 압축된 작은 파일은 안 들어간다. 그때만
hwplib 에 넘긴다.

## 폴백에 문을 단다

넘기기 전에 **두 경로가 같은 격자를 보는지 확인한다.** 표 번호가 어긋나면 hwplib 이
다른 칸에 쓰고, **파일은 정상으로 열려서** 제출 직전에야 드러난다 — 라벨이 겹칠 때
아예 버리는 것과 같은 판단으로, 어긋나면 안 쓴다.
"""

from __future__ import annotations

from finnect.forms import hwp5
from finnect.forms.base import Anchor, Cell, FormsUnavailable, Para, ParaAnchor


class HwpForm:
    """hwp 파일 하나. **읽는 데 Java 가 필요 없다.**"""

    ext = "hwp"

    def __init__(self, path: str) -> None:
        self._path = path
        self._doc = hwp5.read(path)
        self._sub = hwp5.align_substitutes(self._doc.docinfo)
        self._boxes = {
            (b.section, b.table, b.row, b.col): b for b in self._doc.boxes()
        }
        self._blocks = {(p.section, p.index): p for p in self._doc.blocks()}
        #: 구역 → {`PARA_HEADER` 레코드 번호: 값}
        self._edits: dict[int, dict[int, str]] = {}
        #: 폴백이 그대로 다시 넣을 수 있게 남긴다
        self._filled: list[tuple[Anchor | ParaAnchor, str]] = []

    def cells(self) -> list[Cell]:
        return [
            Cell(
                Anchor(b.section, b.table, b.row, b.col),
                b.text,
                b.colspan,
                b.rowspan,
                b.width,
                b.height,
            )
            for b in self._doc.boxes()
        ]

    def paragraphs(self) -> list[Para]:
        return [Para(ParaAnchor(p.section, p.index), p.text) for p in self._doc.blocks()]

    def _locked(self, section: int, para: int) -> bool:
        """개체 앵커가 든 문단인가. **있으면 손대지 않는다.**"""
        recs = self._doc.sections[section].records
        nxt = recs[para + 1] if para + 1 < len(recs) else None
        if nxt is None or nxt[0] != hwp5.HWPTAG_PARA_TEXT:
            return False
        return hwp5.has_object_anchor(nxt[2])

    def fill(self, anchor: Anchor | ParaAnchor, value: str) -> bool:
        """그 자리에 값을 넣어 둔다. **파일은 `save()` 에서 한 번에 쓴다.**

        빈 칸이든 글자가 있든 같은 길로 간다 — 바이트 편집에는 hwplib 의 「`ParaText`
        를 살려 둔 채 갈아 끼우면 밀린다」(판본 C~G)가 해당이 없다. 레코드를 통째로
        다시 만들기 때문이다.
        """
        into_para = isinstance(anchor, ParaAnchor)
        hit = (
            self._blocks.get((anchor.section, anchor.index))
            if into_para
            else self._boxes.get((anchor.section, anchor.table, anchor.row, anchor.col))
        )
        if hit is None or hit.para < 0:
            return False
        if self._locked(anchor.section, hit.para):
            return False
        self._edits.setdefault(anchor.section, {})[hit.para] = value
        self._filled.append((anchor, value))
        return True

    def save(self, path: str) -> None:
        """채운 파일을 쓴다. **포맷을 안 바꾸고 스트림도 안 잃는다.**"""
        blobs: dict[str, bytes] = {}
        for si, values in self._edits.items():
            sec = self._doc.sections[si]
            new, _done, _refused = hwp5.edit(sec.records, values, self._sub)
            blob = (
                hwp5.pack(new, sec.raw_size)
                if self._doc.compressed
                else (new if len(new) == sec.raw_size else None)
            )
            if blob is None:
                self._save_with_hwplib(path)
                return
            blobs[sec.name] = blob
        hwp5.write_streams(self._path, path, blobs)

    def _save_with_hwplib(self, path: str) -> None:
        """원본 스트림 크기에 안 들어가는 파일만 여기 온다 (실측 5~8%).

        **격자가 같은지 먼저 본다.** 두 경로가 표를 세는 방식이 어긋나면 hwplib 이
        다른 칸에 쓰고, 그것은 빈 좌표보다 나쁘다.
        """
        try:
            from finnect.forms.hwplib import HwpLibForm
        except ImportError as e:  # pragma: no cover — jpype 가 없을 때
            msg = "이 파일은 채운 본문이 원본 크기를 넘어서 Java 가 필요해요"
            raise FormsUnavailable(msg) from e

        form = HwpLibForm(self._path)
        if {c.anchor for c in form.cells()} != set(self._boxes):
            raise FormsUnavailable(
                "이 파일은 채운 본문이 원본 크기를 넘는데, 대신 쓸 경로가 같은 칸을 못 찾아요"
            )
        for anchor, value in self._filled:
            form.fill(anchor, value)
        form.save(path)
