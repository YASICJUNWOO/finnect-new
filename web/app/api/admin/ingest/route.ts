import { ApiError } from "@/lib/api";
import { getAdminIngest } from "@/lib/admin";

/** 실행 버튼이 있는 화면이 폴링으로 쓴다(ADR-0065). 서버 컴포넌트는 이 라우트를
 *  안 쓴다 — 처음 그리기는 `page.tsx` 가 직접 `lib/admin.ts` 를 부른다. 폴링만
 *  브라우저에서 하는 것이라 같은 앱의 이 경로가 필요하다(브라우저는 API 주소를 모른다). */
export async function GET() {
  try {
    return Response.json(await getAdminIngest());
  } catch (e) {
    return Response.json({ detail: why(e, "기록을 못 읽었어요") }, { status: code(e) });
  }
}

function code(e: unknown): number {
  return e instanceof ApiError ? (e.status ?? 502) : 500;
}

function why(e: unknown, fallback: string): string {
  return e instanceof Error ? e.message : fallback;
}
