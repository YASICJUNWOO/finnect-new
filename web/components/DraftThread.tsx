"use client";

import { useState } from "react";
import { DraftItemCard, useDraft } from "./DraftView";
import { FormFill } from "./FormFill";
import type { Draft } from "@/lib/draft";
import type { NoticeDocuments } from "@/lib/documents";
import styles from "./DraftThread.module.css";

/** 초안 단 — 무엇이 일어났는지 차례로 쌓인다.
 *
 * **말풍선도 아바타도 타이핑 표시도 없다.** §7 이 UI 크롬에 색과 채움을 금지했고
 * §10 이 대행한다고 말하지 말라고 했다. 여기서 「대화」는 모양이 아니라 **차례**다 —
 * 무엇을 읽었고 무엇을 썼고 무엇이 없는지가 순서대로 남는다.
 *
 * **진행 막대가 없다**(§7 · §12.2). 스레드가 자라는 것이 진행이다.
 *
 * **안 온 항목의 자리를 미리 안 그린다.** 회색 막대를 세우면 그것이 예시 데이터다.
 *
 * ## 입력칸
 *
 * 자유 입력은 **엔드포인트가 아직 없다.** 쓰기 API 가 셋뿐이고(`tests/test_draft_start.py`
 * 가 그 셋뿐임을 잠가 뒀다) 대화 경로가 없다. 그래서 입력칸이 **지금 되는 일만**
 * 한다 — 「초안 쓰기」·「다시 쓰기」를 말로 부를 수 있고, 그 밖의 말에는 아직 못
 * 한다고 답한다. **비활성으로 안 둔다** — §14 의 비활성은 「다른 상태에서는 되는
 * 것」에 쓰는 표시다.
 *
 * 진짜 대화가 붙는 자리는 `POST …/draft/ask` 이고 ADR-0028 이 그 모양을 이미
 * 정해 뒀다(답하면 위키에 먼저 저장한 뒤 그 항목만 재작성). */

/** 사람이 친 말과 우리가 답한 말. **서버에 안 남는다** — 새로고침하면 사라지고
 * 그것을 화면이 말한다. */
type Said = { id: number; who: "나" | "우리"; text: string };

/** 지금 말로 부를 수 있는 것. **여기 없는 말은 못 알아듣는다고 답한다** —
 * 알아듣는 척하면 안 한 일을 했다고 말하게 된다. */
function readCommand(said: string): "start" | null {
  const t = said.replace(/\s+/g, "");
  if (/(초안|다시|새로).*(써|쓰|작성|만들)/.test(t)) return "start";
  return null;
}

