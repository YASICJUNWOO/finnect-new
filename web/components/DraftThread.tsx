"use client";

import { useEffect, useState } from "react";
import { ConfirmRow, DraftItemCard, ResetButton, StartRow, useDraft } from "./DraftView";
import type { Draft } from "@/lib/draft";
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
 * **직접 채우는 폼을 안 세운다.** 초안이 칸 서식까지 채우게 되면서(`WRITABLE_KINDS`)
 * 같은 칸을 두 곳이 그리게 됐고, 그러면 어느 쪽이 진짜인지 알 수 없다.
 *
 * ## 입력칸
 *
 * 자유 입력은 **엔드포인트가 아직 없다.** 쓰기 API 가 셋뿐이고(`tests/test_draft_start.py`
 * 가 그 셋뿐임을 잠가 뒀다) 대화 경로가 없다. 그래서 입력칸이 **지금 되는 일만**
 * 한다 — 「초안 쓰기」·「초기화」를 말로 부를 수 있고, 그 밖의 말에는 아직 못
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
  // **버튼 이름이 「초기화」라 그 말도 받는다.** 화면에 적힌 말을 그대로 쳤는데
  // 못 알아들으면 그 버튼이 없는 것으로 읽힌다
  if (/초기화|리셋/.test(t)) return "start";
  if (/(초안|다시|새로).*(써|쓰|작성|만들)/.test(t)) return "start";
  return null;
}

