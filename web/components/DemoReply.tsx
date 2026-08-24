"use client";

import { useCallback, useEffect, useState } from "react";
import styles from "./DemoReply.module.css";

/** 데모용 초안 응답 — **제품 동작이 아니다.**
 *
 * 시연 공고의 쓰기 화면에 들어가면 **아무것도 안 부르고** 두 단에 로딩을 띄우고
 * 10초를 세다가 고정 문구와 채워 둔 신청서를 낸다. 진짜 경로는 `useDraft().start()`
 * 이고 그것은 LLM 을 불러 몇 분이 걸린다 — 시연에서 그 시간을 기다릴 수 없어서
 * 화면만 흉내 내는 것이다.
 *
 * **턴이 둘이다.** 들어가면 도는 첫 턴(집필)과, 입력칸에 무엇이든 치면 도는 둘째
 * 턴(수정)이다. 둘째 턴도 아무것도 안 부른다 — 사람이 친 말을 그대로 올리고,
 * 도구 줄 하나가 「고치고 있어요」를 말하고, 6초 뒤 오른쪽이 **미리 고쳐 둔 파일**로
 * 갈린다(`DEMO_REVISED_URL`). 진짜 대화 경로는 `POST …/draft/ask` 이고 아직 없다.
 *
 * **두 단이 한 시계를 본다.** `WritePanes` 가 `useDemoReply` 를 들고, 왼쪽에는
 * `demo` 로 내려 주고 오른쪽에는 `DemoViewerLoading` 을 겹친다. 시계가 여기 있는
 * 이유는 `DraftThread` 가 초안을 못 불러온 화면에서 아예 안 서기 때문이다.
 *
 * **이 파일은 지우면 그만이다.** 켜는 자리가 `DEMO` 하나이므로 데모가 끝나면 상수를
 * `false` 로 돌리거나 이 파일과 부르는 자리(`WritePanes`·`DraftThread`·`Upload`)를
 * 같이 지우면 된다. 진짜 초안 경로는 그동안 아무것도 안 바뀐 채로 그대로 있다.
 *
 * ## DESIGN.md 와 어긋나는 것
 *
 * `DraftThread` 의 머리 주석이 **「말풍선도 아바타도 타이핑 표시도 없다」**고 못
 * 박아 뒀고 §7 이 UI 크롬의 채움을 금지한다. 여기는 그 셋을 다 쓴다 — 요청이
 * 「AI 의 메시지 UI」였다. **그래서 제품 스레드의 CSS 를 안 건드리고 파일을
 * 따로 뒀다.** 이 모양이 제품으로 넘어가려면 ADR 이 하나 필요하다. */

/** **시연 모드.** 켜면 시연 공고(`DEMO_NOTICE`)의 쓰기 화면에 들어가는 것만으로
 * 두 단이 로딩을 띄우고 10초 뒤에 채워 둔 신청서로 갈린다. 그 뒤 입력칸에 무엇을
 * 치든 **수정 턴**이 돌아 6초 뒤 고쳐 둔 파일로 한 번 더 갈린다. 꺼져 있으면
 * `DraftThread` 와 `WritePanes` 가 진짜 초안 API 를 부른다 — 분기가 전부 원래
 * 경로로 떨어진다.
 *
 * **2026-08-24 트리거가 바뀌었다.** 예전에는 「초안 쓰기」를 눌러야 5초를 셌고, 지금은
 * **화면에 들어오면 바로** 센다. 사람이 안 눌러도 시작하므로 어느 공고인지를 반드시
 * 봐야 한다 — 그래서 `DEMO_NOTICE` 가 생겼다.
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
export const DEMO = true;

/** 시연을 켤 공고 하나. **이 화면 밖에서는 안 켜진다.**
 *
 * 트리거가 「버튼을 눌렀다」에서 「화면에 들어왔다」로 바뀌면서 필요해진 값이다.
 * 누르는 것이 조건이던 때는 엉뚱한 공고에서 안 돌았지만, 지금은 들어가는 것만으로
 * 시작하므로 **공고를 안 보면 어느 신청서에서든 나린데이터로 채운 현대모비스 파일이
 * 열린다.** `DEMO_FILLED_URL` 과 `DEMO_REVISED_URL` 이 이 공고 하나를 보고 만든
 * 파일이라 다른 공고에서는 화면이 통째로 거짓이 된다. */
export const DEMO_NOTICE = { source: "kstartup", externalId: "178951" } as const;

/** 이 공고에서 시연을 켜나. **`DEMO` 도 같이 본다** — 부르는 쪽이 둘을 각자 확인하면
 * 한쪽을 빠뜨린 자리가 생긴다. */
