"use client";

import { useId, useState } from "react";
import styles from "./WriteWorkspace.module.css";

/** S4 쓰기 화면의 껍데기 — 초안 단과 양식 단을 배치한다.
 *
 * **데이터를 모른다.** 슬롯 셋을 받아 놓기만 한다 — rhwp 도 초안도 여기서는
 * 이름조차 안 나온다.
 *
 * ## 왜 컨테이너 쿼리인가
 *
 * 2단이 설 수 있는지는 **뷰포트가 아니라 이 단이 실제로 받은 폭**이 정한다.
 * 사이드바 200px · 스크롤바 · 사용자 확대가 전부 그 값을 바꾼다.
 *
 * 경계 **1147px** 은 실측에서 나왔다(2026-08-22 · `eval/rhwp-최소폭-실측.md`).
 * 초안 단 최소 360 + 양식 단 787 = 1147 이다.
 *
 * **787 을 정한 근거는 2026-08-23 없어졌다.** 그것은 「rhwp 가 그 아래에서 메뉴
 * 여덟을 파일·편집 둘로 접고 펼칠 방법이 화면에 없다」였는데, 그날 뷰어가 rhwp
 * 화면을 그만 쓰고 쪽 SVG 를 우리가 그리게 됐다(`DocViewer` · `SvgPages`). 지금은
 * 390px 에서도 종이가 폭에 맞춰 서고 가로 스크롤이 없다(실측). **값은 안 내렸다** —
 * 내리는 것은 「표가 읽히는 폭이 얼마인가」라는 다른 질문이고 아직 안 쟀다.
 *
 * **`@media` 로 안 쓴다.** 그러면 그것이 셋째 브레이크포인트이고 ADR-0047 을
 * 어긴다. 컨테이너 쿼리는 레이아웃 층이 아니라 이 컴포넌트가 제 폭을 보는
 * 것이라 그 규칙 밖이고, CSS 라 첫 그림에서 안 튄다.
 *
 * 결과: 1024 뷰포트 → 본문 776 → 1단(양식 776) · 1440 → 본문 1192 → 2단(양식 787). */
export function WriteWorkspace({
  thread,
  viewer,
  viewerHeader,
  collapsible = true,
}: {
  thread: React.ReactNode;
  viewer: React.ReactNode;
  /** 우리 머리줄. 접기 버튼이 여기 얹히므로 워크스페이스가 슬롯으로 받는다 */
  viewerHeader?: React.ReactNode;
  /** 양식이 없으면 접을 것도 없다 */
  collapsible?: boolean;
}) {
  const [tab, setTab] = useState<"draft" | "form">("draft");
  const [collapsed, setCollapsed] = useState(false);
  const id = useId();
  const draftPanelId = `${id}-draft`;
  const formPanelId = `${id}-form`;

  return (
    <div className={styles.workspace} data-collapsed={collapsed || undefined}>
      {/* 좁은 폭 전용. 넓어지면 CSS 가 끈다 — **같은 메뉴가 두 번 있으면 안 된다** */}
      <div className={styles.tabs} role="tablist" aria-label="초안과 양식을 갈아 가며 봐요">
        <button
          type="button"
          role="tab"
          id={`${id}-draft-tab`}
          aria-selected={tab === "draft"}
          aria-controls={draftPanelId}
          className={styles.tab}
          onClick={() => setTab("draft")}
        >
          초안
        </button>
        <button
          type="button"
          role="tab"
          id={`${id}-form-tab`}
          aria-selected={tab === "form"}
          aria-controls={formPanelId}
          className={styles.tab}
          onClick={() => setTab("form")}
        >
          양식
        </button>
      </div>

      <div className={styles.panes} data-tab={tab}>
        <section
          id={draftPanelId}
          role="tabpanel"
          aria-labelledby={`${id}-draft-tab`}
          className={styles.draft}
        >
          {thread}
        </section>

        <section
          id={formPanelId}
          role="tabpanel"
          aria-labelledby={`${id}-form-tab`}
          className={styles.form}
        >
          {(viewerHeader || collapsible) && (
            <div className={styles.formHead}>
              <div className={styles.formHeadSlot}>{viewerHeader}</div>
              {collapsible && (
                <button
                  type="button"
                  className={styles.collapse}
                  aria-expanded={!collapsed}
                  aria-controls={draftPanelId}
                  onClick={() => setCollapsed((c) => !c)}
                >
                  {collapsed ? "초안 펼치기" : "초안 접기"}
                </button>
              )}
            </div>
          )}
          <div className={styles.formBody}>{viewer}</div>
        </section>
      </div>
    </div>
  );
}
