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

/** 첨부 받기 진행. `attach/service.py` `AttachProgress` 사본.
 *
 * **`total` 에 이미 받아 둔 것은 없다.** 3,354건 중 2,827건이 끝난 상태에서 분모가
 * 3,354 면 막대가 처음부터 84% 에서 시작한다 — 그건 이번 실행의 진행이 아니다. */
export type AttachProgress = {
  total: number;
  done: number;
  /** 이미 받아 둬서 대상에서 뺀 것. **`total` 밖의 숫자다** */
  skipped: number;
  bytes_in: number;
  /** 이번에 받기로 한 건수(맛보기). null 이면 전량 */
  target: number | null;
  /** 막대의 분모. **`total` 이 아니다** — 맛보기 2건이면 2다. **화면이 다시 안 나눈다** */
  goal: number | null;
  /** 분모가 0 이면 null. **0% 로 그리지 않는다** */
  percent: number | null;
};

/** 마지막 실행이 어떻게 끝났나. `ingest/jobs.py` `Outcome` 사본.
 *
 * **메모리에만 산다** — API 를 재시작하면 사라진다. 첨부 받기에는 `ingest_run` 같은
 * 표가 없다([ADR-0071](../../docs/adr/0071-첨부-받기를-운영-화면에-연다.md)). */
export type JobOutcome = {
  ok: boolean;
  detail: string;
};

export type AdminAttach = {
  running: boolean;
  /** 첫 보고 전에는 null. **`running` 인데 여기가 비면 "아직 세는 중" 이다** */
  progress: AttachProgress | null;
  /** 아직 안 받은 첨부 URL 수. **버튼이 이 숫자만큼만 받는다** */
  pending: number;
  urls: number;
  last: JobOutcome | null;
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

/** 첨부 받기 카드. **`getAdminAttachments()` 와 따로다** — 저건 집계 다섯을 훑는
 *  무거운 질의라 실행 중에 1.5초마다 부를 것이 아니다. */
export function getAdminAttach(): Promise<AdminAttach> {
  return get<AdminAttach>("/api/admin/attach");
}

/** 첨부 받기를 시작한다([ADR-0071](../../docs/adr/0071-첨부-받기를-운영-화면에-연다.md)).
 *  **수집과 같은 토큰을 쓴다** — 둘 다 운영자가 이 서버에서 돌리는 같은 종류의 일이다. */
export function triggerAttach(opts: {
  limit?: number;
  redo?: boolean;
  token: string;
}): Promise<IngestTrigger> {
  const qs = new URLSearchParams();
  if (opts.limit) qs.set("limit", String(opts.limit));
  if (opts.redo) qs.set("redo", "true");
  const query = qs.toString();
  return send<IngestTrigger>(`/api/admin/attach/run${query ? `?${query}` : ""}`, {
    method: "POST",
    headers: { "x-ingest-trigger-token": opts.token },
  });
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

/** 위키가 서 있는 회사 하나([ADR-0072](../../docs/adr/0072-위키-지우기를-운영-화면에-연다.md)).
 *
 * **`name` 이 없을 수 있다** — `c_dasiro`·`c_narin` 처럼 CLI 로 만든 회사는 입장 게이트
 * 표(`company_account`)에 행이 없다. **`company_id` 로 메우지 않는다.**
 *
 * **`drafts`·`fits` 는 지우기가 안 건드리는 것이다.** 화면이 그걸 적어야 남은 것이
 * 고장으로 안 읽힌다. */
export type AdminWikiCompany = {
  company_id: string;
  name: string | null;
  files: number;
  chunks: number;
  facts: number;
  values: number;
  nodes: number;
  /** 파일이 없으면 null */
  uploaded_at: string | null;
  /** **안 지운다.** 초안은 화면의 「초기화」가 지운다(ADR-0062) */
  drafts: number;
  /** **안 지운다.** 판정은 `match --company` 가 다시 만든다 */
  fits: number;
};

export type AdminWiki = {
  companies: AdminWikiCompany[];
};

/** 지우고 나서 무엇이 없어졌나. **`IngestTrigger` 와 모양이 다르다** — 저건 "시작했다"
 *  이고 이건 **이미 끝났다.** 위키 지우기는 스레드로 안 뗀다. */
export type WikiPurge = {
  company_id: string;
  files: number;
  facts: number;
  /** 원본 파일 디렉터리가 있어서 지웠나 */
  storage: boolean;
};

export function getAdminWiki(): Promise<AdminWiki> {
  return get<AdminWiki>("/api/admin/wiki");
}

/** 그 회사의 위키를 지운다([ADR-0072](../../docs/adr/0072-위키-지우기를-운영-화면에-연다.md)).
 *  **수집·첨부와 같은 토큰을 쓴다** — 버튼마다 토큰을 나누지 않는다(ADR-0071 결정 3). */
export function purgeWiki(companyId: string, token: string): Promise<WikiPurge> {
  return send<WikiPurge>(`/api/admin/wiki/purge/${encodeURIComponent(companyId)}`, {
    method: "POST",
    headers: { "x-ingest-trigger-token": token },
  });
}
