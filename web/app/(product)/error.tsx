"use client";

import styles from "./error.module.css";

/** API 가 안 뜨거나 오류로 답했을 때. **제품 화면 전부가 이걸 쓴다.**
 *
 * **빈 화면으로 죽지 않는다**(plan/09 검증). 다만 2026-08-18 배포본에서 두 가지가 틀린
 * 채로 사용자에게 보였다.
 *
 * 1. **위키(S7)에서도 "공고를 못 불러왔어요"가 떴다.** 이 경계는 `(product)` 전체를
 *    덮는데 카피가 목록 화면 하나를 보고 쓰여 있었다. 화면 이름을 말하지 않는다
 * 2. **사업자에게 `uv run uvicorn ...` 을 실행하라고 했다.** 개발자용 지시가 제품
 *    화면으로 샌 것이다. **개발 중에만 보인다**(`NODE_ENV`)
 *
 * 그리고 배포본에서는 `error.message` 가 쓸모없다. React 가 서버 컴포넌트 오류 메시지를
 * 가리고 `Minified React error #441` 같은 것만 남긴다 — 사용자가 읽을 것이 아니다.
 * **대신 `digest` 를 적는다.** 서버 로그에서 같은 값을 찾을 수 있는 유일한 실이다.
 *
 * 사과하지 않고 모호하게 쓰지 않는다 — DESIGN.md §8.3-4. */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const dev = process.env.NODE_ENV !== "production";

  return (
    <div className={styles.box} role="alert">
      <h1 className={styles.title}>지금은 못 불러왔어요</h1>
      <p className={styles.what}>
        {dev ? error.message : "잠시 뒤에 다시 시도해 주세요. 계속 이러면 저희 쪽 문제예요."}
      </p>

      {dev ? (
        <p className={styles.how}>
          API 서버가 떠 있는지 확인해 주세요.
          <code className={styles.cmd}>uv run uvicorn finnect.api.app:app --port 8100</code>
        </p>
      ) : (
        error.digest && (
          /* 문의할 때 이 값을 주면 서버 로그에서 그 요청을 찾는다.
           * **오류 코드를 숨기지 않는다** — 숨기면 물어볼 방법이 없어진다 */
          <p className={styles.how}>
            문의하실 때 이 번호를 알려 주세요.
            <code className={styles.cmd}>{error.digest}</code>
          </p>
        )
      )}

      <button type="button" onClick={reset} className={styles.retry}>
        다시 시도
      </button>
    </div>
  );
}
