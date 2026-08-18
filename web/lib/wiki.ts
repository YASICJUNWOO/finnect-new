/** 사업 위키(S7). 계약은 `docs/api-contract.md`, 정본은 `api/wiki_schemas.py` 다.
 *
 * **필드 이름을 새로 짓지 않는다.** 서버가 쓰는 이름 그대로다. */

import { ApiError, authHeaders, BASE, get } from "./api";

/** 근거 하나. **출처는 문자열이 아니라 연결이다**(SPEC F1-3).
 *
 * `filename` 과 `page` 가 따로 온다. 미리 이어 붙인 문자열을 받으면 화면이
 * "3쪽"을 다르게 쓸 자유가 없다. */
export type Evidence = {
  filename: string;
  /** PDF · PPTX 만 찬다. 나머지 포맷에는 쪽이라는 것이 없다 */
  page: number | null;
  /** 청크 안에서 근거가 된 조각 */
  quote: string;
};

export type WikiValue = {
  slot: string;
  label: string;
  /** 정규화된 저장값. **화면이 이걸 고쳐 쓰지 않는다** — 병합의 재료다 */
  value: string;
  /** 사람이 읽는 값. 단위가 붙어 있다. **단위 규칙을 프론트에 두지 않는다** */
  display: string;
  qualifier: string | null;
  as_of: string | null;
  /** `current` 지금 값 · `superseded` 더 늦은 값이 있다 · `conflict` 값이 갈렸다 */
  status: string;
  evidence: Evidence[];
};

export type WikiStatement = {
  text: string;
  /** LLM 이 붙인 라벨. **목적지가 아니다** */
  topic: string;
  evidence: Evidence[];
};

export type WikiNode = {
  key: string;
  label: string;
  /** `identity` · `company` · `content`. **색은 이것만 말한다**(DESIGN.md §4.1) */
  kind: string;
  sector: string;
  /** 자격 판별의 입력을 담은 자리인가. 비면 물어야 한다 */
  eligibility: boolean;
  values: WikiValue[];
  statements: WikiStatement[];
  /** 근거로 쓰인 **파일 수**. 근거 개수가 아니다 */
  source_count: number;
  filled: boolean;
  conflicted: boolean;
  /** 이 자리 한 장의 마크다운. **저장된 것이 아니라 매번 만든 것이다** */
  markdown: string;
};

export type WikiFile = {
  filename: string;
  ext: string | null;
  byte_size: number;
  status: string;
  parse_status: string | null;
  parser: string | null;
  parse_error: string | null;
  chunk_count: number | null;
  page_count: number | null;
  /** 이 파일이 근거가 된 궤도 자리들 */
  nodes: string[];
};

export type Wiki = {
  company_id: string;
  /** 궤도 자리 열다섯. **순서가 곧 배치 순서다**(ADR-0017) */
  nodes: WikiNode[];
  files: WikiFile[];
  /** 궤도 위에 얹는 구획 라벨 여섯 */
  sectors: Record<string, string>;
  filled: number;
  total: number;
  conflicts: number;
  uncategorized: number;
  /** 무엇이 사실을 뽑았나. `stub/v1` 이면 픽스처 밖에서는 안 돈 것이다(ADR-0031) */
  extractor: string | null;
};

/** 인증이 아직 없다. **누구의 위키를 볼지 주소가 말한다.**
 *
 * 로그인이 붙으면 이 값이 세션에서 오고 `?company=` 는 사라진다. 그때까지는
 * 기본값 하나를 두고 주소로 갈아탄다 — 시연 대상이 하나뿐이라 성립하는 임시 조치다. */
export const DEFAULT_COMPANY = process.env.FINNECT_COMPANY ?? "c_dasiro";

/** 위키가 없어도 200 이고 궤도 열다섯이 온다.
 *
 * **빈 화면을 "데이터 없음"으로 끝내지 않는다**(DESIGN.md §7-5). 자리가 있어야
 * 사용자가 무엇이 없는지 알고 무엇을 올려야 하는지 안다. */
export function getWiki(companyId: string): Promise<Wiki> {
  return get<Wiki>(`/api/wiki/${encodeURIComponent(companyId)}`);
}

/** 위키 전부를 마크다운 한 덩어리로. 아직 아무것도 없으면 null.
 *
 * **저장된 파일이 아니다.** 서버가 매번 만든다 — 마크다운은 저장소가 아니라 뷰다. */
