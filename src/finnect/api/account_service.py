"""베타 입장 게이트 — 이름을 `company_id` 로 바꾼다(ADR-0066).

**`company_id` 를 발급하는 유일한 자리다.** 그전까지 그 값은 `?company=` 로 손으로
적히는 것이었고(`c_dasiro`·`c_narin`), 사람이 여럿 되면서 서버가 정해야 하게 됐다.

**이름을 그대로 `company_id` 로 쓰지 않는다.** `wiki/storage.py` 의 `_COMPANY_ID` 가
경로 탈출을 막으려고 영숫자·`_`·`-` 만 받는데 테스터가 적는 이름은 「다시로」다.
바꿔 쓰는 규칙(로마자화·해시)을 만들면 그 규칙이 두 이름을 한 자리로 접는 날이 오고,
그날 남의 위키가 열린다. **관계없는 값을 발급하고 표를 통해 잇는다.**
"""

from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from finnect.models import CompanyAccount


class WrongPassword(ValueError):
    """아는 이름인데 비밀번호가 다르다. **「없는 이름」과 구분하지 않는다** —
    부르는 쪽이 둘 다 같은 문장으로 답해야 이름 존재 여부가 안 새어 나간다."""


def new_company_id() -> str:
    """`c_` + hex 12자. **`wiki/storage.py` 의 `_COMPANY_ID` 를 통과해야 한다.**

    앞이 글자여야 해서(`^[A-Za-z0-9]`) 접두를 붙이고, 그 접두가 `c_dasiro` 처럼
    손으로 적힌 기존 값과 모양을 맞춘다.

    **`hash()` 나 `random` 을 안 쓴다** — 앞은 프로세스마다 다르고(plan/12 T-0094)
    뒤는 예측 가능하다. 이 값이 곧 남의 위키를 여는 열쇠라 추측이 되면 안 된다.
    """
    return f"c_{secrets.token_hex(6)}"


def enter(session: Session, name: str, password: str) -> CompanyAccount:
    """처음 보는 이름이면 만들고, 아는 이름이면 대조한다.

    **가입과 로그인을 안 나눈다.** 베타에서 그 둘을 가르면 화면이 둘이 되고 "이미
    가입하셨나요?" 를 사람이 기억해야 한다. 여기서는 같은 이름에 같은 비밀번호를
    적으면 늘 같은 위키로 들어간다.

    **비밀번호 대조에 `compare_digest` 를 쓴다.** 평문이라 해시 비교의 뜻은 없지만
    `==` 은 앞글자부터 갈리는 지점에서 일찍 돌아온다.
    """
    row = session.scalars(select(CompanyAccount).where(CompanyAccount.name == name)).one_or_none()
    if row is None:
        row = CompanyAccount(company_id=new_company_id(), name=name, password=password)
        session.add(row)
        session.flush()
        return row

    if not secrets.compare_digest(password.encode(), row.password.encode()):
        raise WrongPassword(name)
    return row
