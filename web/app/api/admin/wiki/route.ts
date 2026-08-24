import { ApiError } from "@/lib/api";
import { getAdminWiki } from "@/lib/admin";

/** 위키 목록을 브라우저가 다시 받을 때 쓴다([ADR-0072](../../../../../docs/adr/0072-위키-지우기를-운영-화면에-연다.md)).
 *  `admin/attach/route.ts` 와 같은 자리다 — 처음 그리기는 `page.tsx` 가 직접
 *  `lib/admin.ts` 를 부르고, 지운 뒤 다시 받는 것만 브라우저에서 한다
 *  (브라우저는 API 주소를 모른다). */
export async function GET() {
  try {
    return Response.json(await getAdminWiki());
  } catch (e) {
    return Response.json({ detail: why(e, "목록을 못 읽었어요") }, { status: code(e) });
  }
}

function code(e: unknown): number {
  return e instanceof ApiError ? (e.status ?? 502) : 500;
}

function why(e: unknown, fallback: string): string {
  return e instanceof Error ? e.message : fallback;
}
