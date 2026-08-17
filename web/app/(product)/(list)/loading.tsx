import styles from "./loading.module.css";

/** 4. 로딩. 스피너 대신 들어올 모양을 그린다 — 화면이 뛰지 않는다.
 *
 * `prefers-reduced-motion` 은 globals.css 가 전역으로 끈다. */
export default function Loading() {
  return (
    <div className={styles.wrap} aria-busy="true" aria-live="polite">
      <span className="srOnly">공고를 불러오는 중이에요</span>
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className={styles.row} />
      ))}
    </div>
  );
}