export function DraftThread({
  initial,
  source,
  externalId,
  company,
  fields,
  onFocusDoc,
}: {
  initial: Draft;
  source: string;
  externalId: string;
  company: string;
  /** 칸 채우기 서식. 있으면 스레드 끝에 접혀 붙는다 */
  fields: NoticeDocuments | null;
  /** 문서 구분선을 누르면 오른쪽이 그 문서로 간다. 없으면 구분선이 안 눌린다.
   *
   * **`document_id` 로 넘긴다** — `DraftDocument` 에 sha256 이 없고, 둘 다
   * `document.id` 에서 온 값이라 부르는 쪽이 `NoticeDocuments` 로 맞출 수 있다. */
  onFocusDoc?: (documentId: number) => void;
}) {
  const { draft, starting, why, start, onSave, written, done } = useDraft({
    initial,
    source,
    externalId,
    company,
  });
  const [said, setSaid] = useState<Said[]>([]);
  const [typed, setTyped] = useState("");

  const blank = written.length - done;
  const hasDocs = draft.documents.length > 0;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const text = typed.trim();
    if (!text) return;
    setTyped("");

    const mine: Said = { id: Date.now(), who: "나", text };
    if (readCommand(text) === "start") {
      setSaid((s) => [
        ...s,
        mine,
        { id: mine.id + 1, who: "우리", text: hasDocs ? "다시 쓸게요." : "초안을 쓸게요." },
      ]);
      void start();
      return;
    }
    setSaid((s) => [
      ...s,
      mine,
      {
        id: mine.id + 1,
        who: "우리",
        text: "아직 자유롭게 대화하지는 못해요. 지금은 「초안 써 줘」만 알아들어요.",
      },
    ]);
  }

  return (
    <div className={styles.thread}>
      {/* 머리줄 — 스크롤 밖에 고정. 셋 이하로 둔다(§10) */}
      <div className={styles.head}>
        <h2 className={styles.title}>초안</h2>
        {hasDocs && (
          <p className={styles.count} data-numeric>
            {written.length}개 중 <b>{done}개</b>가 써졌어요
          </p>
        )}
      </div>

      {/* **`aria-live="polite"` 다.** assertive 로 하면 몇 분 동안 항목마다 끼어들어
          스크린 리더로 못 쓴다 */}
      <div className={styles.turns} aria-live="polite">
        <p className={styles.system}>
          {hasDocs
            ? `서류 ${draft.documents.length}개를 읽었어요. 항목 ${written.length}개예요.`
            : draft.pending_documents > 0
              ? `글로 쓰는 양식이 ${draft.pending_documents}개 있어요. 초안 쓰기를 누르면 채워 드려요.`
              : "이 공고에는 글로 쓰는 양식이 아직 안 붙어 있어요. 칸만 채우는 서식은 아래에서 쓸 수 있어요."}
        </p>

        {draft.documents.map((doc) => (
          <section key={doc.document_id} className={styles.doc}>
            {/* 두 단이 이어져 있다는 유일한 표시. **오른쪽 칩과 같은 문자열이다** */}
            {onFocusDoc ? (
              <button
                type="button"
                className={styles.divider}
                onClick={() => onFocusDoc(doc.document_id)}
                aria-label={`${doc.title} 양식 열기`}
              >
                {doc.title}
              </button>
            ) : (
              <p className={styles.dividerFlat}>{doc.title}</p>
            )}

            <ol className={styles.items}>
              {doc.items.map((it) => (
                <DraftItemCard key={it.document_item_id} item={it} onSave={onSave} />
              ))}
            </ol>
          </section>
        ))}

        {draft.running && (
          <p className={styles.note}>
            지금 쓰고 있어요. 항목이 많으면 몇 분 걸려요 — 이 화면을 열어 둬도 돼요.
          </p>
        )}

        {/* **칭찬하지 않는다.** 다 썼다는 것은 사실이고 잘 됐다는 것은 우리가 모른다 */}
        {!draft.running && hasDocs && (
          <p className={styles.system}>
            {blank === 0
              ? `${written.length}개를 다 썼어요.`
              : `${written.length}개 중 ${done}개를 썼어요. ${blank}개는 재료가 없어요.`}
          </p>
        )}

        {said.map((s) => (
          <p key={s.id} className={s.who === "나" ? styles.mine : styles.system}>
            {s.text}
          </p>
        ))}

        {why && <p className={styles.fail}>{why}</p>}

        {/* 칸 채우기 서식. **접어 둔다** — 저장이 안 되는 폼이 스레드를 덮으면 안 된다.
            `heading="none"` 이라 제목과 진행은 안 그리고 「저장 안 된다」는 그대로 남는다 */}
        {fields && fields.documents.length > 0 && (
          <details className={styles.fields}>
            <summary className={styles.fieldsSummary}>
              칸만 채우는 서식 <span data-numeric>{fields.documents.length}</span>개
            </summary>
            <FormFill data={fields} heading="none" />
          </details>
        )}
      </div>

      {/* 바닥 — 스크롤 밖에 고정 */}
      <div className={styles.foot}>
        {!draft.running && (
          <div className={styles.startRow}>
            <button
              type="button"
              className={styles.start}
              onClick={() => void start()}
              disabled={starting}
            >
              {hasDocs ? "다시 쓰기" : "초안 쓰기"}
            </button>
            <span className={styles.startWhy}>
              {hasDocs
                ? "못 쓴 항목만 다시 써요. 내가 고친 글은 그대로 둬요."
                : "위키에 있는 것으로 항목마다 써 드려요."}
            </span>
          </div>
        )}

        <form className={styles.composer} onSubmit={submit}>
          <input
            className={styles.input}
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder="초안 써 줘"
            aria-label="초안에게 말하기"
          />
          <button type="submit" className={styles.send} disabled={!typed.trim()}>
            보내기
          </button>
        </form>

        {/* **제약을 숨기지 않는다**(§10). 한 번만 적는다 */}
        <p className={styles.limitNote}>
          아직 「초안 써 줘」만 알아들어요. 여기 주고받은 말은 저장되지 않아요.
        </p>
      </div>
    </div>
  );
}
