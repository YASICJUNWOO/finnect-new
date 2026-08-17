import type { Attachment } from "@/lib/api";
import styles from "./Attachments.module.css";

/** 첨부 해독 상태를 화면 말로.
 *
 * **다섯을 한 덩어리로 뭉개지 않는다.** 셋을 가른 것이 T-0004 의 존재 이유다 —
 * '안 해봤다'와 '해봤는데 안 됐다'와 '해봤는데 0바이트다'는 다른 사실이다. */
const PARSE_LABEL: Record<string, string> = {
  ok: "읽었어요",
  empty: "글자가 없어요",
  unsupported: "아직 못 여는 형식이에요",
  failed: "여는 데 실패했어요",
  container: "압축 파일이라 목록만 봤어요",
};

const PARSE_TONE: Record<string, string> = {
  ok: "ok",
  empty: "warn",
  unsupported: "warn",
  failed: "warn",
  container: "warn",
};

function label(a: Attachment): { text: string; tone: string } {
  if (a.fetch_status && a.fetch_status !== "ok") {
    return { text: "못 받았어요", tone: "warn" };
  }
  if (!a.parse_status) return { text: "아직 안 열어 봤어요", tone: "idle" };
  return {
    text: PARSE_LABEL[a.parse_status] ?? a.parse_status,
    tone: PARSE_TONE[a.parse_status] ?? "warn",
  };
}

export function Attachments({ items, decoded }: { items: Attachment[]; decoded: number }) {
  if (items.length === 0) {
    return (
      <section className={styles.section} aria-labelledby="docs-title">
        <h2 id="docs-title" className={styles.title}>
          낼 서류
        </h2>
        <p className={styles.none}>이 공고에는 붙은 서류가 없어요.</p>
      </section>
    );
  }

  return (
    <section className={styles.section} aria-labelledby="docs-title">
      <div className={styles.head}>
        <h2 id="docs-title" className={styles.title}>
          낼 서류
        </h2>
        {/* 못 읽은 것을 안 읽은 척하지 않는다 */}
        <p className={styles.summary} data-numeric>
          {items.length}개 중 {decoded}개를 읽었어요
        </p>
      </div>

      <ul className={styles.list}>
        {items.map((a) => {
          const { text, tone } = label(a);
          return (
            <li key={a.position} className={styles.item}>
              <div className={styles.name}>
                {a.url ? (
                  <a href={a.url} className={styles.link}>
                    {a.filename}
                  </a>
                ) : (
                  a.filename
                )}
                {a.kind === "공고문" && <span className={styles.kind}>공고문</span>}
              </div>
              <div className={styles.state}>
                <span className={`${styles.badge} ${styles[tone]}`}>{text}</span>
                {/* 파일명이 준 확장자와 내용이 다를 수 있다 — 3,354건 중 7건 */}
                {a.detected_ext && a.ext && a.detected_ext !== a.ext && (
                  <span className={styles.mismatch}>
                    이름은 .{a.ext}인데 내용은 {a.detected_ext}예요
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
