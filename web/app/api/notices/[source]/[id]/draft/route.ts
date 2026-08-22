import { ApiError } from "@/lib/api";
import { getDraft, startDraft } from "@/lib/draft";

/** 초안을 읽고(GET) 만들기 시작한다(POST) — plan/21 T-0121.
 *
 * **브라우저가 API 주소를 모른다**(`next.config.ts`). 화면은 같은 앱의 이 경로를
 * 치고 여기가 `lib/draft.ts` 를 통해 밖으로 나간다 — 경계는 여전히 `lib/` 하나다.
 * `app/api/wiki/[company]/*` 가 같은 모양이다.
 *
 * **GET 이 따로 있는 이유는 화면이 반복해서 묻기 때문이다.** 페이지를 다시 받으면
 * 공고와 서류까지 통째로 따라오는데 집필 중에 필요한 것은 초안 하나다. */
export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ source: string; id: string }> };

export async function GET(req: Request, ctx: Ctx) {
  const { source, id } = await ctx.params;
  const company = new URL(req.url).searchParams.get("company") ?? "";
  if (!company) return Response.json({ detail: "company 가 없어요" }, { status: 400 });

  try {
    return Response.json(await getDraft(source, decodeURIComponent(id), company));
  } catch (e) {
    console.error("초안 조회 실패", e);
    return Response.json({ detail: why(e, "초안을 못 불러왔어요") }, { status: code(e) });
  }
}

export async function POST(req: Request, ctx: Ctx) {
  const { source, id } = await ctx.params;
  const company = new URL(req.url).searchParams.get("company") ?? "";
  if (!company) return Response.json({ detail: "company 가 없어요" }, { status: 400 });

  try {
    // **202 를 그대로 옮긴다.** 거절(`started: false`)도 202 라 화면이 오류로 안 읽는다
    const out = await startDraft(source, decodeURIComponent(id), company);
    return Response.json(out, { status: 202 });
  } catch (e) {
    console.error("초안 시작 실패", e);
    return Response.json({ detail: why(e, "초안을 못 시작했어요") }, { status: code(e) });
  }
}

function code(e: unknown): number {
  return e instanceof ApiError ? (e.status ?? 502) : 500;
}

function why(e: unknown, fallback: string): string {
  return e instanceof Error ? e.message : fallback;
}