export function DraftThread({
  initial,
  source,
  externalId,
  company,
  onFocusDoc,
  onDraft,
}: {
  initial: Draft;
  source: string;
  externalId: string;
  company: string;
  /** 문서 구분선을 누르면 오른쪽이 그 문서로 간다. 없으면 구분선이 안 눌린다.
   *
   * **`document_id` 로 넘긴다** — `DraftDocument` 에 sha256 이 없고, 둘 다
   * `document.id` 에서 온 값이라 부르는 쪽이 `NoticeDocuments` 로 맞출 수 있다. */
  onFocusDoc?: (documentId: number) => void;
  /** 초안이 바뀌었다고 부르는 쪽에 알린다.
   *
   * **이것이 없으면 오른쪽 뷰어가 안 따라온다.** 초안 상태는 `useDraft` 안에서
   * 살고(폴링·저장·재작성이 전부 여기서 일어난다) 서버가 준 `initial` 은 그
   * 자리에 굳어 있다. 채운 파일 주소는 초안 항목 수로 만들어지므로, 알리지 않으면
   * 주소가 안 바뀌고 **새로고침해야 채운 값이 보인다.** */
  onDraft?: (draft: Draft) => void;
}) {
  const {
    draft, starting, why, start, onSave, written, done,
    edited, confirming, askReset, confirmReset, cancelReset,
  } = useDraft({ initial, source, externalId, company });
  const [said, setSaid] = useState<Said[]>([]);
  const [typed, setTyped] = useState("");

  // **렌더 중에 부르지 않는다.** 부모의 setState 를 렌더 도중에 부르면 React 가
  // 경고하고, 폴링이 도는 화면이라 그 경고가 몇 분 동안 쌓인다.
  useEffect(() => {
    onDraft?.(draft);
  }, [draft, onDraft]);

  /** **안 써진 것을 이유별로 가른다.** 「썼다 − 전체」로 세면 안 된다 — 그 차이에는
   *  쓸 자리가 아닌 칸(표 구분선·서명란)과 다른 항목이 재료를 맡은 칸이 섞여 있고,
   *  그 둘은 재료가 없는 것이 아니다. 칸 서식이 대상이 되면서 크게 벌어졌다:
   *  실측 69칸에서 못 채움 0 · 쓸 자리 아님 24 · 다른 항목이 맡음 28 이었는데
   *  화면은 **「52개는 재료가 없어요」**라고 말했다. */
  const blank = written.filter((i) => i.status === "blank").length;
  const hasDocs = draft.documents.length > 0;
  /** 눌러서 **채울** 것이 있나. **없으면 버튼을 안 낸다** — 눌러도 아무 일이 안
   *  일어나는 버튼은 고장 난 것으로 읽힌다(실측 `kstartup:178881`). 다시 쓰는 것은
   *  이 버튼이 아니라 머리줄의 초기화다(T-0161). */
  const canStart = draft.pending_documents > 0;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const text = typed.trim();
    if (!text) return;
    setTyped("");

    const mine: Said = { id: Date.now(), who: "나", text };
    if (readCommand(text) === "start") {
      // **말로 시켜도 같은 자리로 간다**(ADR-0062). 「다시 써 줘」가 초기화이고,
      // 버튼에만 확인을 붙이면 입력칸으로 들어온 사람의 고친 글이 조용히 사라진다
      const reply = !hasDocs
        ? "초안을 쓸게요."
        : edited > 0
          ? `직접 고친 항목이 ${edited}개 있어요. 초기화하면 그 글이 사라지는데, 위에서 눌러 주세요.`
          : "처음부터 다시 쓸게요.";
      setSaid((s) => [...s, mine, { id: mine.id + 1, who: "우리", text: reply }]);
      if (hasDocs) askReset();
      else void start();
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
        {/* **쓴 것이 있을 때만 낸다.** 지울 것이 없으면 초기화가 할 일이 없다 */}
        {hasDocs && !draft.running && (
          <ResetButton starting={starting} onAsk={askReset} styles={styles} />
        )}
      </div>

      {/* **머리줄 밖이다.** 저기는 스크롤 밖에 고정된 자리라 확인 줄까지 넣으면
          단이 짧은 화면에서 대화가 보이는 높이를 먹는다 */}
      {confirming && (
        <ConfirmRow
          edited={edited}
          starting={starting}
          onConfirm={confirmReset}
          onCancel={cancelReset}
          styles={styles}
        />
      )}

      {/* **`aria-live="polite"` 다.** assertive 로 하면 몇 분 동안 항목마다 끼어들어
          스크린 리더로 못 쓴다 */}
      <div className={styles.turns} aria-live="polite">
        {/* **「글로 쓰는 양식」이라고 말하지 않는다.** 칸만 채우는 서식도 초안이
            채운다 — 값 칸에는 값이 앉고 서술 칸에는 글이 선다. 화면이 서술형만
            센다고 말하면 신청서 한 벌이 빠진 것처럼 읽힌다 */}
        <p className={styles.system}>
          {hasDocs
            ? `서류 ${draft.documents.length}개를 읽었어요. 항목 ${written.length}개예요.`
            : draft.pending_documents > 0
              ? `채울 양식이 ${draft.pending_documents}개 있어요. 초안 쓰기를 누르면 채워 드려요.`
              : "이 공고에는 채울 양식이 아직 안 붙어 있어요. 원본 파일은 오른쪽에서 볼 수 있어요."}
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
              ? `${written.length}개 중 ${done}개를 썼어요. 나머지는 쓰는 자리가 아니에요.`
              : `${written.length}개 중 ${done}개를 썼어요. ${blank}개는 재료가 없어요.`}
          </p>
        )}

        {said.map((s) => (
          <p key={s.id} className={s.who === "나" ? styles.mine : styles.system}>
            {s.text}
          </p>
        ))}

        {why && <p className={styles.fail}>{why}</p>}

        {/* **직접 채우는 폼이 여기 없다.** 예전에는 칸 서식이 스레드 끝에 접혀
            붙어서 사람이 손으로 타이핑했고 그 값은 저장되지 않았다. 지금은 초안이
            같은 칸을 채우므로 **같은 칸이 화면에 두 번 나오게 된다** — 남기면 어느
            쪽이 진짜인지 사용자가 알 수 없다. 표본을 보는 화면
            (`/documents/<표본>/write`)에는 그대로 있다 */}
      </div>

      {/* 바닥 — 스크롤 밖에 고정 */}
      <div className={styles.foot}>
        {!draft.running && canStart && (
          <StartRow
            hasDocs={hasDocs}
            pending={draft.pending_documents}
            starting={starting}
            onStart={() => void start()}
            styles={styles}
          />
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
