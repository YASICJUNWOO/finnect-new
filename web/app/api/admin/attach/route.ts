import { ApiError } from "@/lib/api";
import { getAdminAttach } from "@/lib/admin";

/** 첨부 받기 카드가 폴링으로 쓴다([ADR-0071](../../../../../docs/adr/0071-첨부-받기를-운영-화면에-연다.md)).
 *  `admin/ingest/route.ts` 와 같은 자리다 — 처음 그리기는 `page.tsx` 가 직접
 *  `lib/admin.ts` 를 부르고, 폴링만 브라우저에서 해서 이 경로가 필요하다
 *  (브라우저는 API 주소를 모른다). */
export async function GET() {
  try {
    return Response.json(await getAdminAttach());
  } catch (e) {
    return Response.json({ detail: why(e, "상태를 못 읽었어요") }, { status: code(e) });
  }
}

function code(e: unknown): number {
  return e instanceof ApiError ? (e.status ?? 502) : 500;
}

function why(e: unknown, fallback: string): string {
  return e instanceof Error ? e.message : fallback;
}
