# 앱 아이콘이 어느 크기에서 뭉개나 — 2026-08-21

`tools/make-icons.py` 의 궤도 마크를 16·32·48px 로 굽고 **최근접 이웃으로 8배 키워** 봤다.
확대는 판정용이다 — 브라우저가 그 크기로 래스터라이즈한 결과를 눈으로 보려는 것이고,
부드럽게 보간하면 실제보다 좋아 보인다.

| 크기 | 파일 | 읽히나 |
|---|---|---|
| 16px | [궤도-16px.png](궤도-16px.png) | **아니다.** 궤도·살·도트가 한 덩어리로 뭉친다. 중심만 겨우 보인다 |
| 32px | [궤도-32px.png](궤도-32px.png) | **읽힌다.** 중심 하나 + 위성 셋 + 끊긴 고리가 구분된다 |
| 48px | [궤도-48px.png](궤도-48px.png) | 읽힌다 |

## 이 실측이 정한 것

**마크를 둘로 나누지 않았다**([ADR-0039](../../0039-설치되는-앱으로-만들되-서비스-워커는-안-붙인다.md) 결정 3).

16px 이 뭉개니 파비콘만 따로 단순한 글리프를 만들 수도 있었다. 그러면 홈 화면과 탭에
다른 마크가 사는데, 그 둘째 글리프를 정하는 것은 `DESIGN.md` §1 이 **미정으로 남겨 둔
'시그니처 요소'를 결정 없이 채우는 일**이다. 하나로 가고 한계를 적어 두는 쪽을 골랐다.

실무에서 덜 아픈 이유도 있다. `web/app/icon.svg` 는 벡터라 브라우저가 필요한 크기로
굽고, 2배 화면의 탭은 32px 을 요청한다 — 위 표의 둘째 줄이다. 16px 은 1배 화면의 탭에서만 나온다.

## 다시 재는 방법

```bash
python3 tools/make-icons.py            # 마크를 고쳤으면 먼저
python3 - <<'PY'
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("mk", "tools/make-icons.py")
mk = importlib.util.module_from_spec(spec); spec.loader.exec_module(mk)
for src in (16, 32, 48):
    rows = mk.render(src); z = 256 // src
    big = []
    for r in rows:
        px = [r[i*3:i*3+3] for i in range(src)]
        big.extend([b"".join(p * z for p in px)] * z)
    mk.write_png(Path(f"/tmp/궤도-{src}px.png"), src * z, big)
PY
```
