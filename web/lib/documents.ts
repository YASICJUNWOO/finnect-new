/** 공고가 요구하는 문서와 그 안의 작성 항목.
 *
 * 저장 모델은 plan/11 T-0038 이 정한다. 이 타입은 그 모양을 그대로 따르므로
 * 파이프라인이 붙을 때 화면을 고치지 않아도 된다.
 *
 * **두 층을 헷갈리지 않는다.**
 * - 층 1 "무슨 서류를 내나" — 공고문에서 나온다. 양식 파일이 없어도 대부분 뽑힌다
 * - 층 2 "그 서류에 뭘 쓰나" — 양식 파일이 첨부에 실려 있어야 나온다
 *
 * 항목은 양식의 내용물이다. 양식이 없으면 층 1 만 있고, 그게 `submitHint` 다. */

/** 글로 쓰는 것 · 칸만 채우는 것 · 고르는 것. */
export type InputKind = "narrative" | "field" | "choice";

/** 문서 한 벌의 종류. 화면이 이걸로 갈린다(plan/11 T-0039). */
export type DocumentKind = "narrative" | "fields";

export type FormItem = {
  /** `2-1` 같은 항목 번호. 칸 채우기에는 없다. */
  number: string | null;
  title: string;
  /** 양식이 쓴 "무엇을 쓰라". **우리가 고쳐 쓰지 않는다.** */
  instruction: string | null;
  /** `50페이지 내외` 처럼 양식이 준 분량 제한. 있을 때만. */
  limitText?: string | null;
  inputKind: InputKind;
  children: FormItem[];
};

export type FormDocument = {
  id: string;
  title: string;
  kind: DocumentKind;
  attachment: { filename: string; url: string | null };
  /** 원본 파일의 콘텐츠 주소. 미리보기가 이걸로 원본을 받는다 */
  sha256: string;
  /** **내용으로 판정한** 확장자. 파일명의 확장자가 아니다 — 3,354건 중 7건이 다르다 */
  ext: string | null;
  items: FormItem[];
};

export type NoticeDocuments = {
  notice: { id: string; source: string; title: string; url: string | null };
  documents: FormDocument[];
  /** 양식이 첨부에 없을 때, 공고문이 서류에 대해 말한 줄. **원문 그대로다.** */
  submitHint: string[] | null;
  /** 아직 안 갈라 낸 구간 수. 서술형 판정(T-0036)이 붙기 전까지 0 이 아니다. */
  undecided?: number;
};

/** API 가 주는 항목. `api.ts` 의 `ApiFormItem` 과 구조가 같다.
 *
 * 여기 다시 적는 이유는 이 파일이 `api.ts` 를 안 부르기 때문이다 — 매핑 함수가
 * 전송 계층을 임포트하면 픽스처로 화면을 세울 때도 그것이 따라온다. */
type ApiItem = {
  number: string | null;
  title: string;
  instruction: string | null;
  limit_text: string | null;
  input_kind: string;
  children: ApiItem[];
};

/** 항목 하나. **트리째 내려간다** — 자식을 버리면 `2 추진배경 및 목표` 가 잎이 되고,
 * 쓰는 칸이 가지에 붙는다(`FormFill` 의 `leafKeys`). */
function toItem(i: ApiItem): FormItem {
  return {
    number: i.number,
    title: i.title,
    instruction: i.instruction,
    limitText: i.limit_text,
    inputKind: (i.input_kind as InputKind) ?? "field",
    children: (i.children ?? []).map(toItem),
  };
}

/** API 응답을 화면 모양으로. **매핑은 여기 한 곳에만 둔다.**
 *
 * 계약이 snake_case 고 화면은 camelCase 라 어디선가 한 번은 바뀐다. 그 자리를
 * 컴포넌트 안에 흩어 두면 계약이 바뀔 때 고칠 곳을 못 찾는다. */
export function fromApi(
  api: {
    documents: {
      id: number;
      title: string;
      kind: string;
      filename: string;
      url: string | null;
      sha256: string;
      ext: string | null;
      items: ApiItem[];
    }[];
    submit_hint: string[];
    undecided: number;
  },
  notice: { id: string; source: string; title: string; url: string | null },
): NoticeDocuments {
  return {
    notice,
    documents: api.documents.map((d) => ({
      id: String(d.id),
      title: d.title,
      kind: d.kind === "fields" ? "fields" : "narrative",
      attachment: { filename: d.filename, url: d.url },
      sha256: d.sha256,
      ext: d.ext,
      items: d.items.map(toItem),
    })),
    submitHint: api.submit_hint.length > 0 ? api.submit_hint : null,
    undecided: api.undecided,
  };
}

/** 항목 수를 센다. 트리라서 자식까지 내려간다. */
export function countItems(items: FormItem[]): number {
  return items.reduce((n, it) => n + 1 + countItems(it.children), 0);
}

/** 미리보기가 여는 포맷. **API `_VIEWABLE` 과 같아야 한다** —
 * 갈리면 화면이 버튼을 띄우고 서버가 415 를 준다.
 *
 * `zip` 이 없는 것은 안에 뭐가 들었는지 우리가 모르기 때문이고, 그림·xlsx 가 없는
 * 것은 rhwp 가 문서 뷰어이기 때문이다. */
const VIEWABLE = new Set(["hwp", "hwpx", "pdf", "docx"]);

/** 미리보기(`FormPreview`)를 열 수 있나. **원본을 그대로 띄우므로 포맷이 정한다.**
 *
 * 항목 수로 판단하지 않는다 — 우리가 뽑은 항목이 0개여도 원본 문서는 멀쩡히
 * 열린다. 오히려 그럴 때 원본을 보는 것이 제일 쓸모 있다.
 *
 * **파일명으로 거르지 않는다.** 여기 오는 문서는 API 가 이미 `narrative`·`fields`
 * 로 좁힌 것이라(`api/service.py` `notice_documents` 가 `none`·`unknown` 을 뺀다)
 * 전부 신청서 아니면 계획서다. 파일명 `신청|계획` 은 사업계획서를 가진 공고
 * 53건 중 16건만 맞혔다(재현율 30% · 2026-08-22 실측) — 사업계획서가 대개
 * 「공고문」이라는 이름의 묶음 파일 안에 있기 때문이다.
 *
 * **이 함수가 `FormPreview.tsx` 에 있으면 안 된다.** 저기가 `"use client"` 라
 * 서버 컴포넌트인 `FormDocuments` 가 부르면 런타임에 500 이 난다. */
export function canPreview(doc: FormDocument): boolean {
  return doc.ext !== null && VIEWABLE.has(doc.ext);
}