export function isDemoNotice(source: string, externalId: string): boolean {
  return DEMO && source === DEMO_NOTICE.source && externalId === DEMO_NOTICE.externalId;
}

/** 다섯이고 **한 줄로 흐른다** — `idle` → `writing` → `done` → `revising` → `revised`.
 *
 * `idle` 은 시연이 꺼진 화면 · `writing` 은 첫 10초 · `done` 은 채운 파일이 섰다 ·
 * `revising` 은 사람이 친 말을 받고 6초를 세는 중 · `revised` 는 고친 파일이 섰다.
 *
 * **`done` 을 거치지 않고 `revising` 으로 갈 수 있다.** 첫 10초 안에 입력칸에 치면
 * 그렇게 되고, 그때는 채운 파일을 못 보고 고친 파일로 바로 간다 — 막지 않는 이유는
 * 입력칸이 안 먹는 것처럼 보이는 편이 더 나쁘기 때문이다. */
export type DemoPhase = "idle" | "writing" | "done" | "revising" | "revised";

/** 시연에서 기다릴 수 있는 시간. **진짜 집필 시간과 무관하다.** */
export const DEMO_MS = 10000;

/** 수정 턴이 세는 시간. **집필보다 짧다** — 칸 하나를 고치는 것이라 같은 10초를
 * 두 번 기다리면 시연이 늘어진다. 진짜 재작성 시간과도 무관하다(항목 하나에 LLM
 * 한 번이라 실제로는 몇십 초다). */
export const DEMO_REVISE_MS = 6000;

/** 첫 턴이 끝난 뒤 오른쪽 단이 여는 파일. **나린데이터로 이미 채워 둔 신청서다.**
 *
 * 진짜 경로는 `filledDocumentUrl()` 이고 서버가 요청마다 원본에 초안을 넣어 만든다
 * (`forms/service.py` `fill_document`). 여기는 그 결과를 **미리 만들어 둔 정적
 * 파일**로 대신한다 — 초안을 안 만들었으니 서버가 채울 것이 없다.
 *
 * **이 파일은 레포에 없다.** `.gitignore` 가 `web/public/demo/` 를 통째로 무시한다
 * (bd2e175 — 「레포에 있으면 다음 사람이 그것을 제품 자산으로 읽는다」). 시연 전에
 * `spike/hwp_fill_anchored.py` 로 만들어 그 자리에 둬야 한다.
 *
 * **없으면 조용히 원본으로 물러난다.** `DocViewer` 가 채운 파일을 못 받으면 원본을
 * 여는 것이 설계인데(채우기 실패로 양식 자체를 가리지 않는다), 그 결과 10초가 지나도
 * **아무 일도 안 일어난 것처럼 보인다.** `useDemoReply` 가 시작할 때 한 번 확인해
 * 콘솔에 적는다 — 화면에는 안 낸다(시연을 보는 사람이 볼 말이 아니다). */
export const DEMO_FILLED_URL = "/demo/narin-application.hwp";

/** 수정 턴 뒤에 오른쪽 단이 여는 파일. **미리 고쳐 둔 같은 신청서다.**
 *
 * `DEMO_FILLED_URL` 과 **한 칸만 다르다** — 「외부 협업 이력」 칸에서 「참여 이력은
 * 없습니다」로 시작하던 문장이 빠졌다(레포 파서로 표 셀 105개를 대조했다).
 *
 * **그래서 시연에서 무엇을 칠지가 정해져 있다.** 파일이 고정이라 어느 말에나 같은
 * 결과가 나온다 — 그 칸을 두고 말해야 오른쪽에서 바뀌는 것이 방금 한 말과 이어진다.
 *
 * 이 파일도 `.gitignore` 가 무시하는 `web/public/demo/` 에 있다(bd2e175). 없으면
 * 조용히 원본으로 물러나므로 `useDemoReply` 가 시작할 때 둘 다 확인해 콘솔에 적는다. */
export const DEMO_REVISED_URL = "/demo/narin-application-revised.hwp";

/** 턴이 끝났을 때 하는 말. **한 문장씩이고 그게 요청이다**(「그냥 많은 내용 넣지
 * 말고」 · 2026-08-24).
 *
 * 예전에는 무엇을 채웠는지 칸 수까지 세 줄로 적었고 못 채운 자리(「비즈니스 성숙도
 * 5칸」)까지 말했다. **그 줄들이 없어지면서 화면이 못 채운 칸을 말하지 않는다** —
 * 제품 경로에서는 머리줄의 「N칸은 직접 채워 주세요」가 그 일을 하는데, 시연은 정적
 * 파일을 열어서 그 수가 안 온다(`x-finnect-left` 헤더가 없다). 시연에서 잃는 것을
 * 여기 적어 둔다.
 *
 * **파일이 무엇을 했는지와 무관한 말이라 안전하다.** 칸 수를 적을 때는 파일과 대조해
 * 세야 했지만(`forms/hwp.py` 로 표 셀 105개를 나란히 놓고 셌다) 이 두 문장은 「됐다」만
 * 말한다 — 사람이 무엇을 쳐도 참이다. */
