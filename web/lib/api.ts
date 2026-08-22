/** FastAPI(:8100)와의 유일한 경계. 계약은 `docs/api-contract.md` 에 있다.
 *
 * **여기 말고 어디에서도 fetch 하지 않는다.** 프론트는 DB 를 모르고 SQL 도 모른다. */

export const BASE = process.env.FINNECT_API ?? "http://127.0.0.1:8100";

/** 배포본에서만 쓴다. API 쪽 Vercel Authentication 을 서버 대 서버로 통과하는 유일한 수단이다
 *  (`x-vercel-protection-bypass`). 로컬은 값이 없어 헤더가 안 붙는다.
 *  **화면이 API 를 부르는 것과 사용자가 화면을 보는 것은 다른 문이다** — 이 값은 앞쪽 문만 연다. */
const BYPASS = process.env.FINNECT_API_BYPASS;

/** API 가 요구하는 토큰(ADR-0035). **Vercel Authentication 을 대신하는 것이다** —
 *  API 가 이 서버로 내려오면서 그 문이 없어졌고, 없으면 올리기 경로가 인터넷에 열린다. */
const TOKEN = process.env.FINNECT_API_TOKEN;

/** API 로 나가는 모든 요청이 붙이는 헤더. **한 곳에 모은다** — `get()` 과 `uploadFiles()`
 *  가 각자 헤더를 만들면 한쪽만 고쳐지는 날이 오고, 그날 올리기만 401 이 된다.
 *
 *  값이 없으면 그 헤더를 안 붙인다. 로컬은 둘 다 없어서 빈 객체가 나간다. */
export function authHeaders(): Record<string, string> {
  const h: Record<string, string> = {};
  if (BYPASS) h["x-vercel-protection-bypass"] = BYPASS;
  if (TOKEN) h["x-finnect-token"] = TOKEN;
  return h;
}

/** 필드 이름이 `views.py` 의 `Notice` 와 같다. 새로 짓지 않는다. */
export type Notice = {
  source: string;
  external_id: string;
  title: string | null;
  organization: string | null;
  supervisor: string | null;
  category: string | null;

  apply_start: string | null;
  apply_end: string | null;
  /** 날짜가 아닌 원문. "예산 소진시까지" 등 34종. **뭉개지 않는다** */
  apply_period_raw: string | null;
  /** `apply_end` 가 있을 때만. 음수면 지났다. 날짜 계산은 서버가 한다 */
  days_left: number | null;

  detail_url: string | null;
  attachment_count: number;
};

export type Attachment = {
  position: number;
  kind: string;
  filename: string;
  ext: string | null;
  url: string | null;
  /** null = 아직 안 받아 봤다 */
  fetch_status: string | null;
  /** null = 아직 안 읽어 봤다. `unsupported`·`failed`·`empty` 는 각각 뜻이 다르다 */
  parse_status: string | null;
  text_chars: number | null;
  detected_ext: string | null;
};

/** 이 공고가 이 회사에게 왜 맞는가.
 *
 * **자격이 여기 없다.** ADR-0003 이 「판정은 뒤에서 하고 화면은 결과만 준다」로 정했고,
 * 자격 결과는 목록에서 빼는 것으로 이미 나갔다. 등급별 대조표를 화면에 두면 우리 일을
 * 사용자에게 떠넘기는 것이 된다.
 *
 * **점수가 없다**(DESIGN.md §7 · §12.2). 92 와 74 의 차이를 설명할 눈금이 없다. */
export type Fit = {
  /** `맞다` · `애매`. **`아니다` 는 저장되지 않아 여기 안 온다** */
  verdict: string;
  /** 왜 맞는지 한 줄. 템플릿이 만들고 LLM 이 안 만든다 */
  reason: string;
  /** 그 이유가 위키의 몇 개 사실에서 나왔나 */
  evidence_count: number;
};

export type NoticeDetail = Notice & {
  /** HTML 을 푼 평문. 내용이 없으면 null */
  summary: string | null;
  attachments: Attachment[];
  decoded_count: number;
  /** `?company=` 를 줬고 판정이 있을 때만 찬다. **`null` 은 「안 맞아요」가 아니라
   *  「아직 안 봤어요」다** — 화면이 그 자리를 아예 안 그린다 */
  fit: Fit | null;
};

