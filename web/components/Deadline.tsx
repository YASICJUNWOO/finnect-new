import type { Notice } from "@/lib/api";
import { deadlineOf } from "@/lib/deadline";
import styles from "./Deadline.module.css";

/** 접수 기간 한 덩어리.
 *
 * **액센트는 여기 하나뿐이다** — DESIGN.md §8.1-6. 화면의 다른 어디에도 색을 쓰지 않는다. */
export function Deadline({ notice }: { notice: Notice }) {
  const { text, tone, hint } = deadlineOf(notice);
  return (
    <span className={`${styles.badge} ${styles[tone]}`} title={hint} data-numeric>
      {text}
    </span>
  );
}
