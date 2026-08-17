/** 접수 기간을 화면 글자로. [ADR-0024](../../docs/adr/0024-접수-기간-표현.md)를 그대로 구현한다.
 *
 * **세 갈래뿐이다.** 날짜가 있다 / 없지만 원문이 있다 / 둘 다 없다.
 * 원문 34종을 뜻으로 분류하지 않는다 — "예산 소진시까지"를 그대로 보여 주면
 * 사용자가 1초에 판단한다. */

import type { Notice } from "./api";

export type Deadline = {
  text: string;
  /** `urgent` 만 액센트 색을 쓴다. DESIGN.md §8.1-6 — 강조는 하나만 */
  tone: "urgent" | "dated" | "raw" | "unknown";
  /** 마우스를 올렸을 때 나오는 보충. 없으면 undefined */
  hint?: string;
};

/** 며칠 남았을 때부터 급한가. 일주일이다. */
const URGENT_DAYS = 7;

export function deadlineOf(n: Notice): Deadline {
  const { days_left: left, apply_end: end, apply_period_raw: raw } = n;

  if (left !== null && end !== null) {
    if (left < 0) return { text: "마감됐어요", tone: "dated", hint: end };
    if (left === 0) return { text: "오늘 마감", tone: "urgent", hint: end };
    if (left === 1) return { text: "내일 마감", tone: "urgent", hint: end };
    return {
      text: `${left}일 남았어요`,
      tone: left <= URGENT_DAYS ? "urgent" : "dated",
      hint: end,
    };
  }

  // 876건이 여기 온다. **마감일 없음으로 뭉개지 않는다.**
  if (raw) return { text: raw, tone: "raw" };

  // K-Startup 99건. 출처가 접수 기간을 안 줬다.
  return { text: "접수 기간을 안 알려줬어요", tone: "unknown" };
}

/** 목록 아래에 붙일 기간 한 줄. 시작일이 있으면 같이 보여 준다. */
export function periodOf(n: Notice): string | null {
  if (n.apply_start && n.apply_end) return `${n.apply_start} ~ ${n.apply_end}`;
  if (n.apply_end) return `~ ${n.apply_end}`;
  return n.apply_period_raw;
}
