"use client";

import styles from "./error.module.css";

/** API 가 안 뜨거나 오류로 답했을 때.
 *
 * **빈 화면으로 죽지 않는다**(plan/09 검증). 무엇이 잘못됐고 어떻게 고치는지 적는다 —
 * DESIGN.md §8.3-4. 사과하지 않고 모호하게 쓰지 않는다. */
export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className={styles.box} role="alert">
      <h1 className={styles.title}>공고를 못 불러왔어요</h1>
      <p className={styles.what}>{error.message}</p>
      <p className={styles.how}>
        API 서버가 떠 있는지 확인해 주세요.
        <code className={styles.cmd}>uv run uvicorn finnect.api.app:app --port 8100</code>
      </p>
      <button type="button" onClick={reset} className={styles.retry}>
        다시 시도
      </button>
    </div>
  );
}
