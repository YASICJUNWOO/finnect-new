/** 운영 화면이 부르는 것. 경계는 `lib/api.ts` 와 같고 경로만 `/api/admin/` 이다.
 *
 * **제품 타입(`lib/api.ts`)과 섞지 않는다.** 저기는 사용자가 볼 값을 고른 것이고
 * 여기는 출처가 준 것을 하나도 안 고르고 다 받는다. 목적이 반대다(ADR-0027).
 *
 * 이름은 `src/finnect/api/admin_schemas.py` 와 한 글자도 다르지 않다. 새로 짓지 않는다 —
 * 이름이 한 번 더 바뀌면 화면에서 본 값이 DB 의 어느 칸인지 추적이 끊긴다.
 *
 * **여기 말고 어디에서도 fetch 하지 않는다.** 프론트는 DB 를 모르고 SQL 도 모른다. */

import { ApiError, get, send } from "./api";

export type AdminNotice = {
  source: string;
  external_id: string;
  title: string | null;
  organization: string | null;
  apply_end: string | null;
  apply_period_raw: string | null;
  attachment_count: number;
  /** `unknown` 이면 출처가 첨부를 안 알려줬다. **0 과 뜻이 다르다** */
  attachment_status: string | null;
  last_seen_at: string | null;
};

export type AdminNoticeList = {
  items: AdminNotice[];
  total: number;
  page: number;
  pages: number;
  page_size: number;
  sort: string;
  /** 고를 수 있는 정렬. **프론트가 목록을 짓지 않는다** */
  sorts: Record<string, string>;
  by_source: Record<string, number>;
};

export type Field = {
  name: string;
  value: string | null;
  /** null 이면 **공식 문서에 없다.** 이름으로 뜻을 추측해 채우지 않았다 */
  description: string | null;
};

export type AdminAttachment = {
  position: number;
  kind: string;
  filename: string;
  ext: string | null;
  url: string | null;
  fetch_status: string | null;
  parse_status: string | null;
  parser: string | null;
  text_chars: number | null;
  /** 내용으로 판정한 확장자. `ext`(파일명 기준)와 다를 수 있다 */
  detected_ext: string | null;
  fetch_error: string | null;
  parse_error: string | null;
  /** ZIP 안 파일 이름. **풀지는 않았다** */
  contents: string[];
};

export type RawFetch = {
  id: number;
  /** 인증키는 저장 전에 마스킹된다(`ingest/base.py` `mask()`) */
  request_url: string;
  fetched_at: string | null;
  page: number | null;
  item_count: number;
  byte_size: number;
  ratelimit_remaining: number | null;
  envelope: string;
  /** 응답 안에서 이 공고를 못 찾으면 null */
  item: string | null;
  siblings: number;
};

export type AdminNoticeDetail = {
  source: string;
  external_id: string;
  table: string;
  api_fields: Field[];
  ours: Field[];
  /** 비어 있지 않으면 **API 가 늘어났다는 뜻이다** */
  extra: Record<string, string>;
  described: number;
  described_total: number;
  doc_label: string;
  doc_url: string | null;
  attachments: AdminAttachment[];
  decoded_count: number;
  raw: RawFetch | null;
};

export type StatusCount = {
  /** null 이면 **아직 안 해 봤다** */
  status: string | null;
  count: number;
};

export type Coverage = {
  listed: number;
  urls: number;
  files: number;
  /** **이 화면에서 가장 먼저 봐야 하는 값이다.** 0이 아니면 나머지는 모집단이 아니다 */
  unaccounted: number;
  fetch: StatusCount[];
  parse: StatusCount[];
  by_ext: { ext: string | null; status: string; count: number; avg_chars: number }[];
};

export type AdminAttachments = {
  coverage: Coverage;
  ocr: { pdf_empty: number; images: number; image_notices: number };
  formats: string[];
};

