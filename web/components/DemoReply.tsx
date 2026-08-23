"use client";

import { useEffect, useState } from "react";
import styles from "./DemoReply.module.css";

/** 데모용 초안 응답 — **제품 동작이 아니다.**
 *
 * 「초안 쓰기」를 누르면 **아무것도 안 부르고** 5초를 세다가 고정 문구를 낸다.
 * 진짜 경로는 `useDraft().start()` 이고 그것은 LLM 을 불러 몇 분이 걸린다 —
 * 시연에서 그 시간을 기다릴 수 없어서 화면만 흉내 내는 것이다.
 *
 * **이 파일은 지우면 그만이다.** `DraftThread` 가 `DEMO` 한 곳에서만 이걸 켜므로,
 * 데모가 끝나면 상수를 `false` 로 돌리거나 이 파일과 그 분기를 같이 지우면 된다.
 * 진짜 초안 경로는 그동안 아무것도 안 바뀐 채로 그대로 있다.
 *
 * ## DESIGN.md 와 어긋나는 것
 *
 * `DraftThread` 의 머리 주석이 **「말풍선도 아바타도 타이핑 표시도 없다」**고 못
 * 박아 뒀고 §7 이 UI 크롬의 채움을 금지한다. 여기는 그 셋을 다 쓴다 — 요청이
 * 「AI 의 메시지 UI」였다. **그래서 제품 스레드의 CSS 를 안 건드리고 파일을
 * 따로 뒀다.** 이 모양이 제품으로 넘어가려면 ADR 이 하나 필요하다. */

/** **시연 모드. 기본이 꺼짐이다.** 켜면 「초안 쓰기」가 아무것도 안 부르고 5초 뒤
 * 고정 문구를 낸다. 꺼져 있으면 `DraftThread` 와 `WritePanes` 가 진짜 초안 API 를
 * 부른다 — 분기 열한 자리가 전부 원래 경로로 떨어진다.
 *
 * **환경변수가 아니라 소스 상수다.** 백엔드 쪽 짝(`DEMO_RECOMMENDATIONS` ·
 * `DEMO_SNAPSHOT`)은 `.env` 로 켜는데 여기는 손으로 `true` 로 고쳐야 한다. 시연
 * 직전에 고치고 **끝나면 되돌린다** — 켠 채로 배포하면 초안 집필이 통째로 가짜가
 * 되고, 그 화면은 아무 오류도 안 내므로 눈으로 보기 전까지 안 걸린다.
 *
 * `NEXT_PUBLIC_*` 으로 바꾸지 않은 이유는 그러면 켜는 자리가 배포 설정으로 옮겨
 * 가서, 레포를 읽는 사람이 이 화면이 진짜인지 가짜인지 코드로 알 수 없게 되기
 * 때문이다. 상수면 diff 에 남는다.
 *
 * **분기가 이 상수 하나에 걸린다.** 아예 걷으려면 이 파일과
 * `DemoReply.module.css`·`web/public/demo/` 와 부르는 자리 셋을 같이 지운다. */
export const DEMO = false;

/** `idle` 은 아직 안 눌렀다 · `writing` 은 5초를 세는 중 · `done` 은 문구가 섰다. */
export type DemoPhase = "idle" | "writing" | "done";

/** 시연에서 기다릴 수 있는 시간. **진짜 집필 시간과 무관하다.** */
export const DEMO_MS = 5000;

/** 「바꿨어요!」 뒤에 오른쪽 단이 여는 파일. **나린데이터로 이미 채워 둔 신청서다.**
 *
 * 진짜 경로는 `filledDocumentUrl()` 이고 서버가 요청마다 원본에 초안을 넣어 만든다
 * (`forms/service.py` `fill_document`). 여기는 그 결과를 **미리 만들어 둔 정적
 * 파일**로 대신한다 — 초안을 안 만들었으니 서버가 채울 것이 없다.
 *
 * **`.gitignore` 의 `*.hwp` 에 예외를 뒀다.** 화면이 이걸 정적 파일로 받으므로
 * 배포본에 들어가야 한다. */
export const DEMO_FILLED_URL = "/demo/narin-application.hwp";

