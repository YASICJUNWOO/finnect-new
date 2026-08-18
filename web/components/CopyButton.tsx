"use client";

import { useState } from "react";
import styles from "./CopyButton.module.css";

/** 클립보드로 복사. **같은 동작에 같은 단어를 쓴다**(§8.3-3) —
 * 누르기 전 "복사", 누른 뒤 "복사했어요". "완료"로 갈아타지 않는다.
 *
 * 실패하면 사과하지 않고 **무엇을 하면 되는지** 적는다(§8.1-4). http 로 열었거나
 * 브라우저가 막으면 `navigator.clipboard` 가 없다 — 그때 글을 직접 긁으면 된다. */
export function CopyButton({ text, label }: { text: string; label: string }) {
  const [state, setState] = useState<"idle" | "done" | "failed">("idle");

  return (
    <button
      type="button"
      className={styles.button}
      data-state={state}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setState("done");
          setTimeout(() => setState("idle"), 2000);
        } catch {
          setState("failed");
        }
      }}
    >
      {state === "done" ? "복사했어요" : state === "failed" ? "글을 직접 긁어 주세요" : label}
    </button>
  );
}
