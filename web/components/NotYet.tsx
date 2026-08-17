import styles from "./NotYet.module.css";

/** 자리는 있는데 값이 없는 곳.
 *
 * **예시 데이터를 넣지 않기로 한 결과가 이 컴포넌트다**(plan/09). 화면이 미완성으로
 * 읽히는 것을 받아들인다 — 가짜 값으로 완성돼 보이는 것보다 낫다.
 *
 * DESIGN.md §7-5 가 "'데이터 없음'으로 끝내지 않는다"고 했다. `why` 가 필수인 이유다. */
export function NotYet({ title, why }: { title: string; why: string }) {
  return (
    <section className={styles.box} aria-labelledby={`notyet-${slug(title)}`}>
      <h2 id={`notyet-${slug(title)}`} className={styles.title}>
        {title}
      </h2>
      <p className={styles.why}>{why}</p>
    </section>
  );
}

function slug(s: string) {
  return s.replace(/\s+/g, "-");
}
