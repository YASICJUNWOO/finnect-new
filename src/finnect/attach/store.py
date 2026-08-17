"""콘텐츠 주소 저장 — `data/attachments/<sha256[:2]>/<sha256>`.

**저장소를 옮길 때 바뀌는 유일한 파일이다**(ADR-0022 되돌리는 조건). 오브젝트 스토리지로
가더라도 여기 네 함수만 갈면 된다.

파일 이름을 공고 ID 나 첨부 ID 로 짓지 않는 이유는 재수집이다. 공고가 갱신되면 `attachment`
행이 통째로 지워지고 다시 깔려서 ID 기반 이름은 그때 고아가 된다. 내용 해시로 지으면
같은 파일이 다시 와도 같은 자리다.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from finnect.config import settings


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel_path(sha: str, suffix: str = "") -> str:
    """저장 루트 기준 상대 경로. DB 에는 이것만 들어간다."""
    return f"{sha[:2]}/{sha}{suffix}"


def abs_path(rel: str) -> Path:
    return settings.attachment_dir / rel


def put(data: bytes, suffix: str = "") -> str:
    """바이트를 저장하고 상대 경로를 돌려준다. 같은 내용이면 다시 안 쓴다."""
    rel = rel_path(digest(data), suffix)
    target = abs_path(rel)
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        # 같은 파일을 두 프로세스가 쓰면 반쪽짜리가 남는다. 임시 파일에 쓰고 이름을 바꾼다.
        tmp = target.with_suffix(target.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(target)
    return rel


def put_text(sha: str, text: str) -> str:
    """추출 텍스트는 원본 옆에 `.txt` 로. 이름은 **원본의** 해시를 쓴다."""
    rel = rel_path(sha, ".txt")
    target = abs_path(rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(target)
    return rel


def exists(rel: str | None) -> bool:
    return bool(rel) and abs_path(rel).exists()  # type: ignore[arg-type]
