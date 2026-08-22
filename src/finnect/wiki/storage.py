"""사용자 파일 원본 저장 — `data/user-files/<company_id>/<sha256[:2]>/<sha256>`.

**저장소를 옮길 때 바뀌는 유일한 파일이다**(ADR-0029 되돌리는 조건). 오브젝트
스토리지로 가더라도 호출부는 안 고치고 여기 구현만 더한다.

`attach/store.py` 와 형태가 닮았지만 **다른 파일이어야 한다.** 차이가 둘이다.

1. **모든 함수가 `company_id` 를 받는다.** 이것이 격리를 코드에서 강제하는 지점이다.
   `company_id` 없이 사용자 파일에 닿는 함수를 만들지 않는다.
2. **회사 사이 중복 제거를 하지 않는다.** 두 회사가 같은 정부 양식을 올리면 두 벌
   저장된다. 해시를 공유하면 한쪽이 탈퇴할 때 무엇을 지울지가 정해지지 않는다
   (ADR-0029 4번). 우리가 필요한 중복 제거는 한 회사 안에서다.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from finnect.config import settings

#: 경로에 들어가므로 형태를 제한한다. 경로 탈출(`..`)과 구분자를 원천 차단한다.
_COMPANY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class IsolationError(ValueError):
    """company_id 가 경로에 쓸 수 없는 모양이다. 조용히 넘기지 않는다."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _company_dir(company_id: str) -> Path:
    if not _COMPANY_ID.match(company_id or ""):
        raise IsolationError(f"쓸 수 없는 company_id: {company_id!r}")
    return settings.user_file_dir / company_id


def rel_path(sha: str) -> str:
    """회사 디렉터리 기준 상대 경로. **company_id 를 포함하지 않는다** —
    DB 에 company_id 가 따로 있고, 두 곳에 같은 값을 두면 어긋날 자리가 생긴다."""
    return f"{sha[:2]}/{sha}"


def abs_path(company_id: str, sha: str) -> Path:
    return _company_dir(company_id) / rel_path(sha)


def writable() -> bool:
    """여기에 파일을 쓸 수 있나. **올리기를 받기 전에 물어본다**(plan/15 · ADR-0034).

    배포본은 번들이 읽기 전용이고 함수 파일시스템이 휘발성이라 `put()` 이 `OSError` 로
    터진다. 그대로 두면 **사용자가 파일을 다 올린 뒤에 500 을 본다** — 가장 늦고 가장
    안 좋은 자리다. 미리 물어 503 으로 정직하게 답하는 편이 낫다.

    실제로 써 보는 것 말고 판정할 방법이 없다. `os.access` 는 컨테이너에서 거짓말을 한다.
    """
    try:
        settings.user_file_dir.mkdir(parents=True, exist_ok=True)
        probe = settings.user_file_dir / ".writable"
        probe.write_bytes(b"")
        probe.unlink()
    except OSError:
        return False
    return True


def put(company_id: str, data: bytes) -> str:
    """원본을 저장하고 sha256 을 돌려준다. 같은 회사가 같은 파일을 다시 올리면 안 쓴다."""
    sha = digest(data)
    target = abs_path(company_id, sha)
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        # 두 프로세스가 같이 쓰면 반쪽이 남는다. 임시 파일에 쓰고 이름을 바꾼다.
        tmp = target.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(target)
    return sha


def exists(company_id: str, sha: str) -> bool:
    return abs_path(company_id, sha).exists()


def read(company_id: str, sha: str) -> bytes:
    return abs_path(company_id, sha).read_bytes()


def delete(company_id: str, sha: str) -> bool:
    """원본 하나를 지운다. **자리는 여기서 안 지운다**(ADR-0029 5번)."""
    target = abs_path(company_id, sha)
    if not target.exists():
        return False
    target.unlink()
    return True


def purge(company_id: str) -> bool:
    """탈퇴. 회사 디렉터리를 통째로 지운다.

    격리를 경로에서 걸어 둔 값이 여기서 돌아온다 — 고아 파일을 찾아 돌 필요가 없다.
    """
    target = _company_dir(company_id)
    if not target.exists():
        return False
    shutil.rmtree(target)
    return True


def put_text(company_id: str, sha: str, text: str) -> None:
    """해독 텍스트를 원본 옆에 `.txt` 로. 이름은 **원본의** 해시다(`attach/store.py` 와 같다).

    청크가 자기 텍스트를 들고 있는데도 이걸 두는 이유는 **다시 쪼갤 때**다. 청킹 규칙을
    고쳤을 때 원본을 다시 파싱하지 않아도 되고, `char_start`/`char_end` 가 가리키는
    좌표계가 실제로 남아 있어야 되짚을 수 있다.
    """
    target = abs_path(company_id, sha).with_suffix(".txt")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".txt.part")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(target)


def read_text(company_id: str, sha: str) -> str | None:
    target = abs_path(company_id, sha).with_suffix(".txt")
    return target.read_text(encoding="utf-8") if target.exists() else None
