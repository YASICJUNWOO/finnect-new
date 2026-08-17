import styles from "./Filters.module.css";

/** 검색과 출처 고르기.
 *
 * **클라이언트 자바스크립트가 없다.** GET 폼이라 제출하면 주소가 바뀌고 서버가 다시 그린다.
 * 주소에 상태가 그대로 있어서 뒤로 가기와 새로 고침이 자연히 동작한다. */
export function Filters({ q, source }: { q: string; source: string }) {
  return (
    <form className={styles.form} action="/" method="get" role="search">
      <label className="srOnly" htmlFor="q">
        공고 이름으로 찾기
      </label>
      <input
        id="q"
        name="q"
        type="search"
        defaultValue={q}
        placeholder="공고 이름으로 찾아보세요"
        className={styles.input}
      />

      <label className="srOnly" htmlFor="source">
        어디서 온 공고인지
      </label>
      <select id="source" name="source" defaultValue={source} className={styles.select}>
        <option value="">전체</option>
        <option value="bizinfo">기업마당</option>
        <option value="kstartup">K-Startup</option>
      </select>

      <button type="submit" className={styles.submit}>
        찾기
      </button>
    </form>
  );
}