export async function getWikiMarkdown(companyId: string): Promise<string | null> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/wiki/${encodeURIComponent(companyId)}/markdown`, {
      cache: "no-store",
      headers: authHeaders(),
      redirect: "manual",
    });
  } catch (cause) {
    throw new ApiError(`API에 못 붙었어요 (${BASE})`, undefined, { cause });
  }
  // 404 는 "아직 위키가 없다"다. 오류 화면으로 올리지 않는다
  if (res.status === 404) return null;
  if (!res.ok) throw new ApiError(`API가 ${res.status}로 답했어요`, res.status);
  // **JSON 이 아니라 text/markdown 이라 `get()` 을 못 쓴다.** 원문 그대로 받는다
  return res.text();
}

// --- 올리기와 진행 표시 (S1 · plan/15) --------------------------------------

/** 단계 하나. **다섯 개가 고정이고 순서가 곧 진행 순서다.**
 *
 * 라벨을 프론트가 짓지 않는다 — `src/finnect/wiki/progress.py` 가 정본이다. 양쪽이
 * 각자 이름을 들면 갈리고, 갈린 순간 어느 쪽이 진짜 상태인지 알 수 없게 된다. */
export type Step = { key: string; label: string };

export type FileProgress = {
  filename: string;
  ext: string | null;
  byte_size: number;
  /** DB 의 원래 상태. `uploaded` · `parsing` · `chunked` · … 여덟 가지 */
  status: string;
  /** 끝낸 칸 수. 0 ~ 5. **백분율이 아니다** */
  reached: number;
  /** 사람이 읽는 한 마디. 도는 중과 멈춘 것이 다른 말을 한다 */
  label: string;
  moving: boolean;
  /** 끝났고 성공인가. 움직이는 중이면 항상 false 다 — **아직 모른다** */
  ok: boolean;
  /** 왜 못 했나. **조용히 버리지 않는다** */
  detail: string | null;
  chunk_count: number | null;
  page_count: number | null;
  /** 이 파일이 채운 궤도 자리들. **키다** — 이름은 `Progress.places` 가 준다 */
  nodes: string[];
};

export type Progress = {
  company_id: string;
  steps: Step[];
  files: FileProgress[];
  /** 자리 키 → 라벨. **화면이 이름을 짓지 않는다** */
  places: Record<string, string>;
  total: number;
  done: number;
  moving: number;
  /** 글자가 안 나온 것. **실패와 다르다** — OCR 이 붙으면 읽힌다 */
  needs_review: number;
  /** 못 읽은 것과 사실을 못 뽑은 것 */
  stuck: number;
  /** 지금 도는 중인가. **화면이 계속 물어볼지를 이 값으로 정한다** */
  running: boolean;
  filled: number;
  slots: number;
  conflicts: number;
  extractor: string | null;
};

export type Upload = {
  received: number;
  duplicate: number;
  /** [파일명, 사유]. 저장조차 못 한 것 */
  rejected: [string, string][];
  started: boolean;
  reason: string;
  progress: Progress;
};

/** 구축 진행. **아무것도 안 올렸어도 200 이고 단계 다섯이 온다.** */
export function getProgress(companyId: string): Promise<Progress> {
  return get<Progress>(`/api/wiki/${encodeURIComponent(companyId)}/progress`);
}

/** 파일을 통째로 보낸다(F1-1-1). **분류해서 올리라고 요구하지 않는다.**
 *
 * `get()` 을 못 쓴다 — 저기는 JSON 만 보내고 여기는 multipart 다. 그래서 이 함수가
 * `lib/api.ts` 밖의 fetch 이지만 **주소와 헤더는 저기 것을 그대로 쓴다.**
 *
 * **브라우저에서 부르지 않는다.** API 주소는 서버만 안다(`next.config.ts`). 화면은
 * 같은 앱의 라우트 핸들러(`app/api/wiki/[company]/files`)를 치고 그쪽이 이걸 부른다. */
export async function uploadFiles(companyId: string, body: FormData): Promise<Upload> {
  // **주소와 헤더를 여기서 다시 만들지 않는다**(`./api`). 올리기만 자기 것을 들고
  // 있으면 토큰이 붙는 날 이 경로만 401 이 되고, 그게 가장 늦게 발견된다.
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/wiki/${encodeURIComponent(companyId)}/files`, {
      method: "POST",
      body,
      headers: authHeaders(),
      redirect: "manual",
    });
  } catch (cause) {
    throw new ApiError(`API에 못 붙었어요 (${BASE})`, undefined, { cause });
  }
  // 503 은 "이 서버는 파일을 못 받는다"다(ADR-0034). **화면이 그 말을 그대로 옮겨야**
  // 사용자가 어디서 하면 되는지 안다 — "API가 503으로 답했어요"로는 알 수 없다.
  if (!res.ok) {
    throw new ApiError(detailOf(res.status, await res.text().catch(() => "")), res.status);
  }
  return (await res.json()) as Upload;
}

/** FastAPI 는 오류를 `{"detail": "..."}` 로 준다. **그 문장을 버리지 않는다** —
 *  "API가 503으로 답했어요"만 보여 주면 무엇을 해야 할지 알 수 없다. */
function detailOf(status: number, body: string): string {
  try {
    const detail = (JSON.parse(body) as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail) return detail;
  } catch {
    // JSON 이 아니면 상태 코드로 말한다
  }
  return `API가 ${status}로 답했어요`;
}