/** 무엇을 채웠나. **전부 고정 문구다** — 초안을 안 만들었으므로 셀 것이 없다.
 *
 * 이 공고(`kstartup:178951` · 2026 현대모비스 CSV 오픈 이노베이션 신청서)와
 * `c_narin` 을 보고 쓴 것이라 **다른 공고에서는 틀린 말이 된다.** 데모가 이 한
 * 화면만 보여 주기 때문에 그대로 둔다.
 *
 * **칸 수는 원본 양식과 대조해 센 것이다.** 원본(`139432d978…`)의 빈칸·가이드
 * 문구 자리와 `web/public/demo/narin-application.hwp` 를 나란히 놓고 셌다 —
 * 데모라도 화면이 말한 수는 파일에 있어야 한다. */
const CHANGED: readonly { where: string; what: string }[] = [
  { where: "기업개요 17칸", what: "대표자 · 업체명 · 사업자등록번호 · 소재지를 위키에서 가져와 넣었어요" },
  { where: "사업 개요와 협업 제안 12칸", what: "나린데이터 위키의 사실 12개를 근거로 새로 썼어요" },
  { where: "지원 분야와 이력 체크 4칸", what: "고르는 칸이라 위키에 있는 것만 표시했어요" },
];

/** 못 채운 자리. **조용히 넘기지 않는다** — 이 규칙만은 데모에서도 지킨다.
 * 말 안 하면 시연을 보는 사람이 다 채워진 줄로 읽는다. */
const LEFT = "비즈니스 성숙도 5칸";

export function DemoReply({ phase }: { phase: DemoPhase }) {
  if (phase === "idle") return null;

  return (
    <div className={styles.turn}>
      {/* §8 «로고 마크» — 18px 사각형에 6px 모서리, `--ink`. 동작색이 아니다 */}
      <span className={styles.mark} aria-hidden />
      <div className={styles.bubble}>
        {phase === "writing" ? <Writing /> : <Done />}
      </div>
    </div>
  );
}

/** 쓰는 중. **진행 막대를 안 쓴다**(§7 · §12.2) — 몇 퍼센트인지 우리가 모르고,
 * 여기서는 5초를 세는 것뿐이라 더더욱 모른다. */
function Writing() {
  return (
    <p className={styles.writing}>
      초안을 쓰고 있어요
      {/* 점 셋은 장식이라 스크린 리더에서 뺀다. 위 문장이 이미 상태를 말한다 */}
      <span className={styles.dots} aria-hidden>
        <i />
        <i />
        <i />
      </span>
    </p>
  );
}

function Done() {
  return (
    <>
      <p className={styles.headline}>바꿨어요!</p>
      <p className={styles.lede}>
        「2026 현대모비스 CSV 오픈 이노베이션 신청서」 양식을 나린데이터 위키로 채웠어요.
      </p>

      <ul className={styles.list}>
        {CHANGED.map((c) => (
          <li key={c.where} className={styles.row}>
            <span className={styles.where}>{c.where}</span>
            <span className={styles.what}>{c.what}</span>
          </li>
        ))}
      </ul>

      {/* **다음 동작을 적는다**(§10) — 「데이터 없음」으로 끝내지 않는 것과 같은 규칙 */}
      <p className={styles.left}>
        {LEFT}은 해당하는 게 없어서 비워 뒀어요. 직인은 직접 찍어 주세요.
      </p>
    </>
  );
}

/** 5초를 세는 자리. **`DraftThread` 가 이걸 쓴다** — 타이머를 컴포넌트 밖에 두면
 * 화면을 떠난 뒤에도 `setState` 가 돈다.
 *
 * `start()` 를 다시 부르면 `writing` 부터 새로 센다. */
export function useDemoReply(): {
  phase: DemoPhase;
  start: () => void;
  reset: () => void;
} {
  const [phase, setPhase] = useState<DemoPhase>("idle");

  useEffect(() => {
    if (phase !== "writing") return;
    const t = setTimeout(() => setPhase("done"), DEMO_MS);
    return () => clearTimeout(t);
  }, [phase]);

  return {
    phase,
    // **`idle` 을 거쳐 간다.** 곧바로 `writing` 으로 두면 이미 `writing` 일 때
    // 다시 눌러도 effect 의 의존성이 안 바뀌어 타이머가 처음부터 안 돈다.
    start: () => setPhase((p) => (p === "writing" ? p : "writing")),
    reset: () => setPhase("idle"),
  };
}
