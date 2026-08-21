import styles from "./loading.module.css";

/** 4. 로딩(§14). S1 이 뜨기 전.
 *
 * **부모(`wiki/loading.tsx`)를 물려받으면 안 된다.** 저기는 "위키를 불러오는 중이에요"라고
 * 말하고 원을 그리는데, 이 화면에 오는 것은 위키가 아니라 던지는 자리와 파일 줄이다.
 * 틀린 이름을 부르고(§10) 도착 순간 모양이 통째로 바뀐다.
 *
 * `prefers-reduced-motion` 은 globals.css 가 전역으로 끈다. */
export default function Loading() {
  return (
    <div className={styles.wrap} aria-busy="true" aria-live="polite">
      <span className="srOnly">올린 파일을 불러오는 중이에요</span>
      <div className={styles.head} />
      <div className={styles.drop} />
      <div className={styles.row} />
      <div className={styles.row} />
    </div>
  );
}