export type Run = {
  id: number;
  source: string;
  only_open: boolean;
  /** 어느 솎기 정책으로 받았나. null 이면 안 솎았다(ADR-0064) */
  filter_name: string | null;
  /** 정책으로 뺀 건수. `unchanged` 와 다르다 — 저건 안 바뀐 것이고 이건 안 받은 것이다 */
  filtered: number;
  trigger: string;
  status: string;
  started_at: string | null;
  /** 사람이 읽는 문자열. **날짜 계산을 프론트가 하지 않는다** */
  elapsed: string;
  item_limit: number | null;
  expected: number | null;
  truncated: boolean;
  pages: number;
  items: number;
  inserted: number;
  changed: number;
  unchanged: number;
  report: string | null;
  error: string | null;
  /** 처음 보는 필드 {이름: 건수}. **조용히 사라지지 않게 화면까지 들고 온다** */
  unknown_fields: Record<string, number>;
};

/** `running` 이 참일 때만 의미가 있다. `ingest/jobs.py` `Progress` 사본.
 *
 * **단계가 둘이다.** K-Startup 을 모집중만 받으면 목록 뒤에 상세 페이지 긁기가 이어
 * 붙는다 — `phase` 없이는 그 몇 분이 "멈춘 화면"으로 보인다.
 *
 * **`goal`·`percent` 를 다시 계산하지 않는다.** 단계에 맞는 분모로 서버가 이미 나눠서
 * 준다(`jobs.Progress`). 화면이 또 나누면 두 벌이 되고 한쪽만 고쳐지는 날이 온다. */
export type IngestProgress = {
  pages: number;
  items: number;
  expected: number | null;
  target: number | null;
  goal: number | null;
  percent: number | null;
  /** `"목록"` 또는 `"첨부"` */
  phase: string;
  /** 첨부 단계에서만 찬다 */
  scraped: number;
  scrape_total: number;
};

export type AdminIngestCard = {
  name: string;
  label: string;
  expected: number;
  requests: string;
  note: string;
  stored: number;
  last: Run | null;
  /** 2026-08-24 부터 있다(ADR-0065). 값은 DB 가 아니라 이 API 프로세스의 메모리에서 온다 —
   *  재시작하면 사라지고, 다른 프로세스(CLI)에서 도는 것은 여기 안 보인다. */
  running: boolean;
  progress: IngestProgress | null;
};

export type AdminIngest = {
  cards: AdminIngestCard[];
  runs: Run[];
};

/** 실행 요청의 결과. `ingest/jobs.py` `Launch` 사본 */
export type IngestTrigger = {
  started: boolean;
  reason: string;
};

export function listAdminNotices(params: {
  source?: string;
  q?: string;
  sort?: string;
  page?: number;
}): Promise<AdminNoticeList> {
  const qs = new URLSearchParams();
  if (params.source) qs.set("source", params.source);
  if (params.q) qs.set("q", params.q);
  if (params.sort) qs.set("sort", params.sort);
  if (params.page && params.page > 1) qs.set("page", String(params.page));
  const query = qs.toString();
  return get<AdminNoticeList>(`/api/admin/notices${query ? `?${query}` : ""}`);
}

/** 없으면 null. 404 를 오류 화면으로 올리지 않는다 — `notFound()` 가 받는다. */
export async function getAdminNotice(
  source: string,
  id: string,
): Promise<AdminNoticeDetail | null> {
  try {
    return await get<AdminNoticeDetail>(
      `/api/admin/notices/${encodeURIComponent(source)}/${encodeURIComponent(id)}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export function getAdminAttachments(): Promise<AdminAttachments> {
  return get<AdminAttachments>("/api/admin/attachments");
}

export function getAdminIngest(): Promise<AdminIngest> {
  return get<AdminIngest>("/api/admin/ingest");
}

/** 수집을 시작한다(ADR-0065). **토큰은 여기서 안 든다** — 화면에서 사람이 입력한
 *  값을 그대로 실어 보내고, 맞는지는 API 가 판정한다. `lib/admin.ts` 는 그 값을 모른다. */
export function triggerIngest(
  source: string,
  opts: { full?: boolean; limit?: number; token: string },
): Promise<IngestTrigger> {
  const qs = new URLSearchParams();
  if (opts.full) qs.set("full", "true");
  if (opts.limit) qs.set("limit", String(opts.limit));
  const query = qs.toString();
  return send<IngestTrigger>(`/api/admin/ingest/run/${source}${query ? `?${query}` : ""}`, {
    method: "POST",
    headers: { "x-ingest-trigger-token": opts.token },
  });
}