const SAID = {
  done: "사업계획서 작성을 완료했어요! 내용을 확인해주세요.",
  revised: "수정 완료했어요! 추가로 수정할 사항이 있으시다면 말씀해주세요.",
} as const;

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

/** 타이핑 점 셋. **장식이라 스크린 리더에서 뺀다** — 옆 문장이 이미 상태를 말한다.
 * 세 자리(집필 · 양식 단 로딩 · 도구 줄)가 같은 마크업을 들고 있어서 하나로 뺐다. */
function Dots() {
  return (
    <span className={styles.dots} aria-hidden>
      <i />
      <i />
      <i />
    </span>
  );
}

/** 쓰는 중. **진행 막대를 안 쓴다**(§7 · §12.2) — 몇 퍼센트인지 우리가 모르고,
 * 여기서는 10초를 세는 것뿐이라 더더욱 모른다. */
function Writing() {
  return (
    <p className={styles.writing}>
      초안을 쓰고 있어요
      <Dots />
    </p>
  );
}

/** 다 썼다. **한 문장이다** — 그 자리에 목록이 있었고 요청이 그것을 걷었다(`SAID`) */
function Done() {
  return <p className={styles.headline}>{SAID.done}</p>;
}

/** 수정 턴. **사람이 친 말 아래에 선다** — `DraftThread` 가 `said` 뒤에 그린다.
 * 첫 턴(`DemoReply`)은 그 위에 그대로 남는다: 대화가 지워지지 않고 쌓인다.
 *
 * **도구 줄이 여기 있다.** 요청이 「채팅창에도 수정중입니다 같은 tool 메시지」였다 —
 * 무엇을 하고 있는지를 문장이 아니라 이름으로 말하는 줄이다. 끝나도 안 없앤다(상태만
 * 「고쳤어요」로 바뀐다): 없애면 무엇이 그 결과를 만들었는지가 화면에서 사라진다. */
export function DemoRevise({ phase }: { phase: DemoPhase }) {
  if (phase !== "revising" && phase !== "revised") return null;
  const doing = phase === "revising";

  return (
    <div className={styles.turn}>
      {/* §8 «로고 마크» — 첫 턴과 같은 마크다. 같은 쪽이 말하는 것이라 갈라 두지 않는다 */}
      <span className={styles.mark} aria-hidden />
      <div className={styles.bubble}>
        <div className={styles.tool} role="status">
          {/* **버튼처럼 안 보이게 둔다** — 누를 것이 아니다(§4 는 채운 검정을 주
              버튼에만 준다). 이름 하나와 상태 하나, 덩어리 둘이다(§10) */}
          <span className={styles.toolName}>문서 고치기</span>
          <span className={styles.toolState}>
            {doing ? (
              <>
                고치고 있어요
                <Dots />
              </>
            ) : (
              "고쳤어요"
            )}
          </span>
        </div>

        {!doing && <p className={styles.headline}>{SAID.revised}</p>}
      </div>
    </div>
  );
}

/** 양식 단에 겹치는 로딩. **문서를 덮지 않고 비친다** — 아래에서 원본이 열리는 것이
 * 보이고, 10초가 지나 채운 파일로 갈릴 때까지 이 글이 남는다. 요청이 「그사이 문서는
 * 띄워도 되고 로딩창은 유지」였다.
 *
 * **진행 막대가 없다**(§7 · §12.2). 몇 퍼센트인지 모르고, 여기서는 초를 세는 것뿐이라
 * 더더욱 모른다. */
export function DemoViewerLoading({ revising = false }: { revising?: boolean }) {
  return (
    <div className={styles.veil} role="status">
      <p className={styles.veilText}>
        {/* **두 턴이 다른 말을 한다.** 「초안을 넣고 있어요」가 수정 턴에도 서면
            처음부터 다시 쓰는 것으로 읽힌다 — 왼쪽 도구 줄은 고친다고 말하는 중이다 */}
        {revising ? "문서를 고치고 있어요" : "양식에 초안을 넣고 있어요"}
        <Dots />
      </p>
    </div>
  );
}

