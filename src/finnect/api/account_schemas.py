"""베타 입장 게이트 응답 모양(ADR-0066).

**`SPEC.md` §6 이 계정을 범위 밖으로 두고 있고 이것이 그 예외다.** 베타 테스터끼리
데이터가 안 섞이게 하는 것이 유일한 목적이라, 진짜 계정이 갖는 것(이메일·재설정·세션
만료·권한)이 여기 하나도 없다. 늘리고 싶어지면 그때 ADR 을 새로 쓴다.
"""

from __future__ import annotations

from pydantic import BaseModel


class AccountIn(BaseModel):
    """입장 요청. **가입과 로그인을 안 나눈다** — 처음 보는 이름이면 만들고
    아는 이름이면 대조한다. 화면에 폼이 하나뿐인 이유다."""

    #: 사용자가 적은 회사명. **이것이 `company_id` 가 아니다** — 경로에 들어가는 값은
    #: 서버가 발급한다(`account_service.enter`)
    name: str
    #: 평문으로 온다. 평문으로 저장한다(ADR-0066 결정 2)
    password: str


class AccountOut(BaseModel):
    """입장 결과.

    **`password` 를 되돌려 주지 않는다.** 화면이 쓸 일이 없고, 응답에 실리면
    브라우저 기록과 로그에 남는다.
    """

    #: 발급된 격리 키. 쿠키에 이 값이 앉고 이후 모든 경로가 이걸 쓴다
    company_id: str
    #: 사용자가 적은 이름 그대로. 화면이 "○○님" 을 적을 때 쓴다
    name: str
