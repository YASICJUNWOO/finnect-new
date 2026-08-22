import { ApiError } from "@/lib/api";
import { editDraftItem } from "@/lib/draft";

/** 고친 글을 저장한다 — plan/21 T-0123 · ADR-0055.
 *
 * **`text: null` 이 되돌리기다.** 빈 문자열은 되돌리기가 아니라 일부러 비운 것이라
 * 그대로 넘긴다 — 여기서 `?? ""` 로 뭉개면 되돌리기가 없어진다. */
export const dynamic = "force-dynamic";

export async function PUT(
  req: Request,
  ctx: { params: Promise<{ source: string; id: string; itemId: string }> },
) {
  const { source, id, itemId } = await ctx.params;
  const company = new URL(req.url).searchParams.get("company") ?? "";
  if (!company) return Response.json({ detail: "company 가 없어요" }, { status: 400 });

  const n = Number(itemId);
  if (!Number.isInteger(n)) {
    return Response.json({ detail: "항목 번호가 이상해요" }, { status: 400 });
  }

  let text: string | null;
  try {
    const body = (await req.json()) as { text?: unknown };
    // **`undefined` 와 `null` 을 가른다.** 앞은 본문이 잘못된 것이고 뒤는 되돌리기다
    if (body.text !== null && typeof body.text !== "string") {
      return Response.json({ detail: "text 가 없어요" }, { status: 400 });
    }
    text = body.text;
  } catch {
    return Response.json({ detail: "본문을 못 읽었어요" }, { status: 400 });
  }

  try {
    return Response.json(
      await editDraftItem(source, decodeURIComponent(id), company, n, text),
    );
  } catch (e) {
    console.error("초안 저장 실패", e);
    const status = e instanceof ApiError ? (e.status ?? 502) : 500;
    const detail = e instanceof Error ? e.message : "저장을 못 했어요";
    return Response.json({ detail }, { status });
  }
}