/** 시계. **`WritePanes` 가 이걸 쓴다** — 두 단이 같은 상태를 봐야 하고, 초안을 못
 * 불러온 화면(`draft === null`)에서도 시계가 돌아야 한다. `DraftThread` 가 들고
 * 있으면 그 컴포넌트가 안 서는 화면에서 로딩이 영영 안 걷힌다.
 *
 * `auto` 면 **`idle` 을 안 거친다.** 효과로 시작하면 첫 그림에 로딩이 없는 프레임이
 * 하나 끼고, 그 프레임에서 「초안 쓰기」 버튼과 안내 줄이 스쳐 지나간다.
 *
 * **단계를 셈과 함께 든다**(`{ phase, n }`). 이미 `revising` 인데 한 번 더 치면
 * `phase` 만으로는 의존성이 안 바뀌어 **타이머가 처음부터 안 돈다** — 화면에는 두 번째
 * 말이 올라갔는데 문서는 첫 번째 셈의 남은 시간만 기다린다. 셈이 늘면 새 객체가 되어
 * 효과가 다시 돈다.
 *
 * **여는 파일도 여기서 든다**(`file`). 단계에서 계산하면 `revising` 이 무엇을 열지
 * 정할 수 없다 — 그 단계는 「직전에 열려 있던 것을 그대로 둔다」가 답이고, 그건 단계
 * 하나만 봐서는 모른다. 계산했더니 **두 번째 수정에서 문서가 고치기 전 파일로 되돌아갔다**
 * (실측: `revising` → `DEMO_FILLED_URL`). 세는 동안 문서가 거꾸로 가는 것이 보인다. */
export function useDemoReply(auto: boolean): {
  phase: DemoPhase;
  /** 지금 오른쪽 단이 열 파일. `null` 은 「미리 만들어 둔 것이 아직 없다」 — 첫 10초 */
  file: string | null;
  start: () => void;
  revise: () => void;
  reset: () => void;
} {
  const [run, setRun] = useState<{ phase: DemoPhase; n: number; file: string | null }>(
    () => ({ phase: auto ? "writing" : "idle", n: 0, file: null }),
  );

  useEffect(() => {
    // 세는 단계 둘뿐이다. 나머지 셋은 서 있는 상태라 시계가 필요 없다
    const next =
      run.phase === "writing" ? "done" : run.phase === "revising" ? "revised" : null;
    if (!next) return;
    const ms = run.phase === "writing" ? DEMO_MS : DEMO_REVISE_MS;
    const file = next === "done" ? DEMO_FILLED_URL : DEMO_REVISED_URL;
    const t = setTimeout(() => setRun((r) => ({ ...r, phase: next, file })), ms);
    return () => clearTimeout(t);
  }, [run]);

  // **채워 둔 신청서와 고쳐 둔 신청서가 있나.** 없으면 원본이 그대로 열려서 시연이
  // 조용히 헛돈다(`DEMO_FILLED_URL` 주석). 준비하는 사람에게만 말한다
  useEffect(() => {
    if (!auto) return;
    for (const url of [DEMO_FILLED_URL, DEMO_REVISED_URL]) {
      void fetch(url, { method: "HEAD" }).then(
        (r) => {
          if (r.ok) return;
          console.error(
            `시연: 미리 만들어 둔 신청서가 없어요 (${url} → ${r.status}). ` +
              "`.gitignore` 가 `web/public/demo/` 안을 잠그고 쓰는 파일만 이름으로 " +
              "열어 둬요 — 파일을 새로 만들었으면 거기 이름을 같이 적어야 배포본에 " +
              "올라가요. 없으면 원본 양식이 그대로 열려서 아무 일도 안 일어난 것처럼 " +
              "보여요.",
          );
        },
        () => {
          // 못 물어봤으면 아무 말도 안 한다. 여기서 던지면 시연이 통째로 멈춘다
        },
      );
    }
  }, [auto]);

  // **`useCallback` 이다.** 부르는 쪽이 이 값을 `useMemo` 의 의존성으로 들고 스레드에
  // 내려 주므로(`WritePanes.threadDemo`), 매 렌더 새 함수면 그 메모가 뜻을 잃는다.
  // **집필 턴은 파일을 되돌린다**(`file: null`) — 처음부터 다시 쓰는 것이라 그 10초
  // 동안은 원본이 아래에 있어야 맞다. **수정 턴은 안 건드린다** — 위 주석의 그 자리다
  const start = useCallback(
    () => setRun((r) => ({ phase: "writing", n: r.n + 1, file: null })),
    [],
  );
  const revise = useCallback(() => setRun((r) => ({ ...r, phase: "revising", n: r.n + 1 })), []);
  const reset = useCallback(
    () => setRun((r) => ({ phase: "idle", n: r.n + 1, file: null })),
    [],
  );

  return { phase: run.phase, file: run.file, start, revise, reset };
}
