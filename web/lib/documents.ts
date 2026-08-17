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
  items: FormItem[];
};

export type NoticeDocuments = {
  notice: { id: string; source: string; title: string; url: string | null };
  documents: FormDocument[];
  /** 양식이 첨부에 없을 때, 공고문이 서류에 대해 말한 줄. **원문 그대로다.** */
  submitHint: string[] | null;
};

/** 항목 수를 센다. 트리라서 자식까지 내려간다. */
export function countItems(items: FormItem[]): number {
  return items.reduce((n, it) => n + 1 + countItems(it.children), 0);
}
