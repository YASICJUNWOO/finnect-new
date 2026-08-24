"""테스트 세션에서만 `.env` 의 값 둘을 무르게 한다 — `API_TOKEN` 과 데모 플래그.

**`.env` 에 값이 들어 있어서 필요해진 자리다.** `config.py` 의 `api_token` 주석이
「로컬에서 토큰을 강제하면 테스트가 전부 토큰을 들고 다녀야 해서 대가가 더 크다」고
적어 둔 그 대가가, 로컬을 배포본과 같은 모양으로 돌리기로 하면서 실제로 왔다 —
안 비우면 `require_token` 이 켜져서 **API 테스트 28개가 401** 이 된다.

**토큰 문을 재는 테스트는 안 막힌다.** `tests/test_api_token.py` 와
`tests/test_admin_auth.py` 는 `settings.api_token` 을 직접 monkeypatch 하므로
여기서 무엇을 하든 자기가 쓸 값을 스스로 세운다.

**`ADMIN_USER`·`ADMIN_PASSWORD` 와 `INGEST_TRIGGER_TOKEN` 은 안 건드린다.** 저 셋은
비어 있으면 503 이라 오히려 채워져 있는 쪽이 배포본과 같은 모양이고, 실제로 지금
테스트가 그 상태로 전부 통과한다.

## 데모 플래그도 같은 자리다

`DEMO_RECOMMENDATIONS` 를 `.env` 에 넣으면 **테스트 열 개가 깨진다.** 셋은
`Test데모_고정` 이 일부러 잠가 둔 **꺼진 상태**이고(5b96312 — 「상수를 항상 켜 두면
원래 규칙 넷이 한꺼번에 깨지고, 그때 테스트를 고치면 되돌릴 때 무엇이 맞았는지
모른다」), 나머지 일곱은 `DEMO_PICKS` 가 진짜 판정을 가로채서 **`notice_fit` 을
아예 안 읽게** 되는 바람에 세 건·근거 수·`computed`·마감이 전부 어긋난 것이다.

**시연 중에 이 값이 `.env` 에 살아 있는 것이 정상이다.** 그래서 「깨졌으니 값을
빼라」가 아니라 여기서 무르게 한다 — `API_TOKEN` 과 똑같은 대가이고 똑같은 해법이다.

**켜진 쪽을 재는 테스트는 안 막힌다.** `Test데모_고정` 의 `_켠다` 가
`settings.demo_recommendations` 를 직접 monkeypatch 하므로 자기가 쓸 값을 스스로 세운다.

**`DEMO_SNAPSHOT` 은 안 건드린다.** 그 값은 올리기 경로에서만 갈리고 그 경로를 재는
테스트가 `settings.demo_snapshot` 을 직접 세운다.

**`finnect` 를 임포트하기 전에 해야 한다.** `settings` 가 모듈 임포트 시점에
`.env` 를 읽어서 한 번 만들어지고, 그 뒤에 환경변수를 고쳐도 늦다. conftest 는
테스트 모듈보다 먼저 임포트되므로 이 자리가 그 「전」이다.
"""

import os

os.environ["API_TOKEN"] = ""
os.environ["DEMO_RECOMMENDATIONS"] = "false"