/** 추천 한 장. 목록의 `Notice` 에 이유와 근거 수가 붙는다.
 *
 * **순서가 정보를 담는다**(DESIGN.md §7). 서버가 정렬해서 주고 화면은 그대로 그린다 —
 * 여기서 다시 정렬하면 CLI 가 찍는 순서와 화면이 갈린다. */
export type Recommendation = Notice & {
  reason: string;
  evidence_count: number;
};

export type Recommendations = {
  items: Recommendation[];
  /** 판정을 돌렸나. **빈 목록과 다르다** — 저쪽은 맞는 것이 없다는 뜻이고
   *  이쪽은 아직 못 봤다는 뜻이라 화면이 다른 문장을 써야 한다 */
  computed: boolean;
};

export type NoticeList = {
  items: Notice[];
  total: number;
  page: number;
  pages: number;
  open_only: boolean;
};

/** API 가 죽었을 때 화면이 무엇을 말할지 정하려면 원인이 남아야 한다. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
    options?: { cause?: unknown },
  ) {
    super(message, options);
    this.name = "ApiError";
  }
}

/** 유일한 fetch. **`lib/admin.ts` 도 이걸 쓴다** — 운영 화면이 별도 fetch 를 갖게 되면
 *  타임아웃·리다이렉트·SSO 우회 규칙이 두 벌이 되고, 한쪽만 고쳐지는 날이 온다. */
export async function get<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      cache: "no-store",
      headers: authHeaders(),
      // 리다이렉트를 따라가면 SSO 로그인 HTML 을 200 으로 받아 JSON 파싱에서 죽는다.
      // 막혔으면 302 그대로 받아 ApiError 로 올린다.
      redirect: "manual",
    });
  } catch (cause) {
    // 대개 API 가 안 떠 있다. **빈 화면으로 죽지 않고** error.tsx 가 받는다.
    // 원인을 매달아 둔다 — 서버 로그에서 무엇이 끊겼는지 봐야 한다.
    throw new ApiError(`API에 못 붙었어요 (${BASE})`, undefined, { cause });
  }
  if (!res.ok) {
    throw new ApiError(`API가 ${res.status}로 답했어요`, res.status);
  }
  return (await res.json()) as T;
}

/** 쓰기. **`get()` 과 같은 규칙을 쓴다** — 헤더도 리다이렉트 처리도 한 곳에서 온다.
 *
 * `get()` 을 복사하지 않고 따로 둔 이유는 본문과 메서드뿐이다. 합치면 읽기 경로에
 * `method` 인자가 생기고, 그러면 **읽기인 줄 알고 부른 자리가 쓰기가 될 수 있다.** */
export async function send<T>(path: string, init: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      cache: "no-store",
      headers: { "content-type": "application/json", ...authHeaders(), ...init.headers },
      redirect: "manual",
    });
  } catch (cause) {
    throw new ApiError(`API에 못 붙었어요 (${BASE})`, undefined, { cause });
  }
  if (!res.ok) {
    // **서버가 적은 이유를 그대로 올린다.** "API가 404로 답했어요" 보다
    // "초안에 없는 항목: 9999" 가 화면에서 할 말이 많다
    const detail = await res.text().catch(() => "");
    throw new ApiError(reasonOf(detail) ?? `API가 ${res.status}로 답했어요`, res.status);
  }
  return (await res.json()) as T;
}

function reasonOf(body: string): string | null {
  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    return typeof parsed.detail === "string" ? parsed.detail : null;
  } catch {
    return null;
  }
}

export function listNotices(params: {
  q?: string;
  source?: string;
  page?: number;
  openOnly?: boolean;
}): Promise<NoticeList> {
  const qs = new URLSearchParams();
  if (params.q) qs.set("q", params.q);
  if (params.source) qs.set("source", params.source);
  if (params.page && params.page > 1) qs.set("page", String(params.page));
  if (params.openOnly === false) qs.set("open_only", "false");
  const query = qs.toString();
  return get<NoticeList>(`/api/notices${query ? `?${query}` : ""}`);
}

