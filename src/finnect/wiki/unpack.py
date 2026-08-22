"""묶음을 푼다 — T-0102.

**첨부와 반대로 결정했다.** 공고 첨부는 목록만 읽고 안 푼다(ADR-0022 4번) — 166건 안에
799개가 있다는 것만 세어 두고 멈췄다. 사용자 파일은 푼다. 이유가 둘이다.

1. **사용자가 묶어서 던진다.** "가진 파일을 통째로 던지면" 이 제품의 첫 문장인데, 메일로
   받은 제출서류 한 벌은 대개 zip 하나다. 안 풀면 그 사람의 위키가 빈다.
2. **안쪽 파일이 제 행을 가져야 근거가 산다**(ADR-0014). 어느 파일에서 나온 청크인지는
   **나중에 붙일 수 없다.**

이 모듈은 바이트만 다룬다. 행을 만드는 것은 `wiki/service.py` 다 — 나눈 이유는
상한 판정이 DB 없이 테스트돼야 해서다.

**ZIP 이라고 다 묶음이 아니다.** HWPX · DOCX · XLSX · PPTX 가 전부 ZIP 이라,
`is_archive` 가 안 걸러 주면 문서 하나를 풀어 XML 조각 수십 개를 위키에 붓는다.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass

from finnect.attach import formats
from finnect.config import settings

#: 묶음 부스러기. 맥이 만드는 것과 숨김 파일이다. **세고 버린다.**
JUNK_PREFIXES = ("__MACOSX/",)


class BadArchive(RuntimeError):
    """묶음을 못 열었다. **조용히 빈 목록을 주지 않는다** — 부르는 쪽이 실패로 남긴다."""


@dataclass(frozen=True, slots=True)
class Member:
    """묶음 안의 파일 하나.

    `name` 은 **묶음 안의 경로 전체다.** `별첨1.hwp` 가 아니라 `제출서류/별첨1.hwp` 다 —
    사용자가 자기 묶음에서 그 파일을 찾을 수 있어야 하고, 이름만 남기면 같은 이름이
    폴더 둘에 있을 때 화면에 같은 줄이 두 번 뜬다.

    **이 이름으로 경로를 만들지 않는다.** 저장은 콘텐츠 주소라(`storage.put`) 이 값은
    DB 의 `filename` 으로만 간다 — `../` 가 섞여 있어도 밖으로 못 나간다.
    """

    name: str
    data: bytes


@dataclass(frozen=True, slots=True)
class Expanded:
    """푼 결과. **버린 것을 셋으로 나눠 센다** — 뜻이 다르다."""

    members: list[Member]
    #: 묶음 부스러기. 디렉터리 · `__MACOSX/` · 숨김 파일. **사용자 파일이 아니다**
    skipped: int = 0
    #: 상한에 걸려 못 푼 것. **사용자 파일인데 안 넣은 것이라 말해 줘야 한다**
    dropped: int = 0
    #: 총합·개수 상한을 쳤나. **개별 상한은 여기 안 든다** — 저건 그 파일 하나의 사정이고
    #: 이건 "묶음이 너무 커서 뒤를 못 봤다" 라 사용자가 할 일이 다르다
    limit_hit: bool = False


def is_archive(data: bytes) -> bool:
    """풀어야 할 묶음인가. **문서는 아니라고 답한다.**"""
    if not data.startswith(b"PK\x03\x04"):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = set(z.namelist())
    except (zipfile.BadZipFile, OSError):
        return False
    return formats.zip_kind(names) is None


def _is_junk(name: str) -> bool:
    if name.startswith(JUNK_PREFIXES):
        return True
    base = name.rsplit("/", 1)[-1]
    return not base or base.startswith(".")


def expand(
    data: bytes,
    *,
    max_files: int | None = None,
    max_total_bytes: int | None = None,
    max_member_bytes: int | None = None,
) -> Expanded:
    """묶음 하나를 안쪽 파일들로. **깊이 1이다** — 안쪽 zip 은 안 푼다.

    재귀를 열면 깊이 상한 · 순환 · 총합 계산이 전부 다시 필요한데 그걸 정할 실측이
    없다. 안쪽 zip 은 제 행으로 남아서 **있다는 사실은 남는다.**

    상한이 셋인 이유는 각각 다른 것을 막아서다.

    - `max_member_bytes` — 파일 하나가 너무 크다. **그 파일만 뺀다**
    - `max_total_bytes` — 압축률이 높다. 개별 상한만으로는 못 막는다
    - `max_files` — 파일이 너무 많다. 행 수천 개가 한 번에 생기는 것을 막는다
    """
    max_files = max_files if max_files is not None else settings.user_zip_max_files
    max_total_bytes = (
        max_total_bytes
        if max_total_bytes is not None
        else settings.user_zip_max_mb * 1024 * 1024
    )
    max_member_bytes = (
        max_member_bytes
        if max_member_bytes is not None
        else settings.user_file_max_mb * 1024 * 1024
    )

    members: list[Member] = []
    skipped = dropped = total = 0
    limit_hit = False

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for info in z.infolist():
                if info.is_dir() or _is_junk(info.filename):
                    skipped += 1
                    continue

                if len(members) >= max_files:
                    dropped += 1
                    limit_hit = True
                    continue

                # **선언된 크기를 믿지 않는다.** 헤더의 `file_size` 는 묶은 쪽이 적은
                # 값이라 거짓말일 수 있다. 한도보다 한 바이트만 더 읽어 보면 메모리를
                # 안 터뜨리고 판정된다 — 그냥 `z.read()` 하면 그 전에 다 풀린다.
                with z.open(info) as fp:
                    payload = fp.read(max_member_bytes + 1)

                if len(payload) > max_member_bytes:
                    # 이 파일만 뺀다. 나머지는 그대로 간다
                    dropped += 1
                    continue

                if total + len(payload) > max_total_bytes:
                    dropped += 1
                    limit_hit = True
                    continue

                total += len(payload)
                members.append(Member(info.filename, payload))
    except (zipfile.BadZipFile, OSError) as e:
        raise BadArchive(f"묶음을 못 열었다: {e}") from e

    return Expanded(members=members, skipped=skipped, dropped=dropped, limit_hit=limit_hit)
