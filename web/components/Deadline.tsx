import type { Notice } from "@/lib/api";
import { deadlineOf } from "@/lib/deadline";
import styles from "./Deadline.module.css";

/** 접수 기간 한 덩어리.
 *
 * **액센트는 여기 하나뿐이다** — DESIGN.md §7. 화면의 다른 어디에도 색을 쓰지 않는다.
 *
 * `className` 은 놓이는 자리가 주는 것이다 — 목록 행에서는 그리드 칸(`NoticeRow` 의
 * `.dl`)이 된다. **감싸는 span 을 하나 더 두지 않으려고 받는다** — 그리드 칸과 배지
 * 사이에 상자가 하나 더 끼면 baseline 이 한 겹 더 생겨 행이 두꺼워진다. */
export function Deadline({ notice, className }: { notice: Notice; className?: string }) {
  const { text, tone, hint } = deadlineOf(notice);
  return (
    <span
      className={[className, styles.badge, styles[tone]].filter(Boolean).join(" ")}
      title={hint}
      data-numeric
    >
      {text}
    </span>
  );
}