/** 없으면 null. 404 를 오류 화면으로 올리지 않는다 — notFound() 가 받는다.
 *
 * `company` 를 주면 `fit`(왜 맞는지)이 같이 온다. 안 주면 `null` 이다 —
 * **인증이 없어서 부르는 쪽이 누구인지 말한다.** */
export async function getNotice(
  source: string,
  id: string,
  company?: string,
): Promise<NoticeDetail | null> {
  const qs = company ? `?company=${encodeURIComponent(company)}` : "";
  try {
    return await get<NoticeDetail>(
      `/api/notices/${encodeURIComponent(source)}/${encodeURIComponent(id)}${qs}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

/** 추천 세 건 (plan/17 T-0075 · plan/21 T-0119).
 *
 * **실패해도 목록 화면은 떠야 한다.** 아래쪽 「전체 공고」는 위키가 없어도 뜨는
 * 섹션이라, 위쪽이 못 왔다고 화면 전체를 죽이면 `getNoticeDocuments` 가 배포본에서
 * 상세를 통째로 500 으로 만든 것과 같은 일이 난다.
 *
 * **`null` 과 `computed: false` 가 다르다.** `null` 은 우리가 못 물어본 것이고
 * `computed: false` 는 물어봤더니 아직 안 돌렸다는 답이다. */
export async function getRecommendations(
  companyId: string,
): Promise<Recommendations | null> {
  try {
    return await get<Recommendations>(
      `/api/companies/${encodeURIComponent(companyId)}/recommendations`,
    );
  } catch (e) {
    console.error("추천을 못 불러왔다 — 전체 공고는 그대로 띄운다", e);
    return null;
  }
}

/** 작성 항목 하나. **트리다** — 글로 쓰는 양식이 `2` 아래로 `2-1`·`2-2` 를 낳는다.
 *
 * 이름을 붙인 이유가 그것이다 — 익명 타입으로는 `children` 이 자기를 못 가리킨다. */
export type ApiFormItem = {
  number: string | null;
  title: string;
  instruction: string | null;
  limit_text: string | null;
  input_kind: string;
  children: ApiFormItem[];
};

/** 공고가 요구하는 서류. 계약은 `docs/api-contract.md`, 정본은 `api/schemas.py` 다. */
export type NoticeDocuments = {
  source: string;
  external_id: string;
  documents: {
    id: number;
    title: string;
    /** `fields` 칸 채우기 · `narrative` 글로 쓰는 것 */
    kind: string;
    /** 무엇이 판정했나. `rule/v1` · `llm/<모델>` */
    decided_by: string;
    filename: string;
    url: string | null;
    items: ApiFormItem[];
  }[];
  /** 양식이 없을 때 공고문이 서류에 대해 말한 줄. 원문 그대로다. */
  submit_hint: string[];
  /** 아직 안 갈라 낸 구간 수. **0 이 아니면 화면이 그렇게 말해야 한다.** */
  undecided: number;
};

/** 서류를 못 불러와도 **공고 상세는 떠야 한다.**
 *
 * 처음에 404 만 삼키고 나머지를 던졌더니 배포본에서 상세가 통째로 500 이 됐다.
 * 배포 DB 에 `document` 표가 아직 없었는데, **곁다리 섹션 하나가 본문을 죽인 것이다.**
 *
 * 그래서 어떤 실패든 null 로 돌려세운다. **null 은 "양식이 없다"가 아니라 "모른다"다** —
 * 화면은 섹션을 아예 안 그린다. 빈 화면("양식이 첨부에 없어요")은 서버가 빈 목록을
 * 줬을 때만 뜬다. 둘을 섞으면 우리가 못 읽은 것을 공고 탓으로 돌리게 된다. */
export async function getNoticeDocuments(
  source: string,
  id: string,
): Promise<NoticeDocuments | null> {
  try {
    return await get<NoticeDocuments>(
      `/api/notices/${encodeURIComponent(source)}/${encodeURIComponent(id)}/documents`,
    );
  } catch (e) {
    console.error("서류를 못 불러왔다 — 상세는 그대로 띄운다", e);
    return null;
  }
}
