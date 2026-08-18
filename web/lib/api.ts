/** FastAPI(:8100)와의 유일한 경계. 계약은 `docs/api-contract.md` 에 있다.
 *
 * **여기 말고 어디에서도 fetch 하지 않는다.** 프론트는 DB 를 모르고 SQL 도 모른다. */

const BASE = process.env.FINNECT_API ?? "http://127.0.0.1:8100";

/** 배포본에서만 쓴다. API 쪽 Vercel Authentication 을 서버 대 서버로 통과하는 유일한 수단이다
 *  (`x-vercel-protection-bypass`). 로컬은 값이 없어 헤더가 안 붙는다.
 *  **화면이 API 를 부르는 것과 사용자가 화면을 보는 것은 다른 문이다** — 이 값은 앞쪽 문만 연다. */
const BYPASS = process.env.FINNECT_API_BYPASS;

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

export type NoticeDetail = Notice & {
  /** HTML 을 푼 평문. 내용이 없으면 null */
  summary: string | null;
  attachments: Attachment[];
  decoded_count: number;
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
      headers: BYPASS ? { "x-vercel-protection-bypass": BYPASS } : undefined,
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

/** 없으면 null. 404 를 오류 화면으로 올리지 않는다 — notFound() 가 받는다. */
export async function getNotice(source: string, id: string): Promise<NoticeDetail | null> {
  try {
    return await get<NoticeDetail>(
      `/api/notices/${encodeURIComponent(source)}/${encodeURIComponent(id)}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

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
    items: {
      number: string | null;
      title: string;
      instruction: string | null;
      limit_text: string | null;
      input_kind: string;
    }[];
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
