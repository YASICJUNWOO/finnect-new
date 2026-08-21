import styles from "./loading.module.css";

/** 4. 로딩(§14). **스피너 대신 들어올 모양을 그린다** — 궤도가 원이라 원을 그린다.
 *
 * 목록 화면은 행 여섯을 그리는데 여기는 궤도 하나라 모양이 다르다. 같은 스켈레톤을
 * 재사용하면 도착했을 때 화면이 뛴다.
 *
 * `prefers-reduced-motion` 은 globals.css 가 전역으로 끈다. */
export default function Loading() {
  return (
    <div className={styles.wrap} aria-busy="true" aria-live="polite">
      <span className="srOnly">위키를 불러오는 중이에요</span>
      <div className={styles.head} />
      <div className={styles.orbit} />
    </div>
  );
}
