/** 초안 (S4 · plan/16 · plan/21). 계약은 `docs/api-contract.md` 에 있다.
 *
 * **타입 이름을 `api/schemas.py` 에서 가져온다.** 화면이 새로 짓지 않는다 —
 * `place_label` 을 API 가 붙이는 것과 같은 규율이고, 갈리면 어느 쪽이 맞는지 모른다. */

import { get, send } from "./api";

/** 문단 하나가 어디서 나왔나 (F6-13).
 *
 * **`fact_id` 를 든다.** 그 사실이 갱신되면 어느 항목이 낡았는지 되짚는다
 * (ADR-0028 4번). 나중에 붙일 수 없다. */
export type DraftEvidence = {
  fact_id: number;
  place: string;
  /** 사람이 읽는 자리 이름. **화면이 한국어를 짓지 않는다** */
  place_label: string;
  text: string;
  chunk_id: number | null;
  /** 청크에서 잘라 온 조각. 원문을 열기 전에 이걸 먼저 보여 준다 */
  quote: string | null;
  /** `document` · `user_stated`. **색이 아니라 글자로 가른다**(ADR-0028) */
  source_type: string;
};

export type DraftParagraph = {
  ordinal: number;
  text: string;
  evidence: DraftEvidence[];
};

/** 필요한데 위키에 없는 자리. **F6-6 이 가리키는 것** */
export type DraftMissing = {
  place: string;
  place_label: string;
  required: boolean;
};

/** 분량. **저장하지 않고 읽을 때 계산한다** */
export type DraftLength = {
  /** `none` · `ok` · `over` · `unmeasurable` */
  verdict: string;
  limit_text: string | null;
  /** 쪽 수 제한이면 null — **환산하지 않는다** */
  measured: number | null;
  note: string;
};

export type DraftItem = {
  document_item_id: number;
  number: string | null;
  title: string;
  instruction: string | null;
  /** `drafted` · `answered` · `blank` · `no_needs` · `yielded` · `unwritten` · `stale`.
   *  **물어볼 자리는 `blank` 하나다** */
  status: string;
  /** 사람이 고쳤다. `status` 와 다른 축이다(ADR-0055) */
  edited: boolean;
  /** 고쳐서 문단과 근거의 대응이 깨졌다. **행은 DB 에 그대로 있다** */
  evidence_detached: boolean;
  /** 집필기가 쓴 글. 고쳤을 때만 찬다 — 되돌릴 자리를 화면이 알아야 한다 */
  original: string | null;
  paragraphs: DraftParagraph[];
  missing: DraftMissing[];
  missing_optional: DraftMissing[];
  length: DraftLength;
  /** `yielded` 일 때 그 재료를 맡은 항목 번호들 */
  yielded_to: string[];
  error: string | null;
  children: DraftItem[];
};

export type DraftDocument = {
  document_id: number;
  title: string;
  filename: string;
  allotted_by: string | null;
  items: DraftItem[];
};

export type Draft = {
  company_id: string;
  source: string;
  external_id: string;
  documents: DraftDocument[];
  /** 서술형 양식은 있는데 초안이 아직 없다 — 돌리면 생긴다 */
  pending_documents: number;
  /** 지금 쓰고 있다. **빈 목록이 「안 눌렀다」인지 「기다리는 중」인지 가른다** */
  running: boolean;
};

export type DraftStart = {
  started: boolean;
  reason: string;
  draft: Draft;
};

function base(source: string, id: string): string {
  return `/api/notices/${encodeURIComponent(source)}/${encodeURIComponent(id)}/draft`;
}

/** 초안을 읽는다. **없으면 빈 목록이고 404 가 아니다.** */
export function getDraft(source: string, id: string, company: string): Promise<Draft> {
  return get<Draft>(`${base(source, id)}?company=${encodeURIComponent(company)}`);
}

/** 초안을 쓰기 시작한다 (T-0121). **202 이고 거절도 202 다.**
 *
 * `redo` 가 화면의 **「초기화」**다(T-0161). 없으면 이미 초안이 있는 양식을 건너뛰고
 * — API 가 LLM 을 부르기 전에 거른다 — 그것이 하단 「쓰기」가 부르는 길이다. 있으면
 * 그 양식을 처음부터 다시 쓰는데 **사람이 고친 글도 사라진다**(ADR-0062). 그 사실을
 * 먼저 말하는 것은 `DraftView` 의 `ConfirmRow` 몫이다. */
export function startDraft(
  source: string,
  id: string,
  company: string,
  redo = false,
): Promise<DraftStart> {
  const q = `company=${encodeURIComponent(company)}${redo ? "&redo=true" : ""}`;
  return send<DraftStart>(`${base(source, id)}?${q}`, { method: "POST" });
}

/** 고친 글을 저장한다 (T-0123). `text: null` 이 되돌리기다. */
export function editDraftItem(
  source: string,
  id: string,
  company: string,
  itemId: number,
  text: string | null,
): Promise<DraftItem> {
  return send<DraftItem>(
    `${base(source, id)}/items/${itemId}?company=${encodeURIComponent(company)}`,
    { method: "PUT", body: JSON.stringify({ text }) },
  );
}

/** 잎만 센다. **가지는 양식의 묶음이라 쓰는 칸이 아니다** — `FormFill` 과 같은 규칙이다. */
export function leaves(items: DraftItem[]): DraftItem[] {
  return items.flatMap((i) => (i.children.length > 0 ? leaves(i.children) : [i]));
}

/** 이 항목이 지금 들고 있는 글. 고쳤으면 사람 것, 아니면 집필기 것. */
export function bodyOf(item: DraftItem): string {
  return item.paragraphs.map((p) => p.text).join("\n\n");
}
