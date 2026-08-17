import Link from "next/link";
import styles from "./not-found.module.css";

/** 없는 공고. **오류 화면과 다른 물건이다** — 이건 실패가 아니라 정상적인 결과다. */
export default function NotFound() {
  return (
    <div className={styles.box}>
      <h1 className={styles.title}>그 공고를 못 찾았어요</h1>
      <p className={styles.why}>
        주소가 바뀌었거나, 아직 우리가 안 받아 온 공고일 수 있어요.
      </p>
      <Link href="/" className={styles.action}>
        공고 목록으로
      </Link>
    </div>
  );
}
