/** 사업 위키(S7). 계약은 `docs/api-contract.md`, 정본은 `api/wiki_schemas.py` 다.
 *
 * **필드 이름을 새로 짓지 않는다.** 서버가 쓰는 이름 그대로다. */

import { ApiError, get } from "./api";

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
  const base = process.env.FINNECT_API ?? "http://127.0.0.1:8100";
  const bypass = process.env.FINNECT_API_BYPASS;
  let res: Response;
  try {
    res = await fetch(`${base}/api/wiki/${encodeURIComponent(companyId)}/markdown`, {
      cache: "no-store",
      headers: bypass ? { "x-vercel-protection-bypass": bypass } : undefined,
      redirect: "manual",
    });
  } catch (cause) {
    throw new ApiError(`API에 못 붙었어요 (${base})`, undefined, { cause });
  }
  // 404 는 "아직 위키가 없다"다. 오류 화면으로 올리지 않는다
  if (res.status === 404) return null;
  if (!res.ok) throw new ApiError(`API가 ${res.status}로 답했어요`, res.status);
  // **JSON 이 아니라 text/markdown 이라 `get()` 을 못 쓴다.** 원문 그대로 받는다
  return res.text();
}
