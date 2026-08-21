"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import styles from "./Install.module.css";

/** 설치 자리. **한 번 닫으면 다시 안 뜬다**(DESIGN.md §8.1-4 — 강요하지 않는다). */
const KEY = "finnect.install.dismissed";

/** `beforeinstallprompt` 는 표준이 아니라 `lib.dom` 에 타입이 없다. **쓰는 것만 적는다** —
 * `userChoice` 를 타입에 넣으면 읽고 싶어지고, 아래 `install()` 이 그걸 안 읽는 이유가 있다. */
type InstallEvent = Event & { prompt: () => Promise<void> };

/** `none` 물을 이유가 없다 · `ios` 방법을 글로 적는다 · `wait` 이벤트를 기다린다 */
type Mode = "none" | "ios" | "wait";

/** **하나만 바뀔 수 있다.** `read()` 가 보는 셋 중 '닫았나'와 '어느 브라우저냐'는 안 바뀌지만
 * **'설치됐나'는 바뀐다** — 크롬 자기 ⋮ 메뉴로 설치하면 이 탭은 `display-mode: browser` 로
 * 남아서 이미 설치된 앱을 계속 권한다. 그건 `appinstalled` 로 잡고(아래 효과), 여기서는
 * 구독할 것이 없다. */
const NEVER = () => () => {};

function read(): Mode {
  // 프라이빗 모드에서 `localStorage` 접근 자체가 던진다. 던지면 아예 안 묻는다 —
  // 닫은 것을 기억할 수 없는 곳에서 물으면 새로 열 때마다 다시 뜬다
  try {
    if (localStorage.getItem(KEY)) return "none";
  } catch {
    return "none";
  }

  // 이미 설치된 채로 열린 것이면 물을 이유가 없다. iOS 는 `display-mode` 를
  // 안 주던 시절이 있어서 `navigator.standalone` 도 같이 본다
  if (
    window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as { standalone?: boolean }).standalone === true
  ) {
    return "none";
  }

  // **UA 를 보지 않고 능력을 본다.** `navigator.standalone` 은 iOS 사파리에만 있는
  // 속성이다. UA 문자열은 브라우저가 바꾸고, iPadOS 는 자기를 맥이라고 말한다
  return "standalone" in navigator ? "ios" : "wait";
}

/** 홈 화면에 두라고 한 번 권한다.
 *
 * **오프라인을 약속하지 않는다.** 서비스 워커가 없어서(ADR-0039) 더 빨리 뜨지도 않는다 —
 * 달라지는 것은 **닿는 거리** 하나다. 브라우저를 열고 주소를 찾는 대신 한 번 누른다.
 * 그래서 카피가 '바로 열 수 있어요'이고 '빨라요'가 아니다.
 *
 * 길이 둘이다. 안드로이드·데스크톱 크롬은 `beforeinstallprompt` 를 주니 버튼을 누르면
 * 끝이고, **iOS 사파리는 그 이벤트를 안 준다** — 거기서는 방법을 글로 적는 수밖에 없다.
 *
 * **`useSyncExternalStore` 를 쓰는 이유가 규칙 회피가 아니다.** 브라우저 능력을
 * `useEffect` + `setState` 로 읽으면 렌더가 한 번 더 돌고, 서버 스냅샷을 줄 자리가 없어
 * 하이드레이션이 어긋난다. 여기 필요한 것이 정확히 "React 밖의 값을 서버 기본값과 함께
 * 읽기"라서 그 훅이 그 일을 한다. 값이 원시형(문자열)이어야 하는 것도 그 계약이다 —
 * 객체를 돌려주면 매번 새 참조라 무한히 렌더한다. */
export function Install() {
  const mode = useSyncExternalStore(NEVER, read, () => "none" as Mode);
  const [evt, setEvt] = useState<InstallEvent | null>(null);
  const [closed, setClosed] = useState(false);

  useEffect(() => {
    if (mode !== "wait") return;
    const onPrompt = (e: Event) => {
      // 브라우저가 자기 배너를 띄우는 것을 막는다. 우리 자리에서 우리 문장으로 묻는다
      e.preventDefault();
      setEvt(e as InstallEvent);
    };
    // **우리 버튼으로 설치하지 않아도 사라져야 한다.** 크롬 ⋮ 메뉴로 설치하면 이 탭은
    // 브라우저로 남아 있어서, 이게 없으면 이미 설치된 앱을 계속 권한다(§8.1-4)
    const onInstalled = () => close();
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, [mode]);

  function close() {
    try {
      localStorage.setItem(KEY, "1");
    } catch {
      // 기억을 못 해도 이번 화면에서는 사라져야 한다
    }
    setClosed(true);
  }

  async function install() {
    if (!evt) return;
    try {
      await evt.prompt();
    } finally {
      // **`userChoice` 를 안 읽는다.** 받아들였으면 설치됐으니 닫아야 하고, 거절했으면
      // 다시 묻지 않아야 하니 역시 닫아야 한다. 분기해서 갈 곳이 없다.
      //
      // **`finally` 가 이 말을 실제로 하는 구문이다.** `prompt()` 는 두 번 부르거나
      // 사용자 동작 밖에서 부르면 **거부한다** — 그냥 `await` 뒤에 두면 던지고 여기를
      // 안 지나서, 이미 써 버린 이벤트를 든 `설치` 버튼이 화면에 남는다. 누를 수 없는
      // 버튼을 남기지 않는다(§12.4)
      close();
    }
  }

  if (closed || mode === "none") return null;
  // 크롬 쪽은 이벤트가 오기 전까지 아무것도 안 띄운다 — 못 설치하는 곳에서 물으면
  // 누를 수 없는 버튼이 남는다
  if (mode === "wait" && !evt) return null;

  return (
    <aside className={styles.strip}>
      <div className={styles.inner}>
        <p className={styles.text}>
          홈 화면에 두면 바로 열 수 있어요
          {mode === "ios" && (
            <span className={styles.how}>공유 버튼에서 &lsquo;홈 화면에 추가&rsquo;</span>
          )}
        </p>

        {evt && (
          <button type="button" className={styles.go} onClick={install}>
            설치
          </button>
        )}

        <button type="button" className={styles.close} onClick={close}>
          닫기
        </button>
      </div>
    </aside>
  );
}
