"""테스트 세션에서만 `API_TOKEN` 을 비운다.

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

**`finnect` 를 임포트하기 전에 해야 한다.** `settings` 가 모듈 임포트 시점에
`.env` 를 읽어서 한 번 만들어지고, 그 뒤에 환경변수를 고쳐도 늦다. conftest 는
테스트 모듈보다 먼저 임포트되므로 이 자리가 그 「전」이다.
"""

import os

os.environ["API_TOKEN"] = ""
