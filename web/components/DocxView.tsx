"use client";

import { useEffect, useRef, useState } from "react";
import shell from "./DocViewer.module.css";
import styles from "./DocxView.module.css";

/** docx 뷰어 — **rhwp 가 못 여는 포맷을 여기서 연다** (plan/24 T-0155).
 *
 * rhwp 는 한글 문서 뷰어라 docx 를 ZIP 으로 열고 hwpx 구조를 기대하다 실패한다
 * (`필수 파일 누락: Contents/content.hpf`). 화면이 「hwp·hwpx·pdf·docx 를 열 수
 * 있어요」라고 말해 왔지만 **docx 는 한 번도 안 열렸다.**
 *
 * 그 자리가 지금 중요해진 이유는 **docx 가 채워지는 포맷**이기 때문이다. hwp 는
 * 안내문이 든 칸을 못 덮어써서(ADR-0060 결정 3) 값이 몇 칸 안 들어가는데, docx 는
 * XML 이라 다 들어간다 — 채운 결과를 볼 수 있어야 그 이득이 사용자에게 닿는다.
 *
 * **`docx-preview` 는 HTML 로 그린다.** rhwp 처럼 원본을 재현하는 것이 아니라
 * 표·서식을 HTML 로 옮기는 것이라 미세한 차이가 있다. **그래서 쪽 수를 안 낸다** —
 * 여기서 센 쪽 수는 한/글이나 워드가 나눌 쪽과 다르고, 틀린 숫자를 내느니 안 낸다.
 */
export function DocxView({
  url,
  filename,
  downloadUrl,
  onFilled,
}: {
  url: string;
  filename: string;
  /** 못 열었을 때 내려받게 한다. 원본 URL 이다 */
  downloadUrl: string | null;
  /** 몇 칸을 채웠고 몇 칸이 남았나. **헤더로 온다** */
  onFilled?: (filled: number, left: number) => void;
}) {
  const mountRef = useRef<HTMLDivElement>(null);
  const [phase, setPhase] = useState<"여는 중" | "열렸다" | "못 열었다">("여는 중");
  const [why, setWhy] = useState("");

  // 부르는 쪽이 매 렌더 새 함수를 넘겨도 문서를 다시 안 열게 밖에 뺀다
  const filledRef = useRef(onFilled);
  useEffect(() => {
    filledRef.current = onFilled;
  }, [onFilled]);

  // 문서가 바뀌면 상태를 되돌린다. **`useEffect` 가 아니라 렌더 중에 맞춘다** —
  // 효과로 하면 지난 문서의 「못 열었어요」가 한 프레임 스쳐 지나간다.
  // `DocViewer` 가 같은 규칙을 쓴다.
  const [shownFor, setShownFor] = useState(url);
  if (url !== shownFor) {
    setShownFor(url);
    setPhase("여는 중");
  }

  useEffect(() => {
    // **취소 깃발.** 문서를 바꾸면 늦게 온 응답이 없어진 DOM 에 붙는다
    let dead = false;

    (async () => {
      try {
        const res = await fetch(url);
        if (!res.ok) {
          const body = await res.text().catch(() => "");
          throw new Error(reasonOf(body) || `서버가 ${res.status} 로 답했어요`);
        }
        // **채운 칸 수가 헤더로 온다.** 원본을 열 때는 헤더가 없어 안 부른다
        const filled = res.headers.get("x-finnect-filled");
        if (filled !== null) {
          filledRef.current?.(
            Number(filled),
            Number(res.headers.get("x-finnect-left") ?? 0),
          );
        }

        const buf = await res.arrayBuffer();
        if (dead) return;

        const mount = mountRef.current;
        if (!mount) return;
        // **매번 비운다.** `renderAsync` 가 덧붙이는 방식이라 안 비우면 문서를
        // 바꿀 때 앞의 것이 위에 남는다.
        mount.replaceChildren();

        const { renderAsync } = await import("docx-preview");
        if (dead) return;
        await renderAsync(buf, mount, undefined, {
          // 쪽 경계를 그린다. 신청서가 몇 쪽인지 사용자가 봐야 한다
          breakPages: true,
          inWrapper: true,
          // **글꼴을 무시하지 않는다.** 관공서 양식이 자간으로 칸을 맞춰서
          // 서식을 버리면 표가 어긋나 보인다
          ignoreFonts: false,
        });
        if (dead) return;
        setPhase("열렸다");
      } catch (e) {
        if (dead) return;
        setWhy(e instanceof Error ? e.message : "알 수 없는 이유예요");
        setPhase("못 열었다");
      }
    })();

    return () => {
      dead = true;
    };
  }, [url]);

  return (
    <div className={shell.stage}>
      <div ref={mountRef} className={styles.mount} data-busy={phase !== "열렸다"} />

      {phase === "여는 중" && (
        <p className={shell.status}>문서를 여는 중이에요.</p>
      )}

      {/* **`DocViewer` 의 `Notice` 를 안 가져온다.** 저쪽이 이 파일을 임포트하므로
          순환이 된다 — 클래스는 같은 모듈 CSS 에서 온다 */}
      {phase === "못 열었다" && (
        <div className={shell.notice}>
          <p className={shell.noticeTitle}>이 문서를 못 열었어요</p>
          <p className={shell.noticeBody}>{why}</p>
          <p className={shell.filename}>{filename}</p>
          {downloadUrl && (
            <a className={shell.cta} href={downloadUrl}>
              원본 파일 내려받기
            </a>
          )}
        </div>
      )}
    </div>
  );
}

/** 서버가 적은 이유를 꺼낸다. **"서버가 500 으로 답했어요" 보다 할 말이 많다** */
function reasonOf(body: string): string {
  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    return typeof parsed.detail === "string" ? parsed.detail : "";
  } catch {
    return "";
  }
}
